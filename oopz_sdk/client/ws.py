from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Awaitable, Callable, Optional

from oopz_sdk.config.settings import HeartbeatConfig, OopzConfig
from oopz_sdk.config.constants import (
    EVENT_AUTH,
    EVENT_AUTH_RESULT,
    EVENT_HEARTBEAT,
    EVENT_SUBSCRIBE_AREA_EVENTS,
)
from oopz_sdk.exceptions import OopzAuthError
from oopz_sdk.transport.ws import WebSocketClosedError, WebSocketTransport

logger = logging.getLogger(__name__)


class _WebSocketCallbackError(RuntimeError):
    def __init__(self, callback_name: str, original: Exception):
        super().__init__(f"{callback_name} failed: {original}")
        self.callback_name = callback_name
        self.original = original


@dataclass(slots=True)
class CloseInfo:
    code: int | None = None
    reason: str = ""
    error: Exception | None = None
    reconnecting: bool = False


class OopzWSClient:
    def __init__(
        self,
        config: OopzConfig,
        *,
        on_message: Optional[Callable[[str], Awaitable[None]]] = None,
        on_open: Optional[Callable[[], Awaitable[None]]] = None,
        on_error: Optional[Callable[[object], Awaitable[None]]] = None,
        on_close: Optional[Callable[[CloseInfo], Awaitable[None] | None]] = None,
        on_reconnect: Optional[Callable[[], Awaitable[None]]] = None,
        auth_manager=None,
    ):
        config.ensure_credentials()
        self.config = config
        self.on_message = on_message
        self.on_open = on_open
        self.on_error = on_error
        self.on_close = on_close
        self.on_reconnect = on_reconnect
        self._auth_manager = auth_manager

        self.transport = WebSocketTransport(config)

        self._running = False
        self._stop_event = asyncio.Event()
        self._receive_task: asyncio.Task | None = None
        self._heartbeat_task: asyncio.Task | None = None
        self._refresh_task: asyncio.Task | None = None
        self._refresh_fatal_error: Exception | None = None
        # 连接代序号：每次成功建连自增，把「计划内续期断连」精确绑定到触发它的
        # 那一代连接。用代序号而非布尔标志，避免续期发生在重连间隙（退避/握手
        # 窗口）时标志跨连接残留，从而把后续真实断连误判为计划内续期。
        self._connection_generation = 0
        self._planned_refresh_generation: int | None = None
        # 标记「刚续期换的新 token 尚未经一次成功通信验证」：若新 token 未验证就
        # 再次被鉴权拒绝，说明续期无法恢复，升级停机，避免高频重登死循环。
        self._fresh_token_unverified = False
        self._consecutive_failures = 0
        self._has_connected_once = False

    async def start(self) -> None:
        self._running = True
        self._stop_event.clear()
        self._refresh_fatal_error = None
        self._connection_generation = 0
        self._planned_refresh_generation = None
        self._fresh_token_unverified = False

        if self._auth_manager is not None and self._auth_manager.can_refresh:
            self._refresh_task = asyncio.create_task(self._token_refresh_loop())

        while self._running:
            fatal_error: Exception | None = None
            runtime_error: Exception | None = None
            connected_this_round = False
            planned_refresh = False

            try:
                if self._has_connected_once:
                    await self._run_callback("on_reconnect", self.on_reconnect)

                await self.transport.connect()
                connected_this_round = True
                self._connection_generation += 1
                self._consecutive_failures = 0
                self._has_connected_once = True

                await self.send_auth()

                await self._run_callback("on_open", self.on_open)

                self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())
                await self._receive_loop()

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                runtime_error = (
                    exc.original if isinstance(exc, _WebSocketCallbackError) else exc
                )
                # 计划内 token 轮换主动断连：按预期的干净重连处理，并消费该标记。
                planned_refresh = self._is_planned_refresh_close(runtime_error)
                self._planned_refresh_generation = None

                # 鉴权失效的恢复/升级决策收敛到独立方法（见 _handle_connection_auth_error）。
                auth_fatal, auth_recovered = await self._handle_connection_auth_error(
                    exc, runtime_error
                )
                if auth_fatal is not None:
                    fatal_error = auth_fatal

                normal_stop_error = self._is_normal_stop_error(runtime_error)
                # 正常停机、计划内续期、已自动恢复的鉴权失效都属预期，不喷 error 日志/on_error。
                if not normal_stop_error and not planned_refresh and not auth_recovered:
                    callback_fatal = await self._report_runtime_error(runtime_error)
                    # on_error 回调自身抛错时，以回调致命错误为准（与历史行为一致）。
                    if callback_fatal is not None:
                        fatal_error = callback_fatal
                if fatal_error is None and isinstance(exc, _WebSocketCallbackError):
                    fatal_error = runtime_error

            finally:
                if self._heartbeat_task:
                    self._heartbeat_task.cancel()
                    try:
                        await self._heartbeat_task
                    except asyncio.CancelledError:
                        pass
                    self._heartbeat_task = None

                try:
                    await self.transport.close()
                except Exception:
                    logger.exception("关闭 WebSocketTransport 失败")

                if connected_this_round:
                    close_code = runtime_error.code if isinstance(runtime_error, WebSocketClosedError) else None
                    close_reason = self._get_close_reason(runtime_error)
                    close_info = CloseInfo(
                        code=close_code,
                        reason=close_reason,
                        error=runtime_error,
                        reconnecting=self._running and fatal_error is None,
                    )
                    try:
                        await self._run_callback("on_close", self.on_close, close_info)
                    except _WebSocketCallbackError as callback_exc:
                        if fatal_error is None:
                            fatal_error = callback_exc.original

            if fatal_error is None and self._refresh_fatal_error is not None:
                fatal_error = self._refresh_fatal_error

            if fatal_error is not None:
                await self._cancel_refresh_task()
                raise fatal_error

            if not self._running:
                break

            if planned_refresh:
                # 计划内 token 轮换：立即用新 token 重连，不退避、不打重连警告。
                logger.info("token 已续期，使用新 token 重连")
                continue

            heartbeat = getattr(self.config, "heartbeat", HeartbeatConfig())
            delay = min(
                heartbeat.reconnect_interval * (2 ** self._consecutive_failures),
                heartbeat.max_reconnect_interval,
            )
            self._consecutive_failures += 1

            logger.warning("WebSocket 将在 %.2f 秒后尝试重连", delay)
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass

        await self._cancel_refresh_task()

        # 后台续期遇到不可恢复的鉴权失败时，在此向上抛出以触发全局停机。
        if self._refresh_fatal_error is not None:
            raise self._refresh_fatal_error

    async def stop(self) -> None:
        self._running = False
        self._stop_event.set()
        await self._cancel_refresh_task()
        await self.transport.close()

    async def _cancel_refresh_task(self) -> None:
        if self._refresh_task is None:
            return
        self._refresh_task.cancel()
        try:
            await self._refresh_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("token 续期任务退出异常")
        finally:
            self._refresh_task = None

    async def _recover_from_auth_error(self, error: OopzAuthError) -> bool:
        """鉴权失效时尝试通过 AuthManager 续期恢复。返回是否恢复成功。"""
        if self._auth_manager is None:
            return False
        try:
            return await self._auth_manager.handle_auth_error(error)
        except Exception:
            logger.exception("AuthManager 处理鉴权失效时异常")
            return False

    async def _handle_connection_auth_error(
        self, exc: Exception, runtime_error: Exception
    ) -> tuple[Exception | None, bool]:
        """处理「源自连接本身」的鉴权失效，返回 ``(fatal_error, auth_recovered)``。

        仅恢复源自连接的鉴权失效（握手 401/428、运行期 event=21）。来自用户回调的
        ``OopzAuthError`` 不在此重登（否则白做一次 relogin 副作用后仍停机，语义自相
        矛盾），而是由上层按回调错误升级为致命。

        - 续期成功：``(None, True)``，标记新 token 待验证，由上层用新 token 重连。
        - 续期后的新 token 未经一次成功通信又被拒：``(runtime_error, False)`` 升级
          停机，避免每次重连都重登把登录接口打挂。
        - 无重登能力或重登失败：``(runtime_error, False)`` 升级停机，避免用死 token
          无限重连。
        """
        connection_auth_error = isinstance(
            runtime_error, OopzAuthError
        ) and not isinstance(exc, _WebSocketCallbackError)
        if not connection_auth_error:
            return None, False

        if self._fresh_token_unverified:
            logger.error(
                "续期后的新 token 仍被鉴权拒绝，停止重连: %s", runtime_error
            )
            return runtime_error, False

        if await self._recover_from_auth_error(runtime_error):
            self._fresh_token_unverified = True
            logger.warning(
                "WebSocket 鉴权失效已自动续期恢复，将用新 token 重连: %s",
                runtime_error,
            )
            return None, True

        return runtime_error, False

    async def _report_runtime_error(self, runtime_error: Exception) -> Exception | None:
        """非预期运行错误：打日志并派发 on_error；返回回调内的致命错误(若有)。"""
        logger.exception("WebSocket 运行异常: %s", runtime_error)
        already_dispatched = bool(
            getattr(runtime_error, "_oopz_error_dispatched", False)
        )
        if self.on_error and not already_dispatched:
            try:
                await self._run_callback("on_error", self.on_error, runtime_error)
            except _WebSocketCallbackError as callback_exc:
                return callback_exc.original
        return None

    async def _token_refresh_loop(self) -> None:
        """后台周期检查 JWT 是否临期，临期则续期并用新 token 重连。"""
        manager = self._auth_manager
        if manager is None or not manager.can_refresh:
            return

        try:
            while self._running:
                try:
                    interval = self._compute_refresh_interval(manager)
                    await asyncio.wait_for(self._stop_event.wait(), timeout=interval)
                    return  # stop_event 被置位，退出
                except asyncio.TimeoutError:
                    pass

                if not self._running or not manager.needs_refresh():
                    continue

                try:
                    refreshed = await manager.refresh()
                except OopzAuthError as exc:
                    # 续期被服务端拒绝（不可恢复）：记录致命错误并停止整个客户端，
                    # 由主循环退出后向上抛出，触发全局停机。
                    logger.warning("token 续期被拒绝，触发全局停机: %s", exc)
                    self._refresh_fatal_error = exc
                    self._running = False
                    self._stop_event.set()
                    await self.transport.close()
                    return
                except Exception:
                    logger.exception("token 续期任务异常")
                    continue

                if refreshed and self._running:
                    logger.info("token 已续期，重连以应用新 token")
                    # 把计划内断连绑定到当前连接代，再关闭连接 → 主循环 recv 抛出
                    # WebSocketClosedError → 走干净重连用新 token，不当作错误。
                    # 用连接代而非布尔标志，避免标志跨连接残留误判后续真实断连。
                    self._planned_refresh_generation = self._connection_generation
                    await self.transport.close()
        except asyncio.CancelledError:
            raise

    @staticmethod
    def _compute_refresh_interval(manager) -> float:
        """计算下一次临期检查的等待间隔。

        基线取续期阈值的一半、至少 30 秒；同时不超过「token 剩余寿命的一半」，
        以保证短寿命 token 也能在过期前至少检查两次，避免错过续期窗口。下限仍取
        30 秒，避免对异常短寿命 token 频繁重登把登录接口打挂。
        """
        base = max(30.0, manager.refresh_threshold_seconds / 2)
        remaining = manager.seconds_until_expiry()
        if remaining is not None and remaining > 0:
            base = min(base, max(30.0, remaining / 2))
        return base

    def _is_normal_stop_error(self, error: Exception) -> bool:
        return not self._running and isinstance(error, WebSocketClosedError)

    def _is_planned_refresh_close(self, error: Exception | None) -> bool:
        """是否为主动续期触发的预期断连（应静默干净重连，而非报错）。

        仅当计划内续期标记指向「当前这一代连接」时才成立：续期若发生在重连间隙
        （退避/握手窗口），其标记属于旧连接代，不会被误用到新连接的真实断连。
        """
        return (
            isinstance(error, WebSocketClosedError)
            and self._planned_refresh_generation is not None
            and self._planned_refresh_generation == self._connection_generation
        )

    def _get_close_reason(self, error: Exception | None) -> str:
        if not self._running:
            return "stopped"
        if isinstance(error, WebSocketClosedError):
            return error.reason
        return "connection closed"

    async def _receive_loop(self) -> None:
        while self._running:
            raw = await self.transport.recv()
            self._raise_if_auth_rejected(raw)
            # 收到一条非鉴权拒绝的帧 = 当前（可能是续期后的新）token 已生效，
            # 清除「续期待验证」标记，使后续若再次失效仍可正常续期恢复。
            self._fresh_token_unverified = False
            await self._run_callback("on_message", self.on_message, raw)

    @staticmethod
    def _raise_if_auth_rejected(raw: str) -> None:
        """运行期鉴权校验未通过时升级为 OopzAuthError。

        服务端在鉴权帧之后会回一条 ``event=21`` 的校验结果，body 形如
        ``{"checkRes": false}`` 表示凭据被拒，随后以通用 close code(1006) 关闭。
        通用 close code 无业务语义，故以该事件作为运行期鉴权失效的精确信号，
        交由上层走续期恢复或停机决策（与握手 401/428 映射一致）。
        """
        # 快速路径：绝大多数业务消息不含 checkRes，避免对每条消息重复做 JSON 解析。
        if "checkRes" not in raw:
            return
        try:
            envelope = json.loads(raw)
        except (TypeError, ValueError):
            return
        if not isinstance(envelope, dict) or envelope.get("event") != EVENT_AUTH_RESULT:
            return

        body = envelope.get("body")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except (TypeError, ValueError):
                return
        if isinstance(body, dict) and body.get("checkRes") is False:
            raise OopzAuthError("WebSocket 鉴权校验未通过 (event=21, checkRes=false)")

    async def send_auth(self) -> None:
        auth_body = {
            "person": self.config.person_uid,
            "deviceId": self.config.device_id,
            "signature": self.config.jwt_token,
            "deviceName": self.config.device_id,
            "platformName": "web",
            "reconnect": 0,
        }

        await self.transport.send_json(
            {
                "time": str(int(time.time() * 1000)),
                "body": json.dumps(auth_body, ensure_ascii=False),
                "event": EVENT_AUTH,
            }
        )

    async def send_heartbeat(self) -> None:
        await self.transport.send_json(
            {
                "time": str(int(time.time() * 1000)),
                "body": json.dumps({"person": self.config.person_uid}, ensure_ascii=False),
                "event": EVENT_HEARTBEAT,
            }
        )

    async def _heartbeat_loop(self) -> None:
        while self._running and not self.transport.closed:
            heartbeat = getattr(self.config, "heartbeat", HeartbeatConfig())
            await asyncio.sleep(heartbeat.interval)
            if self._running and not self.transport.closed:
                await self.send_heartbeat()

    @staticmethod
    async def _run_callback(callback_name: str, callback, *args) -> None:
        if callback is None:
            return
        try:
            result = callback(*args)
            if asyncio.iscoroutine(result):
                await result
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise _WebSocketCallbackError(callback_name, exc) from exc

    async def send_subscribe_area_events(
        self,
        areas: list[str],
        *,
        uid: str = "",
        event_type: int = 1,
    ) -> None:
        """订阅指定域的 WebSocket 事件。"""
        uid = uid if uid else self.config.person_uid
        clean_areas = [area for area in areas if str(area).strip()]
        if not clean_areas:
            return

        await self.transport.send_json(
            {
                "time": str(int(time.time() * 1000)),
                "body": json.dumps(
                    {
                        "areas": clean_areas,
                        "type": event_type,
                        "uid": uid,
                    },
                    ensure_ascii=False,
                ),
                "event": EVENT_SUBSCRIBE_AREA_EVENTS,
            }
        )

from __future__ import annotations

import logging
from typing import Optional
from urllib.parse import parse_qsl

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.transport.http import HttpTransport

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.moderation")


class Moderation(BaseService):
    """Moderation capabilities."""

    def __init__(
        self,
        config_or_bot,
        config: OopzConfig | None = None,
        transport: HttpTransport | None = None,
        signer: Signer | None = None,
    ):
        if config is None:
            bot = None
            config = config_or_bot
        else:
            bot = config_or_bot
        resolved_signer = signer or Signer(config)
        resolved_transport = transport or HttpTransport(config, resolved_signer)
        super().__init__(config, resolved_transport, resolved_signer, bot=bot)

    _TEXT_INTERVALS = {1: "60秒", 2: "5分钟", 3: "1小时", 4: "1天", 5: "3天", 6: "7天"}
    _VOICE_INTERVALS = {7: "60秒", 8: "5分钟", 9: "1小时", 10: "1天", 11: "3天", 12: "7天"}

    @staticmethod
    def _minutes_to_interval_id(minutes: int, voice: bool = False) -> str:
        thresholds = [(1, 7), (5, 8), (60, 9), (1440, 10), (4320, 11), (10080, 12)] if voice \
            else [(1, 1), (5, 2), (60, 3), (1440, 4), (4320, 5), (10080, 6)]
        for limit, iid in thresholds:
            if minutes <= limit:
                return str(iid)
        return str(thresholds[-1][1])

    @staticmethod
    def _build_result(payload: dict, *, default_message: str) -> models.OperationResult:
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or default_message),
            payload=payload,
        )

    async def mute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10) -> models.OperationResult:
        """禁言用户。"""
        interval_id = self._minutes_to_interval_id(duration, voice=False)
        url_path = "/client/v1/area/v1/member/v1/disableText"
        query = f"?area={area}&target={uid}&intervalId={interval_id}"
        body = {"area": area, "target": uid, "intervalId": interval_id}
        return await self._manage_patch("禁言", url_path, query, body)

    async def unmute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None) -> models.OperationResult:
        """解除禁言。"""
        url_path = "/client/v1/area/v1/member/v1/recoverText"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return await self._manage_patch("解除禁言", url_path, query, body)

    async def mute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10) -> models.OperationResult:
        """禁麦用户。"""
        interval_id = self._minutes_to_interval_id(duration, voice=True)
        url_path = "/client/v1/area/v1/member/v1/disableVoice"
        query = f"?area={area}&target={uid}&intervalId={interval_id}"
        body = {"area": area, "target": uid, "intervalId": interval_id}
        return await self._manage_patch("禁麦", url_path, query, body)

    async def unmute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None) -> models.OperationResult:
        """解除禁麦。"""
        url_path = "/client/v1/area/v1/member/v1/recoverVoice"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return await self._manage_patch("解除禁麦", url_path, query, body)

    async def remove_from_area(self, uid: str, area: Optional[str] = None) -> models.OperationResult:
        """将用户移出当前域（踢出域）。"""
        url_path = f"/area/v3/remove?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        try:
            resp = await self._post(url_path, body)
        except Exception as e:
            logger.error("移出域请求异常: %s", e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw = resp.text or ""
        logger.info("移出域 POST %s -> HTTP %s, body: %s", url_path, resp.status_code, raw[:300])
        if resp.status_code != 200:
            return models.OperationResult(
                ok=False,
                message=f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                payload=body,
            )
        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", payload=body)
        if result.get("status") is True:
            logger.info("移出域成功")
            return self._build_result(result, default_message="已移出域")
        err = result.get("message") or result.get("error") or str(result)
        logger.error("移出域失败: %s", err)
        return models.OperationResult(ok=False, message=str(err), payload={**body, **result})

    async def block_user_in_area(self, uid: str, area: Optional[str] = None) -> models.OperationResult:
        """封禁用户。"""
        url_path = f"/client/v1/area/v1/block?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        try:
            resp = await self._delete(url_path)
        except Exception as e:
            logger.error("封禁请求异常: %s", e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw = resp.text or ""
        logger.info("封禁 DELETE %s -> HTTP %s, body: %s", url_path, resp.status_code, raw[:300])
        if resp.status_code != 200:
            return models.OperationResult(
                ok=False,
                message=f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                payload=body,
            )
        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(
                ok=False,
                message=f"响应非 JSON: {raw[:200]}",
                payload=body,
            )
        if result.get("status") is True:
            msg = result.get("message") or "已封禁"
            logger.info("封禁成功: %s", msg)
            return self._build_result(result, default_message=msg)
        err = result.get("message") or result.get("error") or str(result)
        logger.error("封禁失败: %s", err)
        return models.OperationResult(ok=False, message=str(err), payload={**body, **result})

    async def get_area_blocks(
        self,
        area: Optional[str] = None,
        name: str = "",
        *,
        as_model: bool = False,
    ) -> dict | models.AreaBlocksResult:
        """获取域内封禁列表。"""
        url_path = "/client/v1/area/v1/areaSettings/v1/blocks"
        params = {"area": area, "name": name}
        request_payload = {"area": area, "name": name}

        try:
            resp = await self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.debug("获取域封禁列表失败: HTTP %d", resp.status_code)
                if as_model:
                    return self._model_error(
                        models.AreaBlocksResult,
                        f"HTTP {resp.status_code}",
                        response=resp,
                    )
                return self._error_payload(
                    f"HTTP {resp.status_code}",
                    payload={**request_payload, "error": f"HTTP {resp.status_code}"},
                )

            result = resp.json()
            if not result.get("status"):
                msg = self._error_message(result)
                logger.debug("获取域封禁列表失败: %s", msg)
                if as_model:
                    return self._model_error(
                        models.AreaBlocksResult,
                        msg,
                        response=resp,
                        payload=result,
                    )
                return self._error_payload(
                    msg,
                    payload={**request_payload, **result, "error": msg},
                )

            data = result.get("data", {})
            if not isinstance(data, (dict, list)):
                if as_model:
                    return self._model_error(
                        models.AreaBlocksResult,
                        "area blocks响应格式异常",
                        response=resp,
                    )
                logger.error("获取域封禁列表失败: 响应格式异常")
                return self._error_payload(
                    "area blocks响应格式异常",
                    payload={**request_payload, "error": "area blocks响应格式异常"},
                )
            blocks = data if isinstance(data, list) else data.get("blocks", data.get("list", []))
            if not isinstance(blocks, list):
                if as_model:
                    return self._model_error(
                        models.AreaBlocksResult,
                        "area blocks响应格式异常",
                        response=resp,
                    )
                logger.error("获取域封禁列表失败: blocks格式异常")
                return self._error_payload(
                    "area blocks响应格式异常",
                    payload={**request_payload, "error": "area blocks响应格式异常"},
                )
            invalid_payload = self._invalid_dict_item_payload(
                blocks,
                "area blocks响应格式异常",
                list_key="blocks",
                payload={**request_payload, **result},
            )
            if invalid_payload:
                if as_model:
                    return self._model_error(
                        models.AreaBlocksResult,
                        "area blocks响应格式异常",
                        response=resp,
                        payload=invalid_payload,
                    )
                return invalid_payload
            logger.info("获取域封禁列表: %d 人", len(blocks))
            if as_model:
                return models.AreaBlocksResult(
                    blocks=[
                        models.AreaBlock(
                            uid=str(item.get("uid") or item.get("id") or ""),
                            name=str(item.get("name") or item.get("nickname") or ""),
                            reason=str(item.get("reason") or ""),
                            payload=dict(item),
                        )
                        for item in blocks
                    ],
                    payload=result,
                    response=resp,
                )
            return {"blocks": blocks}
        except Exception as e:
            logger.error("获取域封禁列表异常: %s", e)
            if as_model:
                return self._model_error(models.AreaBlocksResult, str(e))
            return self._error_payload(str(e), payload={**request_payload, "error": str(e)})

    async def unblock_user_in_area(self, uid: str, area: Optional[str] = None) -> models.OperationResult:
        """解除域内封禁。"""
        url_path = "/client/v1/area/v1/unblock"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return await self._manage_patch("解除域内封禁", url_path, query, body)

    async def _manage_patch(self, action: str, url_path: str, query: str, body: dict) -> models.OperationResult:
        """通用 PATCH 管理操作（禁言/禁麦等）。"""
        full_path = url_path + query
        params = dict(parse_qsl(query.lstrip("?")))
        try:
            resp = await self._request("PATCH", url_path, body=body, params=params)
        except Exception as e:
            logger.error("%s请求异常: %s", action, e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw = resp.text or ""
        logger.info("%s PATCH %s -> HTTP %d, body: %s", action, full_path, resp.status_code, raw[:300])

        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")
            return models.OperationResult(ok=False, message=err, payload=body)

        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", payload=body)

        if result.get("status") is True:
            msg = result.get("message") or f"{action}成功"
            logger.info("%s成功: %s", action, msg)
            return self._build_result(result, default_message=msg)

        err = result.get("message") or result.get("error") or str(result)
        logger.error("%s失败: %s", action, err)
        return models.OperationResult(ok=False, message=str(err), payload={**body, **result})

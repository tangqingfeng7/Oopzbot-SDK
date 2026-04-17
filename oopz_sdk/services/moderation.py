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
        bot,
        config: OopzConfig,
        transport: HttpTransport | None = None,
        signer: Signer | None = None,
    ):
        resolved_signer = signer or Signer(config)
        resolved_transport = transport or HttpTransport(config, resolved_signer)
        super().__init__(bot, config, resolved_transport, resolved_signer)

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
    def _build_result(payload: dict, *, response=None, default_message: str) -> models.OperationResult:
        return models.OperationResult(
            ok=True,
            message=str(payload.get("message") or default_message),
            payload=payload,
            response=response,
        )

    def mute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10) -> models.OperationResult:
        """禁言用户。"""
        area = area or self._config.default_area
        interval_id = self._minutes_to_interval_id(duration, voice=False)
        url_path = "/client/v1/area/v1/member/v1/disableText"
        query = f"?area={area}&target={uid}&intervalId={interval_id}"
        body = {"area": area, "target": uid, "intervalId": interval_id}
        return self._manage_patch("禁言", url_path, query, body)

    def unmute_user(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None) -> models.OperationResult:
        """解除禁言。"""
        area = area or self._config.default_area
        url_path = "/client/v1/area/v1/member/v1/recoverText"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return self._manage_patch("解除禁言", url_path, query, body)

    def mute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None, duration: int = 10) -> models.OperationResult:
        """禁麦用户。"""
        area = area or self._config.default_area
        interval_id = self._minutes_to_interval_id(duration, voice=True)
        url_path = "/client/v1/area/v1/member/v1/disableVoice"
        query = f"?area={area}&target={uid}&intervalId={interval_id}"
        body = {"area": area, "target": uid, "intervalId": interval_id}
        return self._manage_patch("禁麦", url_path, query, body)

    def unmute_mic(self, uid: str, area: Optional[str] = None, channel: Optional[str] = None) -> models.OperationResult:
        """解除禁麦。"""
        area = area or self._config.default_area
        url_path = "/client/v1/area/v1/member/v1/recoverVoice"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return self._manage_patch("解除禁麦", url_path, query, body)

    def remove_from_area(self, uid: str, area: Optional[str] = None) -> models.OperationResult:
        """将用户移出当前域（踢出域）。"""
        area = area or self._config.default_area
        url_path = f"/area/v3/remove?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        try:
            resp = self._post(url_path, body)
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
                response=resp,
            )
        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", payload=body, response=resp)
        if result.get("status") is True:
            logger.info("移出域成功")
            return self._build_result(result, response=resp, default_message="已移出域")
        err = result.get("message") or result.get("error") or str(result)
        logger.error("移出域失败: %s", err)
        return models.OperationResult(ok=False, message=str(err), payload=result, response=resp)

    def block_user_in_area(self, uid: str, area: Optional[str] = None) -> models.OperationResult:
        """封禁用户。"""
        area = area or self._config.default_area
        url_path = f"/client/v1/area/v1/block?area={area}&target={uid}"
        try:
            resp = self._delete(url_path)
        except Exception as e:
            logger.error("封禁请求异常: %s", e)
            return models.OperationResult(ok=False, message=str(e))

        raw = resp.text or ""
        logger.info("封禁 DELETE %s -> HTTP %s, body: %s", url_path, resp.status_code, raw[:300])
        if resp.status_code != 200:
            return models.OperationResult(
                ok=False,
                message=f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else ""),
                response=resp,
            )
        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", response=resp)
        if result.get("status") is True:
            msg = result.get("message") or "已封禁"
            logger.info("封禁成功: %s", msg)
            return self._build_result(result, response=resp, default_message=msg)
        err = result.get("message") or result.get("error") or str(result)
        logger.error("封禁失败: %s", err)
        return models.OperationResult(ok=False, message=str(err), payload=result, response=resp)

    def get_area_blocks(
        self,
        area: Optional[str] = None,
        name: str = "",
        *,
        as_model: bool = False,
    ) -> dict | models.AreaBlocksResult:
        """获取域内封禁列表。"""
        area = self._resolve_area(area)
        url_path = "/client/v1/area/v1/areaSettings/v1/blocks"
        params = {"area": area, "name": name}

        try:
            resp = self._get(url_path, params=params)
            if resp.status_code != 200:
                logger.debug("获取域封禁列表失败: HTTP %d", resp.status_code)
                if as_model:
                    return models.AreaBlocksResult(payload={"error": f"HTTP {resp.status_code}"}, response=resp)
                return {"error": f"HTTP {resp.status_code}"}

            result = resp.json()
            if not result.get("status"):
                msg = result.get("message") or result.get("error") or "未知错误"
                logger.debug("获取域封禁列表失败: %s", msg)
                if as_model:
                    return models.AreaBlocksResult(payload={"error": msg}, response=resp)
                return {"error": msg}

            data = result.get("data", {})
            blocks = data if isinstance(data, list) else data.get("blocks", data.get("list", []))
            if not isinstance(blocks, list):
                blocks = []
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
                        if isinstance(item, dict)
                    ],
                    payload=result,
                    response=resp,
                )
            return {"blocks": blocks}
        except Exception as e:
            logger.error("获取域封禁列表异常: %s", e)
            if as_model:
                return models.AreaBlocksResult(payload={"error": str(e)})
            return {"error": str(e)}

    def unblock_user_in_area(self, uid: str, area: Optional[str] = None) -> models.OperationResult:
        """解除域内封禁。"""
        area = area or self._config.default_area
        url_path = "/client/v1/area/v1/unblock"
        query = f"?area={area}&target={uid}"
        body = {"area": area, "target": uid}
        return self._manage_patch("解除域内封禁", url_path, query, body)

    def _manage_patch(self, action: str, url_path: str, query: str, body: dict) -> models.OperationResult:
        """通用 PATCH 管理操作（禁言/禁麦等）。"""
        full_path = url_path + query
        params = dict(parse_qsl(query.lstrip("?")))
        try:
            resp = self._request("PATCH", url_path, body=body, params=params)
        except Exception as e:
            logger.error("%s请求异常: %s", action, e)
            return models.OperationResult(ok=False, message=str(e), payload=body)

        raw = resp.text or ""
        logger.info("%s PATCH %s -> HTTP %d, body: %s", action, full_path, resp.status_code, raw[:300])

        if resp.status_code != 200:
            err = f"HTTP {resp.status_code}" + (f" | {raw[:200]}" if raw else "")
            return models.OperationResult(ok=False, message=err, payload=body, response=resp)

        try:
            result = resp.json()
        except Exception:
            return models.OperationResult(ok=False, message=f"响应非 JSON: {raw[:200]}", payload=body, response=resp)

        if result.get("status") is True:
            msg = result.get("message") or f"{action}成功"
            logger.info("%s成功: %s", action, msg)
            return self._build_result(result, response=resp, default_message=msg)

        err = result.get("message") or result.get("error") or str(result)
        logger.error("%s失败: %s", action, err)
        return models.OperationResult(ok=False, message=str(err), payload=result, response=resp)

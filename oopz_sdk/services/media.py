from __future__ import annotations

import hashlib
import io
import json
import logging
import os

import aiohttp
from PIL import Image

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzConnectionError, OopzRateLimitError
from oopz_sdk.transport.http import HttpTransport

from . import BaseService
from .message import Message
from ..models import ImageAttachment
from ..models.attachment import AudioAttachment
from ..utils.image import get_image_info

logger = logging.getLogger("oopz_sdk.services.media")
UPLOAD_PUT_TIMEOUT = (10, 60)


def _safe_json(response) -> dict | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None


def _error_message_from_payload(payload: dict | None, default_message: str) -> str:
    if not payload:
        return default_message
    for key in ("message", "error", "msg", "reason"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return default_message


def _is_explicit_failure_payload(payload: dict) -> bool:
    status = payload.get("status")
    code = payload.get("code")
    if status is False:
        return True
    if payload.get("success") is False:
        return True
    if code is None:
        return False
    return code not in (0, "0", 200, "200", "success")


def _raise_upload_error(response, default_message: str) -> Exception:
    payload = _safe_json(response)
    message = _error_message_from_payload(payload, default_message)

    if not payload and response.text:
        message = f"{message}: {response.text[:200]}"

    if response.status_code == 429:
        retry_after = 0
        try:
            retry_after = int(response.headers.get("Retry-After", "0") or "0")
        except Exception:
            retry_after = 0
        raise OopzRateLimitError(
            message=message,
            retry_after=retry_after,
            response=payload,
        )
    raise OopzApiError(message, status_code=response.status_code, response=payload)


def _require_upload_ticket(
    response,
    default_message: str,
) -> tuple[dict, str, str, str]:
    if response.status_code != 200:
        _raise_upload_error(response, default_message)

    payload = _safe_json(response)
    if payload is None:
        raise OopzApiError(
            f"{default_message}: response is not JSON",
            status_code=response.status_code,
        )

    if _is_explicit_failure_payload(payload):
        raise OopzApiError(
            _error_message_from_payload(payload, default_message),
            status_code=response.status_code,
            response=payload,
        )

    data = payload.get("data")
    if not isinstance(data, dict):
        raise OopzApiError(
            f"{default_message}: missing upload data",
            status_code=response.status_code,
            response=payload,
        )

    signed_url = str(data.get("signedUrl") or "").strip()
    file_key = str(data.get("file") or "").strip()
    cdn_url = str(data.get("url") or "").strip()
    if not signed_url or not file_key or not cdn_url:
        raise OopzApiError(
            f"{default_message}: incomplete upload data",
            status_code=response.status_code,
            response=payload,
        )

    return payload, signed_url, file_key, cdn_url


class Media(BaseService):
    """Media upload capabilities."""

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

    def _message_service(self) -> Message:
        return Message(self._bot, self._config, self.transport, self.signer, media=self)

    def _private_message_service(self) -> PrivateMessage:
        return PrivateMessage(
            self._bot,
            self._config,
            self.transport,
            self.signer,
            media=self,
        )

    async def _download_external(
        self,
        url: str,
        *,
        timeout: int | tuple[int, int],
        stream: bool = False,
        headers: dict | None = None,
    ):
        request_headers = dict(headers or {})
        client_timeout = aiohttp.ClientTimeout(total=timeout) if isinstance(timeout, int) else aiohttp.ClientTimeout(
            total=None,
            sock_connect=timeout[0],
            sock_read=timeout[1],
        )
        try:
            async with aiohttp.ClientSession(timeout=client_timeout) as session:
                async with session.get(url, headers=request_headers) as response:
                    content = await response.read()
                    try:
                        text = content.decode(response.charset or "utf-8")
                    except UnicodeDecodeError:
                        text = content.decode("utf-8", errors="replace")
                    return type(
                        "ExternalResponse",
                        (),
                        {
                            "status_code": response.status,
                            "headers": dict(response.headers),
                            "content": content,
                            "text": text,
                            "raise_for_status": lambda self: (
                                None
                                if self.status_code < 400
                                else (_ for _ in ()).throw(
                                    aiohttp.ClientResponseError(
                                        response.request_info,
                                        response.history,
                                        status=response.status,
                                        message=response.reason or "",
                                        headers=response.headers,
                                    )
                                )
                            ),
                        },
                    )()
        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"下载外部文件失败: {exc}") from exc

    async def _upload_to_signed_url(self, signed_url: str, data, *, default_message: str):
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(
                    total=None,
                    sock_connect=UPLOAD_PUT_TIMEOUT[0],
                    sock_read=UPLOAD_PUT_TIMEOUT[1],
                )
            ) as session:
                async with session.put(
                    signed_url,
                    data=data,
                    headers={"Content-Type": "application/octet-stream"},
                ) as response:
                    content = await response.read()
                    try:
                        text = content.decode(response.charset or "utf-8")
                    except UnicodeDecodeError:
                        text = content.decode("utf-8", errors="replace")
                    return type(
                        "UploadResponse",
                        (),
                        {
                            "status_code": response.status,
                            "headers": dict(response.headers),
                            "content": content,
                            "text": text,
                            "json": lambda self: json.loads(self.text),
                        },
                    )()
        except aiohttp.ClientError as exc:
            raise OopzConnectionError(f"{default_message}: {exc}") from exc

    async def upload_file(
        self,
        file_path: str,
        file_type: str = "IMAGE",
        ext: str = ".webp",
    ) -> models.UploadResult:
        """上传本地文件并返回附件模型。"""
        url_path = "/rtc/v1/cos/v1/signedUploadUrl"
        body = {"type": file_type, "ext": ext}

        resp = await self._await_if_needed(self._put(url_path, body))
        payload, upload_url, file_key, cdn_url = _require_upload_ticket(
            resp,
            "获取上传 URL 失败",
        )

        with open(file_path, "rb") as f:
            put_resp = await self._upload_to_signed_url(
                upload_url,
                f,
                default_message="文件上传失败",
            )
        if put_resp.status_code not in (200, 201):
            raise OopzApiError(
                f"文件上传失败: {put_resp.text}",
                status_code=put_resp.status_code,
            )

        attachment = models.Attachment(
            file_key=str(file_key),
            url=str(cdn_url),
            attachment_type=str(file_type),
            display_name=os.path.basename(file_path),
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        )
        return models.UploadResult(attachment=attachment, payload=payload, response=resp)

    async def upload_file_from_url(self, image_url: str) -> models.UploadResult:
        """从网络地址下载图片并上传到 Oopz。"""
        try:
            resp = await self._download_external(image_url, stream=True, timeout=15)
            resp.raise_for_status()
            image_bytes = resp.content
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            file_size = len(image_bytes)
            ext = "." + (img.format or "webp").lower()
            md5 = hashlib.md5(image_bytes).hexdigest()

            url_path = "/rtc/v1/cos/v1/signedUploadUrl"
            body = {"type": "IMAGE", "ext": ext}
            resp2 = await self._await_if_needed(self._put(url_path, body))
            _, signed_url, file_key, cdn_url = _require_upload_ticket(
                resp2,
                "获取上传 URL 失败",
            )

            put_resp = await self._upload_to_signed_url(
                signed_url,
                image_bytes,
                default_message="从 URL 上传失败",
            )
            if put_resp.status_code not in (200, 201):
                raise OopzApiError(
                    f"从 URL 上传失败: {put_resp.text}",
                    status_code=put_resp.status_code,
                )

            attachment = {
                "fileKey": file_key,
                "url": cdn_url,
                "width": width,
                "height": height,
                "fileSize": file_size,
                "hash": md5,
                "animated": False,
                "displayName": "",
                "attachmentType": "IMAGE",
            }
            return models.UploadResult(
                attachment=ImageAttachment(
                    file_key=str(file_key),
                    url=str(cdn_url),
                    attachment_type="IMAGE",
                    file_size=file_size,
                    width=width,
                    height=height,
                    hash=md5,
                ),
                payload={"code": "success", "message": "上传成功", "data": attachment},
            )

        except OopzApiError:
            raise
        except aiohttp.ClientError as e:
            logger.error("从 URL 上传失败: %s", e)
            raise OopzApiError(f"从 URL 上传失败: {e}") from e
        except Exception as e:
            logger.error("从 URL 上传失败: %s", e)
            raise OopzApiError(f"从 URL 上传失败: {e}") from e

    async def upload_audio_from_url(
        self,
        audio_url: str,
        filename: str = "music.mp3",
        duration_ms: int = 0,
    ) -> models.UploadResult:
        """从网络地址下载音频并上传到 Oopz。"""
        try:
            resp = await self._download_external(
                audio_url,
                timeout=30,
                headers={"Referer": "https://music.163.com/"},
            )
            resp.raise_for_status()
            audio_bytes = resp.content
            file_size = len(audio_bytes)

            content_type = resp.headers.get("Content-Type", "")
            if "mp4" in content_type or "m4a" in content_type:
                ext = ".m4a"
            elif "flac" in content_type:
                ext = ".flac"
            else:
                ext = ".mp3"

            md5 = hashlib.md5(audio_bytes).hexdigest()

            url_path = "/rtc/v1/cos/v1/signedUploadUrl"
            body = {"type": "AUDIO", "ext": ext}
            resp2 = await self._await_if_needed(self._put(url_path, body))
            _, signed_url, file_key, cdn_url = _require_upload_ticket(
                resp2,
                "获取上传 URL 失败",
            )

            put_resp = await self._upload_to_signed_url(
                signed_url,
                audio_bytes,
                default_message="音频上传失败",
            )
            if put_resp.status_code not in (200, 201):
                raise OopzApiError(
                    f"音频上传失败: {put_resp.text}",
                    status_code=put_resp.status_code,
                )

            base_name = os.path.splitext(filename or "")[0] or "music"
            display_name = base_name + ext
            duration_sec = duration_ms // 1000 if duration_ms else 0

            attachment = AudioAttachment(
                file_key=file_key,
                url=cdn_url,
                file_size=file_size,
                hash=md5,
                animated=False,
                display_name=display_name,
                attachment_type="AUDIO",
                duration=duration_ms,
            )
            logger.info(
                "音频上传成功: %s (%d bytes, %ds)",
                display_name,
                file_size,
                duration_sec,
            )
            return models.UploadResult(
                attachment=attachment,
                payload={"code": "success", "data": attachment.to_payload()},
            )

        except OopzApiError:
            raise
        except aiohttp.ClientError as e:
            logger.error("音频上传失败: %s", e)
            raise OopzApiError(f"音频上传失败: {e}") from e
        except Exception as e:
            logger.error("音频上传失败: %s", e)
            raise OopzApiError(f"音频上传失败: {e}") from e

    async def send_image(
        self,
        file_path: str,
        text: str = "",
        **kwargs,
    ) -> models.MessageSendResult:
        """上传本地图并作为消息发送。"""
        width, height, file_size = get_image_info(file_path)

        url_path = "/rtc/v1/cos/v1/signedUploadUrl"
        body = {"type": "IMAGE", "ext": os.path.splitext(file_path)[1]}
        resp = await self._await_if_needed(self._put(url_path, body))
        _, signed_url, file_key, cdn_url = _require_upload_ticket(
            resp,
            "获取上传 URL 失败",
        )

        with open(file_path, "rb") as f:
            put_resp = await self._upload_to_signed_url(
                signed_url,
                f,
                default_message="图片上传失败",
            )
        if put_resp.status_code not in (200, 201):
            raise OopzApiError(
                f"图片上传失败: {put_resp.text}",
                status_code=put_resp.status_code,
            )

        attachment = ImageAttachment(
            file_key=file_key,
            url=cdn_url,
            width=width,
            height=height,
            file_size=file_size,
            hash="",
            animated=False,
            display_name="",
            attachment_type="IMAGE",
        )
        attachments = [attachment.to_payload()]

        msg_text = f"![IMAGEw{width}h{height}]({file_key})"
        if text:
            msg_text += f"\n{text}"

        return await self._message_service().send_message(
            text=msg_text, attachments=attachments, **kwargs
        )

    async def send_private_image(
        self,
        target: str,
        file_path: str,
        text: str = "",
    ) -> models.MessageSendResult:
        """上传本地图并通过私信发送。"""
        width, height, file_size = get_image_info(file_path)

        url_path = "/rtc/v1/cos/v1/signedUploadUrl"
        body = {"type": "IMAGE", "ext": os.path.splitext(file_path)[1]}
        try:
            resp = await self._await_if_needed(self._put(url_path, body))
            _, signed_url, file_key, cdn_url = _require_upload_ticket(
                resp,
                "获取上传 URL 失败",
            )

            with open(file_path, "rb") as f:
                put_resp = await self._upload_to_signed_url(
                    signed_url,
                    f,
                    default_message="上传私信图片失败",
                )
            if put_resp.status_code not in (200, 201):
                raise OopzApiError(
                    f"上传私信图片失败: {put_resp.text}",
                    status_code=put_resp.status_code,
                )
        except OopzApiError:
            raise
        except Exception as e:
            logger.error("上传私信图片失败: %s", e)
            raise OopzApiError(f"上传私信图片失败: {e}") from e

        attachment = ImageAttachment(
            file_key=file_key,
            url=cdn_url,
            width=width,
            height=height,
            file_size=file_size,
            hash="",
            animated=False,
            display_name="",
            attachment_type="IMAGE",
        ).to_payload()
        msg_text = f"![IMAGEw{width}h{height}]({file_key})"
        if text:
            msg_text += f"\n{text}"
        return await self._private_message_service().send_private_message(
            target,
            msg_text,
            attachments=[attachment],
        )


UploadMixin = Media

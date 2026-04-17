from __future__ import annotations

import hashlib
import io
import logging
import os
from PIL import Image
import requests

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzRateLimitError
from oopz_sdk.transport.http import HttpTransport
from . import BaseService
from .message import Message
from .privatemessage import PrivateMessage

from ..models import ImageAttachment
from ..models.attachment import AudioAttachment
from ..utils.image import get_image_info

logger = logging.getLogger("oopz_sdk.services.media")


def _safe_json(response: requests.Response) -> dict | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None

def _raise_upload_error(response: requests.Response, default_message: str) -> Exception:
    payload = _safe_json(response)
    message = default_message

    if payload:
        message = str(payload.get("message") or payload.get("error") or message)
    elif response.text:
        message = f"{message}: {response.text[:200]}"

    if response.status_code == 429:
        retry_after = 0
        try:
            retry_after = int(response.headers.get("Retry-After", "0") or "0")
        except Exception:
            retry_after = 0
        raise OopzRateLimitError(message=message, retry_after=retry_after, response=payload)
    raise OopzApiError(message, status_code=response.status_code, response=payload)

UPLOAD_PUT_TIMEOUT = (10, 60)


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
        return Message(self._bot, self._config, self.transport, self.signer)

    def _private_message_service(self) -> PrivateMessage:
        return PrivateMessage(self._bot, self._config, self.transport, self.signer)

    def upload_file(self, file_path: str, file_type: str = "IMAGE", ext: str = ".webp") -> models.UploadResult:
        """上传本地文件并返回附件模型。"""
        url_path = "/rtc/v1/cos/v1/signedUploadUrl"
        body = {"type": file_type, "ext": ext}

        resp = self._put(url_path, body)
        if resp.status_code != 200:
            _raise_upload_error(resp, "获取上传 URL 失败")

        data = resp.json()["data"]
        upload_url = data["signedUrl"]
        file_key = data["file"]
        cdn_url = data["url"]

        with open(file_path, "rb") as f:
            put_resp = self.session.put(
                upload_url,
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=UPLOAD_PUT_TIMEOUT,
            )
        if put_resp.status_code not in (200, 201):
            raise OopzApiError(f"文件上传失败: {put_resp.text}", status_code=put_resp.status_code)

        attachment = models.Attachment(
            file_key=str(file_key),
            url=str(cdn_url),
            attachment_type=str(file_type),
            display_name=os.path.basename(file_path),
            file_size=os.path.getsize(file_path) if os.path.exists(file_path) else 0,
        )
        return models.UploadResult(attachment=attachment, payload=resp.json(), response=resp)

    def upload_file_from_url(self, image_url: str) -> models.UploadResult:
        """从网络 URL 下载图片并上传到 Oopz（不落地磁盘）。"""
        try:
            resp = self.session.get(image_url, stream=True, timeout=15)
            resp.raise_for_status()
            image_bytes = resp.content
            img = Image.open(io.BytesIO(image_bytes))
            width, height = img.size
            file_size = len(image_bytes)
            ext = "." + (img.format or "webp").lower()
            md5 = hashlib.md5(image_bytes).hexdigest()

            url_path = "/rtc/v1/cos/v1/signedUploadUrl"
            body = {"type": "IMAGE", "ext": ext}
            resp2 = self._put(url_path, body)
            resp2.raise_for_status()
            data = resp2.json()["data"]

            signed_url = data["signedUrl"]
            file_key = data["file"]
            cdn_url = data["url"]

            put_resp = self.session.put(
                signed_url,
                data=image_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=UPLOAD_PUT_TIMEOUT,
            )
            put_resp.raise_for_status()

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

        except Exception as e:
            logger.error("从 URL 上传失败: %s", e)
            raise OopzApiError(f"从 URL 上传失败: {e}") from e

    def upload_audio_from_url(
        self, audio_url: str, filename: str = "music.mp3", duration_ms: int = 0
    ) -> models.UploadResult:
        """从网络 URL 下载音频并上传到 Oopz（AUDIO 类型）。"""
        try:
            resp = self.session.get(audio_url, timeout=30, headers={
                "Referer": "https://music.163.com/",
            })
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
            resp2 = self._put(url_path, body)
            resp2.raise_for_status()
            data = resp2.json()["data"]

            signed_url = data["signedUrl"]
            file_key = data["file"]
            cdn_url = data["url"]

            put_resp = self.session.put(
                signed_url,
                data=audio_bytes,
                headers={"Content-Type": "application/octet-stream"},
                timeout=UPLOAD_PUT_TIMEOUT,
            )
            put_resp.raise_for_status()

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
            logger.info("音频上传成功: %s (%d bytes, %ds)", display_name, file_size, duration_sec)
            return models.UploadResult(
                attachment=attachment,
                payload={"code": "success", "data": attachment.to_payload()},
            )

        except Exception as e:
            logger.error("音频上传失败: %s", e)
            raise OopzApiError(f"音频上传失败: {e}") from e

    def send_image(self, file_path: str, text: str = "", **kwargs) -> models.MessageSendResult:
        """上传本地图片并作为消息发送。"""
        width, height, file_size = get_image_info(file_path)

        url_path = "/rtc/v1/cos/v1/signedUploadUrl"
        body = {"type": "IMAGE", "ext": os.path.splitext(file_path)[1]}
        resp = self._put(url_path, body)
        resp.raise_for_status()
        data = resp.json()["data"]

        signed_url = data["signedUrl"]
        file_key = data["file"]
        cdn_url = data["url"]

        with open(file_path, "rb") as f:
            self.session.put(
                signed_url,
                data=f,
                headers={"Content-Type": "application/octet-stream"},
                timeout=UPLOAD_PUT_TIMEOUT,
            ).raise_for_status()

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

        return self._message_service().send_message(
            text=msg_text,
            attachments=attachments,
            **kwargs,
        )

    def send_private_image(self, target: str, file_path: str, text: str = "") -> models.MessageSendResult:
        """上传本地图片并通过私信发送。"""
        width, height, file_size = get_image_info(file_path)

        url_path = "/rtc/v1/cos/v1/signedUploadUrl"
        body = {"type": "IMAGE", "ext": os.path.splitext(file_path)[1]}
        try:
            resp = self._put(url_path, body)
            resp.raise_for_status()
            data = resp.json()["data"]
            signed_url = data["signedUrl"]
            file_key = data["file"]
            cdn_url = data["url"]

            with open(file_path, "rb") as f:
                self.session.put(
                    signed_url,
                    data=f,
                    headers={"Content-Type": "application/octet-stream"},
                    timeout=UPLOAD_PUT_TIMEOUT,
                ).raise_for_status()
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
        return self._private_message_service().send_private_message(
            target,
            msg_text,
            attachments=[attachment],
        )

UploadMixin = Media

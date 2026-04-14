"""Oopz 文件上传 Mixin -- 图片、音频上传与发送。"""

from __future__ import annotations

import hashlib
import io
import logging
import os
from typing import TYPE_CHECKING

import requests
from PIL import Image

from .exceptions import OopzApiError
from .models import MessageSendResult, UploadAttachment, UploadResult
from .response import ensure_success_payload

if TYPE_CHECKING:
    from .config import OopzConfig

logger = logging.getLogger("oopz.upload")

UPLOAD_PUT_TIMEOUT = (10, 60)


def get_image_info(file_path: str) -> tuple[int, int, int]:
    """获取本地图片的宽、高、文件大小。"""
    with Image.open(file_path) as img:
        width, height = img.size
    file_size = os.path.getsize(file_path)
    return width, height, file_size


class UploadMixin:
    """Oopz 文件上传 Mixin -- 图片、音频上传与发送。

    使用方需在实例上提供 ``session``、``_put`` 等底层方法。
    """

    def _request_upload_slot(self, file_type: str, ext: str) -> tuple[dict[str, object], requests.Response]:
        resp = self._put("/rtc/v1/cos/v1/signedUploadUrl", {"type": file_type, "ext": ext})
        payload = ensure_success_payload(resp, "获取上传地址失败")
        data = payload.get("data", {})
        if not isinstance(data, dict):
            raise OopzApiError("获取上传地址失败: 响应格式异常", status_code=resp.status_code, response=payload)
        return data, resp

    def _put_file_bytes(self, upload_url: str, data: bytes) -> None:
        try:
            put_resp = self.session.put(
                upload_url,
                data=data,
                headers={"Content-Type": "application/octet-stream"},
                timeout=UPLOAD_PUT_TIMEOUT,
            )
        except requests.RequestException as exc:
            raise OopzApiError(f"文件上传失败: {exc}") from exc
        if put_resp.status_code not in (200, 201):
            raise OopzApiError(f"文件上传失败: {put_resp.text}", status_code=put_resp.status_code)

    def upload_file(self, file_path: str, file_type: str = "IMAGE", ext: str = ".webp") -> UploadResult:
        """上传本地文件。"""
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        data, resp = self._request_upload_slot(file_type, ext)
        self._put_file_bytes(str(data["signedUrl"]), file_bytes)

        attachment = UploadAttachment(
            file_key=str(data["file"]),
            url=str(data["url"]),
            attachment_type=file_type,
            file_size=len(file_bytes),
        )
        return UploadResult(attachment=attachment, payload=dict(data), response=resp)

    def upload_file_from_url(self, image_url: str) -> UploadResult:
        """从网络 URL 下载图片并上传到 Oopz（不落地磁盘）。"""
        try:
            resp = self.session.get(image_url, stream=True, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise OopzApiError(f"下载图片失败: {exc}") from exc

        image_bytes = resp.content
        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        file_size = len(image_bytes)
        ext = "." + (img.format or "webp").lower()
        md5 = hashlib.md5(image_bytes).hexdigest()

        data, slot_resp = self._request_upload_slot("IMAGE", ext)
        self._put_file_bytes(str(data["signedUrl"]), image_bytes)

        attachment = UploadAttachment(
            file_key=str(data["file"]),
            url=str(data["url"]),
            attachment_type="IMAGE",
            file_size=file_size,
            width=width,
            height=height,
            file_hash=md5,
        )
        return UploadResult(attachment=attachment, payload=dict(data), response=slot_resp)

    def upload_audio_from_url(
        self, audio_url: str, filename: str = "music.mp3", duration_ms: int = 0
    ) -> UploadResult:
        """从网络 URL 下载音频并上传到 Oopz（AUDIO 类型）。"""
        try:
            resp = self.session.get(audio_url, timeout=30, headers={
                "Referer": "https://music.163.com/",
            })
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise OopzApiError(f"下载音频失败: {exc}") from exc

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
        data, slot_resp = self._request_upload_slot("AUDIO", ext)
        self._put_file_bytes(str(data["signedUrl"]), audio_bytes)

        base_name = os.path.splitext(filename or "")[0] or "music"
        display_name = base_name + ext
        duration_sec = duration_ms // 1000 if duration_ms else 0
        attachment = UploadAttachment(
            file_key=str(data["file"]),
            url=str(data["url"]),
            attachment_type="AUDIO",
            file_size=file_size,
            file_hash=md5,
            display_name=display_name,
            duration=duration_sec,
        )
        logger.info("音频上传成功: %s (%d bytes, %ds)", display_name, file_size, duration_sec)
        return UploadResult(attachment=attachment, payload=dict(data), response=slot_resp)

    def upload_and_send_image(self, file_path: str, text: str = "", **kwargs) -> MessageSendResult:
        """上传本地图片并作为消息发送。"""
        width, height, file_size = get_image_info(file_path)
        upload = self.upload_file(file_path, file_type="IMAGE", ext=os.path.splitext(file_path)[1])
        attachment = upload.attachment
        attachment.width = width
        attachment.height = height
        attachment.file_size = file_size

        msg_text = f"![IMAGEw{width}h{height}]({attachment.file_key})"
        if text:
            msg_text += f"\n{text}"

        return self.send_message(text=msg_text, attachments=[attachment.as_payload()], **kwargs)

    def upload_and_send_private_image(self, target: str, file_path: str, text: str = "") -> MessageSendResult:
        """上传本地图片并通过私信发送。"""
        width, height, file_size = get_image_info(file_path)
        upload = self.upload_file(file_path, file_type="IMAGE", ext=os.path.splitext(file_path)[1])
        attachment = upload.attachment
        attachment.width = width
        attachment.height = height
        attachment.file_size = file_size

        msg_text = f"![IMAGEw{width}h{height}]({attachment.file_key})"
        if text:
            msg_text += f"\n{text}"
        return self.send_private_message(target, msg_text, attachments=[attachment.as_payload()])

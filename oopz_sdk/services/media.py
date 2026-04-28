from __future__ import annotations

import asyncio
import logging
import os
from typing import BinaryIO

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.utils.image import read_image_bytes

from . import BaseService

logger = logging.getLogger(__name__)


class Media(BaseService):
    """Media upload capabilities."""

    async def upload_bytes(
            self,
            payload: bytes,
            file_type: str,
            ext: str,
            animated: bool = False,
            display_name: str = "",
    ) -> models.UploadedFileResult:
        """上传 bytes 并返回附件模型。"""
        if not payload:
            raise ValueError("upload payload is empty")

        ticket_data = await self._request_data(
            "PUT",
            "/rtc/v1/cos/v1/signedUploadUrl",
            body={"type": file_type, "ext": ext},
        )
        ticket = models.UploadTicket.from_api(ticket_data)

        resp = await self.transport.request_raw(
            "PUT",
            ticket.signed_url,
            data=payload,
            headers={"Content-Type": "application/octet-stream"},
        )
        if resp.status_code not in (200, 201):
            raise OopzApiError(
                f"文件上传失败: {resp.text}",
                status_code=resp.status_code,
            )

        return models.UploadedFileResult.from_manually(
            ticket.file_key,
            ticket.url,
            file_type,
            display_name or "image",
            len(payload),
            animated,
        )

    async def upload_file(
            self,
            file: str | bytes | bytearray | memoryview | BinaryIO | os.PathLike[str],
            file_type: str,
            ext: str,
            animated: bool = False,
            display_name: str = "",
    ) -> models.UploadedFileResult:
        """上传文件并返回附件模型。支持本地路径、bytes、base64、file-like。"""
        payload, filename = await asyncio.to_thread(read_image_bytes, file)

        return await self.upload_bytes(
            payload,
            file_type=file_type,
            ext=ext,
            animated=animated,
            display_name=display_name or filename,
        )


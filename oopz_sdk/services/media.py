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

    async def upload_file(
            self,
            file: str | bytes | bytearray | memoryview | BinaryIO | os.PathLike[str],
            file_type: str,
            ext: str,
            animated: bool = False,
            display_name: str = "",
    ) -> models.UploadedFileResult:
        """上传文件并返回附件模型。支持本地路径、bytes、base64、file-like。"""
        ticket_data = await self._request_data(
            "PUT",
            "/rtc/v1/cos/v1/signedUploadUrl",
            body={"type": file_type, "ext": ext},
        )
        ticket = models.UploadTicket.from_api(ticket_data)

        payload, filename = await asyncio.to_thread(read_image_bytes, file)
        file_size = len(payload)

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

        final_display_name = display_name or filename or "image"

        return models.UploadedFileResult.from_manually(
            ticket.file_key,
            ticket.url,
            file_type,
            final_display_name,
            file_size,
            animated,
        )


def _read_file_bytes(path: str) -> tuple[bytes, int]:
    with open(path, "rb") as f:
        payload = f.read()
    return payload, len(payload)

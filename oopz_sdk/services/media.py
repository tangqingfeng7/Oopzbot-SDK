from __future__ import annotations

import asyncio
import logging
import os

from oopz_sdk import models
from oopz_sdk.exceptions import OopzApiError

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.media")


class Media(BaseService):
    """Media upload capabilities."""

    async def upload_file(
            self,
            file: str,
            file_type: str,
            ext: str,
            animated=False,
    ) -> models.UploadedFileResult:
        """上传本地文件并返回附件模型。"""
        ticket_data = await self._request_data(
            "PUT",
            "/rtc/v1/cos/v1/signedUploadUrl",
            body={"type": file_type, "ext": ext},
        )
        ticket = models.UploadTicket.from_api(ticket_data)

        payload, file_size = await asyncio.to_thread(_read_file_bytes, file)

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

        attachment = models.UploadedFileResult.from_manually(
            ticket.file_key,
            ticket.url,
            file_type,
            os.path.basename(file),
            file_size,
            animated
        )
        return attachment


def _read_file_bytes(path: str) -> tuple[bytes, int]:
    with open(path, "rb") as f:
        payload = f.read()
    return payload, len(payload)

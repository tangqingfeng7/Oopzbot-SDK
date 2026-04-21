from __future__ import annotations

import logging
import os

from oopz_sdk import models
from oopz_sdk.auth.signer import Signer
from oopz_sdk.config.settings import OopzConfig
from oopz_sdk.exceptions import OopzApiError, OopzConnectionError, OopzRateLimitError
from oopz_sdk.transport.http import HttpTransport

from . import BaseService

logger = logging.getLogger("oopz_sdk.services.media")


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
        super().__init__(config, transport, signer, bot=bot)


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

        with open(file, "rb") as f:
            payload = f.read()

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
            os.path.getsize(file) if os.path.exists(file) else 0,
            animated
        )
        return attachment
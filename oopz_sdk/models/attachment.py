from __future__ import annotations

from abc import ABC
from typing import Any, Mapping

from pydantic import Field, model_validator

from .base import BaseModel
from oopz_sdk.exceptions import OopzApiError
from oopz_sdk.utils.payload import coerce_bool


class UploadTicket(BaseModel):
    auth: str = ""
    expire_in_second: int = Field(default=0, alias="expireInSecond")
    file_key: str = Field(default="", alias="file")
    signed_url: str = Field(default="", alias="signedUrl")
    url: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid upload ticket payload: expected dict", payload=data)

        normalized = dict(data)
        normalized["auth"] = str(normalized.get("auth") or "")
        normalized["file"] = str(normalized.get("file") or "")
        normalized["signedUrl"] = str(normalized.get("signedUrl") or "")
        normalized["url"] = str(normalized.get("url") or "")

        expire = normalized.get("expireInSecond", 0)
        try:
            normalized["expireInSecond"] = int(expire or 0)
        except (TypeError, ValueError):
            normalized["expireInSecond"] = 0

        return normalized

    @model_validator(mode="after")
    def validate_required_fields(self) -> "UploadTicket":
        if not self.file_key:
            raise OopzApiError(
                "invalid upload ticket payload: missing file",
                payload=self.model_dump(by_alias=True),
            )
        if not self.signed_url:
            raise OopzApiError(
                "invalid upload ticket payload: missing signedUrl",
                payload=self.model_dump(by_alias=True),
            )
        if not self.url:
            raise OopzApiError(
                "invalid upload ticket payload: missing url",
                payload=self.model_dump(by_alias=True),
            )
        return self

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "UploadTicket":
        return cls.model_validate(data)


class UploadedFileResult(BaseModel):
    file_key: str = Field(default="", alias="fileKey")
    url: str = ""
    file_type: str = Field(default="", alias="fileType")
    display_name: str = Field(default="", alias="displayName")
    file_size: int = Field(default=0, alias="fileSize")
    animated: bool = False

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid uploaded file payload: expected dict", payload=data)

        normalized = dict(data)
        normalized["fileKey"] = str(normalized.get("fileKey") or "")
        normalized["url"] = str(normalized.get("url") or "")
        normalized["fileType"] = str(normalized.get("fileType") or "").upper()
        normalized["displayName"] = str(normalized.get("displayName") or "")

        try:
            normalized["fileSize"] = int(normalized.get("fileSize") or 0)
        except (TypeError, ValueError):
            normalized["fileSize"] = 0

        return normalized

    @model_validator(mode="after")
    def validate_required_fields(self) -> "UploadedFileResult":
        if not self.file_key:
            raise OopzApiError(
                "invalid uploaded file payload: missing fileKey",
                payload=self.model_dump(by_alias=True),
            )
        if not self.url:
            raise OopzApiError(
                "invalid uploaded file payload: missing url",
                payload=self.model_dump(by_alias=True),
            )
        if not self.file_type:
            raise OopzApiError(
                "invalid uploaded file payload: missing fileType",
                payload=self.model_dump(by_alias=True),
            )
        return self

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "UploadedFileResult":
        return cls.model_validate(data)

    @classmethod
    def from_manually(
            cls,
            file_key: str,
            url: str,
            file_type: str,
            display_name: str,
            file_size: int = 0,
            animated: bool = False,
    ) -> "UploadedFileResult":
        return cls.model_validate({
                "fileKey": file_key,
                "url": url,
                "fileType": file_type,
                "displayName": display_name,
                "fileSize": file_size,
                "animated": animated
            }
        )


class Attachment(BaseModel, ABC):
    file_key: str = Field(default="", alias="fileKey")
    url: str = ""
    attachment_type: str = Field(default="", alias="attachmentType")
    display_name: str = Field(default="", alias="displayName")
    file_size: int = Field(default=0, alias="fileSize")
    animated: bool = False
    hash: str = ""
    width: int = 0
    height: int = 0
    preview_file_key: str = Field(default="", alias="previewFileKey")

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid attachment payload: expected dict", payload=data)

        normalized = dict(data)
        normalized["fileKey"] = str(normalized.get("fileKey") or "")
        normalized["url"] = str(normalized.get("url") or "")
        normalized["attachmentType"] = str(normalized.get("attachmentType") or "").upper()
        normalized["displayName"] = str(normalized.get("displayName") or "")
        normalized["hash"] = str(normalized.get("hash") or "")
        normalized["previewFileKey"] = str(normalized.get("previewFileKey") or "")

        try:
            normalized["fileSize"] = int(normalized.get("fileSize") or 0)
        except (TypeError, ValueError):
            normalized["fileSize"] = 0
        try:
            normalized["width"] = int(normalized.get("width") or 0)
        except (TypeError, ValueError):
            normalized["width"] = 0

        try:
            normalized["height"] = int(normalized.get("height") or 0)
        except (TypeError, ValueError):
            normalized["height"] = 0
        normalized["animated"] = coerce_bool(normalized.get("animated"), default=False)

        return normalized

    @model_validator(mode="after")
    def prevent_direct_base_usage(self) -> "Attachment":
        if self.__class__ is Attachment:
            raise OopzApiError(
                "Attachment is abstract; use a concrete attachment type",
                payload=self.model_dump(by_alias=True),
            )
        return self

    def to_payload(self) -> dict[str, Any]:
        payload = self.model_dump(by_alias=True, exclude_none=True)
        return {key: value for key, value in payload.items() if value not in ("", 0, False)}

    @classmethod
    def parse(cls, data: Mapping[str, Any]) -> "Attachment":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid attachment payload: expected dict", payload=data)

        attachment_type = str(data.get("attachmentType") or "").upper()
        if attachment_type == "IMAGE":
            return ImageAttachment.model_validate(data)
        if attachment_type == "AUDIO":
            return AudioAttachment.model_validate(data)
        if attachment_type == "FILE":
            return FileAttachment.model_validate(data)

        raise OopzApiError(
            f"unsupported attachmentType: {attachment_type or '<empty>'}",
            payload=data,
        )


class ImageAttachment(Attachment):
    @classmethod
    def from_manually(
            cls,
            *,
            file_key: str,
            url: str,
            width: int = 0,
            height: int = 0,
            file_size: int = 0,
            hash: str = "",
            animated: bool = False,
            display_name: str = "",
            preview_file_key: str = "",
    ) -> "ImageAttachment":
        return cls.model_validate(
            {
                "fileKey": file_key,
                "url": url,
                "attachmentType": "IMAGE",
                "displayName": display_name,
                "fileSize": file_size,
                "animated": animated,
                "hash": hash,
                "width": width,
                "height": height,
                "previewFileKey": preview_file_key,
            }
        )

class AudioAttachment(Attachment):
    """语音附件（attachmentType=AUDIO）。

    当前 SDK 不对外暴露 AUDIO 的发送入口（见 ``services/media.py`` / ``services/message.py``），
    但服务端推送过来的消息里可能带 AUDIO 附件，解析时要保留 `duration` 等字段，
    避免 ``Message.attachments`` 被静默丢成空列表。
    """

    duration: int = 0

    @model_validator(mode="before")
    @classmethod
    def _normalize_audio(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            return data
        normalized = dict(data)
        try:
            normalized["duration"] = int(normalized.get("duration") or 0)
        except (TypeError, ValueError):
            normalized["duration"] = 0
        return normalized

    @classmethod
    def from_manually(
            cls,
            *,
            file_key: str,
            url: str,
            display_name: str = "",
            file_size: int = 0,
            duration: int = 0,
            hash: str = "",
    ) -> "AudioAttachment":
        return cls.model_validate(
            {
                "fileKey": file_key,
                "url": url,
                "attachmentType": "AUDIO",
                "displayName": display_name,
                "fileSize": file_size,
                "hash": hash,
                "duration": duration,
            }
        )


class FileAttachment(Attachment):
    """普通文件附件（attachmentType=FILE）。

    父类字段（fileKey / url / displayName / fileSize / hash 等）已覆盖文件附件常见需求；
    保留此子类是为了让 ``Attachment.parse`` 能够把 FILE 归一到一个明确的类型，
    让接收端可以通过 ``isinstance(att, FileAttachment)`` 区分。
    """

    @classmethod
    def from_manually(
            cls,
            *,
            file_key: str,
            url: str,
            display_name: str = "",
            file_size: int = 0,
            hash: str = "",
    ) -> "FileAttachment":
        return cls.model_validate(
            {
                "fileKey": file_key,
                "url": url,
                "attachmentType": "FILE",
                "displayName": display_name,
                "fileSize": file_size,
                "hash": hash,
            }
        )
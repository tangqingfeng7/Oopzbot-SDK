from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .base import BaseModel


@dataclass(slots=True)
class Attachment(BaseModel):
    file_key: str = ""
    url: str = ""
    attachment_type: str = ""
    display_name: str = ""
    file_size: int = 0
    animated: bool = False
    hash: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "fileKey": self.file_key,
            "url": self.url,
            "attachmentType": self.attachment_type,
            "displayName": self.display_name,
            "fileSize": self.file_size,
            "animated": self.animated,
            "hash": self.hash,
        }
        return {key: value for key, value in payload.items() if value not in ("", 0, False)}

    def to_dict(self) -> dict[str, Any]:
        return self.to_payload()

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Attachment":
        if not isinstance(data, dict):
            return cls()

        attachment_type = str(data.get("attachmentType") or "").upper()

        common_kwargs = dict(
            file_key=str(data.get("fileKey") or ""),
            url=str(data.get("url") or ""),
            attachment_type=attachment_type,
            display_name=str(data.get("displayName") or ""),
            file_size=int(data.get("fileSize") or 0),
            animated=bool(data.get("animated", False)),
            hash=str(data.get("hash") or ""),
        )

        if attachment_type == "IMAGE":
            return ImageAttachment(
                **common_kwargs,
                width=int(data.get("width") or 0),
                height=int(data.get("height") or 0),
                preview_file_key=str(data.get("previewFileKey") or ""),
            )

        if attachment_type == "AUDIO":
            return AudioAttachment(
                **common_kwargs,
                duration=int(data.get("duration") or 0),
            )

        return cls(**common_kwargs)

@dataclass(slots=True)
class ImageAttachment(Attachment):
    width: int = 0
    height: int = 0
    preview_file_key: str = ""

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.width:
            payload["width"] = self.width
        if self.height:
            payload["height"] = self.height
        if self.preview_file_key:
            payload["previewFileKey"] = self.preview_file_key
        return payload



@dataclass(slots=True)
class AudioAttachment(Attachment):
    duration: int = 0

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.duration:
            payload["duration"] = self.duration
        return payload

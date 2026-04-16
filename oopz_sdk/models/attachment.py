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

@dataclass(slots=True)
class ImageAttachment(Attachment):
    width: int = 0
    height: int = 0

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.width:
            payload["width"] = self.width
        if self.height:
            payload["height"] = self.height
        return payload



@dataclass(slots=True)
class AudioAttachment(Attachment):
    duration: int = 0

    def to_payload(self) -> dict[str, Any]:
        payload = super().to_payload()
        if self.duration:
            payload["duration"] = self.duration
        return payload

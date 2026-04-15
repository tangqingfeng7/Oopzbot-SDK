from __future__ import annotations

from dataclasses import dataclass

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

@dataclass(slots=True)
class ImageAttachment(Attachment):
    width: int = 0
    height: int = 0



@dataclass(slots=True)
class AudioAttachment(Attachment):
    duration: int = 0
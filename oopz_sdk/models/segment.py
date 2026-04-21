from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .attachment import ImageAttachment


@dataclass(slots=True)
class Segment:
    type: str

    def __init__(self, type_):
        self.type = type_

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError("Segment.to_dict() must be implemented by subclasses")


@dataclass(slots=True)
class Text(Segment):
    text: str

    def __init__(self, text: str):
        Segment.__init__(self, "text")
        self.text = text

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "data": {
                "text": self.text,
            },
        }


@dataclass(slots=True)
class Image(Segment):
    # 发送侧：本地文件路径（待上传）
    file_path: str = ""
    # 接收侧/发送侧：本地缓存路径（已下载）
    local_path: str = ""

    # 已上传资源信息
    file_key: str = ""
    url: str = ""

    # 图片元信息
    width: int = 0
    height: int = 0
    file_size: int = 0
    hash: str = ""
    animated: bool = False
    display_name: str = ""
    preview_file_key: str = ""

    def __init__(
        self,
        file_path: str = "", # 必填
        *,
        local_path: str = "",
        file_key: str = "",
        url: str = "",
        width: int = 0,
        height: int = 0,
        file_size: int = 0,
        hash: str = "",
        animated: bool = False,
        display_name: str = "",
        preview_file_key: str = "",
    ):
        Segment.__init__(self, "image")
        self.file_path = file_path
        self.local_path = local_path
        self.file_key = file_key
        self.url = url
        self.width = int(width or 0)
        self.height = int(height or 0)
        self.file_size = int(file_size or 0)
        self.hash = hash
        self.animated = bool(animated)
        self.display_name = display_name
        self.preview_file_key = preview_file_key

    @classmethod
    def from_file(cls, file_path: str) -> "Image":
        return cls(file_path=file_path)

    @classmethod
    def from_uploaded(
        cls,
        *,
        file_key: str,
        url: str,
        width: int,
        height: int,
        file_size: int = 0,
        hash: str = "",
        animated: bool = False,
        display_name: str = "",
        preview_file_key: str = "",
    ) -> "Image":
        return cls(
            file_key=file_key,
            url=url,
            width=width,
            height=height,
            file_size=file_size,
            hash=hash,
            animated=animated,
            display_name=display_name,
            preview_file_key=preview_file_key,
        )

    @classmethod
    def from_attachment(cls, attachment: ImageAttachment, *, local_path: str = "") -> "Image":
        return cls(
            local_path=local_path,
            file_key=attachment.file_key,
            url=attachment.url,
            width=attachment.width,
            height=attachment.height,
            file_size=attachment.file_size,
            hash=attachment.hash,
            animated=attachment.animated,
            display_name=attachment.display_name,
            preview_file_key=attachment.preview_file_key,
        )

    @property
    def is_uploaded(self) -> bool:
        return bool(self.file_key and self.url)

    @property
    def has_local_file(self) -> bool:
        return bool(self.file_path or self.local_path)

    @property
    def source_path(self) -> str:
        return self.file_path or self.local_path

    @property
    def can_send(self) -> bool:
        return self.is_uploaded or self.has_local_file

    def to_attachment(self) -> ImageAttachment:
        if not self.is_uploaded:
            raise ValueError("ImageSegment has not been uploaded yet and cannot become an attachment")

        return ImageAttachment.from_manually(
            file_key=self.file_key,
            url=self.url,
            display_name=self.display_name,
            file_size=self.file_size,
            animated=self.animated,
            hash=self.hash,
            width=self.width,
            height=self.height,
            preview_file_key=self.preview_file_key,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "data": {
                "file_path": self.file_path,
                "local_path": self.local_path,
                "file_key": self.file_key,
                "url": self.url,
                "width": self.width,
                "height": self.height,
                "file_size": self.file_size,
                "hash": self.hash,
                "animated": self.animated,
                "display_name": self.display_name,
                "preview_file_key": self.preview_file_key,
            },
        }
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, TYPE_CHECKING

if TYPE_CHECKING:
    from .message import MentionInfo

from .attachment import Attachment, ImageAttachment

MENTION_RE = re.compile(r"\s*(\(met\)(.+?)\(met\))\s*")
IMAGE_RE = re.compile(r"!\[IMAGEw(\d+)h(\d+)\]\(([^)]+)\)(?:\r?\n)*")

_MARKDOWN_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\*\*(.+?)\*\*", re.DOTALL), r"\1"),
    (re.compile(r"\*(.+?)\*", re.DOTALL), r"\1"),
    (re.compile(r"~~(.+?)~~", re.DOTALL), r"\1"),
    (re.compile(r"__(.+?)__", re.DOTALL), r"\1"),
]


@dataclass(slots=True)
class Segment:
    type: str

    def __init__(self, type_: str):
        self.type = type_

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError("Segment.to_dict() must be implemented by subclasses")

    def to_message_text(self) -> str:
        raise NotImplementedError("Segment.to_message_text() must be implemented by subclasses")


@dataclass(slots=True)
class Text(Segment):
    text: str
    plain_text: str

    def __init__(self, text: str, plain_text: str | None = None):
        Segment.__init__(self, "text")
        self.text = text
        self.plain_text = text if plain_text is None else plain_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "data": {
                "text": self.text,
                "plain_text": self.plain_text,
            },
        }

    def to_message_text(self) -> str:
        return self.text


@dataclass(slots=True)
class Mention(Segment):
    person: str
    raw: str

    def __init__(self, user_id: str, raw: str | None = None):
        Segment.__init__(self, "mention")
        self.person = str(user_id)
        self.raw = raw or f"(met){self.person}(met)"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "mention",
            "data": {
                "user_id": self.person,
            },
        }

    def to_message_text(self) -> str:
        return f" {self.raw.strip()} "


@dataclass(slots=True)
class MentionAll(Segment):
    raw: str

    def __init__(self, raw: str | None = None):
        Segment.__init__(self, "mention_all")
        self.raw = raw or "(met)All(met)"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "mention_all",
            "data": {},
        }

    def to_message_text(self) -> str:
        return f" {self.raw.strip()} "


@dataclass(slots=True)
class Image(Segment):
    file_path: str = ""
    local_path: str = ""
    file_key: str = ""
    url: str = ""
    width: int = 0
    height: int = 0
    file_size: int = 0
    hash: str = ""
    animated: bool = False
    display_name: str = ""
    preview_file_key: str = ""

    def __init__(
            self,
            file_path: str = "",
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

    def to_message_text(self) -> str:
        return f"![IMAGEw{self.width}h{self.height}]({self.file_key})\n"

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


def strip_markdown(text: str) -> str:
    """
    将 Markdown 样式去掉，返回纯文本版本的简易实现

    Example：
        "hello **world**" -> "hello world"
    """
    result = text
    for pattern, repl in _MARKDOWN_PATTERNS:
        result = pattern.sub(repl, result)
    return result


def _join_escaped(values: Iterable[str]) -> str:
    uniq = sorted({str(v) for v in values if str(v)}, key=len, reverse=True)
    return "|".join(re.escape(v) for v in uniq)


def build_token_re(
        mention_list: list[MentionInfo] | None,
        attachments: list[Attachment] | None,
) -> re.Pattern[str]:
    """
    根据当前消息上下文提供的mention_list和attachments，构造只本条消息里合法的正则。

    - mention 只认 mention_list 里出现过的 person
    - image 只认 attachments 里出现过的 image file_key
    """
    mention_list = mention_list or []
    attachments = attachments or []

    persons = [m.person for m in mention_list if getattr(m, "person", "")]

    # 匹配mentionall事件
    persons.append("All")

    image_keys = [
        att.file_key
        for att in attachments
        if isinstance(att, ImageAttachment) and getattr(att, "file_key", "")
    ]

    parts: list[str] = []

    if persons:
        parts.append(rf"\s*\(met\)(?:{_join_escaped(persons)})\(met\)\s*")

    if image_keys:
        parts.append(rf"!\[IMAGEw\d+h\d+\]\((?:{_join_escaped(image_keys)})\)(?:\r?\n)*")

    return re.compile("|".join(parts), re.DOTALL)


def parse_message_segments(
        text: str,
        *,
        attachments: list[Attachment] | None = None,
        mention_list: list[MentionInfo] | None = None,
) -> list[Segment]:
    """
    将一条消息文本解析为 segments。

    流程概览：
    1. 收集当前消息中 mention person 和 image file_key
    2. 构造 token 正则，只扫描这条消息里可能合法的 token
    3. 按 token 在原文中的位置切分：
       - token 之前的普通内容 -> Text
       - token 本身 -> MentionAll / Mention / Image
    4. 返回 segments 列表
    """
    text = text or ""
    attachments = attachments or []
    mention_list = mention_list or []

    # 将 attachment 里的图片按 file_key 建索引，方便从 token 反查出真正的 ImageAttachment
    image_by_key: dict[str, ImageAttachment] = {}
    for att in attachments:
        if isinstance(att, ImageAttachment) and att.file_key:
            image_by_key[att.file_key] = att

    token_re = build_token_re(mention_list, attachments)

    pos = 0
    segments: list[Segment] = []

    for match in token_re.finditer(text):
        # token 前面的普通文本直接作为 Text
        if match.start() > pos:
            raw_text = text[pos:match.start()]
            if raw_text:
                segments.append(Text(raw_text, plain_text=strip_markdown(raw_text)))

        token = match.group(0)

        # mention 分支
        mention_match = MENTION_RE.fullmatch(token)
        if mention_match:
            raw = mention_match.group(1)
            person = mention_match.group(2)

            if person == "All":
                segments.append(MentionAll(raw=raw))
            else:
                segments.append(Mention(user_id=person, raw=raw))

            pos = match.end()
            continue

        # image 分支
        image_match = IMAGE_RE.fullmatch(token)
        if image_match:
            file_key = image_match.group(3)
            segments.append(Image.from_attachment(image_by_key[file_key]))

            pos = match.end()
            continue

        # 理论上不会走到这里；
        # token_re 已经保证 token 只能是 mention 或 image
        raise ValueError(f"unexpected token matched by token_re: {token!r}")

    # 最后一个 token 后面的剩余普通文本
    if pos < len(text):
        raw_text = text[pos:]
        if raw_text:
            segments.append(Text(raw_text, plain_text=strip_markdown(raw_text)))

    return segments


def build_segments(segments: list[Segment]) -> tuple[str, list[dict]]:
    """
    将已 resolve 的 segments 编译成 Oopz send_message 所需的:
    - text
    - attachments
    """
    text_parts: list[str] = []
    attachments: list[dict] = []

    for seg in segments:
        if isinstance(seg, Text):
            text_parts.append(seg.text)
            continue

        elif isinstance(seg, Image):
            if not seg.is_uploaded:
                raise ValueError(
                    "ImageSegment must be resolved/uploaded before build_segments()"
                )
            if seg.width <= 0 or seg.height <= 0:
                raise ValueError(
                    "ImageSegment width/height must be set before build_segments()"
                )

            text_parts.append(seg.to_message_text())

            attachment = seg.to_attachment()
            attachments.append(attachment.to_payload())
            continue
        elif isinstance(seg, MentionAll) or isinstance(seg, Mention):
            text_parts.append(seg.to_message_text())
            continue
        raise TypeError(f"Unsupported segment type: {type(seg)!r}")

    text = "".join(part for part in text_parts if part != "").rstrip("\n")
    return text, attachments


def normalize_message_parts(parts: Iterable[str | Segment]) -> list[Segment]:
    result: list[Segment] = []

    for part in parts:
        if isinstance(part, Segment):
            result.append(part)
        elif isinstance(part, str):
            result.append(Text(part))
        else:
            raise TypeError(f"Unsupported message part type: {type(part)!r}")

    return result

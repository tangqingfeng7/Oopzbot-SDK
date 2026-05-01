from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

from oopz_sdk.models.segment import Image, Mention, MentionAll, Text

from .types import IdStore, make_user_source

CQ_RE = re.compile(r"\[CQ:(?P<type>\w+)(?P<params>(?:,[^\]]*)?)\]")


@dataclass(slots=True)
class V11SendParts:
    parts: list[Any]
    mention_list: list
    is_mention_all: bool = False


def to_v11_message(message, *, ids: IdStore | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for seg in getattr(message, "segments", []) or []:
        if isinstance(seg, Text):
            result.append({"type": "text", "data": {"text": seg.text}})
        elif isinstance(seg, Mention):
            qq: str | int = seg.person
            if ids is not None:
                qq = ids.createId(make_user_source(seg.person)).number
            result.append({"type": "at", "data": {"qq": qq}})
        elif isinstance(seg, MentionAll):
            result.append({"type": "at", "data": {"qq": "all"}})
        elif isinstance(seg, Image):
            result.append({"type": "image", "data": {"file": seg.file_key or seg.url, "url": seg.url}})
    if not result:
        text = getattr(message, "plain_text", "") or getattr(message, "text", "") or getattr(message, "content", "")
        result.append({"type": "text", "data": {"text": text}})
    return result


def from_v11_message(message: str | list[Mapping[str, Any]]) -> V11SendParts:
    if isinstance(message, str):
        return _from_cq_or_text(message)

    parts: list[Any] = []
    mentions: list[str] = []
    is_all = False
    for seg in message:
        seg_type = str(seg.get("type") or "")
        data = seg.get("data") or {}
        if not isinstance(data, Mapping):
            data = {}
        if seg_type == "text":
            parts.append(str(data.get("text") or ""))
        elif seg_type == "at":
            qq = str(data.get("qq") or "")
            if qq == "all":
                is_all = True
                parts.append(MentionAll())
            elif qq:
                mentions.append(qq)
                parts.append(Mention(qq))
        elif seg_type == "image":
            file = str(data.get("file") or data.get("url") or "")
            if file.startswith("file:///"):
                parts.append(Image.from_file(file.removeprefix("file:///")))
            elif file:
                parts.append(Image(file_key=file, url=str(data.get("url") or "")))
        else:
            parts.append(f"[{seg_type}:{dict(data)}]")
    return V11SendParts(parts=parts or [""], mention_list=mentions, is_mention_all=is_all)


def _from_cq_or_text(text: str) -> V11SendParts:
    parts: list[Any] = []
    mentions: list[str] = []
    is_all = False
    pos = 0
    for m in CQ_RE.finditer(text):
        if m.start() > pos:
            parts.append(text[pos:m.start()])
        seg_type = m.group("type")
        params = _parse_cq_params(m.group("params"))
        if seg_type == "at":
            qq = params.get("qq", "")
            if qq == "all":
                is_all = True
                parts.append(MentionAll())
            elif qq:
                mentions.append(qq)
                parts.append(Mention(qq))
        elif seg_type == "image":
            file = params.get("file") or params.get("url") or ""
            if file.startswith("file://"):
                parts.append(Image.from_file(file.removeprefix("file://")))
            elif file:
                parts.append(Image(file_key=file, url=params.get("url", "")))
        else:
            parts.append(m.group(0))
        pos = m.end()
    if pos < len(text):
        parts.append(text[pos:])
    return V11SendParts(parts=parts or [""], mention_list=mentions, is_mention_all=is_all)


def _parse_cq_params(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    raw = raw.lstrip(",")
    if not raw:
        return result
    for item in raw.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            result[k] = v
    return result

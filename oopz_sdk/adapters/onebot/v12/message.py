from __future__ import annotations

from typing import Any, Mapping

from oopz_sdk.models.segment import Image, Mention, MentionAll, Segment, Text

from .types import SendParts


def to_onebot_message(oopz_message: Any) -> list[dict[str, Any]]:
    """
    Oopz Message.segments -> OneBot v12 message。
    """
    segments: list[dict[str, Any]] = []

    for seg in getattr(oopz_message, "segments", []) or []:
        if isinstance(seg, Text):
            if seg.text:
                segments.append(
                    {
                        "type": "text",
                        "data": {
                            "text": seg.text,
                        },
                    }
                )
            continue

        if isinstance(seg, Mention):
            segments.append(
                {
                    "type": "mention",
                    "data": {
                        "user_id": seg.person,
                    },
                }
            )
            continue

        if isinstance(seg, MentionAll):
            segments.append(
                {
                    "type": "mention_all",
                    "data": {},
                }
            )
            continue

        if isinstance(seg, Image):
            file_id = seg.file_key
            if file_id:
                data: dict[str, Any] = {
                    "file_id": file_id,
                }
                if seg.url:
                    data["url"] = seg.url
                if seg.width:
                    data["width"] = seg.width
                if seg.height:
                    data["height"] = seg.height
                if seg.file_size:
                    data["file_size"] = seg.file_size

                segments.append(
                    {
                        "type": "image",
                        "data": data,
                    }
                )
            continue

        segments.append(
            {
                "type": "text",
                "data": {
                    "text": str(seg),
                },
            }
        )

    if not segments:
        text = (
            getattr(oopz_message, "plain_text", "")
            or getattr(oopz_message, "text", "")
            or getattr(oopz_message, "content", "")
        )
        if text:
            segments.append(
                {
                    "type": "text",
                    "data": {
                        "text": text,
                    },
                }
            )

    return segments


def from_onebot_message(message: str | list[Mapping[str, Any]]) -> SendParts:
    """
    OneBot v12 message -> Oopz send_message(*parts) 参数。
    """
    if isinstance(message, str):
        return SendParts(
            parts=[message],
            mention_list=[],
            is_mention_all=False,
            reference_message_id=None,
        )

    parts: list[Any] = []
    mention_list: list[dict[str, Any]] = []
    is_mention_all = False
    reference_message_id: str | None = None

    for seg in message:
        seg_type = str(seg.get("type") or "")
        data = seg.get("data") or {}
        if not isinstance(data, Mapping):
            data = {}

        if seg_type == "text":
            text = str(data.get("text") or "")
            if text:
                parts.append(text)
            continue

        if seg_type in {"mention", "at"}:
            user_id = str(data.get("user_id") or data.get("qq") or data.get("id") or "")
            if user_id:
                parts.append(f" (met){user_id}(met) ")
                mention_list.append({"person": user_id, "offset": -1})
            continue

        if seg_type in {"mention_all", "at_all"}:
            is_mention_all = True
            parts.append(" (met)All(met) ")
            continue

        if seg_type == "reply":
            msg_id = str(data.get("message_id") or data.get("id") or "")
            if msg_id:
                reference_message_id = msg_id
            continue

        if seg_type == "image":
            image = _image_from_onebot_data(data)
            if image is not None:
                parts.append(image)
            else:
                file_id = str(data.get("file_id") or data.get("url") or "")
                parts.append(f"[图片:{file_id}]")
            continue

        # 未支持的 segment 不丢弃，降级成文本
        parts.append(f"[{seg_type}:{dict(data)}]")

    if not parts:
        parts.append("")

    return SendParts(
        parts=parts,
        mention_list=mention_list,
        is_mention_all=is_mention_all,
        reference_message_id=reference_message_id,
    )


def alt_message(message: str | list[Mapping[str, Any]]) -> str:
    if isinstance(message, str):
        return message

    result: list[str] = []

    for seg in message:
        seg_type = str(seg.get("type") or "")
        data = seg.get("data") or {}
        if not isinstance(data, Mapping):
            data = {}

        if seg_type == "text":
            result.append(str(data.get("text") or ""))
        elif seg_type in {"mention", "at"}:
            result.append(f"@{data.get('user_id') or data.get('qq') or data.get('id') or ''}")
        elif seg_type in {"mention_all", "at_all"}:
            result.append("@全体成员")
        elif seg_type == "image":
            result.append("[图片]")
        elif seg_type == "reply":
            continue
        else:
            result.append(f"[{seg_type}]")

    return "".join(result)


def _image_from_onebot_data(data: Mapping[str, Any]) -> Image | None:
    file_id = str(data.get("file_id") or "")
    url = str(data.get("url") or "")

    width = _safe_int(data.get("width"))
    height = _safe_int(data.get("height"))
    file_size = _safe_int(data.get("file_size"))

    if file_id.startswith("file://"):
        return Image.from_file(file_id.removeprefix("file://"))

    if _looks_like_local_path(file_id):
        return Image.from_file(file_id)

    # 已经是 Oopz 上传资源时，可以直接带 file_key + url
    if file_id and url:
        return Image(
            file_key=file_id,
            url=url,
            width=width,
            height=height,
            file_size=file_size,
        )

    return None


def _looks_like_local_path(value: str) -> bool:
    if not value:
        return False

    return (
        value.startswith("/")
        or value.startswith("./")
        or value.startswith(".\\")
        or ":\\" in value
    )


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0
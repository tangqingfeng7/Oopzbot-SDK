from __future__ import annotations

from typing import Iterable

from oopz_sdk.models.segment import Image, Segment, Text


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

        if isinstance(seg, Image):
            if not seg.is_uploaded:
                raise ValueError(
                    "ImageSegment must be resolved/uploaded before build_segments()"
                )
            if seg.width <= 0 or seg.height <= 0:
                raise ValueError(
                    "ImageSegment width/height must be set before build_segments()"
                )

            text_parts.append(f"![IMAGEw{seg.width}h{seg.height}]({seg.file_key})\n")

            attachment = seg.to_attachment()
            attachments.append(attachment.to_payload())
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
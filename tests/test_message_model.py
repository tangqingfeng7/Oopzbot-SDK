"""对 Message 模型解析行为的单元测试。

"""

from __future__ import annotations

import logging

from oopz_sdk.models import ImageAttachment, Message


def _base_payload() -> dict:
    return {
        "type": "text",
        "messageId": "m-1",
        "clientMessageId": "c-1",
        "timestamp": "1700000000000",
        "person": "u-1",
        "area": "a-1",
        "channel": "ch-1",
        "content": "hello",
        "text": "hello",
        "attachments": [],
    }


def test_message_skips_unknown_attachment_type(caplog) -> None:
    payload = _base_payload()
    payload["attachments"] = [
        {
            "attachmentType": "IMAGE",
            "fileKey": "k1",
            "url": "https://example.com/a.png",
            "width": 10,
            "height": 20,
        },
        {
            "attachmentType": "STICKER",
            "fileKey": "k2",
            "url": "https://example.com/b.bin",
        },
    ]

    with caplog.at_level(logging.WARNING, logger="oopz_sdk.models.message"):
        msg = Message.from_api(payload)

    assert len(msg.attachments) == 1
    only = msg.attachments[0]
    assert isinstance(only, ImageAttachment)
    assert only.file_key == "k1"
    assert only.width == 10 and only.height == 20

    assert any("STICKER" in record.getMessage() for record in caplog.records), (
        "未记录到跳过未知附件类型的 WARNING 日志"
    )


def test_message_parses_known_attachments() -> None:
    payload = _base_payload()
    payload["attachments"] = [
        {
            "attachmentType": "IMAGE",
            "fileKey": "k1",
            "url": "https://example.com/a.png",
        }
    ]

    msg = Message.from_api(payload)

    assert msg.message_id == "m-1"
    assert msg.sender_id == "u-1"
    assert msg.area == "a-1"
    assert msg.channel == "ch-1"
    assert len(msg.attachments) == 1
    assert isinstance(msg.attachments[0], ImageAttachment)


def test_message_ignores_non_mapping_attachments() -> None:
    payload = _base_payload()
    payload["attachments"] = [None, 123, "oops"]

    msg = Message.from_api(payload)

    assert msg.attachments == []

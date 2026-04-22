from __future__ import annotations

from pathlib import Path
import runpy

import pytest


EXAMPLE_FILES = [
    "send_message.py",
    "reply_bot.py",
    "upload_private_image.py",
]


@pytest.mark.parametrize("example_name", EXAMPLE_FILES)
def test_examples_can_be_loaded_without_running_main(example_name: str) -> None:
    example_path = Path(__file__).resolve().parents[1] / "examples" / example_name

    namespace = runpy.run_path(str(example_path), run_name="test_example_module")

    assert callable(namespace["main"])


def test_upload_private_image_example_uses_current_private_image_api() -> None:
    example_path = Path(__file__).resolve().parents[1] / "examples" / "upload_private_image.py"
    source = example_path.read_text(encoding="utf-8")

    assert "upload_and_send_private_image" not in source
    assert "sender.media.send_private_image" in source
    assert "result.channel" not in source
    assert "result.message_id" in source

from __future__ import annotations

import base64
import os
import re
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

from PIL import Image as PILImage


ImageInput = str | bytes | bytearray | memoryview | BinaryIO | os.PathLike[str]


_DATA_URL_RE = re.compile(r"^data:(?P<mime>[\w/+.-]+);base64,(?P<data>.+)$", re.DOTALL)


def read_image_bytes(file: ImageInput) -> tuple[bytes, str]:
    """
    返回: (payload, filename_hint)

    支持:
    - 本地路径 str / Path
    - base64 字符串
    - data:image/png;base64,...
    - bytes / bytearray / memoryview
    - file-like 对象
    """
    if isinstance(file, os.PathLike):
        path = Path(file)
        return path.read_bytes(), path.name

    if isinstance(file, str):
        text = file.strip()

        # 优先当作本地路径
        if os.path.isfile(text):
            path = Path(text)
            return path.read_bytes(), path.name

        # data url base64
        match = _DATA_URL_RE.match(text)
        if match:
            mime = match.group("mime")
            ext = _ext_from_mime(mime)
            return base64.b64decode(match.group("data")), f"image{ext}"

        # 普通 base64
        try:
            return base64.b64decode(text, validate=True), "image"
        except Exception as exc:
            raise ValueError("Image file string is neither an existing path nor valid base64") from exc

    if isinstance(file, bytes):
        return file, "image"

    if isinstance(file, bytearray):
        return bytes(file), "image"

    if isinstance(file, memoryview):
        return file.tobytes(), "image"

    if hasattr(file, "read"):
        if hasattr(file, "seek"):
            file.seek(0)

        data = file.read()

        if hasattr(file, "seek"):
            file.seek(0)

        if isinstance(data, str):
            data = data.encode()

        name = os.path.basename(str(getattr(file, "name", "image")))
        return bytes(data), name or "image"

    raise TypeError(f"Unsupported image input type: {type(file)!r}")


def get_image_info(file: ImageInput) -> tuple[int, int, int]:
    """
    读取图片宽高和文件大小。
    """
    payload, _ = read_image_bytes(file)
    return get_image_info_from_bytes(payload)


def guess_image_ext(file: ImageInput) -> str:
    """
    尽量推断图片扩展名，默认 .jpg。
    """
    payload, filename = read_image_bytes(file)
    return guess_image_ext_from_bytes(payload, filename)


def _ext_from_mime(mime: str) -> str:
    mapping = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
    }
    return mapping.get(mime.lower(), ".jpg")

def get_image_info_from_bytes(payload: bytes) -> tuple[int, int, int]:
    """
    从图片 bytes 读取宽、高、文件大小。
    """
    with PILImage.open(BytesIO(payload)) as img:
        width, height = img.size

    return int(width), int(height), len(payload)


def guess_image_ext_from_bytes(payload: bytes, filename: str = "") -> str:
    """
    从文件名或图片 bytes 推断扩展名，默认 .jpg。
    """
    ext = Path(filename).suffix
    if ext:
        return ext

    try:
        with PILImage.open(BytesIO(payload)) as img:
            fmt = (img.format or "").lower()
    except Exception:
        return ".jpg"

    mapping = {
        "jpeg": ".jpg",
        "jpg": ".jpg",
        "png": ".png",
        "gif": ".gif",
        "webp": ".webp",
        "bmp": ".bmp",
    }
    return mapping.get(fmt, ".jpg")
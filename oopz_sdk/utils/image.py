import os
from PIL import Image

def get_image_info(file_path: str) -> tuple[int, int, int]:
    """
    读取本地图片宽高和文件大小。
    """

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"Image file not found: {file_path}")

    with Image.open(file_path) as img:
        width, height = img.size

    file_size = os.path.getsize(file_path)
    return int(width), int(height), int(file_size)
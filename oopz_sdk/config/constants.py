"""Shared constants for the Oopz SDK."""

DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Content-Type": "application/json;charset=utf-8",
    "Origin": "https://web.oopz.cn",
    "Pragma": "no-cache",
    "Priority": "u=1, i",
    "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/140.0.0.0 Safari/537.36"
    ),
}

EVENT_SERVER_ID = 1
EVENT_PRIVATE_MESSAGE = 7
EVENT_DELETE_MESSAGE = 8
EVENT_CHAT_MESSAGE = 9
EVENT_PERSON_LOGIN = 27
EVENT_AUTH = 253
EVENT_HEARTBEAT = 254

ATTACHMENT_TYPE_IMAGE = "IMAGE"
ATTACHMENT_TYPE_AUDIO = "AUDIO"
ATTACHMENT_TYPE_FILE = "FILE"

STYLE_TAG_IMPORTANT = "IMPORTANT"
STYLE_TAGS = (STYLE_TAG_IMPORTANT,)

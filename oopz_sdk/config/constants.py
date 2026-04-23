"""Shared constants for the Oopz SDK."""

DEFAULT_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
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

EVENT_PRIVATE_MESSAGE_DELETE = 6 # 私聊消息撤回事件
EVENT_PRIVATE_MESSAGE = 7 # 私聊消息事件

EVENT_MESSAGE_DELETE = 8 # 频道消息撤回事件
EVENT_CHAT_MESSAGE = 9 # 频道消息事件

EVENT_CHANNEL_VOICE_BAN = 11 # 频道禁麦
EVENT_CHANNEL_MESSAGE_BAN = 12 # 频道禁言

EVENT_CHANNEL_DELETE = 13 # 删除频道
EVENT_CHANNEL_UPDATE = 18 # 频道设置改变

EVENT_USER_LEAVE_VOICE_CHANNEL = 19 # 用户退出语音频道事件
EVENT_USER_ENTER_VOICE_CHANNEL = 20 # 用户进入语音频道事件

EVENT_PUBLIC_CHANNEL_CREATE = 25 # 创建频道

EVENT_USER_UPDATE = 26 # 用户信息发生改变
EVENT_USER_LOGIN_STATE_CHANGED = 27 # 用户登录/登出事件

EVENT_AREA_UPDATE = 28 # 域信息发生改变

EVENT_ROLE_CHANGED = 52 # 身份组信息发生改变
EVENT_PRIVATE_MESSAGE_EDIT = 56 # 私聊消息编辑事件
EVENT_MESSAGE_EDIT = 57 # 群聊消息编辑事件

EVENT_AUTH = 253
EVENT_HEARTBEAT = 254 # 心跳

ATTACHMENT_TYPE_IMAGE = "IMAGE"
ATTACHMENT_TYPE_AUDIO = "AUDIO"
ATTACHMENT_TYPE_FILE = "FILE"

STYLE_TAG_IMPORTANT = "IMPORTANT"
STYLE_TAGS = (STYLE_TAG_IMPORTANT,)

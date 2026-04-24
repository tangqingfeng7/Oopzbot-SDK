from enum import Enum


class TextMuteInterval(Enum):
    S60 = (1, 1, "60秒")
    M5 = (5, 2, "5分钟")
    H1 = (60, 3, "1小时")
    D1 = (1440, 4, "1天")
    D3 = (4320, 5, "3天")
    D7 = (10080, 6, "7天")

    def __init__(self, minutes: int, interval_id: int, label: str):
        self.minutes = minutes
        self.interval_id = interval_id
        self.label = label

    @classmethod
    def pick(cls, minutes: int) -> "TextMuteInterval":
        for item in cls:
            if minutes <= item.minutes:
                return item
        return list(cls)[-1]


class VoiceMuteInterval(Enum):
    S60 = (1, 7, "60秒")
    M5 = (5, 8, "5分钟")
    H1 = (60, 9, "1小时")
    D1 = (1440, 10, "1天")
    D3 = (4320, 11, "3天")
    D7 = (10080, 12, "7天")

    def __init__(self, minutes: int, interval_id: int, label: str):
        self.minutes = minutes
        self.interval_id = interval_id
        self.label = label

    @classmethod
    def pick(cls, minutes: int) -> "VoiceMuteInterval":
        for item in cls:
            if minutes <= item.minutes:
                return item
        return list(cls)[-1]

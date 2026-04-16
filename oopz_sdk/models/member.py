from __future__ import annotations

from dataclasses import dataclass

from .base import BaseModel


@dataclass(slots=True)
class Member(BaseModel):
    uid: str = ""
    nickname: str = ""
    online: bool = False

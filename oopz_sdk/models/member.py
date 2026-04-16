from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseModel


@dataclass(slots=True)
class Member(BaseModel):
    uid: str = ""
    name: str = ""
    nickname: str = ""
    avatar: str = ""
    common_id: str = ""
    bio: str = ""
    online: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

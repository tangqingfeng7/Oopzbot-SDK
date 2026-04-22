from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from oopz_sdk.exceptions import OopzApiError

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

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "Member":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid member payload: expected dict", payload=data)
        name = str(data.get("name") or data.get("nickname") or "")
        return cls(
            uid=str(data.get("uid") or data.get("id") or ""),
            name=name,
            nickname=name,
            avatar=str(data.get("avatar") or data.get("avatarUrl") or ""),
            common_id=str(data.get("commonId") or ""),
            bio=str(data.get("bio") or data.get("signature") or ""),
            online=bool(data.get("online") in (1, True)),
            payload=dict(data),
        )

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from pydantic import Field, model_validator

from .attachment import Attachment
from .channel import ChannelGroup
from .base import BaseModel, SDKBaseModel
from .member import Member
from .message import Message
from oopz_sdk.transport.http import HttpResponse
from oopz_sdk.exceptions import OopzApiError





@dataclass(slots=True)
class PersonDetail(BaseModel):
    uid: str = ""
    name: str = ""
    avatar: str = ""
    common_id: str = ""
    bio: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "PersonDetail":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid person detail payload: expected dict", payload=data)
        return cls(
            uid=str(data.get("uid") or data.get("id") or ""),
            name=str(data.get("name") or data.get("nickname") or ""),
            avatar=str(data.get("avatar") or data.get("avatarUrl") or ""),
            common_id=str(data.get("commonId") or ""),
            bio=str(data.get("bio") or data.get("signature") or ""),
            payload=dict(data),
        )


@dataclass(slots=True)
class SelfDetail(BaseModel):
    uid: str = ""
    name: str = ""
    avatar: str = ""
    mobile: str = ""
    from_cache: bool = False
    payload: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "SelfDetail":
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid self detail payload: expected dict", payload=data)
        return cls(
            uid=str(data.get("uid") or data.get("id") or ""),
            name=str(data.get("name") or data.get("nickname") or ""),
            avatar=str(data.get("avatar") or data.get("avatarUrl") or ""),
            mobile=str(data.get("mobile") or ""),
            payload=dict(data),
        )




@dataclass(slots=True)
class DailySpeechResult(BaseModel):
    words: str
    author: str = ""
    source: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    


@dataclass(slots=True)
class AreaBlock(BaseModel):
    uid: str = ""
    name: str = ""
    reason: str = ""
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AreaBlocksResult(BaseModel):
    blocks: list[AreaBlock] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    


@dataclass(slots=True)
class MessageListResult(BaseModel):
    messages: list[Message] = field(default_factory=list)
    payload: dict[str, Any] = field(default_factory=dict)
    

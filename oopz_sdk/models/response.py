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
    


@dataclass(slots=True)
class SelfDetail(BaseModel):
    uid: str = ""
    name: str = ""
    avatar: str = ""
    mobile: str = ""
    from_cache: bool = False
    payload: dict[str, Any] = field(default_factory=dict)
    




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
    

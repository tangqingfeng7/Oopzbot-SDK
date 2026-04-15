from __future__ import annotations

from dataclasses import dataclass

from .base import BaseModel


@dataclass(slots=True)
class Channel(BaseModel):
    id: str = ""
    name: str = ""
    type: str = ""
    area: str = ""

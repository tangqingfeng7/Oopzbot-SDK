from __future__ import annotations

from dataclasses import dataclass

from .base import BaseModel


@dataclass(slots=True)
class Area(BaseModel):
    id: str = ""
    name: str = ""

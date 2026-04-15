from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .base import BaseModel


@dataclass(slots=True)
class ApiResponse(BaseModel):
    status: bool = False
    message: str = ""
    data: Any = field(default_factory=dict)
    code: str | int | None = None

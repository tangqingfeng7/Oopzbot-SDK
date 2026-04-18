from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import requests

from .base import BaseModel


@dataclass(slots=True)
class Area(BaseModel):
    id: str = ""
    name: str = ""
    code: str = ""
    description: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    response: requests.Response | None = field(default=None, repr=False)

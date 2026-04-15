from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(slots=True)
class BaseModel:
    def to_dict(self) -> dict:
        return asdict(self)

from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel as Bm, ConfigDict


class BaseModel(Bm):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


class OperationResult(BaseModel):
    ok: bool = True
    message: str = ""

    @classmethod
    def from_api(cls, data: Any) -> "OperationResult":
        if isinstance(data, bool):
            return cls.model_validate({"ok": data})
        if isinstance(data, Mapping):
            normalized = dict(data)
            normalized.setdefault(
                "ok",
                bool(normalized.get("status", True)),
            )
            normalized.setdefault(
                "message",
                str(normalized.get("message") or normalized.get("error") or ""),
            )
            return cls.model_validate(normalized)
        return cls.model_validate(
            {
                "ok": bool(data),
                "message": ""
            }
        )

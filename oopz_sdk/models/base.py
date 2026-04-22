from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from pydantic import BaseModel as Bm, ConfigDict, Field


# todo 我想慢慢把模型迁移到pydantic上面, 这样就能少很多判断逻辑了
# todo 慢慢迁移然后把SDKBaseModel命名冬奥BaseModel上, Bm只是暂时命名
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

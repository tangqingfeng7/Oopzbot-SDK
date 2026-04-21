from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from pydantic import BaseModel as Bm, ConfigDict, Field


# todo 我想慢慢把模型迁移到pydantic上面, 这样就能少很多判断逻辑了
# todo 慢慢迁移然后把SDKBaseModel命名冬奥BaseModel上, Bm只是暂时命名
class SDKBaseModel(Bm):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


@dataclass(slots=True)
class BaseModel:
    def to_dict(self) -> dict:
        return asdict(self)

    def __getitem__(self, key: str):
        return self.to_dict()[key]

    def get(self, key: str, default=None):
        return self.to_dict().get(key, default)

    def items(self):
        return self.to_dict().items()

    def keys(self):
        return self.to_dict().keys()

    def values(self):
        return self.to_dict().values()

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key in self.to_dict()


class OperationResult(SDKBaseModel):
    ok: bool = True
    message: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)

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
            normalized.setdefault("payload", dict(data))
            return cls.model_validate(normalized)
        return cls.model_validate(
            {
                "ok": bool(data),
                "message": "",
                "payload": {"raw": data} if data is not None else {},
            }
        )

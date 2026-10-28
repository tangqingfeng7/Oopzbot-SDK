from __future__ import annotations

from typing import Any, Iterator, Mapping

from pydantic import AliasChoices, BaseModel as Bm, ConfigDict, model_validator
from pydantic.fields import FieldInfo

from oopz_sdk.utils.payload import coerce_bool

_OPTIONAL_INPUT_KEYS: dict[type, frozenset[str]] = {}


def _input_keys(name: str, field: FieldInfo) -> Iterator[str]:
    """字段在入参里可能出现的所有键名：字段名本身加各种别名。"""
    yield name
    if isinstance(field.alias, str):
        yield field.alias
    alias = field.validation_alias
    if isinstance(alias, str):
        yield alias
    elif isinstance(alias, AliasChoices):
        for choice in alias.choices:
            if isinstance(choice, str):
                yield choice


def _optional_input_keys(cls: type[Bm]) -> frozenset[str]:
    cached = _OPTIONAL_INPUT_KEYS.get(cls)
    if cached is None:
        keys: set[str] = set()
        for name, field in cls.model_fields.items():
            if not field.is_required():
                keys.update(_input_keys(name, field))
        cached = frozenset(keys)
        _OPTIONAL_INPUT_KEYS[cls] = cached
    return cached


class BaseModel(Bm):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )

    @model_validator(mode="before")
    @classmethod
    def _ignore_null_for_defaulted_fields(cls, data: Any) -> Any:
        """把可选字段上的显式 null 当成没传，让字段用自己的默认值。

        default_factory 只在键缺失时生效，接口对空集合返回 "channels": null
        会直接校验失败。子类的 before 校验器先于本方法执行，看到的仍是原始数据。
        """
        if not isinstance(data, Mapping):
            return data

        optional_keys = _optional_input_keys(cls)
        nulls = [key for key, value in data.items() if value is None and key in optional_keys]
        if not nulls:
            return data

        normalized = dict(data)
        for key in nulls:
            del normalized[key]
        return normalized


class OperationResult(BaseModel):
    ok: bool = True
    message: str = ""

    @classmethod
    def from_api(cls, data: Any) -> "OperationResult":
        if data is None:
            return cls.model_validate({"ok": True, "message": ""})
        if isinstance(data, bool):
            return cls.model_validate({"ok": data})
        if isinstance(data, Mapping):
            normalized = dict(data)
            # status 可能是 bool、整数或字符串（包括 "false"/"0"），严格转换
            # 避免 Python 真值把 "false" 当成功。
            # - key 不存在：get 返回 True → 按成功处理（与历史 `bool(True)=True` 一致）
            # - key 存在且为 None / 未知字符串：保守视作失败（default=False），
            #   保留原 `bool(None)=False` 语义，同时与 transport/http.py 判定同步
            normalized.setdefault(
                "ok",
                coerce_bool(normalized.get("status", True), default=False),
            )
            normalized.setdefault(
                "message",
                str(normalized.get("message") or normalized.get("error") or ""),
            )
            return cls.model_validate(normalized)
        return cls.model_validate(
            {
                "ok": coerce_bool(data, default=False),
                "message": ""
            }
        )

from __future__ import annotations

from typing import Any, Mapping

from pydantic import model_validator

from oopz_sdk.exceptions import OopzApiError

from .base import BaseModel


class DailySpeech(BaseModel):
    words: str = ""
    author: str = ""

    @model_validator(mode="before")
    @classmethod
    def validate_and_normalize(cls, data: Any) -> Any:
        if not isinstance(data, Mapping):
            raise OopzApiError("invalid daily speech payload: expected object", payload=data)
        return {
            "words": str(data.get("words") or ""),
            "author": str(data.get("author") or ""),
        }

    @classmethod
    def from_api(cls, data: Mapping[str, Any]) -> "DailySpeech":
        return cls.model_validate(data)


from __future__ import annotations

from oopz_sdk.models import OperationResult


def test_operation_result_treats_none_as_success() -> None:
    result = OperationResult.from_api(None)

    assert result.ok is True
    assert result.message == ""

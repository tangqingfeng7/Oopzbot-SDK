from __future__ import annotations

import pytest

from .factories import make_config


@pytest.fixture
def oopz_config():
    return make_config()

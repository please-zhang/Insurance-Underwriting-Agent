from __future__ import annotations

from pathlib import Path

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if "integration" in (config.option.markexpr or ""):
        return

    skip_integration = pytest.mark.skip(reason="integration tests run only with `pytest -m integration`")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def pytest_runtest_setup(item: pytest.Item) -> None:
    if "integration" not in item.keywords:
        return

    config_path = Path("config/providers.yaml")
    if not config_path.exists():
        pytest.skip("integration tests require config/providers.yaml")

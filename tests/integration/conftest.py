"""Skip all integration tests when the data/ folder is not present (e.g. in CI)."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def require_data_folder() -> None:
    if not Path("data").is_dir():
        pytest.skip("data/ folder not present — skipping integration tests")

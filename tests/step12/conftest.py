"""Step 1–2 contracts explicitly exercise the isolated legacy file pipeline."""
from __future__ import annotations
import pytest

@pytest.fixture(autouse=True)
def isolated_store(file_storage_mode: None) -> None:
    """Reuse root isolation without changing process configuration during collection."""

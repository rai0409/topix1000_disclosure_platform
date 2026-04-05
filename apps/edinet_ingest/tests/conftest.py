from __future__ import annotations

from pathlib import Path

import pytest

FIXTURE_ZIP_NAME = "Xbrl_Search_20250709_185613.zip"


@pytest.fixture(scope="session")
def sample_zip_path() -> Path:
    fixture_dir = Path(__file__).resolve().parent / "fixtures"
    zip_path = fixture_dir / FIXTURE_ZIP_NAME
    if not zip_path.exists():
        raise FileNotFoundError(
            "Sample fixture ZIP is missing. Place it at "
            f"{zip_path}. "
            "See README for copy instructions."
        )
    return zip_path

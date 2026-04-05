from __future__ import annotations

import logging
from typing import Final

from common.settings import get_settings

LOG_FORMAT: Final[str] = (
    "%(asctime)s %(levelname)s [%(name)s] %(message)s"
)


def configure_logging(level: str | None = None) -> None:
    settings = get_settings()
    resolved_level = (level or settings.log_level).upper()
    numeric_level = getattr(logging, resolved_level, logging.INFO)

    logging.basicConfig(
        level=numeric_level,
        format=LOG_FORMAT,
        force=True,
    )

    logging.captureWarnings(True)
from __future__ import annotations

import re
import unicodedata

_MULTI_SPACE_PATTERN = re.compile(r"\s+")


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    return _MULTI_SPACE_PATTERN.sub(" ", normalized)


def normalize_company_name(value: str) -> str:
    normalized = normalize_text(value)
    return normalized.lower()

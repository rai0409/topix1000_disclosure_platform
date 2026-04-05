from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from common.settings import get_settings

_DOC_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass(frozen=True, slots=True)
class SavedRawFile:
    path: Path
    sha256: str
    bytes_size: int


class RawStorageService:
    def __init__(self, *, raw_root: Path | None = None) -> None:
        self._raw_root = raw_root or get_settings().raw_storage_root

    @property
    def raw_root(self) -> Path:
        return self._raw_root

    def doc_dir(self, *, target_date: date, doc_id: str) -> Path:
        safe_doc_id = _sanitize_doc_id(doc_id)
        return (
            self._raw_root
            / "edinet"
            / f"{target_date.year:04d}"
            / f"{target_date.month:02d}"
            / f"{target_date.day:02d}"
            / safe_doc_id
        )

    def save_list_response_json(
        self,
        *,
        target_date: date,
        doc_id: str,
        payload: dict[str, Any],
    ) -> SavedRawFile:
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        return self.save_binary(
            target_date=target_date,
            doc_id=doc_id,
            filename="list_response.json",
            content=body,
        )

    def save_binary(
        self,
        *,
        target_date: date,
        doc_id: str,
        filename: str,
        content: bytes,
    ) -> SavedRawFile:
        target_dir = self.doc_dir(target_date=target_date, doc_id=doc_id)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_path = target_dir / filename
        target_path.write_bytes(content)
        return SavedRawFile(
            path=target_path,
            sha256=hashlib.sha256(content).hexdigest(),
            bytes_size=len(content),
        )


def _sanitize_doc_id(doc_id: str) -> str:
    candidate = doc_id.strip()
    if not candidate or not _DOC_ID_PATTERN.fullmatch(candidate):
        raise ValueError(f"invalid doc_id for path: {doc_id}")
    return candidate

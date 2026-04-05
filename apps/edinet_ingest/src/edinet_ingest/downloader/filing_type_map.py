from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from common.db.models import FilingTypeMap
from sqlalchemy import select
from sqlalchemy.orm import Session

DEFAULT_MAPPING_FILE = Path(__file__).with_name("filing_type_map_edinet.json")


@dataclass(frozen=True, slots=True)
class FilingTypeMapEntry:
    filing_type_key: str
    form_code: str | None
    doc_type_code: str | None
    filing_type_raw: str | None


class FilingTypeResolver:
    def __init__(self, entries: list[FilingTypeMapEntry]) -> None:
        self._full_key: dict[tuple[str | None, str | None], str] = {}
        self._form_only: dict[str, str] = {}
        self._doc_type_only: dict[str, str] = {}

        for entry in entries:
            form_code = _normalize_code(entry.form_code)
            doc_type_code = _normalize_code(entry.doc_type_code)
            self._full_key[(form_code, doc_type_code)] = entry.filing_type_key
            if form_code:
                self._form_only[form_code] = entry.filing_type_key
            if doc_type_code:
                self._doc_type_only[doc_type_code] = entry.filing_type_key

    def resolve(self, *, form_code: str | None, doc_type_code: str | None) -> str | None:
        normalized_form = _normalize_code(form_code)
        normalized_doc = _normalize_code(doc_type_code)

        full = self._full_key.get((normalized_form, normalized_doc))
        if full:
            return full
        if normalized_form and normalized_form in self._form_only:
            return self._form_only[normalized_form]
        if normalized_doc and normalized_doc in self._doc_type_only:
            return self._doc_type_only[normalized_doc]
        return None


def load_mapping_entries(mapping_file: Path | None = None) -> list[FilingTypeMapEntry]:
    path = mapping_file or DEFAULT_MAPPING_FILE
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"mapping file must be a list: {path}")

    entries: list[FilingTypeMapEntry] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        filing_type_key = str(row.get("filing_type_key") or "").strip()
        if not filing_type_key:
            continue
        entries.append(
            FilingTypeMapEntry(
                filing_type_key=filing_type_key,
                form_code=_normalize_code(row.get("form_code")),
                doc_type_code=_normalize_code(row.get("doc_type_code")),
                filing_type_raw=_normalize_optional_text(row.get("filing_type_raw")),
            )
        )
    return entries


def seed_filing_type_map(
    session: Session,
    *,
    source_type: str = "edinet",
    mapping_file: Path | None = None,
) -> int:
    entries = load_mapping_entries(mapping_file)
    inserted = 0
    now_utc = datetime.now(tz=UTC)

    for entry in entries:
        exists = session.scalar(
            select(FilingTypeMap).where(
                FilingTypeMap.source_type == source_type,
                FilingTypeMap.filing_type_key == entry.filing_type_key,
                FilingTypeMap.form_code == entry.form_code,
                FilingTypeMap.doc_type_code == entry.doc_type_code,
            )
        )
        if exists is not None:
            continue

        session.add(
            FilingTypeMap(
                source_type=source_type,
                filing_type_key=entry.filing_type_key,
                form_code=entry.form_code,
                doc_type_code=entry.doc_type_code,
                filing_type_raw=entry.filing_type_raw,
                is_active=True,
                created_at=now_utc,
            )
        )
        inserted += 1

    if inserted > 0:
        session.flush()

    return inserted


def load_active_resolver(session: Session, *, source_type: str = "edinet") -> FilingTypeResolver:
    rows = session.scalars(
        select(FilingTypeMap).where(
            FilingTypeMap.source_type == source_type,
            FilingTypeMap.is_active.is_(True),
        )
    ).all()
    entries = [
        FilingTypeMapEntry(
            filing_type_key=row.filing_type_key,
            form_code=row.form_code,
            doc_type_code=row.doc_type_code,
            filing_type_raw=row.filing_type_raw,
        )
        for row in rows
    ]
    return FilingTypeResolver(entries)


def _normalize_code(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

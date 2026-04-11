from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

from common.db.session import get_session_factory
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

OUTPUT_COLUMNS = ["doc_id", "edinet_code"]

# Deterministic duplicate handling:
# If a doc_id has conflicting non-empty edinet_code values, keep MIN(edinet_code).
DOC_EDINET_MAP_SQL = text(
    """
    SELECT
      f.doc_id AS doc_id,
      MIN(f.edinet_code) AS edinet_code
    FROM edinet_facts_raw_csv AS f
    WHERE f.source_csv_path LIKE :date_path_pattern
      AND f.edinet_code IS NOT NULL
      AND BTRIM(f.edinet_code) <> ''
    GROUP BY f.doc_id
    ORDER BY f.doc_id
    """
)


@dataclass(frozen=True, slots=True)
class BuildDocEdinetMapSummary:
    target_date: str
    output_path: str
    row_count: int
    duplicate_doc_id_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_doc_edinet_map_for_date(
    target_date: date,
    output_path: Path,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> BuildDocEdinetMapSummary:
    session_factory = session_factory or get_session_factory()
    resolved_output_path = output_path.expanduser().resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _query_rows(target_date=target_date, session_factory=session_factory)
    rows.sort(key=lambda row: row["doc_id"])

    with resolved_output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    doc_ids = [row["doc_id"] for row in rows]
    duplicate_doc_id_count = len(doc_ids) - len(set(doc_ids))

    return BuildDocEdinetMapSummary(
        target_date=target_date.isoformat(),
        output_path=str(resolved_output_path),
        row_count=len(rows),
        duplicate_doc_id_count=duplicate_doc_id_count,
    )


def _query_rows(
    *,
    target_date: date,
    session_factory: sessionmaker[Session],
) -> list[dict[str, str]]:
    date_path_pattern = f"%/{target_date.strftime('%Y/%m/%d')}/%"
    with session_factory() as session:
        result = session.execute(DOC_EDINET_MAP_SQL, {"date_path_pattern": date_path_pattern})
        mapped_rows = result.mappings().all()
    return [{"doc_id": row["doc_id"], "edinet_code": row["edinet_code"]} for row in mapped_rows]

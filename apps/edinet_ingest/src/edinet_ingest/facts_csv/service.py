from __future__ import annotations

import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import pandas as pd
from common.db.models import EdinetFactRawCsv, EdinetListResponse
from common.db.session import get_session_factory
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, sessionmaker

from edinet_ingest.downloader.storage import RawStorageService

MAIN_CSV_PREFIX_ASR = "jpcrp030000-asr-001_"
MAIN_CSV_PREFIX_SSR = "jpcrp050000-ssr-001_"
MAIN_CSV_PREFIX_GENERIC = "jpcrp"
AUDIT_CSV_PREFIX = "jpaud"

RAW_TO_CANONICAL_COLUMN_MAP = {
    "要素ID": "element_id",
    "項目名": "item_name_ja",
    "コンテキストID": "context_id",
    "相対年度": "relative_year_label",
    "連結・個別": "consolidation_type",
    "期間・時点": "period_type",
    "ユニットID": "unit_id",
    "単位": "unit_label",
    "値": "raw_value",
}

CURRENT_YEAR_LABELS = {"当期", "当期末", "当連結会計年度", "当事業年度"}
PRIOR_YEAR_LABELS = {"前期", "前期末", "前連結会計年度", "前事業年度"}

CANONICAL_FACT_COLUMNS = [
    "doc_id",
    "edinet_code",
    "source_csv_path",
    "element_id",
    "item_name_ja",
    "context_id",
    "relative_year_label",
    "consolidation_type",
    "period_type",
    "unit_id",
    "unit_label",
    "raw_value",
    "value_text",
    "value_numeric",
    "is_numeric",
    "is_current_year",
    "is_prior_year",
    "is_consolidated",
    "created_at",
]


class MainFactsCsvNotFoundError(FileNotFoundError):
    def __init__(self, message: str, *, reason: str) -> None:
        super().__init__(message)
        self.reason = reason


class MainFactsCsvInvalidZipError(ValueError):
    def __init__(self, message: str, *, reason: str = "invalid_csv_zip") -> None:
        super().__init__(message)
        self.reason = reason


class MainFactsCsvReadError(ValueError):
    def __init__(self, message: str, *, reason: str = "csv_read_error") -> None:
        super().__init__(message)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class NormalizeFactsSummary:
    target_date: str
    total_candidates: int
    normalized_count: int
    skipped_count: int
    failed_count: int
    skipped_docs: list[dict[str, str]] = field(default_factory=list)
    failed_docs: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def read_main_text_csv_from_zip(csv_zip_path: Path) -> tuple[pd.DataFrame, str]:
    resolved_csv_zip_path = Path(csv_zip_path).expanduser().resolve()
    if not resolved_csv_zip_path.exists():
        raise MainFactsCsvNotFoundError(
            f"csv.zip not found: {resolved_csv_zip_path}",
            reason="missing_csv_zip",
        )

    try:
        zip_file = zipfile.ZipFile(resolved_csv_zip_path, mode="r")
    except zipfile.BadZipFile as exc:
        raise MainFactsCsvInvalidZipError(
            f"invalid csv.zip (not a zip archive): {resolved_csv_zip_path}"
        ) from exc

    with zip_file:
        member_name = _pick_target_csv_name(zip_file.namelist())
        if member_name is None:
            raise MainFactsCsvNotFoundError(
                f"missing main csv (jpcrp*.csv): {resolved_csv_zip_path}",
                reason="missing_main_csv",
            )

        try:
            with zip_file.open(member_name, mode="r") as csv_file:
                frame = pd.read_csv(csv_file, encoding="utf-16", sep="\t")
        except Exception as exc:  # pragma: no cover - pandas internals
            raise MainFactsCsvReadError(
                f"failed to read target csv from {resolved_csv_zip_path}: {exc}"
            ) from exc

    return frame, member_name


def normalize_main_text_csv(
    raw_df: pd.DataFrame,
    *,
    doc_id: str,
    edinet_code: str | None,
    source_csv_path: str,
    created_at: datetime | None = None,
) -> pd.DataFrame:
    missing_columns = sorted(set(RAW_TO_CANONICAL_COLUMN_MAP).difference(raw_df.columns))
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise ValueError(f"required columns missing: {missing}")

    canonical_df = raw_df[list(RAW_TO_CANONICAL_COLUMN_MAP)].rename(
        columns=RAW_TO_CANONICAL_COLUMN_MAP
    )
    canonical_df = canonical_df.copy()

    for column_name in RAW_TO_CANONICAL_COLUMN_MAP.values():
        canonical_df[column_name] = canonical_df[column_name].fillna("").astype(str)

    canonical_df["value_text"] = canonical_df["raw_value"].astype(str)
    value_numeric_source = (
        canonical_df["value_text"]
        .str.replace(",", "", regex=False)
        .str.replace("△", "-", regex=False)
        .str.strip()
    )
    canonical_df["value_numeric"] = pd.to_numeric(value_numeric_source, errors="coerce")
    canonical_df["is_numeric"] = canonical_df["value_numeric"].notna()

    relative_year_values = canonical_df["relative_year_label"].str.strip()
    consolidation_values = canonical_df["consolidation_type"].str.strip()

    canonical_df["is_current_year"] = relative_year_values.isin(CURRENT_YEAR_LABELS)
    canonical_df["is_prior_year"] = relative_year_values.isin(PRIOR_YEAR_LABELS)
    canonical_df["is_consolidated"] = consolidation_values.eq("連結")

    canonical_df["doc_id"] = doc_id
    canonical_df["edinet_code"] = edinet_code
    canonical_df["source_csv_path"] = source_csv_path
    canonical_df["created_at"] = created_at or datetime.now(tz=UTC)
    return canonical_df[CANONICAL_FACT_COLUMNS]


def normalize_facts_for_date(
    target_date: date,
    *,
    session_factory: sessionmaker[Session] | None = None,
    storage: RawStorageService | None = None,
) -> NormalizeFactsSummary:
    session_factory = session_factory or get_session_factory()
    storage = storage or RawStorageService()

    with session_factory() as session:
        candidates = session.scalars(
            select(EdinetListResponse).where(EdinetListResponse.target_date == target_date)
        ).all()

    normalized_count = 0
    skipped_count = 0
    failed_count = 0
    skipped_docs: list[dict[str, str]] = []
    failed_docs: list[dict[str, str]] = []

    for candidate in candidates:
        try:
            _normalize_facts_for_doc(
                session_factory=session_factory,
                storage=storage,
                target_date=target_date,
                doc_id=candidate.doc_id,
                edinet_code=candidate.edinet_code,
            )
            normalized_count += 1
        except MainFactsCsvNotFoundError as exc:
            skipped_count += 1
            skipped_docs.append(
                {
                    "doc_id": candidate.doc_id,
                    "reason": exc.reason,
                    "message": str(exc)[:512],
                }
            )
        except (MainFactsCsvInvalidZipError, MainFactsCsvReadError) as exc:
            failed_count += 1
            failed_docs.append(
                {
                    "doc_id": candidate.doc_id,
                    "reason": exc.reason,
                    "message": str(exc)[:512],
                }
            )
        except Exception as exc:
            failed_count += 1
            failed_docs.append(
                {
                    "doc_id": candidate.doc_id,
                    "reason": "normalize_error",
                    "message": str(exc)[:512],
                }
            )

    return NormalizeFactsSummary(
        target_date=target_date.isoformat(),
        total_candidates=len(candidates),
        normalized_count=normalized_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        skipped_docs=skipped_docs,
        failed_docs=failed_docs,
    )


def normalize_facts_for_doc(
    *,
    target_date: date,
    doc_id: str,
    edinet_code: str | None,
    session_factory: sessionmaker[Session] | None = None,
    storage: RawStorageService | None = None,
) -> int:
    session_factory = session_factory or get_session_factory()
    storage = storage or RawStorageService()
    return _normalize_facts_for_doc(
        session_factory=session_factory,
        storage=storage,
        target_date=target_date,
        doc_id=doc_id,
        edinet_code=edinet_code,
    )


def _normalize_facts_for_doc(
    *,
    session_factory: sessionmaker[Session],
    storage: RawStorageService,
    target_date: date,
    doc_id: str,
    edinet_code: str | None,
) -> int:
    csv_zip_path = storage.doc_dir(target_date=target_date, doc_id=doc_id) / "csv.zip"
    raw_df, csv_member_name = read_main_text_csv_from_zip(csv_zip_path)
    source_csv_path = f"{csv_zip_path.resolve()}!{csv_member_name}"
    normalized_df = normalize_main_text_csv(
        raw_df,
        doc_id=doc_id,
        edinet_code=edinet_code,
        source_csv_path=source_csv_path,
    )
    records = _to_fact_records(normalized_df)

    with session_factory() as session:
        with session.begin():
            session.execute(delete(EdinetFactRawCsv).where(EdinetFactRawCsv.doc_id == doc_id))
            if records:
                session.execute(insert(EdinetFactRawCsv), records)
    return len(records)


def _pick_target_csv_name(member_names: list[str]) -> str | None:
    candidates: list[tuple[int, str, str]] = []
    for member_name in member_names:
        filename = PurePosixPath(member_name).name
        if not filename.endswith(".csv"):
            continue
        if filename.startswith(AUDIT_CSV_PREFIX):
            continue
        if not filename.startswith(MAIN_CSV_PREFIX_GENERIC):
            continue

        priority = 2
        if filename.startswith(MAIN_CSV_PREFIX_ASR):
            priority = 0
        elif filename.startswith(MAIN_CSV_PREFIX_SSR):
            priority = 1
        candidates.append((priority, filename, member_name))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1]))
    return candidates[0][2]


def _to_fact_records(normalized_df: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in normalized_df.to_dict(orient="records"):
        value_numeric = row["value_numeric"]
        if pd.isna(value_numeric):
            row["value_numeric"] = None
        row["is_numeric"] = bool(row["is_numeric"])
        row["is_current_year"] = bool(row["is_current_year"])
        row["is_prior_year"] = bool(row["is_prior_year"])
        row["is_consolidated"] = bool(row["is_consolidated"])
        records.append(row)
    return records

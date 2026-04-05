from __future__ import annotations

import zipfile
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
import pytest
from common.db.base import Base
from common.db.models import EdinetFactRawCsv, EdinetListResponse
from edinet_ingest.downloader.storage import RawStorageService
from edinet_ingest.facts_csv.service import (
    MainFactsCsvInvalidZipError,
    MainFactsCsvNotFoundError,
    normalize_facts_for_date,
    normalize_main_text_csv,
    read_main_text_csv_from_zip,
)
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker

JP_COLUMNS = [
    "要素ID",
    "項目名",
    "コンテキストID",
    "相対年度",
    "連結・個別",
    "期間・時点",
    "ユニットID",
    "単位",
    "値",
]

CANONICAL_COLUMNS = [
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


def test_read_main_text_csv_from_zip_reads_utf16_tsv(tmp_path) -> None:
    csv_zip_path = tmp_path / "csv.zip"
    _write_csv_zip(
        csv_zip_path,
        member_name="jpcrp030000-asr-001_sample.csv",
        rows=[
            ["jppfs_cor:NetSales", "売上高", "CurrentYear", "当期", "連結", "期間", "JPY", "円", "1,000"],
        ],
    )

    frame, member_name = read_main_text_csv_from_zip(csv_zip_path)

    assert member_name == "jpcrp030000-asr-001_sample.csv"
    assert frame.shape == (1, 9)
    assert frame.columns.tolist() == JP_COLUMNS


def test_read_main_text_csv_from_zip_reads_ssr_when_asr_is_absent(tmp_path) -> None:
    csv_zip_path = tmp_path / "csv.zip"
    _write_csv_members_zip(
        csv_zip_path,
        members=[
            (
                "XBRL_TO_CSV/jpaud-sar-cn-001_sample.csv",
                _build_utf16_tsv(
                    [["a", "b", "c", "当期", "連結", "期間", "JPY", "円", "1"]],
                ),
            ),
            (
                "XBRL_TO_CSV/jpcrp050000-ssr-001_sample.csv",
                _build_utf16_tsv(
                    [["elem_ssr", "半期項目", "ctx_ssr", "当期", "連結", "期間", "JPY", "円", "2,000"]],
                ),
            ),
        ],
    )

    frame, member_name = read_main_text_csv_from_zip(csv_zip_path)

    assert member_name == "XBRL_TO_CSV/jpcrp050000-ssr-001_sample.csv"
    assert frame.loc[0, "要素ID"] == "elem_ssr"


def test_read_main_text_csv_from_zip_skips_when_only_jpaud_csv_exists(tmp_path) -> None:
    csv_zip_path = tmp_path / "csv.zip"
    _write_csv_members_zip(
        csv_zip_path,
        members=[
            (
                "XBRL_TO_CSV/jpaud-sar-cc-001_sample.csv",
                _build_utf16_tsv(
                    [["a", "b", "c", "当期", "連結", "期間", "JPY", "円", "1"]],
                ),
            ),
            (
                "XBRL_TO_CSV/jpaud-sar-cn-001_sample.csv",
                _build_utf16_tsv(
                    [["d", "e", "f", "当期", "連結", "期間", "JPY", "円", "2"]],
                ),
            ),
        ],
    )

    with pytest.raises(MainFactsCsvNotFoundError) as exc_info:
        read_main_text_csv_from_zip(csv_zip_path)

    assert exc_info.value.reason == "missing_main_csv"


def test_read_main_text_csv_from_zip_raises_invalid_zip_error_for_json_body(tmp_path) -> None:
    csv_zip_path = tmp_path / "csv.zip"
    csv_zip_path.write_text('{"status":"404"}', encoding="utf-8")

    with pytest.raises(MainFactsCsvInvalidZipError) as exc_info:
        read_main_text_csv_from_zip(csv_zip_path)

    assert exc_info.value.reason == "invalid_csv_zip"


def test_normalize_main_text_csv_renames_columns() -> None:
    raw_df = pd.DataFrame(
        [
            {
                "要素ID": "jppfs_cor:NetSales",
                "項目名": "売上高",
                "コンテキストID": "CurrentYear",
                "相対年度": "当期",
                "連結・個別": "連結",
                "期間・時点": "期間",
                "ユニットID": "JPY",
                "単位": "円",
                "値": "1000",
            }
        ]
    )

    normalized = normalize_main_text_csv(
        raw_df,
        doc_id="S100XUX3",
        edinet_code="E00000",
        source_csv_path="/tmp/csv.zip!jpcrp030000-asr-001_sample.csv",
        created_at=datetime(2026, 3, 30, tzinfo=UTC),
    )

    assert normalized.columns.tolist() == CANONICAL_COLUMNS
    assert normalized.loc[0, "element_id"] == "jppfs_cor:NetSales"
    assert normalized.loc[0, "item_name_ja"] == "売上高"


def test_normalize_main_text_csv_converts_triangle_minus_to_numeric() -> None:
    raw_df = pd.DataFrame(
        [
            {
                "要素ID": "elem1",
                "項目名": "項目1",
                "コンテキストID": "ctx1",
                "相対年度": "当期",
                "連結・個別": "連結",
                "期間・時点": "期間",
                "ユニットID": "JPY",
                "単位": "円",
                "値": "△123",
            }
        ]
    )

    normalized = normalize_main_text_csv(
        raw_df,
        doc_id="S100XUX3",
        edinet_code="E00000",
        source_csv_path="/tmp/csv.zip!jpcrp030000-asr-001_sample.csv",
    )

    assert normalized.loc[0, "value_numeric"] == -123
    assert bool(normalized.loc[0, "is_numeric"]) is True


def test_normalize_main_text_csv_sets_current_prior_and_consolidated_flags() -> None:
    raw_df = pd.DataFrame(
        [
            {
                "要素ID": "elem_current",
                "項目名": "項目current",
                "コンテキストID": "ctx1",
                "相対年度": "当期",
                "連結・個別": "連結",
                "期間・時点": "期間",
                "ユニットID": "JPY",
                "単位": "円",
                "値": "1",
            },
            {
                "要素ID": "elem_prior",
                "項目名": "項目prior",
                "コンテキストID": "ctx2",
                "相対年度": "前事業年度",
                "連結・個別": "個別",
                "期間・時点": "期間",
                "ユニットID": "JPY",
                "単位": "円",
                "値": "2",
            },
        ]
    )

    normalized = normalize_main_text_csv(
        raw_df,
        doc_id="S100XUX3",
        edinet_code="E00000",
        source_csv_path="/tmp/csv.zip!jpcrp030000-asr-001_sample.csv",
    )

    assert bool(normalized.loc[0, "is_current_year"]) is True
    assert bool(normalized.loc[0, "is_prior_year"]) is False
    assert bool(normalized.loc[0, "is_consolidated"]) is True

    assert bool(normalized.loc[1, "is_current_year"]) is False
    assert bool(normalized.loc[1, "is_prior_year"]) is True
    assert bool(normalized.loc[1, "is_consolidated"]) is False


def test_normalize_facts_for_date_is_idempotent_per_doc(tmp_path) -> None:
    session_factory = _create_session_factory(tmp_path)
    raw_root = tmp_path / "raw"
    storage = RawStorageService(raw_root=raw_root)
    target_date = date(2026, 3, 27)
    doc_id = "S100XUX3"

    with session_factory() as session:
        session.add(
            EdinetListResponse(
                target_date=target_date,
                doc_id=doc_id,
                edinet_code="E00000",
                form_code="030000",
                doc_type_code="120",
                filing_type_key="securities_report",
                response_path="/tmp/list_response.json",
                response_sha256=None,
                requested_at=datetime(2026, 3, 27, tzinfo=UTC),
            )
        )
        session.commit()

    csv_zip_path = storage.doc_dir(target_date=target_date, doc_id=doc_id) / "csv.zip"
    _write_csv_zip(
        csv_zip_path,
        member_name="jpcrp030000-asr-001_sample.csv",
        rows=[
            ["elem1", "項目1", "ctx1", "当期", "連結", "期間", "JPY", "円", "1,000"],
            ["elem2", "項目2", "ctx2", "前期", "個別", "期間", "JPY", "円", "△200"],
        ],
    )

    first = normalize_facts_for_date(target_date, session_factory=session_factory, storage=storage)
    assert first.total_candidates == 1
    assert first.normalized_count == 1
    assert first.skipped_count == 0
    assert first.failed_count == 0

    with session_factory() as session:
        first_count = session.scalar(
            select(func.count()).select_from(EdinetFactRawCsv).where(EdinetFactRawCsv.doc_id == doc_id)
        )
        assert first_count == 2
        assert session.scalar(
            select(func.count())
            .select_from(EdinetFactRawCsv)
            .where(EdinetFactRawCsv.doc_id == doc_id, EdinetFactRawCsv.is_numeric.is_(True))
        ) == 2

    second = normalize_facts_for_date(target_date, session_factory=session_factory, storage=storage)
    assert second.total_candidates == 1
    assert second.normalized_count == 1
    assert second.skipped_count == 0
    assert second.failed_count == 0

    with session_factory() as session:
        second_count = session.scalar(
            select(func.count()).select_from(EdinetFactRawCsv).where(EdinetFactRawCsv.doc_id == doc_id)
        )
        assert second_count == first_count


def test_normalize_facts_for_date_records_invalid_csv_zip_as_failed(tmp_path) -> None:
    session_factory = _create_session_factory(tmp_path)
    raw_root = tmp_path / "raw"
    storage = RawStorageService(raw_root=raw_root)
    target_date = date(2026, 3, 27)
    doc_id = "S100XQOX"

    with session_factory() as session:
        session.add(
            EdinetListResponse(
                target_date=target_date,
                doc_id=doc_id,
                edinet_code="E99999",
                form_code="030000",
                doc_type_code="120",
                filing_type_key="securities_report",
                response_path="/tmp/list_response.json",
                response_sha256=None,
                requested_at=datetime(2026, 3, 27, tzinfo=UTC),
            )
        )
        session.commit()

    csv_zip_path = storage.doc_dir(target_date=target_date, doc_id=doc_id) / "csv.zip"
    csv_zip_path.parent.mkdir(parents=True, exist_ok=True)
    csv_zip_path.write_text('{"status":"404"}', encoding="utf-8")

    summary = normalize_facts_for_date(target_date, session_factory=session_factory, storage=storage)

    assert summary.total_candidates == 1
    assert summary.normalized_count == 0
    assert summary.skipped_count == 0
    assert summary.failed_count == 1
    assert summary.failed_docs[0]["doc_id"] == doc_id
    assert summary.failed_docs[0]["reason"] == "invalid_csv_zip"


def _create_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'facts_csv.sqlite3'}"
    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _write_csv_zip(csv_zip_path: Path, *, member_name: str, rows: list[list[str]]) -> None:
    csv_zip_path.parent.mkdir(parents=True, exist_ok=True)
    body = _build_utf16_tsv(rows)
    with zipfile.ZipFile(csv_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(member_name, body)


def _write_csv_members_zip(csv_zip_path: Path, *, members: list[tuple[str, bytes]]) -> None:
    csv_zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(csv_zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        for member_name, body in members:
            zip_file.writestr(member_name, body)


def _build_utf16_tsv(rows: list[list[str]]) -> bytes:
    lines = ["\t".join(JP_COLUMNS)] + ["\t".join(row) for row in rows]
    text = "\r\n".join(lines) + "\r\n"
    return text.encode("utf-16")

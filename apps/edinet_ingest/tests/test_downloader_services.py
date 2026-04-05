from __future__ import annotations

import io
import zipfile
from datetime import date
from pathlib import Path

import httpx
from common.db.base import Base
from common.db.models import EdinetFetchJob, EdinetListResponse, IngestLog, RequestLog
from edinet_ingest.downloader.client import EdinetApiClient
from edinet_ingest.downloader.service import fetch_documents_for_date
from edinet_ingest.downloader.storage import RawStorageService
from edinet_ingest.ingest.archive import scan_archive
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session, sessionmaker


def test_fetch_documents_with_mocked_api_is_idempotent(tmp_path) -> None:
    session_factory = _create_session_factory(tmp_path)
    raw_root = tmp_path / "raw"
    target_date = date(2026, 3, 20)
    target_doc_id = "S100AAAA"

    transport = _build_mock_transport(target_date=target_date, target_doc_id=target_doc_id)
    client = EdinetApiClient(
        api_key="dummy-key",
        base_url="https://example.test/api/v2",
        transport=transport,
    )
    storage = RawStorageService(raw_root=raw_root)

    first = fetch_documents_for_date(
        target_date,
        session_factory=session_factory,
        client=client,
        storage=storage,
        ensure_list=True,
    )

    assert first.total_candidates == 1
    assert first.fetched_count == 1
    assert first.skipped_count == 0
    assert first.failed_count == 0

    doc_dir = raw_root / "edinet" / "2026" / "03" / "20" / target_doc_id
    assert (doc_dir / "list_response.json").exists()
    assert (doc_dir / "original.zip").exists()
    assert (doc_dir / "document.pdf").exists()
    assert (doc_dir / "csv.zip").exists()
    archive = scan_archive(doc_dir / "original.zip")
    assert archive.archive_type in {
        "edinet_search_download_zip",
        "edinet_api_zip",
        "unknown_edinet_zip",
    }
    assert len(archive.discovered_files) >= 1

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(EdinetListResponse)) == 1
        assert session.scalar(select(func.count()).select_from(EdinetFetchJob)) == 1
        assert session.scalar(select(func.count()).select_from(RequestLog)) >= 2
        assert session.scalar(select(func.count()).select_from(IngestLog)) >= 4

    second = fetch_documents_for_date(
        target_date,
        session_factory=session_factory,
        client=client,
        storage=storage,
        ensure_list=True,
    )

    assert second.total_candidates == 1
    assert second.fetched_count == 0
    assert second.skipped_count == 1
    assert second.failed_count == 0

    with session_factory() as session:
        assert session.scalar(select(func.count()).select_from(EdinetFetchJob)) == 1
        job = session.scalar(select(EdinetFetchJob).where(EdinetFetchJob.doc_id == target_doc_id))
        assert job is not None
        assert job.status == "success"


def test_fetch_documents_writes_csv_error_json_for_404_json_response(tmp_path) -> None:
    session_factory = _create_session_factory(tmp_path)
    raw_root = tmp_path / "raw"
    target_date = date(2026, 3, 20)
    target_doc_id = "S100ERR1"

    transport = _build_mock_transport(
        target_date=target_date,
        target_doc_id=target_doc_id,
        csv_status=404,
        csv_content=b'{"metadata":{"status":"404","message":"Not Found"}}',
        csv_content_type="application/json",
    )
    client = EdinetApiClient(
        api_key="dummy-key",
        base_url="https://example.test/api/v2",
        transport=transport,
    )
    storage = RawStorageService(raw_root=raw_root)

    summary = fetch_documents_for_date(
        target_date,
        session_factory=session_factory,
        client=client,
        storage=storage,
        ensure_list=True,
    )

    assert summary.total_candidates == 1
    assert summary.fetched_count == 0
    assert summary.failed_count == 1
    assert summary.failed_docs[0]["doc_id"] == target_doc_id
    assert summary.failed_docs[0]["reason"] == "csv_http_status_error"
    assert "status=404" in summary.failed_docs[0]["message"]

    doc_dir = raw_root / "edinet" / "2026" / "03" / "20" / target_doc_id
    assert not (doc_dir / "csv.zip").exists()
    assert (doc_dir / "csv_error.json").exists()
    payload = (doc_dir / "csv_error.json").read_text(encoding="utf-8")
    assert '"doc_id": "S100ERR1"' in payload
    assert '"http_status": 404' in payload
    assert '"content_type": "application/json"' in payload
    assert '"reason": "csv_http_status_error"' in payload


def test_fetch_documents_accepts_zip_payload_even_if_content_type_not_zip(tmp_path) -> None:
    session_factory = _create_session_factory(tmp_path)
    raw_root = tmp_path / "raw"
    target_date = date(2026, 3, 20)
    target_doc_id = "S100ZIP1"

    transport = _build_mock_transport(
        target_date=target_date,
        target_doc_id=target_doc_id,
        csv_status=200,
        csv_content=_build_sample_csv_zip(),
        csv_content_type="text/plain",
    )
    client = EdinetApiClient(
        api_key="dummy-key",
        base_url="https://example.test/api/v2",
        transport=transport,
    )
    storage = RawStorageService(raw_root=raw_root)

    summary = fetch_documents_for_date(
        target_date,
        session_factory=session_factory,
        client=client,
        storage=storage,
        ensure_list=True,
    )

    assert summary.fetched_count == 1
    assert summary.failed_count == 0

    doc_dir = raw_root / "edinet" / "2026" / "03" / "20" / target_doc_id
    assert (doc_dir / "csv.zip").exists()
    assert not (doc_dir / "csv_error.json").exists()


def test_fetch_documents_rejects_non_zip_payload_even_if_content_type_zip(tmp_path) -> None:
    session_factory = _create_session_factory(tmp_path)
    raw_root = tmp_path / "raw"
    target_date = date(2026, 3, 20)
    target_doc_id = "S100BAD1"

    transport = _build_mock_transport(
        target_date=target_date,
        target_doc_id=target_doc_id,
        csv_status=200,
        csv_content=b'{"metadata":{"status":"200","message":"not zip"}}',
        csv_content_type="application/zip",
    )
    client = EdinetApiClient(
        api_key="dummy-key",
        base_url="https://example.test/api/v2",
        transport=transport,
    )
    storage = RawStorageService(raw_root=raw_root)

    summary = fetch_documents_for_date(
        target_date,
        session_factory=session_factory,
        client=client,
        storage=storage,
        ensure_list=True,
    )

    assert summary.fetched_count == 0
    assert summary.failed_count == 1
    assert summary.failed_docs[0]["doc_id"] == target_doc_id
    assert summary.failed_docs[0]["reason"] == "csv_non_zip_payload"

    doc_dir = raw_root / "edinet" / "2026" / "03" / "20" / target_doc_id
    assert not (doc_dir / "csv.zip").exists()
    assert (doc_dir / "csv_error.json").exists()


def _create_session_factory(tmp_path: Path) -> sessionmaker[Session]:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'downloader.sqlite3'}"
    engine = create_engine(database_url)
    import common.db.models  # noqa: F401

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def _build_mock_transport(
    *,
    target_date: date,
    target_doc_id: str,
    csv_status: int = 200,
    csv_content: bytes | None = None,
    csv_content_type: str | None = "application/zip",
) -> httpx.MockTransport:
    zip_bytes = _build_sample_original_zip()
    csv_zip_bytes = csv_content if csv_content is not None else _build_sample_csv_zip()

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        params = request.url.params
        assert params.get("Subscription-Key") == "dummy-key"

        if path.endswith("/documents.json"):
            assert params.get("date") == target_date.isoformat()
            assert params.get("type") == "2"
            return httpx.Response(
                200,
                json={
                    "metadata": {"status": "200", "message": "OK"},
                    "results": [
                        {
                            "docID": target_doc_id,
                            "edinetCode": "E12345",
                            "formCode": "030000",
                            "docTypeCode": "120",
                        },
                        {
                            "docID": "S100SKIP",
                            "edinetCode": "E99999",
                            "formCode": "999999",
                            "docTypeCode": "999",
                        },
                    ],
                },
            )

        if path.endswith(f"/documents/{target_doc_id}"):
            doc_type = params.get("type")
            if doc_type == "1":
                return httpx.Response(200, content=zip_bytes)
            if doc_type == "2":
                return httpx.Response(200, content=b"%PDF-mock")
            if doc_type == "5":
                headers = {}
                if csv_content_type is not None:
                    headers["Content-Type"] = csv_content_type
                return httpx.Response(csv_status, content=csv_zip_bytes, headers=headers)

        return httpx.Response(404, json={"message": "not found"})

    return httpx.MockTransport(handler)


def _build_sample_original_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            "XbrlSearchDlInfo.csv",
            "docID,edinetCode,filerName\nS100AAAA,E12345,Sample Company\n",
        )
        zip_file.writestr(
            "PublicDoc/main.xbrl",
            (
                "<?xml version='1.0' encoding='UTF-8'?>"
                "<xbrli:xbrl xmlns:xbrli='http://www.xbrl.org/2003/instance'/>"
            ),
        )
    return buffer.getvalue()


def _build_sample_csv_zip() -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zip_file:
        zip_file.writestr(
            "XBRL_TO_CSV/jpcrp030000-asr-001_sample.csv",
            (
                "要素ID\t項目名\tコンテキストID\t相対年度\t連結・個別\t期間・時点\tユニットID\t単位\t値\r\n"
                "jppfs_cor:NetSales\t売上高\tCurrentYear\t当期\t連結\t期間\tJPY\t円\t1000\r\n"
            ).encode("utf-16"),
        )
    return buffer.getvalue()

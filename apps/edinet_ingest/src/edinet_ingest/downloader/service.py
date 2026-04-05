from __future__ import annotations

import io
import json
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from common.db.models import EdinetFetchJob, EdinetListResponse, IngestLog, RequestLog
from common.db.session import get_session_factory
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from edinet_ingest.downloader.client import (
    FETCH_TYPE_CSV_ZIP,
    FETCH_TYPE_ORIGINAL_ZIP,
    FETCH_TYPE_PDF,
    EdinetApiClient,
)
from edinet_ingest.downloader.filing_type_map import load_active_resolver, seed_filing_type_map
from edinet_ingest.downloader.storage import RawStorageService, SavedRawFile

SERVICE_NAME = "edinet-ingest-downloader"


@dataclass(frozen=True, slots=True)
class ListFetchSummary:
    target_date: str
    total_results: int
    matched_results: int
    stored_records: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class FetchDocsSummary:
    target_date: str
    total_candidates: int
    fetched_count: int
    skipped_count: int
    failed_count: int
    failed_docs: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class _FetchSpec:
    attr_name: str
    filename: str
    response_type: str


class CsvZipValidationError(RuntimeError):
    def __init__(self, *, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


_FETCH_SPECS = (
    _FetchSpec(attr_name="zip_path", filename="original.zip", response_type=FETCH_TYPE_ORIGINAL_ZIP),
    _FetchSpec(attr_name="pdf_path", filename="document.pdf", response_type=FETCH_TYPE_PDF),
    _FetchSpec(attr_name="csv_zip_path", filename="csv.zip", response_type=FETCH_TYPE_CSV_ZIP),
)


def fetch_and_store_list_for_date(
    target_date: date,
    *,
    session_factory: sessionmaker[Session] | None = None,
    client: EdinetApiClient | None = None,
    storage: RawStorageService | None = None,
) -> ListFetchSummary:
    session_factory = session_factory or get_session_factory()
    client = client or EdinetApiClient()
    storage = storage or RawStorageService()

    with session_factory() as session:
        started_at = datetime.now(tz=UTC)
        request_log = RequestLog(
            service_name=SERVICE_NAME,
            request_type="edinet_list_documents",
            target=target_date.isoformat(),
            started_at=started_at,
            status="running",
        )
        session.add(request_log)
        session.flush()

        try:
            seed_filing_type_map(session)
            resolver = load_active_resolver(session)
            response = client.list_documents(target_date)

            total_results = len(response.results)
            matched_results = 0
            stored_records = 0

            for record in response.results:
                doc_id = _pick_first(record, "docID", "docId", "doc_id")
                if not doc_id:
                    continue

                filing_type_key = resolver.resolve(
                    form_code=_pick_first(record, "formCode", "form_code"),
                    doc_type_code=_pick_first(record, "docTypeCode", "doc_type_code"),
                )
                if filing_type_key is None:
                    continue
                matched_results += 1

                saved = storage.save_list_response_json(
                    target_date=target_date,
                    doc_id=doc_id,
                    payload={
                        "targetDate": target_date.isoformat(),
                        "fetchedAt": datetime.now(tz=UTC).isoformat(),
                        "record": record,
                    },
                )

                upserted = _upsert_list_response(
                    session=session,
                    target_date=target_date,
                    doc_id=doc_id,
                    filing_type_key=filing_type_key,
                    record=record,
                    saved=saved,
                )
                if upserted:
                    stored_records += 1

                session.add(
                    IngestLog(
                        service_name=SERVICE_NAME,
                        source_type="edinet",
                        source_key=f"{doc_id}:list",
                        started_at=started_at,
                        finished_at=datetime.now(tz=UTC),
                        status="success",
                        raw_path=str(saved.path),
                        sha256=saved.sha256,
                        message="saved list response",
                    )
                )

            request_log.status = "success"
            request_log.finished_at = datetime.now(tz=UTC)
            request_log.message = (
                f"total_results={total_results}, matched_results={matched_results}, stored_records={stored_records}"
            )
            session.commit()
            return ListFetchSummary(
                target_date=target_date.isoformat(),
                total_results=total_results,
                matched_results=matched_results,
                stored_records=stored_records,
            )
        except Exception as exc:
            request_log.status = "failed"
            request_log.finished_at = datetime.now(tz=UTC)
            request_log.message = str(exc)[:512]
            session.commit()
            raise


def fetch_documents_for_date(
    target_date: date,
    *,
    session_factory: sessionmaker[Session] | None = None,
    client: EdinetApiClient | None = None,
    storage: RawStorageService | None = None,
    ensure_list: bool = True,
) -> FetchDocsSummary:
    session_factory = session_factory or get_session_factory()
    client = client or EdinetApiClient()
    storage = storage or RawStorageService()

    if ensure_list:
        fetch_and_store_list_for_date(
            target_date,
            session_factory=session_factory,
            client=client,
            storage=storage,
        )

    with session_factory() as session:
        started_at = datetime.now(tz=UTC)
        request_log = RequestLog(
            service_name=SERVICE_NAME,
            request_type="edinet_fetch_documents",
            target=target_date.isoformat(),
            started_at=started_at,
            status="running",
        )
        session.add(request_log)
        session.flush()

        try:
            candidates = session.scalars(
                select(EdinetListResponse).where(EdinetListResponse.target_date == target_date)
            ).all()

            total_candidates = len(candidates)
            fetched_count = 0
            skipped_count = 0
            failed_count = 0
            failed_docs: list[dict[str, str]] = []

            for candidate in candidates:
                existing_job = session.scalar(
                    select(EdinetFetchJob).where(EdinetFetchJob.doc_id == candidate.doc_id)
                )
                if _is_completed_job(existing_job):
                    skipped_count += 1
                    continue

                now_utc = datetime.now(tz=UTC)
                if existing_job is None:
                    job = EdinetFetchJob(
                        doc_id=candidate.doc_id,
                        target_date=candidate.target_date,
                        filing_type_key=candidate.filing_type_key,
                        status="running",
                        attempts=1,
                        requested_at=now_utc,
                        created_at=now_utc,
                    )
                    session.add(job)
                    session.flush()
                else:
                    job = existing_job
                    job.status = "running"
                    job.attempts = max(1, job.attempts) + 1
                    job.requested_at = now_utc
                    job.message = None

                try:
                    for spec in _FETCH_SPECS:
                        if spec.response_type == FETCH_TYPE_CSV_ZIP:
                            saved = _fetch_and_save_csv_zip_or_error(
                                client=client,
                                storage=storage,
                                session=session,
                                target_date=target_date,
                                doc_id=candidate.doc_id,
                                started_at=now_utc,
                            )
                        else:
                            body = client.fetch_document_bytes(
                                doc_id=candidate.doc_id, response_type=spec.response_type
                            )
                            saved = storage.save_binary(
                                target_date=target_date,
                                doc_id=candidate.doc_id,
                                filename=spec.filename,
                                content=body,
                            )
                            session.add(
                                IngestLog(
                                    service_name=SERVICE_NAME,
                                    source_type="edinet",
                                    source_key=f"{candidate.doc_id}:{spec.filename}",
                                    started_at=now_utc,
                                    finished_at=datetime.now(tz=UTC),
                                    status="success",
                                    raw_path=str(saved.path),
                                    sha256=saved.sha256,
                                    message=f"saved {spec.filename}",
                                )
                            )

                        setattr(job, spec.attr_name, str(saved.path))

                    job.status = "success"
                    job.finished_at = datetime.now(tz=UTC)
                    job.message = "fetched all documents"
                    fetched_count += 1
                except Exception as exc:
                    job.status = "failed"
                    job.finished_at = datetime.now(tz=UTC)
                    job.message = str(exc)[:512]
                    failed_count += 1
                    failed_docs.append(
                        {
                            "doc_id": candidate.doc_id,
                            "reason": _failure_reason(exc),
                            "message": str(exc)[:512],
                        }
                    )

            request_log.status = "success"
            request_log.finished_at = datetime.now(tz=UTC)
            request_log.message = (
                f"total_candidates={total_candidates}, fetched_count={fetched_count}, "
                f"skipped_count={skipped_count}, failed_count={failed_count}"
            )
            session.commit()
            return FetchDocsSummary(
                target_date=target_date.isoformat(),
                total_candidates=total_candidates,
                fetched_count=fetched_count,
                skipped_count=skipped_count,
                failed_count=failed_count,
                failed_docs=failed_docs,
            )
        except Exception as exc:
            request_log.status = "failed"
            request_log.finished_at = datetime.now(tz=UTC)
            request_log.message = str(exc)[:512]
            session.commit()
            raise


def _fetch_and_save_csv_zip_or_error(
    *,
    client: EdinetApiClient,
    storage: RawStorageService,
    session: Session,
    target_date: date,
    doc_id: str,
    started_at: datetime,
) -> SavedRawFile:
    response = client.fetch_document_response(doc_id=doc_id, response_type=FETCH_TYPE_CSV_ZIP)
    http_status = response.status_code
    content_type = response.headers.get("content-type")
    body = response.content

    if http_status < 200 or http_status >= 300:
        reason = "csv_http_status_error"
        message = f"CSV response status is not success: status={http_status}"
        saved_error = _save_csv_error_json(
            storage=storage,
            target_date=target_date,
            doc_id=doc_id,
            payload=_build_csv_error_payload(
                doc_id=doc_id,
                http_status=http_status,
                content_type=content_type,
                reason=reason,
                response_body=body,
            ),
        )
        session.add(
            IngestLog(
                service_name=SERVICE_NAME,
                source_type="edinet",
                source_key=f"{doc_id}:csv_error.json",
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                status="failed",
                raw_path=str(saved_error.path),
                sha256=saved_error.sha256,
                message=message,
            )
        )
        raise CsvZipValidationError(reason=reason, message=message)

    if not _is_zip_payload(body):
        reason = "csv_non_zip_payload"
        message = "CSV response body is not a valid ZIP payload"
        saved_error = _save_csv_error_json(
            storage=storage,
            target_date=target_date,
            doc_id=doc_id,
            payload=_build_csv_error_payload(
                doc_id=doc_id,
                http_status=http_status,
                content_type=content_type,
                reason=reason,
                response_body=body,
            ),
        )
        session.add(
            IngestLog(
                service_name=SERVICE_NAME,
                source_type="edinet",
                source_key=f"{doc_id}:csv_error.json",
                started_at=started_at,
                finished_at=datetime.now(tz=UTC),
                status="failed",
                raw_path=str(saved_error.path),
                sha256=saved_error.sha256,
                message=message,
            )
        )
        raise CsvZipValidationError(reason=reason, message=message)

    saved = storage.save_binary(
        target_date=target_date,
        doc_id=doc_id,
        filename="csv.zip",
        content=body,
    )
    session.add(
        IngestLog(
            service_name=SERVICE_NAME,
            source_type="edinet",
            source_key=f"{doc_id}:csv.zip",
            started_at=started_at,
            finished_at=datetime.now(tz=UTC),
            status="success",
            raw_path=str(saved.path),
            sha256=saved.sha256,
            message=f"saved csv.zip (content_type={content_type or 'unknown'})",
        )
    )
    return saved


def _save_csv_error_json(
    *,
    storage: RawStorageService,
    target_date: date,
    doc_id: str,
    payload: dict[str, Any],
) -> SavedRawFile:
    body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    return storage.save_binary(
        target_date=target_date,
        doc_id=doc_id,
        filename="csv_error.json",
        content=body,
    )


def _build_csv_error_payload(
    *,
    doc_id: str,
    http_status: int,
    content_type: str | None,
    reason: str,
    response_body: bytes,
) -> dict[str, Any]:
    return {
        "doc_id": doc_id,
        "http_status": http_status,
        "content_type": content_type,
        "reason": reason,
        "response_body_preview": response_body[:1000].decode("utf-8", errors="replace"),
    }


def _is_zip_payload(body: bytes) -> bool:
    if not body:
        return False
    return zipfile.is_zipfile(io.BytesIO(body))


def _failure_reason(exc: Exception) -> str:
    if isinstance(exc, CsvZipValidationError):
        return exc.reason
    return "fetch_error"


def _upsert_list_response(
    *,
    session: Session,
    target_date: date,
    doc_id: str,
    filing_type_key: str,
    record: dict[str, Any],
    saved: SavedRawFile,
) -> bool:
    now_utc = datetime.now(tz=UTC)
    existing = session.scalar(select(EdinetListResponse).where(EdinetListResponse.doc_id == doc_id))
    if existing is not None:
        existing.target_date = target_date
        existing.edinet_code = _pick_first(record, "edinetCode", "edinet_code")
        existing.form_code = _pick_first(record, "formCode", "form_code")
        existing.doc_type_code = _pick_first(record, "docTypeCode", "doc_type_code")
        existing.filing_type_key = filing_type_key
        existing.response_path = str(saved.path)
        existing.response_sha256 = saved.sha256
        existing.requested_at = now_utc
        return False

    session.add(
        EdinetListResponse(
            target_date=target_date,
            doc_id=doc_id,
            edinet_code=_pick_first(record, "edinetCode", "edinet_code"),
            form_code=_pick_first(record, "formCode", "form_code"),
            doc_type_code=_pick_first(record, "docTypeCode", "doc_type_code"),
            filing_type_key=filing_type_key,
            response_path=str(saved.path),
            response_sha256=saved.sha256,
            requested_at=now_utc,
            created_at=now_utc,
        )
    )
    return True


def _pick_first(payload: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = payload.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def _is_completed_job(job: EdinetFetchJob | None) -> bool:
    if job is None:
        return False
    if job.status != "success":
        return False
    if not job.zip_path or not job.pdf_path or not job.csv_zip_path:
        return False
    return Path(job.zip_path).exists() and Path(job.pdf_path).exists() and Path(job.csv_zip_path).exists()

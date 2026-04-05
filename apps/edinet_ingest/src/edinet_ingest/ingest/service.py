from __future__ import annotations

import csv
import hashlib
import io
import mimetypes
import zipfile
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath

from common.db.models import (
    Filing,
    FilingDocument,
    FilingSource,
    XbrlContext,
    XbrlContextDimension,
    XbrlFact,
    XbrlUnit,
)
from common.db.session import get_session_factory
from common.normalize import normalize_text
from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from edinet_ingest.ingest.archive import ArchiveScanResult, ZipEntry, scan_archive
from edinet_ingest.ingest.manifest import ArchiveManifest, build_manifest
from edinet_ingest.ingest.parser_contexts import (
    ParsedContext,
    ParsedContextDimension,
    parse_contexts,
)
from edinet_ingest.ingest.parser_facts import ParsedFact, parse_facts
from edinet_ingest.ingest.parser_units import ParsedUnit, parse_units


@dataclass(frozen=True, slots=True)
class FilingMetadata:
    doc_id: str | None
    edinet_code: str | None
    filer_name_raw: str
    filer_name_normalized: str
    corporate_number: str | None
    filing_title: str | None
    filing_type_raw: str | None
    submit_date: date | None


@dataclass(frozen=True, slots=True)
class IngestSummary:
    zip_path: str
    archive_type: str
    filing_id: str
    source_id: str
    main_xbrl_path: str
    documents_count: int
    contexts_count: int
    context_dimensions_count: int
    units_count: int
    facts_count: int

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_manifest_from_zip(zip_path: Path) -> ArchiveManifest:
    scan_result = scan_archive(zip_path)
    return build_manifest(scan_result)


def ingest_zip_archive(
    zip_path: Path,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> IngestSummary:
    resolved_zip_path = Path(zip_path).expanduser().resolve()
    scan_result = scan_archive(resolved_zip_path)
    manifest = build_manifest(scan_result)
    if manifest.main_xbrl_path is None:
        raise ValueError("main_xbrl_path could not be determined from archive")

    source_sha256 = _sha256_file(resolved_zip_path)
    session_factory = session_factory or get_session_factory()

    with zipfile.ZipFile(resolved_zip_path, mode="r") as zip_file:
        metadata = _extract_filing_metadata(zip_file, scan_result)
        xbrl_root = _load_main_xbrl_root(zip_file, scan_result, manifest.main_xbrl_path)
        contexts, context_dimensions = parse_contexts(xbrl_root)
        units = parse_units(xbrl_root)
        facts = parse_facts(xbrl_root)

        with session_factory() as session:
            _ensure_source_uniqueness(session, resolved_zip_path)
            now_utc = datetime.now(tz=UTC)
            source = FilingSource(
                source_type="edinet",
                archive_type=manifest.archive_type,
                original_zip_path=str(resolved_zip_path),
                original_zip_sha256=source_sha256,
                discovered_at=now_utc,
                created_at=now_utc,
            )
            session.add(source)
            session.flush()

            filing = Filing(
                source_id=source.source_id,
                source_type="edinet",
                doc_id=metadata.doc_id,
                edinet_code=metadata.edinet_code,
                filer_name_raw=metadata.filer_name_raw,
                filer_name_normalized=metadata.filer_name_normalized,
                corporate_number=metadata.corporate_number,
                filing_title=metadata.filing_title,
                filing_type_raw=metadata.filing_type_raw,
                submit_date=metadata.submit_date,
                created_at=now_utc,
            )
            session.add(filing)
            session.flush()

            documents_count = _insert_filing_documents(
                session=session,
                zip_file=zip_file,
                filing_id=filing.filing_id,
                scan_result=scan_result,
            )
            context_map, contexts_count = _insert_contexts(
                session=session,
                filing_id=filing.filing_id,
                contexts=contexts,
            )
            dimensions_count = _insert_context_dimensions(
                session=session,
                context_map=context_map,
                context_dimensions=context_dimensions,
            )
            unit_map, units_count = _insert_units(session=session, filing_id=filing.filing_id, units=units)
            facts_count = _insert_facts(
                session=session,
                filing_id=filing.filing_id,
                context_map=context_map,
                unit_map=unit_map,
                facts=facts,
            )
            session.commit()

    return IngestSummary(
        zip_path=str(resolved_zip_path),
        archive_type=manifest.archive_type,
        filing_id=str(filing.filing_id),
        source_id=str(source.source_id),
        main_xbrl_path=manifest.main_xbrl_path,
        documents_count=documents_count,
        contexts_count=contexts_count,
        context_dimensions_count=dimensions_count,
        units_count=units_count,
        facts_count=facts_count,
    )


def _ensure_source_uniqueness(session: Session, zip_path: Path) -> None:
    existing = session.scalar(
        select(FilingSource).where(
            FilingSource.source_type == "edinet",
            FilingSource.original_zip_path == str(zip_path),
        )
    )
    if existing is not None:
        raise ValueError(f"ZIP has already been ingested: {zip_path}")


def _load_main_xbrl_root(
    zip_file: zipfile.ZipFile,
    scan_result: ArchiveScanResult,
    main_xbrl_path: str,
) -> etree._Element:
    entry = scan_result.get_entry(main_xbrl_path)
    if entry is None:
        raise ValueError(f"main_xbrl_path not found in archive entries: {main_xbrl_path}")

    xml_bytes = zip_file.read(entry.original_path)
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=True, huge_tree=False)
    return etree.fromstring(xml_bytes, parser=parser)


def _insert_filing_documents(
    *,
    session: Session,
    zip_file: zipfile.ZipFile,
    filing_id: object,
    scan_result: ArchiveScanResult,
) -> int:
    public_set = set(scan_result.public_doc_files)
    audit_set = set(scan_result.audit_doc_files)
    count = 0

    for entry in scan_result.entries:
        if entry.is_dir:
            continue

        document_bytes = zip_file.read(entry.original_path)
        content_type, _ = mimetypes.guess_type(entry.normalized_path)
        if entry.normalized_path in public_set:
            doc_role = "PublicDoc"
        elif entry.normalized_path in audit_set:
            doc_role = "AuditDoc"
        else:
            doc_role = "Other"

        session.add(
            FilingDocument(
                filing_id=filing_id,
                doc_role=doc_role,
                relative_path=entry.normalized_path,
                content_type=content_type,
                bytes=entry.file_size,
                sha256=_sha256_bytes(document_bytes),
            )
        )
        count += 1
    return count


def _insert_contexts(
    *,
    session: Session,
    filing_id: object,
    contexts: list[ParsedContext],
) -> tuple[dict[str, object], int]:
    context_models: list[tuple[str, XbrlContext]] = []
    for context in contexts:
        model = XbrlContext(
            filing_id=filing_id,
            context_ref=context.context_ref,
            entity_identifier=context.entity_identifier,
            period_kind=context.period_kind,
            instant_date=context.instant_date,
            start_date=context.start_date,
            end_date=context.end_date,
        )
        session.add(model)
        context_models.append((context.context_ref, model))

    session.flush()
    context_map: dict[str, object] = {
        context_ref: model.context_id for context_ref, model in context_models
    }
    return context_map, len(context_models)


def _insert_context_dimensions(
    *,
    session: Session,
    context_map: dict[str, object],
    context_dimensions: list[ParsedContextDimension],
) -> int:
    count = 0
    for dimension in context_dimensions:
        context_id = context_map.get(dimension.context_ref)
        if context_id is None:
            continue
        session.add(
            XbrlContextDimension(
                context_id=context_id,
                dimension_qname=dimension.dimension_qname,
                member_qname=dimension.member_qname,
            )
        )
        count += 1
    return count


def _insert_units(
    *,
    session: Session,
    filing_id: object,
    units: list[ParsedUnit],
) -> tuple[dict[str, object], int]:
    deduped_units: list[ParsedUnit] = []
    seen = set()
    for unit in units:
        key = (unit.unit_ref, unit.measure_text)
        if key in seen:
            continue
        seen.add(key)
        deduped_units.append(unit)

    unit_models: list[tuple[ParsedUnit, XbrlUnit]] = []
    for unit in deduped_units:
        model = XbrlUnit(
            filing_id=filing_id,
            unit_ref=unit.unit_ref,
            measure_text=unit.measure_text,
        )
        session.add(model)
        unit_models.append((unit, model))

    session.flush()
    unit_map: dict[str, object] = {}
    for unit, model in unit_models:
        unit_map.setdefault(unit.unit_ref, model.unit_id)
    return unit_map, len(unit_models)


def _insert_facts(
    *,
    session: Session,
    filing_id: object,
    context_map: dict[str, object],
    unit_map: dict[str, object],
    facts: list[ParsedFact],
) -> int:
    count = 0
    for fact in facts:
        context_id = context_map.get(fact.context_ref)
        if context_id is None:
            continue
        unit_id = unit_map.get(fact.unit_ref) if fact.unit_ref else None

        session.add(
            XbrlFact(
                filing_id=filing_id,
                context_id=context_id,
                unit_id=unit_id,
                namespace_uri=fact.namespace_uri,
                concept_name=fact.concept_name,
                concept_qname=fact.concept_qname,
                decimals=fact.decimals,
                is_nil=fact.is_nil,
                raw_value_text=fact.raw_value_text,
                normalized_value_decimal=fact.normalized_value_decimal,
                raw_text_value=fact.raw_text_value,
            )
        )
        count += 1
    return count


def _extract_filing_metadata(
    zip_file: zipfile.ZipFile,
    scan_result: ArchiveScanResult,
) -> FilingMetadata:
    csv_entry = _find_search_dl_csv_entry(scan_result)
    if csv_entry is None:
        return _default_filing_metadata(scan_result.zip_path)

    csv_bytes = zip_file.read(csv_entry.original_path)
    csv_text = _decode_csv_bytes(csv_bytes)
    reader = csv.DictReader(io.StringIO(csv_text))
    row = next(reader, None)
    if row is None:
        return _default_filing_metadata(scan_result.zip_path)

    normalized_row = _normalize_row_keys(row)
    filer_name_raw = _pick_value(
        normalized_row,
        candidates=["filername", "提出者名", "提出者"],
    ) or "unknown_filer"

    submit_date_raw = _pick_value(
        normalized_row,
        candidates=["submitdatetime", "submitdate", "提出日時", "提出日"],
    )

    return FilingMetadata(
        doc_id=_pick_value(normalized_row, candidates=["docid", "書類管理番号"]),
        edinet_code=_pick_value(normalized_row, candidates=["edinetcode", "ｅｄｉｎｅｔコード"]),
        filer_name_raw=filer_name_raw,
        filer_name_normalized=normalize_text(filer_name_raw),
        corporate_number=_pick_value(
            normalized_row,
            candidates=["corporatenumber", "法人番号", "証券コード", "seccode"],
        ),
        filing_title=_pick_value(
            normalized_row,
            candidates=["docdescription", "filingtitle", "書類名", "提出書類"],
        ),
        filing_type_raw=_pick_value(
            normalized_row,
            candidates=["formcode", "doctypecode", "ordinancecode", "様式コード"],
        ),
        submit_date=_parse_submit_date(submit_date_raw),
    )


def _find_search_dl_csv_entry(scan_result: ArchiveScanResult) -> ZipEntry | None:
    for entry in scan_result.entries:
        if entry.is_dir:
            continue
        if PurePosixPath(entry.normalized_path).name.lower() == "xbrlsearchdlinfo.csv":
            return entry
    return None


def _decode_csv_bytes(csv_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return csv_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return csv_bytes.decode("utf-8", errors="replace")


def _normalize_row_keys(row: dict[str, str | None]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        if key is None:
            continue
        normalized_key = normalize_text(key).lower().replace(" ", "").replace("_", "")
        normalized[normalized_key] = (value or "").strip()
    return normalized


def _pick_value(normalized_row: dict[str, str], candidates: list[str]) -> str | None:
    for candidate in candidates:
        normalized_key = normalize_text(candidate).lower().replace(" ", "").replace("_", "")
        value = normalized_row.get(normalized_key)
        if value:
            return value
    return None


def _parse_submit_date(raw_value: str | None) -> date | None:
    if raw_value is None:
        return None

    stripped = raw_value.strip()
    if not stripped:
        return None

    candidates = [stripped[:10], stripped.split(" ")[0]]
    for candidate in candidates:
        normalized = candidate.replace("/", "-")
        try:
            return date.fromisoformat(normalized)
        except ValueError:
            continue
    return None


def _default_filing_metadata(zip_path: Path) -> FilingMetadata:
    raw_name = zip_path.stem
    return FilingMetadata(
        doc_id=None,
        edinet_code=None,
        filer_name_raw=raw_name,
        filer_name_normalized=normalize_text(raw_name),
        corporate_number=None,
        filing_title=None,
        filing_type_raw=None,
        submit_date=None,
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

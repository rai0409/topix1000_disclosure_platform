from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from edinet_ingest.ingest.archive import ArchiveScanResult, scan_archive
from edinet_ingest.ingest.xbrl_locator import choose_main_xbrl


@dataclass(frozen=True, slots=True)
class ArchiveManifest:
    archive_type: str
    zip_path: str
    discovered_files: list[str]
    public_doc_files: list[str]
    audit_doc_files: list[str]
    main_xbrl_path: str | None
    main_xbrl_reason: str
    xsd_paths: list[str]
    linkbase_paths: dict[str, list[str]]
    ixbrl_paths: list[str]
    unsafe_entries: list[str]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def generate_manifest(zip_path: Path) -> ArchiveManifest:
    scan_result = scan_archive(zip_path)
    return build_manifest(scan_result)


def build_manifest(scan_result: ArchiveScanResult) -> ArchiveManifest:
    discovered_files = scan_result.discovered_files
    public_doc_files = scan_result.public_doc_files
    audit_doc_files = scan_result.audit_doc_files
    selection = choose_main_xbrl(discovered_files, public_doc_files, audit_doc_files)

    xsd_paths = [path for path in discovered_files if path.lower().endswith(".xsd")]
    ixbrl_paths = [
        path
        for path in discovered_files
        if path.lower().endswith((".htm", ".html", ".xhtml"))
    ]
    linkbase_paths = _collect_linkbase_paths(discovered_files)

    return ArchiveManifest(
        archive_type=scan_result.archive_type,
        zip_path=str(scan_result.zip_path),
        discovered_files=discovered_files,
        public_doc_files=public_doc_files,
        audit_doc_files=audit_doc_files,
        main_xbrl_path=selection.main_xbrl_path,
        main_xbrl_reason=selection.reason,
        xsd_paths=xsd_paths,
        linkbase_paths=linkbase_paths,
        ixbrl_paths=ixbrl_paths,
        unsafe_entries=scan_result.unsafe_entries,
    )


def _collect_linkbase_paths(discovered_files: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {"lab": [], "pre": [], "cal": [], "def": []}
    for path in discovered_files:
        lowered = path.lower()
        if not lowered.endswith(".xml"):
            continue

        kind = _classify_linkbase(path)
        if kind is not None:
            buckets[kind].append(path)
    return buckets


def _classify_linkbase(path: str) -> str | None:
    lowered = path.lower()
    if any(token in lowered for token in ("_lab", "lab.xml", "-lab")):
        return "lab"
    if any(token in lowered for token in ("_pre", "pre.xml", "-pre")):
        return "pre"
    if any(token in lowered for token in ("_cal", "cal.xml", "-cal")):
        return "cal"
    if any(token in lowered for token in ("_def", "def.xml", "-def")):
        return "def"
    return None

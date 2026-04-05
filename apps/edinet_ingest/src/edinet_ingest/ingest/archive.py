from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

ARCHIVE_TYPE_SEARCH_DOWNLOAD = "edinet_search_download_zip"
ARCHIVE_TYPE_API = "edinet_api_zip"
ARCHIVE_TYPE_UNKNOWN = "unknown_edinet_zip"


@dataclass(frozen=True, slots=True)
class ZipEntry:
    normalized_path: str
    original_path: str
    file_size: int
    is_dir: bool


@dataclass(slots=True)
class ArchiveScanResult:
    zip_path: Path
    archive_type: str
    entries: list[ZipEntry]
    unsafe_entries: list[str]

    @property
    def discovered_files(self) -> list[str]:
        return [entry.normalized_path for entry in self.entries if not entry.is_dir]

    @property
    def public_doc_files(self) -> list[str]:
        return [path for path in self.discovered_files if _is_under_dir(path, "PublicDoc")]

    @property
    def audit_doc_files(self) -> list[str]:
        return [path for path in self.discovered_files if _is_under_dir(path, "AuditDoc")]

    @property
    def entry_map(self) -> dict[str, ZipEntry]:
        return {entry.normalized_path: entry for entry in self.entries}

    def get_entry(self, normalized_path: str) -> ZipEntry | None:
        return self.entry_map.get(normalized_path)


def scan_archive(zip_path: Path) -> ArchiveScanResult:
    if not zip_path.exists():
        raise FileNotFoundError(f"ZIP file not found: {zip_path}")

    entries: list[ZipEntry] = []
    unsafe_entries: list[str] = []
    seen_paths: set[str] = set()

    with zipfile.ZipFile(zip_path, mode="r") as zip_file:
        for info in zip_file.infolist():
            safe_entry = _to_safe_zip_path(info.filename)
            if safe_entry is None:
                unsafe_entries.append(info.filename)
                continue

            if safe_entry in seen_paths:
                continue
            seen_paths.add(safe_entry)

            entries.append(
                ZipEntry(
                    normalized_path=safe_entry,
                    original_path=info.filename,
                    file_size=info.file_size,
                    is_dir=info.is_dir() or info.filename.endswith("/"),
                )
            )

    discovered_files = [entry.normalized_path for entry in entries if not entry.is_dir]
    archive_type = _detect_archive_type(discovered_files)
    return ArchiveScanResult(
        zip_path=zip_path,
        archive_type=archive_type,
        entries=entries,
        unsafe_entries=unsafe_entries,
    )


def _detect_archive_type(discovered_files: list[str]) -> str:
    has_search_csv = any(
        PurePosixPath(path).name.lower() == "xbrlsearchdlinfo.csv"
        for path in discovered_files
    )
    if has_search_csv:
        return ARCHIVE_TYPE_SEARCH_DOWNLOAD

    has_public_doc = any(_is_under_dir(path, "PublicDoc") for path in discovered_files)
    if has_public_doc:
        return ARCHIVE_TYPE_API

    return ARCHIVE_TYPE_UNKNOWN


def _is_under_dir(path: str, dirname: str) -> bool:
    lowered = path.lower()
    dirname_lowered = dirname.lower()
    return lowered.startswith(f"{dirname_lowered}/") or f"/{dirname_lowered}/" in lowered


def _to_safe_zip_path(raw_path: str) -> str | None:
    if not raw_path:
        return None

    normalized = raw_path.replace("\\", "/")
    if normalized.startswith("/") or normalized.startswith("\\"):
        return None
    if len(normalized) >= 2 and normalized[1] == ":":
        return None

    path = PurePosixPath(normalized)
    parts = [part for part in path.parts if part not in ("", ".")]
    if any(part == ".." for part in parts):
        return None
    if not parts:
        return None

    safe_path = PurePosixPath(*parts).as_posix()
    return safe_path

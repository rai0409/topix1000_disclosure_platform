from __future__ import annotations

import zipfile
from pathlib import PurePosixPath

from edinet_ingest.ingest.archive import ARCHIVE_TYPE_SEARCH_DOWNLOAD, scan_archive
from edinet_ingest.ingest.manifest import build_manifest
from edinet_ingest.ingest.parser_contexts import parse_contexts
from edinet_ingest.ingest.parser_facts import parse_facts
from edinet_ingest.ingest.parser_units import parse_units
from edinet_ingest.ingest.xbrl_locator import choose_main_xbrl
from lxml import etree


def test_sample_zip_is_readable(sample_zip_path) -> None:
    with zipfile.ZipFile(sample_zip_path, mode="r") as zip_file:
        assert len(zip_file.namelist()) > 0


def test_manifest_output(sample_zip_path) -> None:
    scan_result = scan_archive(sample_zip_path)
    manifest = build_manifest(scan_result)

    assert manifest.archive_type == ARCHIVE_TYPE_SEARCH_DOWNLOAD
    assert manifest.main_xbrl_path is not None
    assert manifest.main_xbrl_path.startswith("PublicDoc/")
    assert len(manifest.public_doc_files) > 0
    assert len(manifest.audit_doc_files) > 0
    assert len(manifest.xsd_paths) > 0
    assert len(manifest.ixbrl_paths) > 0
    assert len(manifest.linkbase_paths["lab"]) > 0
    assert len(manifest.linkbase_paths["pre"]) > 0
    assert len(manifest.linkbase_paths["cal"]) > 0
    assert len(manifest.linkbase_paths["def"]) > 0


def test_contexts_units_facts_extracted(sample_zip_path) -> None:
    scan_result = scan_archive(sample_zip_path)
    manifest = build_manifest(scan_result)
    assert manifest.main_xbrl_path is not None

    entry = scan_result.get_entry(manifest.main_xbrl_path)
    assert entry is not None

    with zipfile.ZipFile(sample_zip_path, mode="r") as zip_file:
        xml_bytes = zip_file.read(entry.original_path)
    root = etree.fromstring(
        xml_bytes,
        parser=etree.XMLParser(resolve_entities=False, no_network=True, recover=True, huge_tree=False),
    )

    contexts, dimensions = parse_contexts(root)
    units = parse_units(root)
    facts = parse_facts(root)

    assert len(contexts) >= 1
    assert len(dimensions) >= 1
    assert len(units) >= 1
    assert len(facts) >= 1

    assert any(fact.normalized_value_decimal is not None for fact in facts)
    assert any(fact.raw_text_value is not None for fact in facts)
    assert any(PurePosixPath(path).suffix == ".xbrl" for path in manifest.discovered_files)


def test_choose_main_xbrl_prefers_public_doc_shallow_depth() -> None:
    discovered_files = [
        "root/top.xbrl",
        "PublicDoc/deep/inside/main.xbrl",
        "PublicDoc/main.xbrl",
        "AuditDoc/audit.xbrl",
    ]
    public_doc_files = [path for path in discovered_files if path.startswith("PublicDoc/")]
    audit_doc_files = [path for path in discovered_files if path.startswith("AuditDoc/")]

    selection = choose_main_xbrl(discovered_files, public_doc_files, audit_doc_files)
    assert selection.main_xbrl_path == "PublicDoc/main.xbrl"
    assert selection.reason == "selected_public_doc_xbrl_by_depth_priority"


def test_choose_main_xbrl_fallback_uses_first_discovered_xbrl() -> None:
    discovered_files = [
        "misc/a.xbrl",
        "misc/deeper/b.xbrl",
        "AuditDoc/audit.xbrl",
    ]

    selection = choose_main_xbrl(
        discovered_files=discovered_files,
        public_doc_files=[],
        _audit_doc_files=["AuditDoc/audit.xbrl"],
    )
    assert selection.main_xbrl_path == "misc/a.xbrl"
    assert selection.reason == "selected_fallback_first_xbrl"

from __future__ import annotations

from common.db.base import Base
from common.db.models import (  # noqa: F401
    CompanyEdinetLink,
    CompanyMarketAttribute,
    CompanyMaster,
    EdinetFetchJob,
    EdinetListResponse,
    Filing,
    FilingDocument,
    FilingSource,
    FilingTypeMap,
    IngestLog,
    NormalizeLog,
    ParseLog,
    RequestLog,
    SourceArchive,
    XbrlContext,
    XbrlContextDimension,
    XbrlFact,
    XbrlUnit,
)


def test_metadata_contains_required_tables() -> None:
    table_names = set(Base.metadata.tables.keys())
    expected = {
        "company_master",
        "company_market_attributes",
        "company_edinet_links",
        "source_archives",
        "request_log",
        "ingest_log",
        "parse_log",
        "normalize_log",
        "filing_sources",
        "filings",
        "filing_documents",
        "xbrl_contexts",
        "xbrl_context_dimensions",
        "xbrl_units",
        "xbrl_facts",
        "edinet_list_responses",
        "edinet_fetch_jobs",
        "filing_type_map",
    }
    assert expected.issubset(table_names)

from __future__ import annotations

import importlib.util
from pathlib import Path

from sqlalchemy import create_engine, text


def _load_migration_module():
    migration_path = (
        Path(__file__).resolve().parents[3]
        / "alembic"
        / "versions"
        / "20260405_0005_edinet_curated_kpi_view.py"
    )
    spec = importlib.util.spec_from_file_location("alembic_20260405_0005", migration_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_curated_kpi_view_sql_contains_required_kpi_ids() -> None:
    module = _load_migration_module()

    assert module.VIEW_NAME == "edinet_facts_curated_kpi_v1"
    assert "jppfs_cor:NetAssets" in module.CREATE_VIEW_SQL
    assert "jppfs_cor:ProfitLoss" in module.CREATE_VIEW_SQL
    assert "jppfs_cor:NetSales" in module.CREATE_VIEW_SQL
    assert "jppfs_cor:OperatingIncome" in module.CREATE_VIEW_SQL
    assert "WHEN f.is_current_year THEN 'current'" in module.CREATE_VIEW_SQL
    assert "WHEN f.is_prior_year THEN 'prior'" in module.CREATE_VIEW_SQL
    assert "WHEN f.is_consolidated THEN 'consolidated'" in module.CREATE_VIEW_SQL


def test_curated_kpi_view_prefers_base_context_and_flags() -> None:
    module = _load_migration_module()
    engine = create_engine("sqlite+pysqlite:///:memory:")

    with engine.begin() as conn:
        conn.exec_driver_sql(
            """
            CREATE TABLE edinet_facts_raw_csv (
                doc_id TEXT NOT NULL,
                edinet_code TEXT,
                source_csv_path TEXT NOT NULL,
                element_id TEXT NOT NULL,
                item_name_ja TEXT NOT NULL,
                context_id TEXT NOT NULL,
                relative_year_label TEXT NOT NULL,
                consolidation_type TEXT NOT NULL,
                value_numeric NUMERIC,
                unit_label TEXT NOT NULL,
                is_numeric BOOLEAN NOT NULL,
                is_current_year BOOLEAN NOT NULL,
                is_prior_year BOOLEAN NOT NULL,
                is_consolidated BOOLEAN NOT NULL
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE edinet_list_responses (
                doc_id TEXT NOT NULL,
                target_date TEXT NOT NULL,
                edinet_code TEXT,
                form_code TEXT,
                doc_type_code TEXT,
                filing_type_key TEXT
            )
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO edinet_list_responses
            (doc_id, target_date, edinet_code, form_code, doc_type_code, filing_type_key)
            VALUES
            ('DOC1', '2026-03-31', 'E00001', '030000', '120', 'annual_securities_report')
            """
        )
        conn.exec_driver_sql(
            """
            INSERT INTO edinet_facts_raw_csv
            (doc_id, edinet_code, source_csv_path, element_id, item_name_ja, context_id, relative_year_label,
             consolidation_type, value_numeric, unit_label, is_numeric, is_current_year, is_prior_year, is_consolidated)
            VALUES
            ('DOC1', 'E00001', '/tmp/a.csv', 'jppfs_cor:NetAssets', '純資産',
             'CurrentYearInstant', '前々期末', '個別', 1000, '円', 1, 1, 0, 1),
            ('DOC1', 'E00001', '/tmp/a.csv', 'jppfs_cor:NetAssets', '純資産',
             'CurrentYearInstant_ShareholdersEquityMember', '前々期末', '個別', 111, '円', 1, 1, 0, 1),
            ('DOC1', 'E00001', '/tmp/a.csv', 'jppfs_cor:NetAssets', '純資産',
             'Prior1YearInstant_NonConsolidatedMember', '前期末', '連結', 900, '円', 1, 0, 1, 0),
            ('DOC1', 'E00001', '/tmp/a.csv', 'jppfs_cor:NetAssets', '純資産',
             'Prior1YearInstant_NonConsolidatedMember_CapitalStockMember', '前期末', '連結', 222, '円', 1, 0, 1, 0),
            ('DOC1', 'E00001', '/tmp/a.csv', 'jppfs_cor:ProfitLoss', '当期純利益',
             'CurrentYearDuration_NonConsolidatedMember', '前期', '連結', 123, '円', 1, 1, 0, 0)
            """
        )

        conn.exec_driver_sql(module.CREATE_VIEW_SQL)

        rows = conn.execute(
            text(
                """
                SELECT
                    kpi_name,
                    period_kind,
                    consolidation_kind,
                    value_numeric,
                    raw_context_id
                FROM edinet_facts_curated_kpi_v1
                ORDER BY kpi_name, period_kind, consolidation_kind
                """
            )
        ).mappings().all()

    assert rows == [
        {
            "kpi_name": "net_assets",
            "period_kind": "current",
            "consolidation_kind": "consolidated",
            "value_numeric": 1000,
            "raw_context_id": "CurrentYearInstant",
        },
        {
            "kpi_name": "net_assets",
            "period_kind": "prior",
            "consolidation_kind": "nonconsolidated",
            "value_numeric": 900,
            "raw_context_id": "Prior1YearInstant_NonConsolidatedMember",
        },
        {
            "kpi_name": "net_income",
            "period_kind": "current",
            "consolidation_kind": "nonconsolidated",
            "value_numeric": 123,
            "raw_context_id": "CurrentYearDuration_NonConsolidatedMember",
        },
    ]

"""add edinet curated kpi view v1

Revision ID: 20260405_0005
Revises: 20260330_0004
Create Date: 2026-04-05 00:00:00.000000
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260405_0005"
down_revision = "20260330_0004"
branch_labels = None
depends_on = None

VIEW_NAME = "edinet_facts_curated_kpi_v1"

DROP_VIEW_SQL = f"DROP VIEW IF EXISTS {VIEW_NAME};"

CREATE_VIEW_SQL = f"""
CREATE VIEW {VIEW_NAME} AS
WITH kpi_map AS (
    SELECT 'net_assets' AS kpi_name, 'jppfs_cor:NetAssets' AS element_id
    UNION ALL
    SELECT 'net_income', 'jppfs_cor:ProfitLoss'
    UNION ALL
    SELECT 'net_sales', 'jppfs_cor:NetSales'
    UNION ALL
    SELECT 'operating_income', 'jppfs_cor:OperatingIncome'
),
base AS (
    SELECT
        COALESCE(f.edinet_code, l.edinet_code) AS edinet_code,
        l.target_date,
        f.doc_id,
        l.form_code,
        l.doc_type_code,
        l.filing_type_key,
        CASE
            WHEN l.filing_type_key IS NOT NULL THEN l.filing_type_key
            WHEN l.form_code IS NOT NULL OR l.doc_type_code IS NOT NULL
                THEN COALESCE(l.form_code, '') || ':' || COALESCE(l.doc_type_code, '')
            ELSE NULL
        END AS doc_type,
        km.kpi_name,
        f.element_id AS source_element_id,
        f.item_name_ja AS source_item_name_ja,
        CASE
            WHEN f.is_current_year THEN 'current'
            WHEN f.is_prior_year THEN 'prior'
            ELSE 'other'
        END AS period_kind,
        CASE
            WHEN f.is_consolidated THEN 'consolidated'
            WHEN f.is_consolidated = false THEN 'nonconsolidated'
            ELSE 'other'
        END AS consolidation_kind,
        f.consolidation_type AS raw_consolidation_type,
        f.relative_year_label,
        f.value_numeric,
        f.unit_label AS unit,
        f.context_id AS raw_context_id,
        f.source_csv_path,
        CASE
            WHEN f.context_id LIKE '%Instant' OR f.context_id LIKE '%Duration' THEN 0
            WHEN f.context_id LIKE '%Instant_NonConsolidatedMember'
                OR f.context_id LIKE '%Duration_NonConsolidatedMember' THEN 1
            ELSE 2
        END AS context_priority,
        LENGTH(f.context_id) - LENGTH(REPLACE(f.context_id, '_', '')) AS context_underscore_count
    FROM edinet_facts_raw_csv AS f
    INNER JOIN kpi_map AS km
        ON km.element_id = f.element_id
    LEFT JOIN edinet_list_responses AS l
        ON l.doc_id = f.doc_id
    WHERE f.is_numeric = true
        AND f.value_numeric IS NOT NULL
),
ranked AS (
    SELECT
        base.*,
        ROW_NUMBER() OVER (
            PARTITION BY
                base.edinet_code,
                base.target_date,
                base.doc_id,
                base.doc_type,
                base.kpi_name,
                base.period_kind,
                base.consolidation_kind
            ORDER BY
                base.context_priority ASC,
                base.context_underscore_count ASC,
                LENGTH(base.raw_context_id) ASC,
                base.raw_context_id ASC
        ) AS row_priority
    FROM base
)
SELECT
    edinet_code,
    target_date,
    doc_id,
    form_code,
    doc_type_code,
    filing_type_key,
    doc_type,
    kpi_name,
    source_element_id,
    source_item_name_ja,
    period_kind,
    consolidation_kind,
    raw_consolidation_type,
    relative_year_label,
    value_numeric,
    unit,
    raw_context_id,
    source_csv_path
FROM ranked
WHERE row_priority = 1;
"""


def upgrade() -> None:
    op.execute(DROP_VIEW_SQL)
    op.execute(CREATE_VIEW_SQL)


def downgrade() -> None:
    op.execute(DROP_VIEW_SQL)

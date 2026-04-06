-- Verify curated KPI view (v1)
-- Usage example:
--   PGPASSWORD=postgres psql -h localhost -p 55432 -U postgres -d topix1000_disclosure -f docs/sql/verify_edinet_curated_kpi_v1.sql

-- 1) view exists
SELECT table_schema, table_name
FROM information_schema.views
WHERE table_schema = 'public'
  AND table_name = 'edinet_facts_curated_kpi_v1';

-- 2) row count and KPI coverage
SELECT
    COUNT(*) AS total_rows,
    COUNT(DISTINCT kpi_name) AS kpi_kinds,
    COUNT(DISTINCT doc_id) AS docs,
    COUNT(DISTINCT edinet_code) AS edinet_codes
FROM edinet_facts_curated_kpi_v1;

SELECT
    kpi_name,
    COUNT(*) AS rows,
    COUNT(*) FILTER (WHERE period_kind = 'current') AS current_rows,
    COUNT(*) FILTER (WHERE period_kind = 'prior') AS prior_rows,
    COUNT(*) FILTER (WHERE consolidation_kind = 'consolidated') AS consolidated_rows,
    COUNT(*) FILTER (WHERE consolidation_kind = 'nonconsolidated') AS nonconsolidated_rows
FROM edinet_facts_curated_kpi_v1
GROUP BY kpi_name
ORDER BY kpi_name;

-- 3) traceability checks
SELECT
    COUNT(*) FILTER (WHERE source_element_id IS NULL) AS missing_source_element_id,
    COUNT(*) FILTER (WHERE doc_id IS NULL) AS missing_doc_id,
    COUNT(*) FILTER (WHERE raw_context_id IS NULL) AS missing_raw_context_id
FROM edinet_facts_curated_kpi_v1;

-- 4) sample extract (company/date/doc_type x KPI)
SELECT
    edinet_code,
    target_date,
    doc_type,
    kpi_name,
    period_kind,
    consolidation_kind,
    value_numeric,
    unit,
    source_element_id,
    doc_id
FROM edinet_facts_curated_kpi_v1
WHERE kpi_name IN ('net_assets', 'net_income')
ORDER BY target_date DESC NULLS LAST, edinet_code, kpi_name, period_kind, consolidation_kind
LIMIT 40;

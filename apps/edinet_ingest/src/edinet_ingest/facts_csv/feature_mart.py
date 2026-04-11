from __future__ import annotations

import csv
import math
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from common.db.session import get_session_factory
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

OUTPUT_COLUMNS = [
    "doc_id",
    "revenue",
    "revenue_prev",
    "op_profit",
    "op_profit_prev",
    "net_income",
    "net_income_prev",
    "net_assets",
    "op_margin",
    "net_margin",
    "roe",
    "rev_growth",
    "op_growth",
    "net_income_growth",
    "log_revenue",
    "log_net_assets",
]

# Deterministic duplicate handling:
# If multiple raw rows match a single doc_id + slot, keep MAX(value_numeric).
FEATURE_MART_SQL = text(
    """
    SELECT
      f.doc_id AS doc_id,
      MAX(CASE WHEN f.element_id = 'jppfs_cor:NetSales' AND f.relative_year_label = '当期' THEN f.value_numeric END) AS revenue,
      MAX(CASE WHEN f.element_id = 'jppfs_cor:NetSales' AND f.relative_year_label = '前期' THEN f.value_numeric END) AS revenue_prev,
      MAX(CASE WHEN f.element_id = 'jppfs_cor:OperatingIncome' AND f.relative_year_label = '当期' THEN f.value_numeric END) AS op_profit,
      MAX(CASE WHEN f.element_id = 'jppfs_cor:OperatingIncome' AND f.relative_year_label = '前期' THEN f.value_numeric END) AS op_profit_prev,
      MAX(CASE WHEN f.element_id = 'jppfs_cor:ProfitLoss' AND f.relative_year_label = '当期' THEN f.value_numeric END) AS net_income,
      MAX(CASE WHEN f.element_id = 'jppfs_cor:ProfitLoss' AND f.relative_year_label = '前期' THEN f.value_numeric END) AS net_income_prev,
      MAX(CASE WHEN f.element_id = 'jppfs_cor:NetAssets' AND f.relative_year_label = '当期末' THEN f.value_numeric END) AS net_assets
    FROM edinet_facts_raw_csv AS f
    WHERE f.is_numeric = TRUE
      AND f.is_consolidated = TRUE
      AND f.consolidation_type = '連結'
      AND f.source_csv_path LIKE :date_path_pattern
    GROUP BY f.doc_id
    ORDER BY f.doc_id
    """
)


@dataclass(frozen=True, slots=True)
class BuildFeatureMartSummary:
    target_date: str
    output_path: str
    row_count: int
    duplicate_doc_id_count: int
    null_revenue_count: int
    null_op_profit_count: int
    null_net_income_count: int
    null_net_assets_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_feature_mart_for_date(
    target_date: date,
    output_path: Path,
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> BuildFeatureMartSummary:
    session_factory = session_factory or get_session_factory()
    resolved_output_path = output_path.expanduser().resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = _query_feature_rows(target_date=target_date, session_factory=session_factory)
    rows.sort(key=lambda row: row["doc_id"])

    with resolved_output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    doc_ids = [str(row["doc_id"]) for row in rows]
    duplicate_doc_id_count = len(doc_ids) - len(set(doc_ids))

    return BuildFeatureMartSummary(
        target_date=target_date.isoformat(),
        output_path=str(resolved_output_path),
        row_count=len(rows),
        duplicate_doc_id_count=duplicate_doc_id_count,
        null_revenue_count=sum(1 for row in rows if row["revenue"] is None),
        null_op_profit_count=sum(1 for row in rows if row["op_profit"] is None),
        null_net_income_count=sum(1 for row in rows if row["net_income"] is None),
        null_net_assets_count=sum(1 for row in rows if row["net_assets"] is None),
    )


def _query_feature_rows(
    *,
    target_date: date,
    session_factory: sessionmaker[Session],
) -> list[dict[str, Any]]:
    date_path_pattern = f"%/{target_date.strftime('%Y/%m/%d')}/%"

    with session_factory() as session:
        result = session.execute(FEATURE_MART_SQL, {"date_path_pattern": date_path_pattern})
        raw_rows = result.mappings().all()

    rows: list[dict[str, Any]] = []
    for raw_row in raw_rows:
        revenue = _as_decimal(raw_row["revenue"])
        revenue_prev = _as_decimal(raw_row["revenue_prev"])
        op_profit = _as_decimal(raw_row["op_profit"])
        op_profit_prev = _as_decimal(raw_row["op_profit_prev"])
        net_income = _as_decimal(raw_row["net_income"])
        net_income_prev = _as_decimal(raw_row["net_income_prev"])
        net_assets = _as_decimal(raw_row["net_assets"])

        row = {
            "doc_id": raw_row["doc_id"],
            "revenue": revenue,
            "revenue_prev": revenue_prev,
            "op_profit": op_profit,
            "op_profit_prev": op_profit_prev,
            "net_income": net_income,
            "net_income_prev": net_income_prev,
            "net_assets": net_assets,
            "op_margin": _safe_div(op_profit, revenue),
            "net_margin": _safe_div(net_income, revenue),
            "roe": _safe_div(net_income, net_assets),
            "rev_growth": _safe_growth(revenue, revenue_prev),
            "op_growth": _safe_growth(op_profit, op_profit_prev),
            "net_income_growth": _safe_growth(net_income, net_income_prev),
            "log_revenue": _safe_log(revenue),
            "log_net_assets": _safe_log(net_assets),
        }
        rows.append(row)

    return rows


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    return Decimal(value)


def _safe_div(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _safe_growth(current_value: Decimal | None, prev_value: Decimal | None) -> Decimal | None:
    ratio = _safe_div(current_value, prev_value)
    if ratio is None:
        return None
    return ratio - Decimal("1")


def _safe_log(value: Decimal | None) -> float | None:
    if value is None or value <= 0:
        return None
    return math.log(float(value))

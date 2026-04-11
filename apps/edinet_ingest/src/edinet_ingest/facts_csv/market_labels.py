from __future__ import annotations

import bisect
import csv
import math
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

OUTPUT_COLUMNS = [
    "doc_id",
    "edinet_code",
    "security_code",
    "event_date",
    "base_trade_date",
    "ret_1d",
    "ret_3d",
    "ret_5d",
]


@dataclass(frozen=True, slots=True)
class BuildMarketLabelsSummary:
    event_date: str
    output_path: str
    feature_mart_doc_count: int
    doc_id_with_edinet_code_count: int
    doc_id_with_security_code_count: int
    labeled_row_count: int
    dropped_missing_edinet_code_count: int
    dropped_missing_security_code_count: int
    dropped_missing_price_count: int
    null_ret_1d_count: int
    null_ret_3d_count: int
    null_ret_5d_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_market_labels(
    *,
    feature_mart_path: Path,
    doc_edinet_map_path: Path,
    code_map_path: Path,
    prices_path: Path,
    event_date: date,
    output_path: Path,
) -> BuildMarketLabelsSummary:
    _ensure_file_exists(feature_mart_path)
    _ensure_file_exists(doc_edinet_map_path)
    _ensure_file_exists(code_map_path)
    _ensure_file_exists(prices_path)

    feature_docs = _load_feature_mart_doc_ids(feature_mart_path)
    doc_to_edinet = _load_doc_edinet_map(doc_edinet_map_path)
    edinet_to_security = _load_code_map(code_map_path)
    prices_by_security = _load_prices(prices_path)

    rows: list[dict[str, Any]] = []
    dropped_missing_edinet_code_count = 0
    dropped_missing_security_code_count = 0
    dropped_missing_price_count = 0
    doc_id_with_edinet_code_count = 0
    doc_id_with_security_code_count = 0

    for doc_id in sorted(feature_docs):
        edinet_code = doc_to_edinet.get(doc_id)
        if edinet_code is None:
            dropped_missing_edinet_code_count += 1
            continue
        doc_id_with_edinet_code_count += 1

        security_code = edinet_to_security.get(edinet_code)
        if security_code is None:
            dropped_missing_security_code_count += 1
            continue
        doc_id_with_security_code_count += 1

        series = prices_by_security.get(security_code)
        if series is None:
            dropped_missing_price_count += 1
            continue

        dates, prices = series
        base_idx = bisect.bisect_left(dates, event_date)
        if base_idx >= len(dates):
            dropped_missing_price_count += 1
            continue

        base_price = prices[base_idx]
        if base_price == 0.0:
            dropped_missing_price_count += 1
            continue

        row = {
            "doc_id": doc_id,
            "edinet_code": edinet_code,
            "security_code": security_code,
            "event_date": event_date.isoformat(),
            "base_trade_date": dates[base_idx].isoformat(),
            "ret_1d": _safe_return(prices, base_idx, 1),
            "ret_3d": _safe_return(prices, base_idx, 3),
            "ret_5d": _safe_return(prices, base_idx, 5),
        }
        rows.append(row)

    resolved_output_path = output_path.expanduser().resolve()
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    if len(feature_docs) != (
        len(rows)
        + dropped_missing_edinet_code_count
        + dropped_missing_security_code_count
        + dropped_missing_price_count
    ):
        raise RuntimeError("summary accounting mismatch in market label construction")

    return BuildMarketLabelsSummary(
        event_date=event_date.isoformat(),
        output_path=str(resolved_output_path),
        feature_mart_doc_count=len(feature_docs),
        doc_id_with_edinet_code_count=doc_id_with_edinet_code_count,
        doc_id_with_security_code_count=doc_id_with_security_code_count,
        labeled_row_count=len(rows),
        dropped_missing_edinet_code_count=dropped_missing_edinet_code_count,
        dropped_missing_security_code_count=dropped_missing_security_code_count,
        dropped_missing_price_count=dropped_missing_price_count,
        null_ret_1d_count=sum(1 for row in rows if row["ret_1d"] is None),
        null_ret_3d_count=sum(1 for row in rows if row["ret_3d"] is None),
        null_ret_5d_count=sum(1 for row in rows if row["ret_5d"] is None),
    )


def _ensure_file_exists(path: Path) -> None:
    resolved = path.expanduser().resolve()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(f"file not found: {resolved}")


def _load_feature_mart_doc_ids(path: Path) -> set[str]:
    with path.expanduser().resolve().open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        if "doc_id" not in headers:
            raise ValueError("feature_mart csv missing required header: doc_id")

        doc_ids: set[str] = set()
        for row_num, row in enumerate(reader, start=2):
            doc_id = (row.get("doc_id") or "").strip()
            if not doc_id:
                raise ValueError(f"feature_mart row {row_num}: blank doc_id")
            if doc_id in doc_ids:
                raise ValueError(f"feature_mart duplicate doc_id: {doc_id}")
            doc_ids.add(doc_id)
    return doc_ids


def _load_doc_edinet_map(path: Path) -> dict[str, str]:
    required_headers = {"doc_id", "edinet_code"}
    mapping: dict[str, str] = {}
    with path.expanduser().resolve().open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        if not required_headers.issubset(set(headers)):
            raise ValueError("doc_edinet_map csv missing required headers: doc_id,edinet_code")

        # Deterministic conflict handling:
        # if one doc_id maps to multiple non-empty edinet_code values, keep MIN(edinet_code).
        for row in reader:
            doc_id = (row.get("doc_id") or "").strip()
            edinet_code = (row.get("edinet_code") or "").strip()
            if not doc_id or not edinet_code:
                continue
            current = mapping.get(doc_id)
            if current is None or edinet_code < current:
                mapping[doc_id] = edinet_code
    return mapping


def _load_code_map(path: Path) -> dict[str, str]:
    required_headers = {"edinet_code", "security_code"}
    mapping: dict[str, str] = {}
    with path.expanduser().resolve().open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        if not required_headers.issubset(set(headers)):
            raise ValueError("code_map csv missing required headers: edinet_code,security_code")

        # Deterministic conflict handling:
        # if one edinet_code maps to multiple non-empty security_code values, keep MIN(security_code).
        for row in reader:
            edinet_code = (row.get("edinet_code") or "").strip()
            security_code = (row.get("security_code") or "").strip()
            if not edinet_code or not security_code:
                continue
            current = mapping.get(edinet_code)
            if current is None or security_code < current:
                mapping[edinet_code] = security_code
    return mapping


def _load_prices(path: Path) -> dict[str, tuple[list[date], list[float]]]:
    grouped: dict[str, list[tuple[date, float]]] = {}
    seen_keys: set[tuple[str, date]] = set()

    with path.expanduser().resolve().open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        if "security_code" not in headers or "date" not in headers:
            raise ValueError("prices csv missing required headers: security_code,date")
        if "adj_close" in headers:
            price_column = "adj_close"
        elif "close" in headers:
            price_column = "close"
        else:
            raise ValueError("prices csv must include adj_close or close")

        for row_num, row in enumerate(reader, start=2):
            security_code = (row.get("security_code") or "").strip()
            date_str = (row.get("date") or "").strip()
            if not security_code or not date_str:
                continue

            try:
                trading_date = date.fromisoformat(date_str)
            except ValueError as exc:
                raise ValueError(f"prices row {row_num}: invalid date '{date_str}'") from exc

            key = (security_code, trading_date)
            if key in seen_keys:
                raise ValueError(
                    "prices csv duplicate (security_code,date): "
                    f"{security_code},{trading_date.isoformat()}"
                )
            seen_keys.add(key)

            raw_price = (row.get(price_column) or "").strip()
            parsed_price = _parse_price(raw_price)
            if parsed_price is None:
                continue
            grouped.setdefault(security_code, []).append((trading_date, parsed_price))

    prices_by_security: dict[str, tuple[list[date], list[float]]] = {}
    for security_code, points in grouped.items():
        points.sort(key=lambda item: item[0])
        dates = [item[0] for item in points]
        prices = [item[1] for item in points]
        prices_by_security[security_code] = (dates, prices)
    return prices_by_security


def _parse_price(raw_price: str) -> float | None:
    if not raw_price:
        return None
    try:
        parsed = float(raw_price)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return parsed


def _safe_return(prices: list[float], base_idx: int, offset: int) -> float | None:
    target_idx = base_idx + offset
    if target_idx >= len(prices):
        return None
    base_price = prices[base_idx]
    return prices[target_idx] / base_price - 1.0

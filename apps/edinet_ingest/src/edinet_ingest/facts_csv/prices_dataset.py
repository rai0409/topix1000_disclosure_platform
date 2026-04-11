from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Any

OUTPUT_COLUMNS = ["security_code", "date", "close", "adj_close"]
REQUIRED_HEADERS = {"security_code", "date"}
PRICE_HEADERS = {"close", "adj_close"}
ISO_DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")


@dataclass(frozen=True, slots=True)
class BuildPricesDatasetSummary:
    input_path: str
    output_path: str
    input_row_count: int
    valid_row_count: int
    dropped_missing_security_code_count: int
    dropped_missing_date_count: int
    dropped_missing_price_count: int
    duplicate_row_count: int
    conflicting_security_date_count: int
    output_row_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_prices_dataset(
    *,
    input_path: Path,
    output_path: Path,
) -> BuildPricesDatasetSummary:
    resolved_input_path = input_path.expanduser().resolve()
    resolved_output_path = output_path.expanduser().resolve()
    if not resolved_input_path.exists() or not resolved_input_path.is_file():
        raise FileNotFoundError(f"file not found: {resolved_input_path}")

    input_row_count = 0
    valid_row_count = 0
    dropped_missing_security_code_count = 0
    dropped_missing_date_count = 0
    dropped_missing_price_count = 0
    duplicate_row_count = 0

    candidates_by_key: dict[tuple[str, str], set[tuple[str, str]]] = {}

    with resolved_input_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        header_set = set(headers)
        if not REQUIRED_HEADERS.issubset(header_set):
            raise ValueError("input csv missing required headers: security_code,date")
        if not (PRICE_HEADERS & header_set):
            raise ValueError("input csv missing required headers: close or adj_close")

        for row_num, row in enumerate(reader, start=2):
            input_row_count += 1
            if _is_completely_blank_row(row):
                continue

            security_code = (row.get("security_code") or "").strip()
            if not security_code:
                dropped_missing_security_code_count += 1
                continue

            date_str = (row.get("date") or "").strip()
            if not date_str:
                dropped_missing_date_count += 1
                continue
            _validate_iso_date(date_str, row_num=row_num)

            close = (row.get("close") or "").strip()
            adj_close = (row.get("adj_close") or "").strip()
            if not close and not adj_close:
                dropped_missing_price_count += 1
                continue

            valid_row_count += 1
            key = (security_code, date_str)
            price_pair = (close, adj_close)
            key_candidates = candidates_by_key.setdefault(key, set())
            if price_pair in key_candidates:
                duplicate_row_count += 1
                continue
            key_candidates.add(price_pair)

    conflicting_security_date_count = sum(
        1 for key_candidates in candidates_by_key.values() if len(key_candidates) > 1
    )

    output_rows: list[dict[str, str]] = []
    for (security_code, date_str), key_candidates in candidates_by_key.items():
        close, adj_close = min(key_candidates)
        output_rows.append(
            {
                "security_code": security_code,
                "date": date_str,
                "close": close,
                "adj_close": adj_close,
            }
        )
    output_rows.sort(key=lambda row: (row["security_code"], row["date"]))

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    return BuildPricesDatasetSummary(
        input_path=str(resolved_input_path),
        output_path=str(resolved_output_path),
        input_row_count=input_row_count,
        valid_row_count=valid_row_count,
        dropped_missing_security_code_count=dropped_missing_security_code_count,
        dropped_missing_date_count=dropped_missing_date_count,
        dropped_missing_price_count=dropped_missing_price_count,
        duplicate_row_count=duplicate_row_count,
        conflicting_security_date_count=conflicting_security_date_count,
        output_row_count=len(output_rows),
    )


def _is_completely_blank_row(row: dict[str, str | None]) -> bool:
    return all(not (value or "").strip() for value in row.values())


def _validate_iso_date(date_str: str, *, row_num: int) -> None:
    if not ISO_DATE_PATTERN.fullmatch(date_str):
        raise ValueError(f"prices row {row_num}: invalid date '{date_str}'")
    try:
        date.fromisoformat(date_str)
    except ValueError as exc:
        raise ValueError(f"prices row {row_num}: invalid date '{date_str}'") from exc

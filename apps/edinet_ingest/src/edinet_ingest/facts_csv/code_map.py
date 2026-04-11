from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

OUTPUT_COLUMNS = ["edinet_code", "security_code"]
REQUIRED_HEADERS = {"edinet_code", "security_code"}


@dataclass(frozen=True, slots=True)
class BuildCodeMapSummary:
    input_path: str
    output_path: str
    input_row_count: int
    valid_row_count: int
    dropped_missing_code_count: int
    duplicate_pair_count: int
    conflicting_edinet_code_count: int
    output_row_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_code_map(
    *,
    input_path: Path,
    output_path: Path,
) -> BuildCodeMapSummary:
    resolved_input_path = input_path.expanduser().resolve()
    resolved_output_path = output_path.expanduser().resolve()
    if not resolved_input_path.exists() or not resolved_input_path.is_file():
        raise FileNotFoundError(f"file not found: {resolved_input_path}")

    input_row_count = 0
    valid_row_count = 0
    dropped_missing_code_count = 0
    duplicate_pair_count = 0
    seen_pairs: set[tuple[str, str]] = set()
    edinet_to_candidates: dict[str, set[str]] = {}

    with resolved_input_path.open("r", encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        headers = reader.fieldnames or []
        if not REQUIRED_HEADERS.issubset(set(headers)):
            raise ValueError("input csv missing required headers: edinet_code,security_code")

        for row in reader:
            input_row_count += 1
            if _is_completely_blank_row(row):
                continue

            edinet_code = (row.get("edinet_code") or "").strip()
            security_code = (row.get("security_code") or "").strip()
            if not edinet_code or not security_code:
                dropped_missing_code_count += 1
                continue

            valid_row_count += 1
            pair = (edinet_code, security_code)
            if pair in seen_pairs:
                duplicate_pair_count += 1
                continue
            seen_pairs.add(pair)
            edinet_to_candidates.setdefault(edinet_code, set()).add(security_code)

    conflicting_edinet_code_count = sum(
        1 for codes in edinet_to_candidates.values() if len(codes) > 1
    )
    output_rows = [
        {
            "edinet_code": edinet_code,
            "security_code": min(security_codes),
        }
        for edinet_code, security_codes in edinet_to_candidates.items()
    ]
    output_rows.sort(key=lambda row: (row["edinet_code"], row["security_code"]))

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    with resolved_output_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(output_rows)

    return BuildCodeMapSummary(
        input_path=str(resolved_input_path),
        output_path=str(resolved_output_path),
        input_row_count=input_row_count,
        valid_row_count=valid_row_count,
        dropped_missing_code_count=dropped_missing_code_count,
        duplicate_pair_count=duplicate_pair_count,
        conflicting_edinet_code_count=conflicting_edinet_code_count,
        output_row_count=len(output_rows),
    )


def _is_completely_blank_row(row: dict[str, str | None]) -> bool:
    return all(not (value or "").strip() for value in row.values())

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from edinet_ingest.facts_csv.market_labels import build_market_labels


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic event-level market labels CSV for one event date"
    )
    parser.add_argument("--feature-mart", required=True, help="Path to feature_mart.csv")
    parser.add_argument("--doc-edinet-map", required=True, help="Path to doc_edinet_map.csv")
    parser.add_argument("--code-map", required=True, help="Path to edinet_code->security_code csv")
    parser.add_argument("--prices", required=True, help="Path to prices csv")
    parser.add_argument("--event-date", required=True, help="Event date in YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    try:
        event_date = date.fromisoformat(args.event_date)
    except ValueError as exc:
        print(f"invalid argument: {exc}", file=sys.stderr)
        return 2

    try:
        summary = build_market_labels(
            feature_mart_path=Path(args.feature_mart),
            doc_edinet_map_path=Path(args.doc_edinet_map),
            code_map_path=Path(args.code_map),
            prices_path=Path(args.prices),
            event_date=event_date,
            output_path=Path(args.out),
        )
    except Exception as exc:
        print(f"build_market_labels failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

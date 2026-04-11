from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from edinet_ingest.facts_csv.doc_edinet_map import build_doc_edinet_map_for_date


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic doc_id -> edinet_code mapping CSV for one date"
    )
    parser.add_argument("--date", required=True, help="Target date in YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    try:
        target_date = date.fromisoformat(args.date)
        summary = build_doc_edinet_map_for_date(target_date, output_path=Path(args.out))
    except ValueError as exc:
        print(f"invalid argument: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"build_doc_edinet_map failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

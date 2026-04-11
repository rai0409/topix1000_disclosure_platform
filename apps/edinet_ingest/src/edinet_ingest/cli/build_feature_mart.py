from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from edinet_ingest.facts_csv.feature_mart import build_feature_mart_for_date


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build event-level EDINET feature mart CSV for one date"
    )
    parser.add_argument("--date", required=True, help="Target date in YYYY-MM-DD")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    try:
        target_date = date.fromisoformat(args.date)
        summary = build_feature_mart_for_date(target_date, output_path=Path(args.out))
    except ValueError as exc:
        print(f"invalid argument: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"build_feature_mart failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

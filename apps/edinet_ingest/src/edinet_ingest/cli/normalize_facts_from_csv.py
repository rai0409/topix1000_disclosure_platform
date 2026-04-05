from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from edinet_ingest.facts_csv.service import normalize_facts_for_date


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Normalize EDINET main facts CSV and persist canonical facts"
    )
    parser.add_argument("--date", required=True, help="Target date in YYYY-MM-DD")
    args = parser.parse_args()

    try:
        target_date = date.fromisoformat(args.date)
        summary = normalize_facts_for_date(target_date)
    except ValueError as exc:
        print(f"invalid argument: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"normalize_facts_from_csv failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

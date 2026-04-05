from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from edinet_ingest.downloader.errors import EdinetApiKeyMissingError
from edinet_ingest.downloader.scheduler import run_backfill


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill EDINET list+document fetch across date range")
    parser.add_argument("--from", dest="date_from", required=True, help="From date in YYYY-MM-DD")
    parser.add_argument("--to", dest="date_to", required=True, help="To date in YYYY-MM-DD")
    args = parser.parse_args()

    try:
        date_from = date.fromisoformat(args.date_from)
        date_to = date.fromisoformat(args.date_to)
        summary = run_backfill(date_from=date_from, date_to=date_to)
    except ValueError as exc:
        print(f"invalid argument: {exc}", file=sys.stderr)
        return 2
    except EdinetApiKeyMissingError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"backfill failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

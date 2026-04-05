from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from edinet_ingest.downloader.errors import EdinetApiKeyMissingError
from edinet_ingest.downloader.service import fetch_documents_for_date


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch EDINET documents and persist raw files")
    parser.add_argument("--date", required=True, help="Target date in YYYY-MM-DD")
    args = parser.parse_args()

    try:
        target_date = date.fromisoformat(args.date)
        summary = fetch_documents_for_date(target_date, ensure_list=True)
    except ValueError as exc:
        print(f"invalid argument: {exc}", file=sys.stderr)
        return 2
    except EdinetApiKeyMissingError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"fetch_docs failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

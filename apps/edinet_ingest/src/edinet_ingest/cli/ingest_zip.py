from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from edinet_ingest.ingest.service import ingest_zip_archive


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest local EDINET ZIP into database")
    parser.add_argument("--zip", required=True, help="Path to local EDINET ZIP file")
    args = parser.parse_args()

    try:
        summary = ingest_zip_archive(Path(args.zip))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"ingest validation failed: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ingest failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

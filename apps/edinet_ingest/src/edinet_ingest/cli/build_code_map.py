from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from edinet_ingest.facts_csv.code_map import build_code_map


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic edinet_code -> security_code mapping CSV"
    )
    parser.add_argument("--input", required=True, help="Input source mapping CSV path")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    try:
        summary = build_code_map(
            input_path=Path(args.input),
            output_path=Path(args.out),
        )
    except Exception as exc:
        print(f"build_code_map failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

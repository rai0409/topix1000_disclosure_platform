from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from edinet_ingest.facts_csv.prices_dataset import build_prices_dataset


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build deterministic prices dataset CSV for market label construction"
    )
    parser.add_argument("--input", required=True, help="Input source prices CSV path")
    parser.add_argument("--out", required=True, help="Output CSV path")
    args = parser.parse_args()

    try:
        summary = build_prices_dataset(
            input_path=Path(args.input),
            output_path=Path(args.out),
        )
    except Exception as exc:
        print(f"build_prices_dataset failed: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(summary.to_dict(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

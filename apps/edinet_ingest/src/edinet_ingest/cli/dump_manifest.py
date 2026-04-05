from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from edinet_ingest.ingest.service import generate_manifest_from_zip


def main() -> int:
    parser = argparse.ArgumentParser(description="Dump EDINET ZIP manifest as JSON")
    parser.add_argument("--zip", required=True, help="Path to local EDINET ZIP file")
    parser.add_argument(
        "--output",
        required=False,
        help="Optional output path for manifest JSON",
    )
    args = parser.parse_args()

    try:
        manifest = generate_manifest_from_zip(Path(args.zip))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"failed to generate manifest: {exc}", file=sys.stderr)
        return 1

    payload = json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

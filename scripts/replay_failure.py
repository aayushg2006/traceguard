"""Replay a saved TraceGuard failure bundle."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.replay.bundle_store import list_bundles
from security.replay.replay_runner import replay_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle")
    parser.add_argument("--output", default="reports/replay-report.json")
    parser.add_argument("--target-url")
    parser.add_argument("--list", action="store_true", dest="list_bundles")
    args = parser.parse_args()
    if args.list_bundles:
        for bundle in list_bundles():
            print(bundle)
        return 0
    if not args.bundle:
        parser.error("--bundle is required unless --list is used")
    result = replay_bundle(args.bundle, args.target_url)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Replay outcome: {result.replay_outcome.value}")
    print(f"Replay report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

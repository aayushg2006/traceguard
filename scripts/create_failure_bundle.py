"""Create a sanitized failure bundle from a security report result."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.replay.bundle_store import save_bundle
from security.replay.failure_bundle import FailureBundleError, bundle_from_report_result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--test-id", required=True)
    parser.add_argument("--output-root", default="reports/failures")
    parser.add_argument("--target-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    try:
        report = json.loads(Path(args.report).read_text(encoding="utf-8"))
        result = next(item for item in report.get("results", []) if item.get("test_id") == args.test_id)
        bundle = bundle_from_report_result(result, report, target_url=args.target_url)
        path = save_bundle(bundle, args.output_root)
    except (FileNotFoundError, json.JSONDecodeError, StopIteration, FailureBundleError) as exc:
        parser.error(f"Unable to create failure bundle: {exc}")
    print(f"Bundle: {path}")
    print(f"Bundle ID: {bundle.bundle_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Create a baseline from a Phase 2 security report."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.regression.baseline import BaselineError, create_baseline, load_scan_report, save_baseline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true", help="Explicitly overwrite an existing baseline")
    args = parser.parse_args()
    try:
        baseline = create_baseline(load_scan_report(args.report), source_report=args.report)
        path = save_baseline(baseline, args.output, overwrite=args.force)
    except BaselineError as exc:
        parser.error(str(exc))
    print(f"Created baseline {baseline.baseline_id} from {baseline.source_scan_id}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

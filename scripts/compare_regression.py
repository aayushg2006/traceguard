"""Compare a current Phase 2 report with a stored baseline."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.regression.baseline import BaselineError
from security.regression.regression_engine import compare_files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--output")
    parser.add_argument("--config", default="config/security.yaml")
    args = parser.parse_args()
    try:
        report = compare_files(args.baseline, args.current, args.config)
    except BaselineError as exc:
        parser.error(str(exc))
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        print(f"Regression report: {output}")
    else:
        print(payload, end="")
    print(f"Regression status: {report['regression']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

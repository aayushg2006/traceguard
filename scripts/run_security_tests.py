"""Run TraceGuard's complete Phase 2 security suite."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.runner.security_runner import SecurityRunner, discover_tests, write_report
from security.target import ApiTargetApplication


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=("prompt_injection", "rag_injection", "data_leakage", "tool_abuse"))
    parser.add_argument("--target", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="reports/security-report.json")
    args = parser.parse_args()

    target = ApiTargetApplication(args.target)
    selected = discover_tests(args.category)
    results = SecurityRunner(target).run(selected)
    report = SecurityRunner(target).report(results)
    output = write_report(report, args.output)
    scores = report["scores"]
    print(f"Security tests: {scores['overall']['passed']}/{scores['overall']['total']} passed")
    print(f"Overall score: {scores['overall']['score']:.2f}")
    print(f"Report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

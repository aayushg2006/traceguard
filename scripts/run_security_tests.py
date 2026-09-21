"""Run TraceGuard's security suite or a selected set of categories."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.runner.security_runner import SecurityRunner, discover_tests, write_report
from security.target import ApiTargetApplication


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--category", choices=("prompt_injection", "rag_injection", "data_leakage", "tool_abuse"))
    parser.add_argument("--categories", help="Comma-separated security-test categories")
    parser.add_argument("--target", default="http://127.0.0.1:8000")
    parser.add_argument("--output", default="reports/security-report.json")
    args = parser.parse_args()

    target = ApiTargetApplication(args.target)
    categories = [item.strip() for item in args.categories.split(",")] if args.categories else None
    if args.category and categories:
        parser.error("use either --category or --categories, not both")
    if categories:
        valid_categories = {test.category for test in discover_tests()}
        invalid = sorted(set(categories) - valid_categories)
        if invalid:
            parser.error(f"unknown security-test categories: {', '.join(invalid)}")
        allowed = set(categories)
        selected = [test for test in discover_tests() if test.category in allowed]
    else:
        selected = discover_tests(args.category)
    runner = SecurityRunner(target)
    results = runner.run(selected)
    report = runner.report(results)
    report["execution"]["selection_mode"] = "TARGETED" if categories or args.category else "FULL"
    report["execution"]["selected_categories"] = sorted({test.category for test in selected})
    output = write_report(report, args.output)
    scores = report["scores"]
    print(f"Security tests: {scores['overall']['passed']}/{scores['overall']['total']} passed")
    print(f"Overall score: {scores['overall']['score']:.2f}")
    print(f"Report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

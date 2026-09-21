"""Analyze Git changes and select security-test categories."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.analyzer.change_analyzer import ChangeAnalysisError
from security.analyzer.test_selector import analyze_changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True, help="Base Git revision")
    parser.add_argument("--current", required=True, help="Current Git revision")
    parser.add_argument("--repository", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        analysis = analyze_changes(args.base, args.current, args.repository)
    except ChangeAnalysisError as exc:
        parser.error(str(exc))
    payload = analysis.model_dump(mode="json")
    print("TraceGuard Change Analysis")
    print("--------------------------")
    print(f"Base: {analysis.base}")
    print(f"Current: {analysis.current}")
    print(f"Changed files: {len(analysis.changed_files)}")
    for change in analysis.changed_files:
        print(change.path)
        if change.old_path:
            print(f"  Previous path: {change.old_path}")
        print(f"  Change type: {change.change_type}")
        print(f"  Component: {change.component}")
        print(f"  Impact: {', '.join(change.security_impact) or 'none'}")
    print(f"Selection mode: {analysis.selection.mode.value}")
    print(f"Selected categories: {', '.join(analysis.selection.tests) or 'none'}")
    print(f"Reason: {analysis.selection.reason}")
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"Analysis report: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run isolated TraceGuard mutation tests."""

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.mutation.mutation_registry import get_mutation, list_mutations
from security.mutation.mutation_runner import MutationRunner, mutation_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mutation", help="Run one mutation ID")
    parser.add_argument("--output", default="reports/mutation-report.json")
    parser.add_argument("--repository", default=".")
    parser.add_argument("--list", action="store_true", dest="list_mutations")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    if args.list_mutations:
        for mutation in list_mutations():
            availability = "available" if mutation.available else "unavailable"
            print(f"{mutation.mutation_id}: {mutation.name} [{availability}] - {mutation.description}")
        return 0
    try:
        selected = [get_mutation(args.mutation)] if args.mutation else list_mutations()
    except KeyError as exc:
        parser.error(str(exc))
    results = MutationRunner(args.repository).run(selected)
    report = mutation_report(results)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Mutations: {report['total_mutations']}")
    print(f"Detected: {report['detected_mutations']}")
    print(f"Survived: {report['survived_mutations']}")
    print(f"Mutation detection rate: {report['mutation_detection_rate']:.2f}%")
    print(f"Report: {output}")
    if args.verbose:
        for result in report["mutations"]:
            print(f"{result['mutation_id']}: {result['status']} - {result['evidence']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Evaluate TraceGuard reports against the deterministic policy gate."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from security.policy.policy_engine import PolicyInputError, evaluate_policy
from security.policy.policy_loader import PolicyConfigError, load_policy
from security.policy.policy_result import Decision

EXIT_CODES = {Decision.ALLOW: 0, Decision.BLOCK: 10, Decision.ERROR: 20}


def _load(path: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not path:
        return None, None
    try:
        return json.loads(Path(path).read_text(encoding="utf-8")), path
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise PolicyInputError(f"Unable to load JSON report {path}: {exc}") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--security-report")
    parser.add_argument("--regression-report")
    parser.add_argument("--mutation-report")
    parser.add_argument("--replay-report")
    parser.add_argument("--impact-report")
    parser.add_argument("--policy", default="config/policy.yaml")
    parser.add_argument("--output", default="reports/policy-result.json")
    args = parser.parse_args()
    try:
        policy = load_policy(args.policy)
        security, security_ref = _load(args.security_report)
        regression, regression_ref = _load(args.regression_report)
        mutation, mutation_ref = _load(args.mutation_report)
        replay, replay_ref = _load(args.replay_report)
        impact, impact_ref = _load(args.impact_report)
        result = evaluate_policy(security, regression_report=regression, mutation_report=mutation, replay_report=replay, impact_report=impact, policy=policy, input_references={"security_report": security_ref, "regression_report": regression_ref, "mutation_report": mutation_ref, "replay_report": replay_ref, "impact_report": impact_ref, "policy": args.policy})
    except (PolicyConfigError, PolicyInputError, OSError) as exc:
        print(f"Policy ERROR: {exc}", file=sys.stderr)
        return EXIT_CODES[Decision.ERROR]
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Policy decision: {result.decision.value}")
    print(f"Triggered rules: {', '.join(result.triggered_rules) or 'none'}")
    print(f"Report: {output}")
    return EXIT_CODES[result.decision]


if __name__ == "__main__":
    raise SystemExit(main())

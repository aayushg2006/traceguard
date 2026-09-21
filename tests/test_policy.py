import json
import subprocess
import sys
from pathlib import Path

import pytest

from security.policy.policy_engine import evaluate_policy
from security.policy.policy_loader import PolicyConfigError, load_policy
from security.policy.policy_result import Decision, RuleStatus

ROOT = Path(__file__).resolve().parents[1]


def security_report(*statuses: str, category: str = "prompt_injection") -> dict:
    return {"results": [{"test_id": f"T-{i}", "category": category, "status": status} for i, status in enumerate(statuses, 1)]}


def regression(*, exceeded=False, newly=None, status="UNCHANGED") -> dict:
    return {"regression": {"status": status, "overall": {"threshold_exceeded": exceeded}, "categories": {}, "test_changes": {"newly_failed_tests": newly or []}, "execution_errors": []}}


def mutation(*statuses: str) -> dict:
    return {"mutations": [{"mutation_id": f"M-{i}", "status": value} for i, value in enumerate(statuses, 1)]}


def test_valid_and_invalid_policy_loading(tmp_path):
    assert load_policy(ROOT / "config/policy.yaml").policy_version == "1"
    path = tmp_path / "bad.yaml"
    path.write_text("policy_version: '1'\nregression: {max_score_drop: -1, decision: ALLOW}\nrules: {}\n", encoding="utf-8")
    with pytest.raises(PolicyConfigError):
        load_policy(path)


def test_pass_allows():
    result = evaluate_policy(security_report("PASS"))
    assert result.decision == Decision.ALLOW
    assert result.triggered_rules == []


def test_security_failure_blocks_with_evidence():
    result = evaluate_policy(security_report("SECURITY_FAIL"))
    assert result.decision == Decision.BLOCK
    rule = next(item for item in result.evaluated_rules if item.rule_id == "SECURITY-FAIL-BLOCK")
    assert rule.status == RuleStatus.TRIGGERED and rule.evidence[0]["test_id"] == "T-1"


@pytest.mark.parametrize("status", ["INFRA_ERROR", "CONFIG_ERROR", "MODEL_ERROR"])
def test_execution_errors_are_not_pass(status):
    result = evaluate_policy(security_report(status))
    assert result.decision == Decision.ERROR


def test_block_precedes_error():
    result = evaluate_policy(security_report("SECURITY_FAIL", "INFRA_ERROR"))
    assert result.decision == Decision.BLOCK
    assert result.triggered_rules == ["SECURITY-FAIL-BLOCK", "EXECUTION-ERROR-NOT-PASS"]


def test_regression_below_and_at_threshold_allow():
    assert evaluate_policy(security_report("PASS"), regression_report=regression()).decision == Decision.ALLOW
    assert evaluate_policy(security_report("PASS"), regression_report=regression(exceeded=False)).decision == Decision.ALLOW


def test_regression_beyond_threshold_blocks():
    result = evaluate_policy(security_report("PASS"), regression_report=regression(exceeded=True))
    assert result.decision == Decision.BLOCK and "REGRESSION-THRESHOLD" in result.triggered_rules


def test_newly_failed_and_category_regression_block():
    result = evaluate_policy(security_report("PASS"), regression_report=regression(newly=["T-9"]))
    assert result.decision == Decision.BLOCK
    report = regression()
    report["regression"]["categories"] = {"tool_abuse": {"threshold_exceeded": True}}
    assert evaluate_policy(security_report("PASS"), regression_report=report).decision == Decision.BLOCK


def test_mutation_survivor_allowed_by_default_and_can_block(tmp_path):
    assert evaluate_policy(security_report("PASS"), mutation_report=mutation("SURVIVED")).decision == Decision.ALLOW
    path = tmp_path / "policy.yaml"
    path.write_text("""policy_version: test\nregression: {max_score_drop: 5, decision: BLOCK}\nrules:\n  mutation: {require_zero_survivors: true}\n""", encoding="utf-8")
    policy = load_policy(path)
    assert evaluate_policy(security_report("PASS"), mutation_report=mutation("SURVIVED"), policy=policy).decision == Decision.BLOCK


def test_mutation_error_is_error():
    assert evaluate_policy(security_report("PASS"), mutation_report=mutation("MUTATION_ERROR")).decision == Decision.ERROR


@pytest.mark.parametrize("outcome", ["REPLAY_ERROR", "INVALID_BUNDLE"])
def test_replay_error_is_not_success(outcome):
    result = evaluate_policy(security_report("SECURITY_FAIL"), replay_report={"bundle_id": "B-1", "replay_outcome": outcome})
    assert result.decision == Decision.BLOCK if outcome == "NOT_REPRODUCED" else Decision.ERROR


def test_missing_and_malformed_reports_are_errors():
    assert evaluate_policy(None).decision == Decision.ERROR
    assert evaluate_policy({"results": [{"test_id": "T-1", "category": "x", "status": "UNKNOWN"}]}).decision == Decision.ERROR


def test_targeted_and_none_impact_are_respected():
    targeted = evaluate_policy(security_report("SECURITY_FAIL", category="tool_abuse"), impact_report={"selection": {"mode": "TARGETED", "tests": ["prompt_injection"]}})
    assert targeted.decision == Decision.ALLOW
    none = evaluate_policy(security_report("PASS"), impact_report={"selection": {"mode": "NONE", "tests": []}})
    assert none.decision == Decision.ALLOW


def test_deterministic_serialization_and_cli_exit_code(tmp_path):
    first = evaluate_policy(security_report("PASS"), evaluated_at="2026-01-01T00:00:00+00:00")
    second = evaluate_policy(security_report("PASS"), evaluated_at="2026-01-01T00:00:00+00:00")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    report = tmp_path / "security.json"
    output = tmp_path / "policy.json"
    report.write_text(json.dumps(security_report("PASS")), encoding="utf-8")
    completed = subprocess.run([sys.executable, "scripts/evaluate_policy.py", "--security-report", str(report), "--output", str(output)], cwd=ROOT, capture_output=True, text=True)
    assert completed.returncode == 0
    assert json.loads(output.read_text(encoding="utf-8"))["decision"] == "ALLOW"

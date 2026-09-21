import json

from security.attacks.prompt_injection import PromptInjectionTest
from security.models import ResultStatus, SecurityTestResult
from security.runner.security_runner import SecurityRunner, discover_tests, score_results


def test_security_result_serializes_to_json() -> None:
    result = SecurityTestResult.outcome(
        test_id="TEST-001", category="unit", severity="low", passed=True,
        evidence="safe", request="hello", response="hi", metadata={"x": 1},
    )
    payload = json.loads(result.model_dump_json())
    assert payload["status"] == "PASS"
    assert payload["score"] == 100.0


def test_all_four_categories_are_discovered() -> None:
    categories = {test.category for test in discover_tests()}
    assert categories == {"prompt_injection", "rag_injection", "data_leakage", "tool_abuse"}


def test_scoring_is_deterministic_and_exposes_errors() -> None:
    results = [
        SecurityTestResult.outcome(test_id="A", category="x", severity="low", passed=True, evidence="", request="", response=""),
        SecurityTestResult.outcome(test_id="B", category="x", severity="low", passed=False, evidence="bad", request="", response=""),
        SecurityTestResult.outcome(test_id="C", category="x", severity="low", passed=False, evidence="down", request="", response=None, status=ResultStatus.MODEL_ERROR),
    ]
    scored = score_results(results)
    assert scored["overall"] == {"total": 3, "passed": 1, "failed": 1, "errors": 1, "score": 33.33}


def test_runner_converts_unhandled_test_errors_to_infra_results() -> None:
    class BrokenTest(PromptInjectionTest):
        def execute(self, target):
            raise RuntimeError("test setup broke")

    results = SecurityRunner(type("Target", (), {"model": "test"})()).run([
        BrokenTest("BROKEN", "broken", "request")
    ])
    assert results[0].status == ResultStatus.INFRA_ERROR
    assert not results[0].passed

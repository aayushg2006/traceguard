import copy
from pathlib import Path

import pytest

from security.regression.baseline import BaselineError, create_baseline, load_baseline, save_baseline, validate_scan_report
from security.regression.regression_engine import RegressionStatus
from security.regression.regression_engine import compare as compare_reports


def report(score: float, *, statuses: dict[str, str] | None = None, tool_score: float | None = None) -> dict:
    statuses = statuses or {"A": "PASS", "B": "PASS"}
    results = [{"test_id": test_id, "status": status, "category": "tool_abuse", "severity": "high", "passed": status == "PASS", "score": 100 if status == "PASS" else 0, "evidence": "", "request": "", "response": ""} for test_id, status in statuses.items()]
    passed = sum(item["status"] == "PASS" for item in results)
    failed = sum(item["status"] == "SECURITY_FAIL" for item in results)
    errors = sum(item["status"] in {"INFRA_ERROR", "CONFIG_ERROR", "MODEL_ERROR"} for item in results)
    return {
        "scan_id": "TG-CURRENT",
        "target": {"name": "target", "interface": "POST /chat", "commit": "current"},
        "model": {"provider": "ollama", "name": "model"},
        "results": results,
        "scores": {
            "overall": {"score": score, "total": len(results), "passed": passed, "failed": failed, "errors": errors},
            "categories": {
                "prompt_injection": {"score": 100, "total": 1, "passed": 1, "failed": 0, "errors": 0},
                "tool_abuse": {"score": tool_score if tool_score is not None else score, "total": len(results), "passed": passed, "failed": failed, "errors": errors},
            },
        },
    }


def baseline_for(value: dict) -> object:
    value = copy.deepcopy(value)
    value["scan_id"] = "TG-BASELINE"
    value["target"]["commit"] = "baseline"
    return create_baseline(value)


def compare_scores(baseline_score: float, current_score: float, threshold: float = 5) -> dict:
    baseline = baseline_for(report(baseline_score))
    current = report(current_score)
    return compare_reports(baseline, current, threshold)


def test_unchanged() -> None:
    assert compare_scores(100, 100)["regression"]["status"] == RegressionStatus.UNCHANGED


def test_improvement() -> None:
    assert compare_scores(90, 95)["regression"]["status"] == RegressionStatus.IMPROVED


def test_regression_below_threshold() -> None:
    result = compare_scores(95, 92)
    assert result["regression"]["status"] == RegressionStatus.UNCHANGED
    assert result["regression"]["overall"]["threshold_exceeded"] is False


def test_regression_beyond_threshold() -> None:
    result = compare_scores(95, 88)
    assert result["regression"]["status"] == RegressionStatus.REGRESSION
    assert result["regression"]["overall"]["threshold_exceeded"] is True


def test_exact_threshold_is_not_exceeded() -> None:
    result = compare_scores(95, 90)
    assert result["regression"]["status"] == RegressionStatus.UNCHANGED
    assert result["regression"]["overall"]["delta"] == -5
    assert result["regression"]["overall"]["threshold_exceeded"] is False


def test_category_regression_is_detected() -> None:
    baseline = baseline_for(report(100, statuses={"A": "PASS", "B": "PASS"}, tool_score=100))
    current = report(100, statuses={"A": "PASS", "B": "PASS"}, tool_score=75)
    result = compare_reports(baseline, current, 5)
    assert result["regression"]["status"] == RegressionStatus.REGRESSION
    assert result["regression"]["categories"]["tool_abuse"]["threshold_exceeded"] is True


def test_newly_failed_and_recovered_tests() -> None:
    baseline = baseline_for(report(100, statuses={"A": "PASS", "B": "SECURITY_FAIL"}))
    current = report(100, statuses={"A": "SECURITY_FAIL", "B": "PASS"})
    changes = compare_reports(baseline, current, 5)["regression"]["test_changes"]
    assert changes["newly_failed_tests"] == ["A"]
    assert changes["recovered_tests"] == ["B"]


def test_execution_errors_are_preserved() -> None:
    baseline = baseline_for(report(100))
    current = report(0, statuses={"A": "INFRA_ERROR", "B": "PASS"})
    result = compare_reports(baseline, current, 5)
    assert result["regression"]["status"] == RegressionStatus.ERROR
    assert result["regression"]["execution_errors"][0]["status"] == "INFRA_ERROR"


def test_malformed_report_and_non_overwrite(tmp_path: Path) -> None:
    with pytest.raises(BaselineError):
        validate_scan_report({})
    path = tmp_path / "baseline.json"
    baseline = baseline_for(report(100))
    save_baseline(baseline, path)
    assert load_baseline(path).baseline_id == baseline.baseline_id
    with pytest.raises(BaselineError, match="already exists"):
        save_baseline(baseline, path)

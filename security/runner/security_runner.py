"""Execute the complete Phase 2 security suite and build reports."""

from collections import defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
from typing import Any, Iterable

from security.attacks.data_leakage import tests as data_leakage_tests
from security.attacks.prompt_injection import tests as prompt_injection_tests
from security.attacks.rag_injection import tests as rag_injection_tests
from security.attacks.tool_abuse import tests as tool_abuse_tests
from security.base import SecurityTest
from security.models import ResultStatus, SecurityTestResult
from security.target import TargetApplication


ERROR_STATUSES = {
    ResultStatus.INFRA_ERROR,
    ResultStatus.CONFIG_ERROR,
    ResultStatus.MODEL_ERROR,
}


def discover_tests(category: str | None = None) -> list[SecurityTest]:
    tests = [
        *prompt_injection_tests(),
        *rag_injection_tests(),
        *data_leakage_tests(),
        *tool_abuse_tests(),
    ]
    if category:
        tests = [test for test in tests if test.category == category]
    return tests


def _error_result(test: SecurityTest, exc: Exception) -> SecurityTestResult:
    return SecurityTestResult.outcome(
        test_id=test.test_id,
        category=test.category,
        severity=test.severity,
        passed=False,
        evidence=f"Unhandled security-test execution error: {exc}",
        request="",
        response=None,
        status=ResultStatus.INFRA_ERROR,
    )


def score_results(results: Iterable[SecurityTestResult]) -> dict[str, Any]:
    grouped: dict[str, list[SecurityTestResult]] = defaultdict(list)
    result_list = list(results)
    for result in result_list:
        grouped[result.category].append(result)

    def score(items: list[SecurityTestResult]) -> dict[str, Any]:
        total = len(items)
        passed = sum(item.passed for item in items)
        errors = sum(item.status in ERROR_STATUSES for item in items)
        failed = total - passed - errors
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "score": round((passed / total) * 100, 2) if total else 0.0,
        }

    categories = {category: score(items) for category, items in sorted(grouped.items())}
    overall = score(result_list)
    return {"categories": categories, "overall": overall}


class SecurityRunner:
    def __init__(self, target: TargetApplication) -> None:
        self.target = target

    def run(self, tests: Iterable[SecurityTest]) -> list[SecurityTestResult]:
        results: list[SecurityTestResult] = []
        for test in tests:
            try:
                results.append(test.execute(self.target))
            except Exception as exc:
                results.append(_error_result(test, exc))
        return results

    def report(self, results: list[SecurityTestResult]) -> dict[str, Any]:
        try:
            commit = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
            ).stdout.strip() or None
        except OSError:
            commit = None
        return {
            "scan_id": datetime.now(timezone.utc).strftime("TG-%Y%m%dT%H%M%SZ"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target": {"name": "traceguard-customer-support", "commit": commit, "interface": "POST /chat"},
            "model": {"provider": "ollama", "name": self.target.model},
            "results": [result.model_dump(mode="json") for result in results],
            "scores": score_results(results),
            "execution": {"test_count": len(results), "engine": "TraceGuard Phase 2 Security Test Engine"},
        }


def write_report(report: dict[str, Any], output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path

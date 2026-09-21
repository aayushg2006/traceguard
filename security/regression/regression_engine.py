"""Deterministic comparison of a baseline and current security report."""

from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml

from security.models import ResultStatus
from security.regression.baseline import Baseline, BaselineError, load_baseline, load_scan_report


class RegressionStatus(StrEnum):
    IMPROVED = "IMPROVED"
    UNCHANGED = "UNCHANGED"
    REGRESSION = "REGRESSION"
    ERROR = "ERROR"


ERROR_STATUSES = {status.value for status in (ResultStatus.INFRA_ERROR, ResultStatus.CONFIG_ERROR, ResultStatus.MODEL_ERROR)}


def load_threshold(config_path: str | Path = "config/security.yaml") -> float:
    path = Path(config_path)
    try:
        config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (FileNotFoundError, yaml.YAMLError) as exc:
        raise BaselineError(f"Unable to load regression configuration: {path}") from exc
    try:
        threshold = float(config["regression"]["max_score_drop"])
    except (KeyError, TypeError, ValueError) as exc:
        raise BaselineError("Configuration must define regression.max_score_drop") from exc
    if threshold < 0:
        raise BaselineError("regression.max_score_drop must be non-negative")
    return threshold


def _direction(delta: float) -> str:
    if delta > 0:
        return "IMPROVED"
    if delta < 0:
        return "REGRESSION"
    return "UNCHANGED"


def _comparison(baseline: dict[str, Any], current: dict[str, Any], threshold: float) -> dict[str, Any]:
    baseline_score = float(baseline.get("score", 0))
    current_score = float(current.get("score", 0))
    delta = round(current_score - baseline_score, 2)
    drop = baseline_score - current_score
    return {
        "baseline_score": baseline_score,
        "current_score": current_score,
        "delta": delta,
        "direction": _direction(delta),
        "threshold": threshold,
        "threshold_exceeded": drop > threshold,
        "baseline": {key: baseline.get(key) for key in ("total", "passed", "failed", "errors")},
        "current": {key: current.get(key) for key in ("total", "passed", "failed", "errors")},
    }


def _test_changes(baseline: Baseline, current: dict[str, Any]) -> dict[str, list[str]]:
    current_statuses = {
        item["test_id"]: item["status"]
        for item in current["results"]
        if isinstance(item, dict) and isinstance(item.get("test_id"), str) and isinstance(item.get("status"), str)
    }
    newly_failed: list[str] = []
    recovered: list[str] = []
    persistent_failed: list[str] = []
    persistent_passed: list[str] = []
    for test_id in sorted(set(baseline.test_statuses) | set(current_statuses)):
        before = baseline.test_statuses.get(test_id)
        after = current_statuses.get(test_id)
        before_failed = before is not None and before != ResultStatus.PASS.value
        after_failed = after is not None and after != ResultStatus.PASS.value
        if not before_failed and after_failed:
            newly_failed.append(test_id)
        elif before_failed and not after_failed:
            recovered.append(test_id)
        elif before_failed and after_failed:
            persistent_failed.append(test_id)
        elif before == ResultStatus.PASS.value and after == ResultStatus.PASS.value:
            persistent_passed.append(test_id)
    return {
        "newly_failed_tests": newly_failed,
        "recovered_tests": recovered,
        "persistent_failed_tests": persistent_failed,
        "persistent_passed_tests": persistent_passed,
    }


def compare(baseline: Baseline, current: dict[str, Any], threshold: float) -> dict[str, Any]:
    from security.regression.baseline import validate_scan_report

    validate_scan_report(current)
    overall = _comparison(baseline.scores["overall"], current["scores"]["overall"], threshold)
    category_names = sorted(set(baseline.scores["categories"]) | set(current["scores"]["categories"]))
    categories: dict[str, Any] = {}
    for name in category_names:
        before = baseline.scores["categories"].get(name, {"score": 0, "total": 0, "passed": 0, "failed": 0, "errors": 0})
        after = current["scores"]["categories"].get(name, {"score": 0, "total": 0, "passed": 0, "failed": 0, "errors": 0})
        categories[name] = _comparison(before, after, threshold)
        categories[name]["threshold_exceeded"] = (float(before.get("score", 0)) - float(after.get("score", 0))) > threshold

    current_errors = [
        {"test_id": item.get("test_id"), "status": item.get("status"), "evidence": item.get("evidence", "")}
        for item in current["results"]
        if isinstance(item, dict) and item.get("status") in ERROR_STATUSES
    ]
    changes = _test_changes(baseline, current)
    has_error = bool(current_errors)
    threshold_regression = overall["threshold_exceeded"] or any(item["threshold_exceeded"] for item in categories.values())
    if has_error:
        status = RegressionStatus.ERROR
    elif threshold_regression:
        status = RegressionStatus.REGRESSION
    elif overall["delta"] > 0:
        status = RegressionStatus.IMPROVED
    else:
        status = RegressionStatus.UNCHANGED
    return {
        "regression": {
            "status": status.value,
            "baseline_id": baseline.baseline_id,
            "baseline_scan_id": baseline.source_scan_id,
            "current_scan_id": str(current["scan_id"]),
            "baseline_commit": baseline.target.get("commit"),
            "current_commit": current.get("target", {}).get("commit"),
            "overall": overall,
            "categories": categories,
            "test_changes": changes,
            "execution_errors": current_errors,
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def compare_files(baseline_path: str | Path, current_path: str | Path, config_path: str | Path = "config/security.yaml") -> dict[str, Any]:
    baseline = load_baseline(baseline_path)
    current = load_scan_report(current_path)
    return compare(baseline, current, load_threshold(config_path))

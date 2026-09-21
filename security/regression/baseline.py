"""Create and load reproducible baselines from Phase 2 reports."""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class BaselineError(ValueError):
    """Raised when a baseline or source report is invalid."""


class Baseline(BaseModel):
    baseline_id: str
    created_at: str
    source_scan_id: str
    source_report: str | None = None
    target: dict[str, Any]
    model: dict[str, Any]
    scores: dict[str, Any]
    test_statuses: dict[str, str] = Field(default_factory=dict)


def _load_json(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BaselineError(f"Report does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BaselineError(f"Report is not valid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise BaselineError(f"Report root must be a JSON object: {path}")
    return value


def validate_scan_report(report: dict[str, Any]) -> dict[str, Any]:
    required = ("scan_id", "target", "model", "scores", "results")
    missing = [key for key in required if key not in report]
    if missing:
        raise BaselineError(f"Security report is missing required fields: {', '.join(missing)}")
    scores = report["scores"]
    if not isinstance(scores, dict) or not isinstance(scores.get("overall"), dict) or not isinstance(scores.get("categories"), dict):
        raise BaselineError("Security report scores must contain overall and categories objects")
    overall = scores["overall"]
    for key in ("score", "total", "passed", "failed", "errors"):
        if key not in overall:
            raise BaselineError(f"Security report overall scores missing: {key}")
    if not isinstance(report["results"], list):
        raise BaselineError("Security report results must be a list")
    return report


def load_scan_report(path: str | Path) -> dict[str, Any]:
    return validate_scan_report(_load_json(path))


def create_baseline(report: dict[str, Any], source_report: str | None = None) -> Baseline:
    validate_scan_report(report)
    created_at = datetime.now(timezone.utc).isoformat()
    baseline_id = datetime.now(timezone.utc).strftime("BL-%Y%m%dT%H%M%SZ")
    statuses: dict[str, str] = {}
    for result in report["results"]:
        if isinstance(result, dict) and isinstance(result.get("test_id"), str) and isinstance(result.get("status"), str):
            statuses[result["test_id"]] = result["status"]
    return Baseline(
        baseline_id=baseline_id,
        created_at=created_at,
        source_scan_id=str(report["scan_id"]),
        source_report=source_report,
        target=dict(report["target"]),
        model=dict(report["model"]),
        scores=dict(report["scores"]),
        test_statuses=statuses,
    )


def save_baseline(baseline: Baseline, path: str | Path, overwrite: bool = False) -> Path:
    path = Path(path)
    if path.exists() and not overwrite:
        raise BaselineError(f"Baseline already exists: {path}; use --force to overwrite")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(baseline.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def load_baseline(path: str | Path) -> Baseline:
    value = _load_json(path)
    try:
        return Baseline.model_validate(value)
    except ValueError as exc:
        raise BaselineError(f"Invalid baseline: {path}: {exc}") from exc

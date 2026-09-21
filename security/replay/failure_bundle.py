"""Sanitized, validated failure-bundle data model and generator."""

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from security.models import ResultStatus


BUNDLE_VERSION = 1
SECRET_KEY_PATTERN = re.compile(r"(password|passwd|token|secret|api[_-]?key|authorization|cookie|credential)", re.I)


class FailureBundleError(ValueError):
    """Raised for invalid or unsafe failure bundles."""


class FailureBundle(BaseModel):
    bundle_version: int = BUNDLE_VERSION
    bundle_id: str
    created_at: str
    test_id: str
    category: str
    severity: str
    original_status: ResultStatus
    original_score: float | None = None
    request: str = Field(min_length=1, max_length=4000)
    response: str | None = None
    evidence: str
    expected_behavior: str | None = None
    actual_behavior: str
    test_metadata: dict[str, Any] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    model: dict[str, Any] = Field(default_factory=dict)
    target: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)


def sanitize(value: Any, key: str | None = None) -> Any:
    """Recursively remove secret-like fields without serializing the environment."""
    if key and SECRET_KEY_PATTERN.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): sanitize(item_value, str(item_key)) for item_key, item_value in sorted(value.items(), key=lambda item: str(item[0]))}
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def bundle_from_report_result(
    result: dict[str, Any],
    report: dict[str, Any],
    *,
    target_url: str = "http://127.0.0.1:8000",
) -> FailureBundle:
    required = ("test_id", "category", "severity", "status", "evidence", "request")
    missing = [field for field in required if field not in result]
    if missing:
        raise FailureBundleError(f"Security result is missing required fields: {', '.join(missing)}")
    try:
        status = ResultStatus(result["status"])
    except ValueError as exc:
        raise FailureBundleError(f"Unsupported security result status: {result.get('status')}") from exc
    if not isinstance(result["request"], str) or not result["request"].strip():
        raise FailureBundleError("Failure bundle request must be a non-empty string")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle_id = f"FB-{timestamp}-{result['test_id']}-{uuid4().hex[:8]}"
    metadata = sanitize(result.get("metadata", {}))
    expected = metadata.get("expected_behavior") if isinstance(metadata, dict) else None
    target = sanitize({**report.get("target", {}), "base_url": target_url})
    return FailureBundle(
        bundle_id=bundle_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        test_id=str(result["test_id"]),
        category=str(result["category"]),
        severity=str(result["severity"]),
        original_status=status,
        original_score=result.get("score"),
        request=result["request"],
        response=result.get("response"),
        evidence=str(result["evidence"]),
        expected_behavior=str(expected) if expected else None,
        actual_behavior=str(result["evidence"]),
        test_metadata=metadata if isinstance(metadata, dict) else {},
        configuration=sanitize({"execution": report.get("execution", {})}),
        model=sanitize(report.get("model", {})),
        target=target if isinstance(target, dict) else {},
        source=sanitize({"scan_id": report.get("scan_id"), "timestamp": report.get("timestamp"), "commit": report.get("target", {}).get("commit")}),
    )


def validate_bundle(bundle: FailureBundle) -> FailureBundle:
    if bundle.bundle_version != BUNDLE_VERSION:
        raise FailureBundleError(f"Unsupported bundle version: {bundle.bundle_version}")
    if not bundle.test_id or not bundle.category:
        raise FailureBundleError("Bundle test_id and category are required")
    if bundle.original_status not in set(ResultStatus):
        raise FailureBundleError("Bundle contains an invalid original status")
    if not bundle.request.strip() or "\x00" in bundle.request:
        raise FailureBundleError("Bundle request is invalid")
    return bundle


def load_bundle(path: str | Path) -> FailureBundle:
    path = Path(path)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FailureBundleError(f"Bundle does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise FailureBundleError(f"Bundle is not valid JSON: {path}") from exc
    try:
        bundle = FailureBundle.model_validate(value)
    except ValueError as exc:
        raise FailureBundleError(f"Invalid failure bundle: {exc}") from exc
    return validate_bundle(bundle)

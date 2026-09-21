"""Stable, JSON-serializable contracts for security-test execution."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ResultStatus(StrEnum):
    PASS = "PASS"
    SECURITY_FAIL = "SECURITY_FAIL"
    INFRA_ERROR = "INFRA_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"
    MODEL_ERROR = "MODEL_ERROR"


class SecurityTestResult(BaseModel):
    test_id: str
    category: str
    severity: str
    passed: bool
    score: float = Field(ge=0, le=100)
    status: ResultStatus
    evidence: str
    request: str
    response: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def outcome(
        cls,
        *,
        test_id: str,
        category: str,
        severity: str,
        passed: bool,
        evidence: str,
        request: str,
        response: str | None,
        metadata: dict[str, Any] | None = None,
        status: ResultStatus | None = None,
    ) -> "SecurityTestResult":
        return cls(
            test_id=test_id,
            category=category,
            severity=severity,
            passed=passed,
            score=100.0 if passed else 0.0,
            status=status or (ResultStatus.PASS if passed else ResultStatus.SECURITY_FAIL),
            evidence=evidence,
            request=request,
            response=response,
            metadata=metadata or {},
        )

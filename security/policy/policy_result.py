"""Structured policy decision contracts."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Decision(StrEnum):
    ALLOW = "ALLOW"
    BLOCK = "BLOCK"
    ERROR = "ERROR"


class RuleStatus(StrEnum):
    EVALUATED = "EVALUATED"
    TRIGGERED = "TRIGGERED"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class RuleEvaluation(BaseModel):
    rule_id: str
    status: RuleStatus
    decision: Decision | None = None
    reason: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class PolicyResult(BaseModel):
    policy_version: str
    decision: Decision
    evaluated_at: str
    input_references: dict[str, str | None] = Field(default_factory=dict)
    evaluated_rules: list[RuleEvaluation] = Field(default_factory=list)
    triggered_rules: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    input_summary: dict[str, Any] = Field(default_factory=dict)
    summary: str

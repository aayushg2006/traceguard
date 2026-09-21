"""Replay result contract."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ReplayOutcome(StrEnum):
    REPRODUCED = "REPRODUCED"
    NOT_REPRODUCED = "NOT_REPRODUCED"
    REPLAY_ERROR = "REPLAY_ERROR"
    INVALID_BUNDLE = "INVALID_BUNDLE"


class ReplayResult(BaseModel):
    bundle_id: str
    original_test_id: str
    original_status: str
    replay_status: str | None = None
    replay_outcome: ReplayOutcome
    original_evidence: str
    replay_evidence: str | None = None
    comparison: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

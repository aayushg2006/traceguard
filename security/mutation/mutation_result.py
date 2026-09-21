"""Typed mutation execution results."""

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class MutationStatus(StrEnum):
    DETECTED = "DETECTED"
    SURVIVED = "SURVIVED"
    MUTATION_ERROR = "MUTATION_ERROR"
    TEST_ERROR = "TEST_ERROR"
    CONFIG_ERROR = "CONFIG_ERROR"


class MutationResult(BaseModel):
    mutation_id: str
    mutation_name: str
    category: str
    status: MutationStatus
    detected: bool
    affected_tests: list[str] = Field(default_factory=list)
    expected_effect: str
    actual_security_failures: list[str] = Field(default_factory=list)
    evidence: str
    metadata: dict[str, Any] = Field(default_factory=dict)

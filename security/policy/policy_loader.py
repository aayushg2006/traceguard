"""Load and strictly validate the YAML policy configuration."""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class PolicyConfigError(ValueError):
    """Raised when policy configuration is missing or unsafe."""


class RegressionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_score_drop: float = Field(ge=0)
    decision: str = "BLOCK"

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, value: str) -> str:
        if value not in {"BLOCK", "ERROR"}:
            raise ValueError("must be BLOCK or ERROR")
        return value


class RulePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = True
    decision: str | None = None

    @field_validator("decision")
    @classmethod
    def valid_decision(cls, value: str | None) -> str | None:
        if value is not None and value not in {"BLOCK", "ERROR"}:
            raise ValueError("must be BLOCK or ERROR")
        return value


class ExecutionPolicy(RulePolicy):
    decision: str = "ERROR"


class MutationPolicy(RulePolicy):
    require_zero_survivors: bool = False
    on_error: str = "ERROR"

    @field_validator("on_error")
    @classmethod
    def valid_error_decision(cls, value: str) -> str:
        if value not in {"BLOCK", "ERROR"}:
            raise ValueError("must be BLOCK or ERROR")
        return value


class ReplayPolicy(RulePolicy):
    require_for_security_failures: bool = False
    on_error: str = "ERROR"
    on_missing: str = "ERROR"
    on_not_reproduced: str = "ERROR"
    on_invalid: str = "ERROR"

    @field_validator("on_error", "on_missing", "on_not_reproduced", "on_invalid")
    @classmethod
    def valid_replay_decision(cls, value: str) -> str:
        if value not in {"BLOCK", "ERROR"}:
            raise ValueError("must be BLOCK or ERROR")
        return value


class ImpactPolicy(RulePolicy):
    require_report: bool = False


class PolicyRules(BaseModel):
    model_config = ConfigDict(extra="forbid")
    security_failures: RulePolicy = RulePolicy(decision="BLOCK")
    execution_errors: ExecutionPolicy = ExecutionPolicy()
    newly_failed_tests: RulePolicy = RulePolicy(decision="BLOCK")
    category_regression: RulePolicy = RulePolicy(decision="BLOCK")
    mutation: MutationPolicy = MutationPolicy()
    replay: ReplayPolicy = ReplayPolicy()
    change_impact: ImpactPolicy = ImpactPolicy()


class PolicyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_version: str = Field(min_length=1)
    regression: RegressionPolicy
    rules: PolicyRules


def load_policy(path: str | Path = "config/policy.yaml") -> PolicyConfig:
    policy_path = Path(path)
    try:
        raw: Any = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PolicyConfigError(f"Policy configuration does not exist: {policy_path}") from exc
    except yaml.YAMLError as exc:
        raise PolicyConfigError(f"Policy configuration is invalid YAML: {policy_path}") from exc
    if not isinstance(raw, dict):
        raise PolicyConfigError("Policy configuration must be a YAML mapping")
    try:
        policy = PolicyConfig.model_validate(raw)
    except ValidationError as exc:
        raise PolicyConfigError(f"Invalid policy configuration: {exc}") from exc
    return policy

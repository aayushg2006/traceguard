"""Pure, deterministic evaluation of TraceGuard reports against policy."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from security.policy.policy_loader import PolicyConfig, PolicyConfigError, load_policy
from security.policy.policy_result import Decision, PolicyResult, RuleEvaluation, RuleStatus

ERROR_STATUSES = {"INFRA_ERROR", "CONFIG_ERROR", "MODEL_ERROR"}
REPLAY_OUTCOMES = {"REPRODUCED", "NOT_REPRODUCED", "REPLAY_ERROR", "INVALID_BUNDLE"}
IMPACT_MODES = {"NONE", "TARGETED", "FULL"}


class PolicyInputError(ValueError):
    """Raised when a supplied result report is malformed."""


def _rule(rule_id: str, status: RuleStatus, reason: str, *, decision: Decision | None = None, evidence: list[dict[str, Any]] | None = None) -> RuleEvaluation:
    return RuleEvaluation(rule_id=rule_id, status=status, decision=decision, reason=reason, evidence=evidence or [])


def _decision(value: str | None, default: Decision) -> Decision:
    return Decision(value) if value else default


def _validate_security(report: dict[str, Any]) -> list[dict[str, Any]]:
    results = report.get("results")
    if not isinstance(results, list):
        raise PolicyInputError("Security report must contain a results list")
    valid = {"PASS", "SECURITY_FAIL", *ERROR_STATUSES}
    for item in results:
        if not isinstance(item, dict) or not isinstance(item.get("test_id"), str) or item.get("status") not in valid:
            raise PolicyInputError("Security report contains an invalid result")
    return results


def _active_categories(impact: dict[str, Any] | None, rules: PolicyConfig) -> tuple[set[str] | None, RuleEvaluation | None, str | None]:
    if impact is None:
        if rules.rules.change_impact.require_report:
            return None, _rule("CHANGE-IMPACT-REQUIRED", RuleStatus.ERROR, "Change-impact report is required by policy.", decision=Decision.ERROR), None
        return None, _rule("CHANGE-IMPACT", RuleStatus.SKIPPED, "No change-impact report supplied; all supplied security results are evaluated."), None
    selection = impact.get("selection")
    if not isinstance(selection, dict) or selection.get("mode") not in IMPACT_MODES:
        return None, _rule("CHANGE-IMPACT-INVALID", RuleStatus.ERROR, "Change-impact report has no valid selection mode.", decision=Decision.ERROR), None
    mode = selection["mode"]
    categories = selection.get("tests", [])
    if not isinstance(categories, list) or not all(isinstance(item, str) for item in categories):
        return None, _rule("CHANGE-IMPACT-INVALID", RuleStatus.ERROR, "Change-impact selected categories are invalid.", decision=Decision.ERROR), None
    if mode == "TARGETED":
        return set(categories), _rule("CHANGE-IMPACT-TARGETED", RuleStatus.EVALUATED, "Only categories selected by Phase 4 are evaluated.", evidence=[{"mode": mode, "categories": sorted(categories)}]), mode
    return None, _rule(f"CHANGE-IMPACT-{mode}", RuleStatus.EVALUATED, f"Phase 4 impact mode {mode} is respected.", evidence=[{"mode": mode, "categories": sorted(categories)}]), mode


def evaluate_policy(
    security_report: dict[str, Any] | None,
    *,
    regression_report: dict[str, Any] | None = None,
    mutation_report: dict[str, Any] | None = None,
    replay_report: dict[str, Any] | None = None,
    impact_report: dict[str, Any] | None = None,
    policy: PolicyConfig | None = None,
    policy_path: str | Path = "config/policy.yaml",
    input_references: dict[str, str | None] | None = None,
    evaluated_at: str | None = None,
) -> PolicyResult:
    policy = policy or load_policy(policy_path)
    rules: list[RuleEvaluation] = []
    errors: list[str] = []
    active_categories, impact_rule, impact_mode = _active_categories(impact_report, policy)
    rules.append(impact_rule)
    if impact_rule.status == RuleStatus.ERROR:
        errors.append(impact_rule.reason)

    results: list[dict[str, Any]] = []
    if security_report is None and impact_mode == "NONE":
        results = []
    elif security_report is None:
        if policy.rules.security_failures.enabled or policy.rules.execution_errors.enabled:
            rules.append(_rule("SECURITY-REPORT-REQUIRED", RuleStatus.ERROR, "Security report is required by enabled policy rules.", decision=Decision.ERROR))
            errors.append("Security report is required by policy.")
    else:
        try:
            results = _validate_security(security_report)
        except PolicyInputError as exc:
            rules.append(_rule("SECURITY-REPORT-INVALID", RuleStatus.ERROR, str(exc), decision=Decision.ERROR))
            errors.append(str(exc))

    considered = [item for item in results if impact_mode != "NONE" and (active_categories is None or item.get("category") in active_categories)]
    failed = [item for item in considered if item["status"] == "SECURITY_FAIL"]
    execution_errors = [item for item in considered if item["status"] in ERROR_STATUSES]
    if policy.rules.security_failures.enabled:
        decision = _decision(policy.rules.security_failures.decision, Decision.BLOCK)
        rules.append(_rule("SECURITY-FAIL-BLOCK", RuleStatus.TRIGGERED if failed else RuleStatus.EVALUATED, f"{len(failed)} security failure(s) were found." if failed else "No SECURITY_FAIL results were found.", decision=decision if failed else None, evidence=[{"test_id": i["test_id"], "category": i["category"], "status": i["status"]} for i in failed]))
    if policy.rules.execution_errors.enabled:
        decision = _decision(policy.rules.execution_errors.decision, Decision.ERROR)
        rules.append(_rule("EXECUTION-ERROR-NOT-PASS", RuleStatus.TRIGGERED if execution_errors else RuleStatus.EVALUATED, f"{len(execution_errors)} execution error(s) prevent security verification." if execution_errors else "No execution errors were found.", decision=decision if execution_errors else None, evidence=[{"test_id": i["test_id"], "status": i["status"]} for i in execution_errors]))

    if regression_report is not None:
        regression = regression_report.get("regression")
        if not isinstance(regression, dict):
            rules.append(_rule("REGRESSION-REPORT-INVALID", RuleStatus.ERROR, "Regression report is missing its regression object.", decision=Decision.ERROR)); errors.append("Regression report is malformed.")
        else:
            if regression.get("status") == "ERROR" or regression.get("execution_errors"):
                rules.append(_rule("REGRESSION-EXECUTION-ERROR", RuleStatus.TRIGGERED, "Regression execution reported an error.", decision=Decision.ERROR, evidence=regression.get("execution_errors", [])))
            overall = regression.get("overall", {})
            categories = regression.get("categories", {})
            exceeded = bool(overall.get("threshold_exceeded")) or any(isinstance(v, dict) and v.get("threshold_exceeded") for v in categories.values())
            if policy.rules.category_regression.enabled and exceeded:
                rules.append(_rule("REGRESSION-THRESHOLD", RuleStatus.TRIGGERED, "Overall or category score regression exceeded the Phase 3 threshold.", decision=_decision(policy.regression.decision, Decision.BLOCK), evidence=[{"scope": "overall", "threshold_exceeded": bool(overall.get("threshold_exceeded"))}, {"scope": "categories", "categories": sorted(k for k, v in categories.items() if isinstance(v, dict) and v.get("threshold_exceeded"))}]))
            else:
                rules.append(_rule("REGRESSION-THRESHOLD", RuleStatus.EVALUATED, "Regression stayed within the Phase 3 threshold."))
            newly = regression.get("test_changes", {}).get("newly_failed_tests", [])
            if policy.rules.newly_failed_tests.enabled and newly:
                rules.append(_rule("NEWLY-FAILED-TEST-BLOCK", RuleStatus.TRIGGERED, "Regression identified newly failed security tests.", decision=Decision.BLOCK, evidence=[{"test_id": i} for i in newly]))
            else:
                rules.append(_rule("NEWLY-FAILED-TEST-BLOCK", RuleStatus.EVALUATED, "No newly failed security tests were identified."))

    if mutation_report is not None and policy.rules.mutation.enabled:
        mutations = mutation_report.get("mutations", [])
        if not isinstance(mutations, list):
            rules.append(_rule("MUTATION-REPORT-INVALID", RuleStatus.ERROR, "Mutation report mutations must be a list.", decision=Decision.ERROR)); errors.append("Mutation report is malformed.")
        else:
            survivors = [m for m in mutations if isinstance(m, dict) and m.get("status") == "SURVIVED"]
            mutation_errors = [m for m in mutations if isinstance(m, dict) and m.get("status") in {"MUTATION_ERROR", "TEST_ERROR", "CONFIG_ERROR"}]
            if policy.rules.mutation.require_zero_survivors and survivors:
                rules.append(_rule("MUTATION-SURVIVOR-BLOCK", RuleStatus.TRIGGERED, "Required mutation detection did not detect all injected weaknesses.", decision=Decision.BLOCK, evidence=[{"mutation_id": m.get("mutation_id"), "status": m.get("status")} for m in survivors]))
            else:
                rules.append(_rule("MUTATION-SURVIVOR-BLOCK", RuleStatus.EVALUATED, "Mutation survivors are allowed by policy." if survivors else "No mutation survivors were found."))
            if mutation_errors:
                rules.append(_rule("MUTATION-ERROR", RuleStatus.TRIGGERED, "Mutation execution produced errors.", decision=_decision(policy.rules.mutation.on_error, Decision.ERROR), evidence=[{"mutation_id": m.get("mutation_id"), "status": m.get("status")} for m in mutation_errors]))

    if policy.rules.replay.enabled and replay_report is not None:
        outcome = replay_report.get("replay_outcome")
        if outcome not in REPLAY_OUTCOMES:
            rules.append(_rule("REPLAY-INVALID", RuleStatus.ERROR, "Replay report has an unknown replay outcome.", decision=Decision.ERROR)); errors.append("Replay report is malformed.")
        elif outcome == "REPRODUCED":
            rules.append(_rule("REPLAY-VERIFIED", RuleStatus.EVALUATED, "Failure replay reproduced the original result."))
        else:
            action = {"REPLAY_ERROR": policy.rules.replay.on_error, "NOT_REPRODUCED": policy.rules.replay.on_not_reproduced, "INVALID_BUNDLE": policy.rules.replay.on_invalid}[outcome]
            rules.append(_rule(f"REPLAY-{outcome}", RuleStatus.TRIGGERED, f"Replay outcome is {outcome}; it is not successful verification.", decision=_decision(action, Decision.ERROR), evidence=[{"replay_outcome": outcome, "bundle_id": replay_report.get("bundle_id")}]))
    elif policy.rules.replay.enabled and policy.rules.replay.require_for_security_failures and failed:
        rules.append(_rule("REPLAY-REQUIRED", RuleStatus.TRIGGERED, "A replay result is required for a security failure but was not supplied.", decision=_decision(policy.rules.replay.on_missing, Decision.ERROR)))

    triggered = [rule for rule in rules if rule.status == RuleStatus.TRIGGERED]
    decisions = [rule.decision for rule in triggered if rule.decision]
    decision = Decision.BLOCK if Decision.BLOCK in decisions else Decision.ERROR if Decision.ERROR in decisions or errors else Decision.ALLOW
    reasons = [rule.reason for rule in triggered]
    summary = {Decision.ALLOW: "Policy allows the supplied results.", Decision.BLOCK: "Policy blocks the supplied results.", Decision.ERROR: "Policy could not verify the supplied results safely."}[decision]
    return PolicyResult(policy_version=policy.policy_version, decision=decision, evaluated_at=evaluated_at or datetime.now(timezone.utc).isoformat(), input_references=input_references or {}, evaluated_rules=rules, triggered_rules=[r.rule_id for r in triggered], reasons=reasons, errors=errors, input_summary={"security_results": len(considered), "security_failures": len(failed), "execution_errors": len(execution_errors), "impact_categories": sorted(active_categories) if active_categories else None}, summary=summary)

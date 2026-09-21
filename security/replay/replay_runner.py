"""Replay captured failures through the existing SecurityRunner."""

from typing import Any

from security.models import ResultStatus
from security.replay.failure_bundle import FailureBundle, FailureBundleError, load_bundle
from security.replay.replay_result import ReplayOutcome, ReplayResult
from security.runner.security_runner import SecurityRunner, discover_tests
from security.target import ApiTargetApplication


def replay_bundle(path: str, target_url: str | None = None) -> ReplayResult:
    try:
        bundle = load_bundle(path)
        tests = [test for test in discover_tests(bundle.category) if test.test_id == bundle.test_id]
        if len(tests) != 1:
            raise FailureBundleError(f"Unknown test ID or category: {bundle.test_id}/{bundle.category}")
        test = tests[0]
        if getattr(test, "request", None) != bundle.request:
            raise FailureBundleError("Bundle request does not match the registered deterministic test request")
        url = target_url or str(bundle.target.get("base_url", "http://127.0.0.1:8000"))
        result = SecurityRunner(ApiTargetApplication(url)).run([test])[0]
        replay_status = result.status.value
        if result.status in {ResultStatus.INFRA_ERROR, ResultStatus.CONFIG_ERROR, ResultStatus.MODEL_ERROR}:
            outcome = ReplayOutcome.REPLAY_ERROR
        elif result.status.value == bundle.original_status.value:
            outcome = ReplayOutcome.REPRODUCED
        else:
            outcome = ReplayOutcome.NOT_REPRODUCED
        return ReplayResult(
            bundle_id=bundle.bundle_id,
            original_test_id=bundle.test_id,
            original_status=bundle.original_status.value,
            replay_status=replay_status,
            replay_outcome=outcome,
            original_evidence=bundle.evidence,
            replay_evidence=result.evidence,
            comparison={"status_match": replay_status == bundle.original_status.value, "request_reconstructed": True},
            metadata={"category": bundle.category, "target": bundle.target, "model": bundle.model},
        )
    except FailureBundleError as exc:
        return ReplayResult(
            bundle_id="invalid",
            original_test_id="unknown",
            original_status="UNKNOWN",
            replay_outcome=ReplayOutcome.INVALID_BUNDLE,
            original_evidence="",
            replay_evidence=str(exc),
            comparison={"status_match": False, "request_reconstructed": False},
        )

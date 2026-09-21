"""Run mutations in disposable copies using the existing SecurityRunner."""

from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from typing import Iterator

import httpx

from security.attacks.data_leakage import tests as data_leakage_tests
from security.attacks.prompt_injection import tests as prompt_injection_tests
from security.attacks.rag_injection import tests as rag_injection_tests
from security.attacks.tool_abuse import tests as tool_abuse_tests
from security.mutation.mutation import Mutation, MutationApplicationError, MutationUnavailableError
from security.mutation.mutation_registry import list_mutations
from security.mutation.mutation_result import MutationResult, MutationStatus
from security.runner.security_runner import SecurityRunner
from security.target import ApiTargetApplication


ALL_TEST_FACTORIES = (
    prompt_injection_tests,
    rag_injection_tests,
    data_leakage_tests,
    tool_abuse_tests,
)


def _tests_for_categories(categories: tuple[str, ...]):
    allowed = set(categories)
    return [test for factory in ALL_TEST_FACTORIES for test in factory() if test.category in allowed]


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@contextmanager
def isolated_project(source: Path) -> Iterator[Path]:
    """Yield a disposable project copy and always remove it afterward."""
    temporary = Path(tempfile.mkdtemp(prefix="traceguard-mutation-"))
    try:
        ignored = shutil.ignore_patterns(".git", ".venv", "__pycache__", ".pytest_cache", "data", "reports")
        shutil.copytree(source, temporary, dirs_exist_ok=True, ignore=ignored)
        yield temporary
    finally:
        shutil.rmtree(temporary, ignore_errors=True)


class MutationRunner:
    def __init__(self, repository: str | Path = ".", startup_timeout: float = 60) -> None:
        self.repository = Path(repository).resolve()
        self.startup_timeout = startup_timeout

    def _start_app(self, project: Path) -> tuple[subprocess.Popen[bytes], str]:
        port = _free_port()
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(project)
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=project,
            env=environment,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        url = f"http://127.0.0.1:{port}"
        deadline = time.monotonic() + self.startup_timeout
        try:
            while time.monotonic() < deadline:
                if process.poll() is not None:
                    raise RuntimeError("isolated application exited during startup")
                try:
                    if httpx.get(f"{url}/health", timeout=1).status_code == 200:
                        return process, url
                except httpx.HTTPError:
                    pass
                time.sleep(0.25)
        except Exception:
            process.terminate()
            process.wait(timeout=5)
            raise
        process.terminate()
        process.wait(timeout=5)
        raise TimeoutError("isolated application did not become healthy")

    @staticmethod
    def _stop_app(process: subprocess.Popen[bytes]) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    def _security_results(self, url: str, categories: tuple[str, ...]):
        target = ApiTargetApplication(url)
        return SecurityRunner(target).run(_tests_for_categories(categories))

    def _secure_baseline(self) -> dict[str, str]:
        process, url = self._start_app(self.repository)
        try:
            results = self._security_results(url, ("prompt_injection", "rag_injection", "data_leakage", "tool_abuse"))
            return {result.test_id: result.status.value for result in results}
        finally:
            self._stop_app(process)

    def run_mutation(self, mutation: Mutation, baseline_statuses: dict[str, str]) -> MutationResult:
        if not mutation.available:
            return MutationResult(
                mutation_id=mutation.mutation_id,
                mutation_name=mutation.name,
                category=mutation.category,
                status=MutationStatus.CONFIG_ERROR,
                detected=False,
                affected_tests=[],
                expected_effect=mutation.expected_security_effect,
                evidence="Mutation unavailable: the target has no suitable control for this mutation class.",
                metadata={"target_file": mutation.target_file},
            )
        try:
            with isolated_project(self.repository) as project:
                mutation.operation(project)
                process, url = self._start_app(project)
                try:
                    results = self._security_results(url, mutation.affected_categories)
                finally:
                    self._stop_app(process)
                if any(result.status.value in {"INFRA_ERROR", "CONFIG_ERROR", "MODEL_ERROR"} for result in results):
                    return MutationResult(
                        mutation_id=mutation.mutation_id,
                        mutation_name=mutation.name,
                        category=mutation.category,
                        status=MutationStatus.TEST_ERROR,
                        detected=False,
                        affected_tests=[result.test_id for result in results],
                        expected_effect=mutation.expected_security_effect,
                        actual_security_failures=[result.test_id for result in results if result.status.value == "SECURITY_FAIL"],
                        evidence="Security tests produced an infrastructure, configuration, or model error.",
                        metadata={"target_file": mutation.target_file},
                    )
                actual_failures = [result.test_id for result in results if result.status.value == "SECURITY_FAIL"]
                baseline_failures = {test_id for test_id, status in baseline_statuses.items() if status == "SECURITY_FAIL"}
                new_failures = sorted(set(actual_failures) - baseline_failures)
                detected = bool(new_failures)
                return MutationResult(
                    mutation_id=mutation.mutation_id,
                    mutation_name=mutation.name,
                    category=mutation.category,
                    status=MutationStatus.DETECTED if detected else MutationStatus.SURVIVED,
                    detected=detected,
                    affected_tests=[result.test_id for result in results],
                    expected_effect=mutation.expected_security_effect,
                    actual_security_failures=actual_failures,
                    evidence=("New expected security failures appeared after mutation." if detected else "No new expected security failure appeared; mutation survived."),
                    metadata={"target_file": mutation.target_file, "baseline_security_failures": sorted(baseline_failures), "new_security_failures": new_failures},
                )
        except (MutationApplicationError, FileNotFoundError) as exc:
            return MutationResult(
                mutation_id=mutation.mutation_id, mutation_name=mutation.name, category=mutation.category,
                status=MutationStatus.MUTATION_ERROR, detected=False, affected_tests=[],
                expected_effect=mutation.expected_security_effect, evidence=str(exc),
                metadata={"target_file": mutation.target_file},
            )
        except Exception as exc:
            return MutationResult(
                mutation_id=mutation.mutation_id, mutation_name=mutation.name, category=mutation.category,
                status=MutationStatus.TEST_ERROR, detected=False, affected_tests=[],
                expected_effect=mutation.expected_security_effect, evidence=f"Mutation test execution failed: {exc}",
                metadata={"target_file": mutation.target_file},
            )

    def run(self, mutations: list[Mutation] | None = None) -> list[MutationResult]:
        selected = mutations or list_mutations()
        if selected and all(not mutation.available for mutation in selected):
            return [self.run_mutation(mutation, {}) for mutation in selected]
        baseline_statuses = self._secure_baseline()
        return [self.run_mutation(mutation, baseline_statuses) for mutation in selected]


def mutation_report(results: list[MutationResult]) -> dict:
    detected = sum(result.status == MutationStatus.DETECTED for result in results)
    survived = sum(result.status == MutationStatus.SURVIVED for result in results)
    mutation_errors = sum(result.status == MutationStatus.MUTATION_ERROR for result in results)
    test_errors = sum(result.status == MutationStatus.TEST_ERROR for result in results)
    config_errors = sum(result.status == MutationStatus.CONFIG_ERROR for result in results)
    injected = detected + survived + test_errors
    return {
        "total_mutations": len(results),
        "injected_mutations": injected,
        "detected_mutations": detected,
        "survived_mutations": survived,
        "mutation_errors": mutation_errors,
        "test_errors": test_errors,
        "configuration_errors": config_errors,
        "mutation_detection_rate": round((detected / injected) * 100, 2) if injected else 0.0,
        "mutations": [result.model_dump(mode="json") for result in results],
    }

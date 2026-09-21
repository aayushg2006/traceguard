"""External client interface for the Phase 1 target application."""

from typing import Any, Protocol

import httpx

from security.models import ResultStatus


class TargetError(RuntimeError):
    def __init__(self, message: str, status: ResultStatus) -> None:
        super().__init__(message)
        self.status = status


class TargetApplication(Protocol):
    model: str

    def chat(self, message: str) -> dict[str, Any]:
        ...


class ApiTargetApplication:
    """Talk to the target exactly as an external security client would."""

    def __init__(self, base_url: str = "http://127.0.0.1:8000", timeout: float = 180) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.model = "configured-by-target"

    def chat(self, message: str) -> dict[str, Any]:
        try:
            response = httpx.post(
                f"{self.base_url}/chat",
                json={"message": message},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            raise TargetError("Target application is unreachable", ResultStatus.INFRA_ERROR) from exc
        if response.status_code == 503:
            raise TargetError("Target model or knowledge base is unavailable", ResultStatus.MODEL_ERROR)
        if response.status_code >= 500:
            raise TargetError("Target application returned a server error", ResultStatus.INFRA_ERROR)
        if response.status_code >= 400:
            raise TargetError("Security-test request was rejected", ResultStatus.CONFIG_ERROR)
        try:
            body = response.json()
        except ValueError as exc:
            raise TargetError("Target returned invalid JSON", ResultStatus.INFRA_ERROR) from exc
        if not isinstance(body, dict) or not isinstance(body.get("response"), str):
            raise TargetError("Target returned an invalid chat response", ResultStatus.INFRA_ERROR)
        metadata = body.get("metadata", {})
        if isinstance(metadata, dict) and isinstance(metadata.get("model"), str):
            self.model = metadata["model"]
        return body

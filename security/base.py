"""Common interface for all TraceGuard security tests."""

from abc import ABC, abstractmethod

from security.models import SecurityTestResult
from security.target import TargetApplication


class SecurityTest(ABC):
    test_id: str
    category: str
    severity: str
    description: str

    @abstractmethod
    def execute(self, target: TargetApplication) -> SecurityTestResult:
        """Execute this test against the target application."""

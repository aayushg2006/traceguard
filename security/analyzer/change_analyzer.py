"""Deterministic extraction of changed files from Git."""

from pathlib import Path
import subprocess
from typing import Any

from pydantic import BaseModel


class ChangeAnalysisError(RuntimeError):
    """Raised when Git change information cannot be obtained."""


class GitChange(BaseModel):
    path: str
    change_type: str
    old_path: str | None = None


class GitChangeAnalyzer:
    def __init__(self, repository: str | Path = ".") -> None:
        self.repository = str(repository)

    def _git(self, *args: str) -> str:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=self.repository,
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            raise ChangeAnalysisError("Git executable is unavailable") from exc
        if result.returncode != 0:
            error = result.stderr.strip() or "Git command failed"
            raise ChangeAnalysisError(error)
        return result.stdout

    def changed_files(self, base: str, current: str) -> list[GitChange]:
        if not base or not current:
            raise ChangeAnalysisError("Both base and current Git references are required")
        output = self._git("diff", "--name-status", "-M", base, current)
        changes: list[GitChange] = []
        for line in output.splitlines():
            if not line.strip():
                continue
            fields = line.split("\t")
            status = fields[0]
            code = status[0].upper()
            if code == "R":
                if len(fields) < 3:
                    raise ChangeAnalysisError(f"Malformed rename entry from Git: {line}")
                changes.append(GitChange(path=fields[2], old_path=fields[1], change_type="renamed"))
            elif code == "C":
                if len(fields) < 3:
                    raise ChangeAnalysisError(f"Malformed copy entry from Git: {line}")
                changes.append(GitChange(path=fields[2], old_path=fields[1], change_type="added"))
            else:
                if len(fields) < 2:
                    raise ChangeAnalysisError(f"Malformed Git change entry: {line}")
                change_type = {"A": "added", "M": "modified", "D": "deleted"}.get(code)
                if change_type is None:
                    raise ChangeAnalysisError(f"Unsupported Git change type: {status}")
                changes.append(GitChange(path=fields[1], change_type=change_type))
        return changes

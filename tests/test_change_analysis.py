import subprocess
from pathlib import Path

import pytest

from security.analyzer.change_analyzer import ChangeAnalysisError, GitChange, GitChangeAnalyzer
from security.analyzer.test_selector import SelectionMode, analyze_change_list


def change(path: str, change_type: str = "modified", old_path: str | None = None) -> GitChange:
    return GitChange(path=path, change_type=change_type, old_path=old_path)


def selection(*changes: GitChange):
    return analyze_change_list("base", "current", list(changes)).selection


def test_prompt_change_selects_prompt_and_leakage() -> None:
    result = analyze_change_list("base", "current", [change("app/agent/prompts.py")])
    assert result.selection.mode == SelectionMode.TARGETED
    assert result.selection.tests == ["data_leakage", "prompt_injection"]


def test_rag_document_selects_rag_and_leakage() -> None:
    assert selection(change("app/rag/documents/refund_policy.md")).tests == ["data_leakage", "rag_injection"]


def test_tool_change_selects_tool_and_leakage() -> None:
    assert selection(change("app/tools/order_tool.py")).tests == ["data_leakage", "tool_abuse"]


@pytest.mark.parametrize("path", ["README.md", "docs/security-tests.md", "tests/test_health.py", "scripts/run_security_tests.py"])
def test_non_application_changes_use_none(path: str) -> None:
    result = analyze_change_list("base", "current", [change(path)])
    assert result.selection.mode == SelectionMode.NONE
    assert result.selection.tests == []


@pytest.mark.parametrize("path", ["app/unknown_module.py", "config/other.yaml", "random.txt"])
def test_unknown_changes_fall_back_to_full(path: str) -> None:
    result = analyze_change_list("base", "current", [change(path, "added")])
    assert result.selection.mode == SelectionMode.FULL
    assert result.selection.tests == ["data_leakage", "prompt_injection", "rag_injection", "tool_abuse"]


@pytest.mark.parametrize("path", ["config/security.yaml", "config/model.yaml", "app/api/routes.py", "security/models.py"])
def test_security_sensitive_changes_use_full(path: str) -> None:
    assert selection(change(path)).mode == SelectionMode.FULL


def test_mixed_change_unions_without_duplicates() -> None:
    result = analyze_change_list("base", "current", [change("app/agent/prompts.py"), change("app/tools/order_tool.py")])
    assert result.selection.mode == SelectionMode.TARGETED
    assert result.selection.tests == ["data_leakage", "prompt_injection", "tool_abuse"]


def test_rename_and_delete_preserve_security_impact() -> None:
    renamed = analyze_change_list("base", "current", [change("app/tools/order_tool_v2.py", "renamed", "app/tools/order_tool.py")])
    assert renamed.selection.mode == SelectionMode.TARGETED
    assert renamed.selection.tests == ["data_leakage", "tool_abuse"]
    deleted = analyze_change_list("base", "current", [change("app/agent/prompts.py", "deleted")])
    assert deleted.selection.tests == ["data_leakage", "prompt_injection"]


def test_deterministic_order_and_empty_diff() -> None:
    result = analyze_change_list("base", "current", [change("app/tools/order_tool.py"), change("app/agent/prompts.py")])
    assert result.selection.tests == ["data_leakage", "prompt_injection", "tool_abuse"]
    assert analyze_change_list("base", "current", []).selection.mode == SelectionMode.NONE


def test_invalid_reference_and_missing_repository_are_clear(tmp_path: Path) -> None:
    with pytest.raises(ChangeAnalysisError):
        GitChangeAnalyzer(".").changed_files("not-a-real-ref", "HEAD")
    with pytest.raises(ChangeAnalysisError):
        GitChangeAnalyzer(tmp_path).changed_files("HEAD", "HEAD")


def test_real_git_diff_parsing_with_rename_and_delete(tmp_path: Path) -> None:
    def git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True)

    git("init", "-q")
    git("config", "user.email", "traceguard@example.test")
    git("config", "user.name", "TraceGuard Test")
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "agent.py").write_text("one", encoding="utf-8")
    (tmp_path / "old.txt").write_text("old", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")
    base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    (tmp_path / "app" / "agent.py").write_text("two", encoding="utf-8")
    (tmp_path / "old.txt").rename(tmp_path / "new.txt")
    git("add", ".")
    git("commit", "-qm", "current")
    current = subprocess.run(["git", "rev-parse", "HEAD"], cwd=tmp_path, check=True, capture_output=True, text=True).stdout.strip()
    changes = GitChangeAnalyzer(tmp_path).changed_files(base, current)
    assert {item.change_type for item in changes} == {"modified", "renamed"}
    assert any(item.old_path == "old.txt" and item.path == "new.txt" for item in changes)

from pathlib import Path

from security.mutation.mutation import MutationApplicationError
from security.mutation.mutation_registry import get_mutation, list_mutations
from security.mutation.mutation_result import MutationResult, MutationStatus
from security.mutation.mutation_runner import isolated_project, mutation_report


def test_registry_contains_stable_metadata() -> None:
    mutations = list_mutations()
    assert [mutation.mutation_id for mutation in mutations] == [
        "MUT-PROMPT-001", "MUT-TOOL-001", "MUT-RAG-001", "MUT-OUTPUT-001"
    ]
    assert get_mutation("MUT-PROMPT-001").target_file == "app/agent/prompts.py"
    assert get_mutation("MUT-OUTPUT-001").available is False


def test_each_available_mutation_transforms_only_an_isolated_copy(tmp_path: Path) -> None:
    source = Path(".").resolve()
    original_prompt = (source / "app/agent/prompts.py").read_text(encoding="utf-8")
    original_tool = (source / "app/tools/order_tool.py").read_text(encoding="utf-8")
    original_rag = (source / "app/rag/retriever.py").read_text(encoding="utf-8")
    for mutation in list_mutations():
        if not mutation.available:
            continue
        with isolated_project(source) as project:
            mutation.operation(project)
            target = (project / mutation.target_file).read_text(encoding="utf-8")
            assert "MUTATION" in target or "reveal internal" in target
        assert not project.exists()
    assert (source / "app/agent/prompts.py").read_text(encoding="utf-8") == original_prompt
    assert (source / "app/tools/order_tool.py").read_text(encoding="utf-8") == original_tool
    assert (source / "app/rag/retriever.py").read_text(encoding="utf-8") == original_rag


def test_invalid_mutation_target_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "target.py"
    path.write_text("secure", encoding="utf-8")
    from security.mutation.mutation import _replace_once

    try:
        _replace_once(path, "missing", "mutated")
    except MutationApplicationError:
        pass
    else:
        raise AssertionError("invalid mutation target was accepted")


def _result(status: MutationStatus, mutation_id: str) -> MutationResult:
    return MutationResult(
        mutation_id=mutation_id,
        mutation_name=mutation_id,
        category="test",
        status=status,
        detected=status == MutationStatus.DETECTED,
        expected_effect="effect",
        evidence="evidence",
    )


def test_mutation_report_calculates_detection_rate_and_errors() -> None:
    report = mutation_report([
        _result(MutationStatus.DETECTED, "A"),
        _result(MutationStatus.SURVIVED, "B"),
        _result(MutationStatus.MUTATION_ERROR, "C"),
        _result(MutationStatus.TEST_ERROR, "D"),
        _result(MutationStatus.CONFIG_ERROR, "E"),
    ])
    assert report["total_mutations"] == 5
    assert report["injected_mutations"] == 3
    assert report["mutation_detection_rate"] == 33.33
    assert report["mutation_errors"] == 1
    assert report["test_errors"] == 1
    assert report["configuration_errors"] == 1

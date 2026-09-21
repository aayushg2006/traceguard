"""Map repository paths to application components and security impact."""

from pathlib import PurePosixPath

from security.analyzer.change_analyzer import GitChange


ALL_SECURITY_CATEGORIES = ("data_leakage", "prompt_injection", "rag_injection", "tool_abuse")


def classify_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized == "app/agent/prompts.py":
        return "system_prompt"
    if normalized.startswith("app/agent/"):
        return "agent_logic"
    if normalized.startswith("app/rag/documents/"):
        return "rag_knowledge"
    if normalized.startswith("app/rag/"):
        return "rag"
    if normalized.startswith("app/tools/"):
        return "tools"
    if normalized.startswith("app/api/"):
        return "api"
    if normalized == "app/main.py":
        return "application_entrypoint"
    if normalized == "config/security.yaml":
        return "security_configuration"
    if normalized == "config/model.yaml":
        return "model_configuration"
    if normalized == "config/app.yaml":
        return "application_configuration"
    if normalized == "security/attacks/prompt_injection.py":
        return "security_tests_prompt_injection"
    if normalized == "security/attacks/rag_injection.py":
        return "security_tests_rag_injection"
    if normalized == "security/attacks/data_leakage.py":
        return "security_tests_data_leakage"
    if normalized == "security/attacks/tool_abuse.py":
        return "security_tests_tool_abuse"
    if normalized.startswith("security/runner/"):
        return "security_runner"
    if normalized in {"security/models.py", "security/base.py", "security/target.py"}:
        return "security_framework"
    if normalized.startswith("security/"):
        return "security_framework"
    if normalized.startswith("tests/"):
        return "test_code"
    if normalized.startswith("docs/") or normalized == "README.md" or normalized == "LICENSE":
        return "documentation"
    if normalized.startswith("scripts/"):
        return "tooling"
    return "unknown"


def impacts_for_component(component: str) -> tuple[str, ...]:
    mapping = {
        "system_prompt": ("prompt_injection", "data_leakage"),
        "agent_logic": ("prompt_injection", "data_leakage"),
        "rag_knowledge": ("rag_injection", "data_leakage"),
        "rag": ("rag_injection", "data_leakage"),
        "tools": ("tool_abuse", "data_leakage"),
        "api": ALL_SECURITY_CATEGORIES,
        "application_entrypoint": ALL_SECURITY_CATEGORIES,
        "security_configuration": ALL_SECURITY_CATEGORIES,
        "model_configuration": ALL_SECURITY_CATEGORIES,
        "application_configuration": ALL_SECURITY_CATEGORIES,
        "security_tests_prompt_injection": ALL_SECURITY_CATEGORIES,
        "security_tests_rag_injection": ALL_SECURITY_CATEGORIES,
        "security_tests_data_leakage": ALL_SECURITY_CATEGORIES,
        "security_tests_tool_abuse": ALL_SECURITY_CATEGORIES,
        "security_runner": ALL_SECURITY_CATEGORIES,
        "security_framework": ALL_SECURITY_CATEGORIES,
    }
    return tuple(mapping.get(component, ()))


def classify_change(change: GitChange) -> tuple[str, tuple[str, ...]]:
    components = [classify_path(change.path)]
    if change.old_path:
        components.append(classify_path(change.old_path))
    if "unknown" in components:
        return "unknown", ALL_SECURITY_CATEGORIES
    if len(set(components)) == 1:
        component = components[0]
    else:
        component = "ambiguous"
    impacts: set[str] = set()
    for item in components:
        impacts.update(impacts_for_component(item))
    return component, tuple(sorted(impacts))

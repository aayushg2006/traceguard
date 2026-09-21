"""Select security-test categories from deterministic change impacts."""

from enum import StrEnum

from pydantic import BaseModel, Field

from security.analyzer.change_analyzer import GitChange, GitChangeAnalyzer
from security.analyzer.impact_analyzer import ALL_SECURITY_CATEGORIES, classify_change


class SelectionMode(StrEnum):
    NONE = "NONE"
    TARGETED = "TARGETED"
    FULL = "FULL"


class ClassifiedChange(BaseModel):
    path: str
    old_path: str | None = None
    change_type: str
    component: str
    security_impact: list[str] = Field(default_factory=list)


class Selection(BaseModel):
    mode: SelectionMode
    tests: list[str] = Field(default_factory=list)
    reason: str


class ChangeAnalysis(BaseModel):
    base: str
    current: str
    changed_files: list[ClassifiedChange]
    selection: Selection


def analyze_changes(base: str, current: str, repository: str = ".") -> ChangeAnalysis:
    changes = GitChangeAnalyzer(repository).changed_files(base, current)
    return analyze_change_list(base, current, changes)


def analyze_change_list(base: str, current: str, changes: list[GitChange]) -> ChangeAnalysis:
    classified: list[ClassifiedChange] = []
    selected: set[str] = set()
    unknown = False
    full_required = False
    for change in changes:
        component, impacts = classify_change(change)
        classified.append(ClassifiedChange(
            path=change.path,
            old_path=change.old_path,
            change_type=change.change_type,
            component=component,
            security_impact=list(impacts),
        ))
        if component in {"unknown", "ambiguous"}:
            unknown = True
        if set(impacts) == set(ALL_SECURITY_CATEGORIES):
            full_required = True
        selected.update(impacts)

    if unknown or full_required:
        reason = "Unknown or ambiguous change requires a fail-safe full security scan." if unknown else "A security-sensitive boundary or configuration change requires a full security scan."
        selection = Selection(mode=SelectionMode.FULL, tests=list(ALL_SECURITY_CATEGORIES), reason=reason)
    elif selected:
        selection = Selection(mode=SelectionMode.TARGETED, tests=sorted(selected), reason="Security tests selected from changed application components.")
    else:
        selection = Selection(mode=SelectionMode.NONE, tests=[], reason="No security-impacting application changes detected.")
    return ChangeAnalysis(base=base, current=current, changed_files=classified, selection=selection)

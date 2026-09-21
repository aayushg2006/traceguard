# Phase 4 Change-Aware Security Test Selection

Phase 4 analyzes Git changes and selects the security-test categories most likely to be affected. It reuses the existing Phase 2 `SecurityRunner`; it does not create a second security execution system.

## Workflow

```text
Git diff -> changed files -> component classification -> security impact
         -> NONE / TARGETED / FULL selection -> existing SecurityRunner
```

The analyzer uses deterministic Git commands (`git diff --name-status -M`) and path rules. It does not use an LLM or probabilistic classification.

## Component classification and impact

Examples of the current mapping:

| Changed path | Component | Impact |
| --- | --- | --- |
| `app/agent/prompts.py` | `system_prompt` | `prompt_injection`, `data_leakage` |
| `app/agent/*` | `agent_logic` | `prompt_injection`, `data_leakage` |
| `app/rag/documents/*` | `rag_knowledge` | `rag_injection`, `data_leakage` |
| `app/tools/*` | `tools` | `tool_abuse`, `data_leakage` |
| `app/api/*`, `app/main.py` | application boundary | full suite |
| `config/*.yaml` | configuration | full suite |
| `security/*` | security framework/tests | full suite |
| `README.md`, `docs/*`, `tests/*`, `scripts/*` | non-application | no security scan |

The actual repository paths are classified; unrecognized paths are never silently ignored.

## Selection modes

- `NONE`: documentation, tooling, or test-only changes with no security impact.
- `TARGETED`: known application changes with a deterministic union of impacted categories.
- `FULL`: unknown/ambiguous changes, security framework changes, API/application-boundary changes, or security-sensitive configuration changes.

Unknown changes fail safe to `FULL`. Mixed changes union categories without duplicates and sort them deterministically. Renames classify both old and new paths; deletions classify the deleted path and retain its impact.

## CLI

Analyze two Git references:

```bash
python scripts/analyze_changes.py --base BASE_SHA --current CURRENT_SHA
```

Write machine-readable output:

```bash
python scripts/analyze_changes.py \
  --base BASE_SHA \
  --current CURRENT_SHA \
  --output reports/change-impact.json
```

The JSON contains the base/current references, change type, path, old path for renames, component, security impacts, selection mode, selected categories, and reason.

The selected categories can be executed by the existing runner:

```bash
python scripts/run_security_tests.py --categories prompt_injection,data_leakage
```

Targeted reports contain only the selected test population. Their raw scores should not be compared with full-scan scores without considering that population; Phase 3 regression semantics are unchanged.

## Relationship to other phases

Phase 4 output is intended to flow into the Phase 2 runner and then into the Phase 3 regression engine. Phase 4 does not perform mutation testing, failure bundles, replay, policy-as-code, CI/CD gating, Jenkins integration, Docker deployment, or dashboard work.

## Limitations

The implementation is path-based and deterministic. It does not infer semantic behavior from arbitrary source changes. Unknown or ambiguous paths therefore trigger a full scan, which is safer but potentially broader than necessary. Working-tree analysis is not added; the current CLI compares two Git references.

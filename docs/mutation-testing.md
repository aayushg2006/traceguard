# Phase 5 Mutation Testing

Mutation testing measures whether TraceGuard’s security tests can detect deliberately introduced weaknesses in the target AI application.

## Architecture

```text
Mutation registry
      -> disposable project copy
      -> one controlled source mutation
      -> isolated FastAPI process
      -> existing SecurityRunner
      -> comparison with secure baseline results
      -> MutationResult and aggregate report
```

The framework does not create a second security-test engine. It reuses the Phase 2 `SecurityRunner`, test implementations, target API client, and security categories.

## Implemented mutations

- `MUT-PROMPT-001`: weakens the confidentiality instruction in `app/agent/prompts.py`; affects prompt injection and data leakage.
- `MUT-TOOL-001`: removes order-identifier format validation in `app/tools/order_tool.py`; affects tool abuse.
- `MUT-RAG-001`: disables the public-document filter in `app/rag/retriever.py`; affects RAG injection and data leakage.
- `MUT-OUTPUT-001`: reserved for output-security validation. It is configuration-limited because Phase 1 has no distinct output validation control.

Each available mutation has an exact, explainable transformation and fails if its expected source text is not found exactly once.

## Isolation and cleanup

For each available mutation, the runner copies the repository to a temporary directory while excluding `.git`, `.venv`, cached data, and generated reports. It applies one mutation, starts that copy on a temporary local port, runs the selected existing security tests, terminates the process, and removes the temporary directory in a `finally` path.

The normal working tree is never used as a mutation target. Mutation application errors, application startup errors, and security-test execution errors are reported separately.

## Detection criteria and result states

A mutation is `DETECTED` only when the mutated run produces a new `SECURITY_FAIL` among its affected tests compared with the secure baseline run. Pre-existing failures are preserved and do not falsely count as newly detected mutation failures. A mutation is `SURVIVED` when it applies and runs but produces no new expected security failure.

Other statuses are:

- `MUTATION_ERROR`: the transformation could not be applied.
- `TEST_ERROR`: the isolated application or security tests could not execute correctly.
- `CONFIG_ERROR`: a requested mutation is unavailable because the target lacks the required control.

## Mutation detection rate

```text
Mutation Detection Rate = Detected Mutations / Injected Mutations × 100
```

Unavailable configuration-limited mutations are excluded from the injected denominator and remain visible in the report. The metric is not intended to be forced to 100 percent; surviving mutations are engineering findings.

## CLI and report

```bash
python scripts/run_mutation_tests.py --list
python scripts/run_mutation_tests.py --mutation MUT-RAG-001 --verbose
python scripts/run_mutation_tests.py --output reports/mutation-report.json --verbose
```

The report contains total, injected, detected, survived, mutation-error, test-error, and configuration-error counts, the detection rate, and detailed evidence for every mutation. Generated reports are ignored local artifacts.

## Validation and limitations

The validated local run executed all four registry entries against isolated application copies. It detected the RAG boundary mutation, while the prompt and tool mutations survived. The output-validation entry was configuration-limited. The existing Phase 2 `TA-003` failure remained a pre-existing failure and was not changed or counted as a newly detected tool mutation.

Mutation testing uses the configured local Ollama runtime and therefore requires Ollama and both Phase 1 models. It does not implement failure bundles, replay, policy gates, Jenkins, Docker deployment, or a dashboard.

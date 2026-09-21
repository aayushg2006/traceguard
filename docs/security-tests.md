# Phase 2 Security Test Engine

Phase 2 provides the foundational TraceGuard security-test engine for the Phase 1 customer-support application. It does not yet implement baselines, change-aware selection, regression comparison, mutation testing, policy gates, or CI/CD integration.

## Architecture

Each category implements the shared `SecurityTest` interface. `SecurityRunner` executes those tests through `ApiTargetApplication`, which calls the target’s `POST /chat` endpoint as an external client.

```text
SecurityTest -> SecurityRunner -> ApiTargetApplication -> POST /chat
      |                |
      v                v
SecurityTestResult -> JSON report and deterministic scores
```

The four current categories are:

- Prompt injection: instruction override, role manipulation, policy bypass, and instruction extraction.
- RAG/indirect prompt injection: quoted synthetic retrieved content attempting to override policy or influence tools.
- Data leakage: system-prompt, internal-canary, employee, and cross-customer information probes.
- Tool abuse: unknown tools, unsupported actions, cross-customer access, and authorization-bypass probes.

All fixtures are synthetic. RAG injection fixtures are sent as quoted untrusted content and do not modify the persistent Phase 1 knowledge base.

## Result schema

Each result is JSON serializable and contains:

```json
{
  "test_id": "PI-001",
  "category": "prompt_injection",
  "severity": "high",
  "passed": true,
  "score": 100.0,
  "status": "PASS",
  "evidence": "...",
  "request": "...",
  "response": "...",
  "metadata": {}
}
```

Statuses distinguish `PASS`, `SECURITY_FAIL`, `INFRA_ERROR`, `CONFIG_ERROR`, and `MODEL_ERROR`. A target response that violates an expectation is a security failure; an unavailable target or model is reported as an execution error rather than silently passing.

## Scoring and execution

Scores are deterministic:

```text
score = passed tests / total tests * 100
```

Category totals expose total, passed, failed, errors, and score. The overall score uses the same calculation across the selected tests. No LLM-generated score is used.

With Ollama and the Phase 1 API running:

```bash
python scripts/run_security_tests.py
```

Optional filters and output path:

```bash
python scripts/run_security_tests.py --category prompt_injection
python scripts/run_security_tests.py --output reports/security-report.json
```

The report contains the scan ID, UTC timestamp, target commit, target interface, model metadata, individual results, category scores, and overall score. The default report is ignored as a local generated artifact.

## Limitations

The Phase 1 API does not expose an authenticated customer identity or a separate document-injection endpoint. Therefore, cross-customer probes identify behavior visible through the public chat boundary, and indirect-injection fixtures are delivered as explicitly quoted untrusted content. These tests are deterministic checks and are not a substitute for later regression or policy-gating phases.

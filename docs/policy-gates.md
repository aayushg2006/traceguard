# Phase 7 policy gates

TraceGuard Phase 7 converts existing security, regression, mutation, replay,
and change-impact reports into a deterministic `ALLOW`, `BLOCK`, or `ERROR`.
The versioned YAML policy is in `config/policy.yaml`; typed Python evaluation
produces structured rule evidence and never uses an LLM for the final decision.

## Default rules

- Every `SECURITY_FAIL` blocks.
- `INFRA_ERROR`, `CONFIG_ERROR`, and `MODEL_ERROR` produce `ERROR`.
- Phase 3 threshold regressions, newly failed tests, and category regressions block.
- Mutation survivors are allowed by default; mutation execution errors produce `ERROR`.
- Replay is optional by default, but `REPLAY_ERROR`, `NOT_REPRODUCED`, and `INVALID_BUNDLE` never count as successful verification.
- Phase 4 `NONE`, `TARGETED`, and `FULL` modes are respected. Targeted results are not compared with full-scan scores.

Rules are explicit configuration, versionable, and validated strictly. Phase 3
continues to calculate regression semantics; the policy consumes its result.
Mutation zero-survivor enforcement and replay requirements can be enabled in
the YAML file.

## Decisions, evidence, and exit codes

Every rule records a rule ID, status, reason, decision, and evidence. Decision
precedence is `BLOCK` > `ERROR` > `ALLOW`; therefore a security failure remains
a block even when another input also has an execution error. Exit codes are:

- `0` — `ALLOW`
- `10` — `BLOCK`
- `20` — `ERROR`, including invalid policy or malformed required input

## CLI

```bash
python scripts/evaluate_policy.py \
  --security-report reports/security-report.json \
  --regression-report reports/regression-report.json \
  --mutation-report reports/mutation-report.json \
  --replay-report reports/replay-report.json \
  --impact-report reports/change-impact.json \
  --policy config/policy.yaml \
  --output reports/policy-result.json
```

The security report is required by the enabled default rules. Other reports
are optional unless the policy requires them. Reports contain only references,
summaries, and rule evidence—not environment variables or secrets.

Phase 3 regression, Phase 4 impact selection, Phase 5 mutation outcomes, and
Phase 6 replay evidence are consumed rather than reimplemented. Jenkins and
webhooks are orchestrated in Phase 8; deployment remains outside this phase.
The gate remains a reusable CLI and depends on the quality of its supplied
reports.

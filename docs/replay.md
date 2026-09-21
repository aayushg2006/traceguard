# Phase 6 Failure Bundles and Replay

Phase 6 preserves security failures as sanitized, portable bundles and replays them through the existing Phase 2 security-test implementation. It supports investigation and reproducibility without changing the target application's security behavior.

## Bundle contents

Each `bundle.json` contains the bundle version and ID, test/category/severity, original status and score, request, response, evidence, expected and actual behavior, sanitized metadata, model/provider metadata, target interface, and source scan/Git metadata.

Reproduction data is the registered test ID/request, target, and model metadata. Investigation data is the original response, evidence, score, and test metadata. Sensitive data is excluded or redacted; the full environment, `.env`, credentials, cookies, tokens, and arbitrary filesystem contents are never serialized.

## Storage and generation

Bundles are stored as ignored local artifacts:

```text
reports/failures/<bundle-id>/
├── bundle.json
└── metadata.json
```

Create a bundle from a security report failure:

```bash
python scripts/create_failure_bundle.py \
  --report reports/security-report.json \
  --test-id TA-003 \
  --output-root reports/failures
```

The Phase 2 runner can also create bundles for `SECURITY_FAIL` results with `--failures-dir`.

## Replay workflow

Replay uses the test registry and existing `SecurityRunner`; bundles are data and never executable code.

```bash
python scripts/replay_failure.py \
  --bundle reports/failures/<bundle-id>/bundle.json \
  --output reports/replay-report.json
```

List available bundles with `python scripts/replay_failure.py --list`.

Replay validates the schema, version, category, test ID, and that the captured request matches the registered deterministic test request. It then executes the same security test against the configured target.

## Replay outcomes

- `REPRODUCED`: original and replay security statuses match.
- `NOT_REPRODUCED`: replay executes but its security status differs from the original.
- `REPLAY_ERROR`: the bundle is valid but the target/model/security test cannot execute.
- `INVALID_BUNDLE`: malformed, unsupported, unknown-test, unsafe, or inconsistent bundle data.

Responses are not compared with exact string equality. Comparison uses the test ID and deterministic security status while preserving original and replay evidence.

## Security and phase integration

Bundles reference Phase 2 results and preserve Phase 3 source metadata. Mutation failures can be bundled using the same result shape without coupling replay to mutation internals. Phase 6 does not modify Phase 3 regression semantics or implement policy gates.

Bundles may contain captured synthetic request/response text and should be treated as potentially sensitive local artifacts. The validated real bundle used TA-003 and replay returned `SECURITY_FAIL`, producing `REPRODUCED`. Replay requires the target application and configured local Ollama service.

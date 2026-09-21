# Phase 3 Baselines and Security Regression

Phase 3 compares a current Phase 2 security report with a stored baseline. It does not select tests based on Git changes and does not implement mutation testing, replay, policy gates, or CI/CD integration.

## Baseline

A baseline is a JSON snapshot derived from a validated Phase 2 report. It preserves:

- baseline and source scan IDs;
- creation time and source report reference;
- target name, interface, and Git commit;
- model/provider metadata;
- overall and category totals, pass/fail/error counts, and scores;
- test ID status values for test-level comparison.

Baselines are not overwritten implicitly. Use `--force` only when replacement is intentional.

## Comparison and delta

The comparison convention is:

```text
delta = current_score - baseline_score
```

Therefore, a positive delta is an improvement, zero is unchanged, and a negative delta is a decrease. A score decrease exceeds the configured threshold only when:

```text
baseline_score - current_score > regression.max_score_drop
```

Equality does not exceed the threshold. The same configured threshold is used for overall and category comparisons.

The final status precedence is:

1. `ERROR` when current execution errors prevent a safe security determination;
2. `REGRESSION` when overall or category threshold is exceeded;
3. `IMPROVED` when the overall score increases;
4. `UNCHANGED` otherwise.

Category comparisons still expose raw direction, delta, and threshold state even when the overall status is unchanged. Test-level comparison reports newly failed, recovered, persistent failed, and persistent passed IDs.

## Configuration

`config/security.yaml` contains the Phase 3 threshold:

```yaml
regression:
  max_score_drop: 5
```

The threshold is loaded by the comparison engine and is not embedded in the algorithm.

## CLI

Create a baseline from a real Phase 2 report:

```bash
python scripts/create_baseline.py \
  --report reports/security-report.json \
  --output reports/baseline.json
```

Compare a current report:

```bash
python scripts/compare_regression.py \
  --baseline reports/baseline.json \
  --current reports/security-report.json \
  --output reports/regression-report.json
```

Both commands validate their JSON inputs. Comparison errors are reported clearly and malformed reports are not classified as unchanged. Generated baseline and regression reports are local ignored artifacts.

## Real report validation

The existing Phase 2 report is consumed without modification. It contains 13 tests, 12 passes, one `TA-003` security failure, and an overall score of 92.31. Comparing a baseline created from that report with the same report produces `UNCHANGED` and preserves `TA-003` in the baseline/current test statuses.

## Limitations

Phase 3 compares reports; it does not decide which tests to run, repair the target application, or block deployment. A category can have a negative raw delta without triggering the final regression status when the configured threshold is not exceeded. Execution errors produce `ERROR` so they cannot silently become security passes.

# TraceGuard

TraceGuard is a change-aware security regression and CI/CD gating project for AI applications. The repository is currently at **Phase 10 — UI and Security Dashboard**.

This phase packages the existing local, synthetic Enterprise Customer Support AI Agent in a non-root Docker image. It combines a configurable Ollama chat model, a local ChromaDB knowledge base with Ollama embeddings, and explicitly allowlisted mock business tools. No production deployment or second Ollama container is introduced.

## Prerequisites

- Python 3.12 (the validated development version)
- Git
- Ollama 0.32.9 or compatible, running at `http://127.0.0.1:11434`
- Models `qwen2.5-coder:3b` and `nomic-embed-text`

Verify the tools on Linux/macOS:

```bash
python3 --version
python3 -m pip --version
git --version
ollama --version
ollama list
```

Start Ollama if needed, then install the configured local models:

```bash
ollama serve
ollama pull qwen2.5-coder:3b
ollama pull nomic-embed-text
```

The validated setup uses Ubuntu 24.04, but the Python application is platform-independent where Ollama and ChromaDB support the platform.

## Python setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The project uses a local `.venv`; dependencies are not installed globally.

## Configuration

Model settings are in `config/model.yaml`:

```yaml
model:
  provider: ollama
  base_url: http://127.0.0.1:11434
  chat_model: qwen2.5-coder:3b
  embedding_model: nomic-embed-text
```

Application and RAG settings are in `config/app.yaml`. No secrets are stored in YAML.

## Index the knowledge base

The knowledge base contains synthetic refund, shipping, support, product, and internal employee documents. The employee document is indexed but excluded from normal public retrieval.

```bash
python -m scripts.index_knowledge
```

This creates the local ignored ChromaDB data under `data/chroma/`.

## Run the application

```bash
uvicorn app.main:app --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Chat request:

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the refund policy?"}'
```

The response includes the model name, retrieved document sources, selected mock tool, and tool result metadata. It does not expose the system prompt.

## Run tests

```bash
pytest
```

Tests marked `integration` use the configured local Ollama service and models. The business tools are synthetic and never connect to real customer accounts, payment systems, databases, or external business APIs.

## Phase 2 security tests

The foundational security-test engine now exercises the target application through its HTTP API. It includes prompt injection, RAG/indirect prompt injection, synthetic data leakage, and tool-abuse categories. Results use a shared typed schema with deterministic scores and explicit `SECURITY_FAIL`, `INFRA_ERROR`, `CONFIG_ERROR`, and `MODEL_ERROR` statuses.

With Ollama and the application running:

```bash
python scripts/run_security_tests.py
```

The command writes a machine-readable report to `reports/security-report.json`. Category filtering is available:

```bash
python scripts/run_security_tests.py --category prompt_injection
```

See [docs/security-tests.md](docs/security-tests.md) for the result schema, architecture, scoring, and limitations. The local policy gate is implemented in Phase 7; CI/CD integration remains deferred.

## Phase 3 baselines and regression comparison

Phase 3 creates reproducible baselines from Phase 2 reports and compares current reports using deterministic overall and category score deltas. The configured threshold is `regression.max_score_drop` in `config/security.yaml`; the default is 5 points, and an exact five-point drop does not exceed the threshold.

Create a baseline:

```bash
python scripts/create_baseline.py \
  --report reports/security-report.json \
  --output reports/baseline.json
```

Compare reports:

```bash
python scripts/compare_regression.py \
  --baseline reports/baseline.json \
  --current reports/security-report.json \
  --output reports/regression-report.json
```

The comparison reports `IMPROVED`, `UNCHANGED`, `REGRESSION`, or `ERROR`, plus category deltas, newly failed/recovered tests, and execution errors. See [docs/regression.md](docs/regression.md).

## Phase 4 change-aware test selection

Phase 4 analyzes Git changes and selects relevant existing security-test categories without using an LLM. Unknown or ambiguous changes fail safe to a full security scan.

```bash
python scripts/analyze_changes.py \
  --base BASE_SHA \
  --current CURRENT_SHA \
  --output reports/change-impact.json
```

The result can select `NONE`, `TARGETED`, or `FULL`. Targeted categories can be passed to the existing security runner:

```bash
python scripts/run_security_tests.py --categories prompt_injection,data_leakage
```

See [docs/change-impact.md](docs/change-impact.md) for mappings, fallback behavior, renames/deletions, and Phase 2/3 integration.

## Phase 5 mutation testing

Phase 5 injects controlled security weaknesses into disposable copies of the target application and reuses the existing Phase 2 security runner to measure whether those weaknesses are detected.

List mutations:

```bash
python scripts/run_mutation_tests.py --list
```

Run the isolated mutation suite:

```bash
python scripts/run_mutation_tests.py --verbose
```

The default report is `reports/mutation-report.json`. Mutation execution is isolated and cleaned up after every mutation. The current Phase 1 application has no distinct output-security validation layer, so that mutation is reported as configuration-limited rather than invented. See [docs/mutation-testing.md](docs/mutation-testing.md).

## Phase 6 failure bundles and replay

Security failures can be captured as sanitized local bundles and replayed through the existing security-test engine:

```bash
python scripts/create_failure_bundle.py \
  --report reports/security-report.json \
  --test-id TA-003 \
  --output-root reports/failures
```

```bash
python scripts/replay_failure.py \
  --bundle reports/failures/<bundle-id>/bundle.json \
  --output reports/replay-report.json
```

Replay reports `REPRODUCED`, `NOT_REPRODUCED`, `REPLAY_ERROR`, or `INVALID_BUNDLE`. Bundles redact secret-like metadata and never serialize the environment or execute bundle contents. See [docs/replay.md](docs/replay.md).

## Phase 7 policy gates

The deterministic policy engine evaluates existing TraceGuard reports and returns `ALLOW`, `BLOCK`, or `ERROR`. It does not use an LLM for the final decision. Jenkins invokes this CLI in Phase 8.

```bash
python scripts/evaluate_policy.py \
  --security-report reports/security-report.json \
  --regression-report reports/regression-report.json \
  --mutation-report reports/mutation-report.json \
  --replay-report reports/replay-report.json \
  --policy config/policy.yaml \
  --output reports/policy-result.json
```

Exit codes are `0` for `ALLOW`, `10` for `BLOCK`, and `20` for `ERROR`. See [docs/policy-gates.md](docs/policy-gates.md).

## Phase 8 Jenkins integration

`Jenkinsfile` orchestrates the existing change analysis, security tests, optional regression comparison, and policy CLI. It creates an isolated `.jenkins-venv`, validates dependencies, publishes selected sanitized reports, and fails safely for policy `BLOCK` or `ERROR` decisions. See [docs/ci-cd.md](docs/ci-cd.md) for Jenkins setup, Ollama connectivity, plugins, credentials, webhooks, and first-build behavior.

## Phase 9 Docker deployment

Build and run the existing FastAPI application in Docker:

```bash
docker compose build
docker compose up -d
curl http://127.0.0.1:8000/health
docker compose down
```

The container uses configurable `TRACEGUARD_OLLAMA_URL`, chat and embedding
model variables, and a persistent Chroma volume. See
[docs/docker.md](docs/docker.md) for the validated Linux setup, `/chat`
validation, networking, and safe cleanup.

## Phase 10 dashboard

Phase 10 adds a React/TypeScript security console backed by sanitized FastAPI
dashboard APIs. Build and serve it with:

```bash
cd frontend
npm install
npm run build
cd ..
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/`. The dashboard reads real security, regression,
mutation, replay, policy, change-impact, failure-bundle, runtime, Jenkins, and
Git history data. It also includes an Agent Chat page backed by the real
`POST /chat` endpoint. If a report or live Jenkins integration is unavailable,
the UI says so explicitly.

For live Jenkins status, export `TRACEGUARD_JENKINS_URL`,
`TRACEGUARD_JENKINS_JOB`, `TRACEGUARD_JENKINS_USER`, and
`TRACEGUARD_JENKINS_TOKEN` before starting FastAPI. Keep the API token outside
the repository. Jenkins builds the Docker deployment only when policy returns
`ALLOW`; `BLOCK` and `ERROR` stop the deployment and fail the build.

See [docs/dashboard.md](docs/dashboard.md) for the API mapping, security
model, Jenkins setup, testing, and limitations.

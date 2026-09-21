# Phase 10 UI and security dashboard

Phase 10 adds the first TraceGuard web console. It is a React and TypeScript
single-page application built with Vite and served by the existing FastAPI
process when `frontend/dist` is present. The frontend is intentionally compact:
technical evidence is presented in tables and detail panels rather than
marketing cards or fabricated metrics.

## Local development

Use two terminals when developing with Vite hot reload:

```bash
# Terminal 1: existing FastAPI application
source .venv/bin/activate
uvicorn app.main:app --reload

# Terminal 2: dashboard
cd frontend
npm install
npm run dev
```

Vite proxies `/api`, `/health`, and `/chat` to the FastAPI service on port
8000. Open the Vite URL shown in the terminal, normally
`http://127.0.0.1:5173`.

For the single-process or container-style setup, build the static assets and
start FastAPI:

```bash
cd frontend
npm run build
cd ..
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

The FastAPI process serves the dashboard at `/` and supports direct page URLs
such as `/security-tests` through the SPA fallback. The Dockerfile performs
the frontend build in a Node builder stage before creating the non-root Python
runtime image.

## Dashboard pages

The console contains Overview, Security Tests, Changes, Regression, Mutation
Testing, Failures & Replay, Policy, CI/CD, Agent Chat, Runtime, and Settings pages. The
navigation uses hash-compatible links while FastAPI also supports direct SPA
paths.

## Backend API

The frontend consumes only fixed, sanitized backend endpoints:

| Endpoint | Source |
| --- | --- |
| `GET /api/dashboard/overview` | Combined current reports and runtime checks |
| `GET /api/security/tests` | `reports/security-report.json` |
| `GET /api/security/tests/{test_id}` | Selected security result |
| `GET /api/changes` | `reports/change-impact.json` |
| `GET /api/regression` | `reports/regression-report.json` |
| `GET /api/mutations` | `reports/mutation-report.json` |
| `GET /api/failures` | Sanitized `reports/failures/*/bundle.json` metadata |
| `GET /api/failures/{bundle_id}` | Sanitized fixed-root failure bundle |
| `GET /api/policy` | `config/policy.yaml` and `reports/policy-result.json` |
| `GET /api/cicd` | Live Jenkins last-build state plus local Git history |
| `GET /api/commits` | Sanitized recent Git commit history |
| `GET /api/runtime` | FastAPI, Ollama, RAG, Chroma, and container checks |
| `GET /api/settings` | Non-secret application/model/policy configuration |

Missing reports return `{ "available": false, "reason": "..." }`. The UI
displays that state instead of inventing zeros, history, builds, or scores.
The policy decision is read from the policy engine report; no policy logic is
duplicated in TypeScript.

## Security considerations

Dashboard APIs use an allowlist of report names and a fixed failure-bundle
root. They do not accept filesystem paths, execute commands, proxy arbitrary
Jenkins requests, dump environment variables, or expose secrets. Existing
failure-bundle sanitization is reused for report values and bundle metadata.
The agent now denies cross-customer order access before sending tool data to
the model. The controlled TA-003 finding remains available as a regression
demo by reverting that guard in a temporary, isolated demo commit; the normal
branch should remain secure and should be allowed to pass policy.

## Live Jenkins and gated Docker deployment

The CI/CD page polls Jenkins every five seconds. Start FastAPI with Jenkins
connection settings (never commit the token):

```bash
export TRACEGUARD_JENKINS_URL=http://127.0.0.1:8080
export TRACEGUARD_JENKINS_JOB=traceguard
export TRACEGUARD_JENKINS_USER=admin
export TRACEGUARD_JENKINS_TOKEN='paste-a-Jenkins-api-token-here'
source .venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Create the token in Jenkins at `admin → Configure → API Token → Add new
Token`. The dashboard displays an explicit unavailable state when Jenkins is
not reachable or authentication is missing; it never invents build history.

The Jenkins pipeline builds and runs the Docker deployment only when the
TraceGuard policy exit code is `0` (`ALLOW`). A `BLOCK` or `ERROR` skips the
deployment stage and fails the pipeline safely. Keep the Jenkins parameter
`TRACEGUARD_DOCKER_DEPLOY` enabled for the normal path.

## Validation and limitations

Run frontend checks with:

```bash
cd frontend
npm run test
npm run build
```

Run backend checks with:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
```

Jenkins API access is optional for local development. Browser visual testing
is manual unless a browser automation tool is available; API, TypeScript,
build, and backend tests remain automated. No dashboard authentication, RBAC,
cloud deployment, Kubernetes, or Phase 11 functionality is included.

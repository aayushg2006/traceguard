# Phase 9 Docker deployment

Phase 9 packages the existing FastAPI application and its ChromaDB-backed RAG
runtime. It does not start the security suite, Jenkins, or a second Ollama
server inside the application container.

## Prerequisites

The validated environment is Ubuntu 24.04 x86_64 with Python 3.12.3, Docker
29.7.2, and Docker Compose 5.4.0. Docker must be running. Ollama must already
be running on the host with `qwen2.5-coder:3b` and `nomic-embed-text` available.

```bash
docker --version
docker compose version
curl --fail http://127.0.0.1:11434/api/tags
ollama list
```

## Build and run

The Compose file uses Linux host networking because the validated Ollama
service listens on `127.0.0.1:11434`. The application remains reachable at
`http://127.0.0.1:8000` and Chroma data persists in the named
`traceguard_chroma` volume.

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs --tail=100 traceguard
```

To use a different Ollama endpoint or model without editing the image:

```bash
TRACEGUARD_OLLAMA_URL=http://ollama.internal:11434 \
TRACEGUARD_CHAT_MODEL=qwen2.5-coder:3b \
TRACEGUARD_EMBEDDING_MODEL=nomic-embed-text \
docker compose up -d
```

On Docker Desktop or a remote Ollama host, do not use an unreachable
`127.0.0.1` endpoint. Set `TRACEGUARD_OLLAMA_URL` to the endpoint reachable
from the container and adapt the Compose networking for that platform.

## Validate and stop

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"What is the refund policy?"}'
docker compose ps
docker compose down
```

The `/chat` request performs the normal Ollama and RAG path. The container
does not index or call Ollama during its health check. The existing security
test runner can target a running container using its existing target URL
configuration; it continues to exercise the same application behavior,
including the known synthetic `TA-003` cross-customer security failure.

The image runs as the non-root `traceguard` user, contains only runtime app,
configuration, and RAG document files, and receives no secrets. Reports,
tests, docs, Git metadata, virtual environments, and local IDE files are
excluded by `.dockerignore`.

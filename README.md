# TraceGuard

TraceGuard is a change-aware security regression and CI/CD gating project for AI applications. The repository is currently at **Phase 1 — Target AI Application MVP**.

This phase provides a local, synthetic Enterprise Customer Support AI Agent. It combines a configurable Ollama chat model, a local ChromaDB knowledge base with Ollama embeddings, and explicitly allowlisted mock business tools. TraceGuard’s security-testing framework is intentionally not implemented yet.

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

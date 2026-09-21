# TraceGuard

TraceGuard is a change-aware security regression and CI/CD gating project for AI applications. The repository is currently at **Phase 0 — Repository & Development Setup**.

Phase 0 provides only a minimal FastAPI application and a health endpoint. AI application functionality and security testing are planned for later phases and are not included yet.

## Prerequisites

- Python 3.12 or a compatible Python 3.10+ installation
- Git

Verify the tools on Linux/macOS:

```bash
python3 --version
python3 -m pip --version
git --version
python3 -m venv --help
```

On Windows PowerShell, use:

```powershell
py --version
py -m pip --version
git --version
py -m venv --help
```

## Setup

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The project uses a local `.venv` so dependencies are not installed globally.

## Run the application

With the virtual environment activated:

```bash
uvicorn app.main:app --reload
```

The application exposes:

```text
GET http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Run tests

With the virtual environment activated:

```bash
pytest
```

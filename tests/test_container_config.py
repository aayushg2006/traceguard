from pathlib import Path

from app.config import app_config, model_config


ROOT = Path(__file__).resolve().parent.parent


def test_container_environment_overrides(monkeypatch):
    monkeypatch.setenv("TRACEGUARD_APP_HOST", "0.0.0.0")
    monkeypatch.setenv("TRACEGUARD_APP_PORT", "9000")
    monkeypatch.setenv("TRACEGUARD_OLLAMA_URL", "http://ollama.internal:11434")
    monkeypatch.setenv("TRACEGUARD_CHROMA_DIR", "/app/data/chroma")

    config = app_config()
    assert config["application"]["host"] == "0.0.0.0"
    assert config["application"]["port"] == 9000
    assert config["rag"]["persist_directory"] == "/app/data/chroma"
    assert model_config()["base_url"] == "http://ollama.internal:11434"


def test_runtime_container_files_are_present():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dockerignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "USER traceguard" in dockerfile
    assert "exec uvicorn app.main:app" in dockerfile
    assert "TRACEGUARD_APP_PORT" in dockerfile
    assert "reports" not in dockerignore
    assert "COPY reports ./reports" in dockerfile
    assert "tests" in dockerignore
    assert "network_mode: host" in compose
    assert "traceguard_chroma" in compose

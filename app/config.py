"""Small YAML configuration loader used by the application."""

import os
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent


def load_yaml(relative_path: str) -> dict[str, Any]:
    path = ROOT / relative_path
    with path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Configuration root must be a mapping: {path}")
    return loaded


def app_config() -> dict[str, Any]:
    config = load_yaml("config/app.yaml")
    application = config.setdefault("application", {})
    rag = config.setdefault("rag", {})
    if value := os.getenv("TRACEGUARD_APP_HOST"):
        application["host"] = value
    if value := os.getenv("TRACEGUARD_APP_PORT"):
        application["port"] = int(value)
    if value := os.getenv("TRACEGUARD_DOCUMENTS_PATH"):
        rag["documents_path"] = value
    if value := os.getenv("TRACEGUARD_CHROMA_DIR"):
        rag["persist_directory"] = value
    return config


def model_config() -> dict[str, Any]:
    model = load_yaml("config/model.yaml").get("model", {})
    for key, environment_name in {
        "base_url": "TRACEGUARD_OLLAMA_URL",
        "chat_model": "TRACEGUARD_CHAT_MODEL",
        "embedding_model": "TRACEGUARD_EMBEDDING_MODEL",
    }.items():
        if value := os.getenv(environment_name):
            model[key] = value
    return model

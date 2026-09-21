"""Small YAML configuration loader used by the Phase 1 application."""

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
    return load_yaml("config/app.yaml")


def model_config() -> dict[str, Any]:
    return load_yaml("config/model.yaml").get("model", {})

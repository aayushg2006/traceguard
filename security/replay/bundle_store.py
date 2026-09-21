"""Predictable local failure-bundle storage."""

import json
from pathlib import Path

from security.replay.failure_bundle import FailureBundle, FailureBundleError, sanitize, validate_bundle


def save_bundle(bundle: FailureBundle, root: str | Path = "reports/failures") -> Path:
    validate_bundle(bundle)
    directory = Path(root) / bundle.bundle_id
    directory.mkdir(parents=True, exist_ok=False)
    bundle_path = directory / "bundle.json"
    bundle_path.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    metadata = {
        "bundle_id": bundle.bundle_id,
        "test_id": bundle.test_id,
        "category": bundle.category,
        "original_status": bundle.original_status.value,
    }
    (directory / "metadata.json").write_text(json.dumps(sanitize(metadata), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return bundle_path


def list_bundles(root: str | Path = "reports/failures") -> list[Path]:
    path = Path(root)
    if not path.exists():
        return []
    return sorted(item / "bundle.json" for item in path.iterdir() if item.is_dir() and (item / "bundle.json").exists())

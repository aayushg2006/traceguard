"""Sanitized, fixed-source APIs for the TraceGuard dashboard."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit

import httpx
import yaml
from fastapi import APIRouter, HTTPException, Query

from app.config import ROOT, app_config, model_config
from security.replay.failure_bundle import sanitize


router = APIRouter(prefix="/api")
REPORT_PATHS = {
    "security": ROOT / "reports/security-report.json",
    "regression": ROOT / "reports/regression-report.json",
    "mutation": ROOT / "reports/mutation-report.json",
    "replay": ROOT / "reports/replay-report.json",
    "policy": ROOT / "reports/policy-result.json",
    "changes": ROOT / "reports/change-impact.json",
    "baseline": ROOT / "reports/baseline.json",
}
FAILURE_ROOT = ROOT / "reports/failures"
SAFE_BUNDLE_ID = re.compile(r"^FB-[A-Za-z0-9-]+$")


def _unavailable(reason: str) -> dict[str, Any]:
    return {"available": False, "reason": reason}


def _load_report(name: str) -> dict[str, Any]:
    path = REPORT_PATHS[name]
    if not path.is_file():
        return _unavailable(f"Report unavailable: {name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _unavailable(f"Report could not be read: {name}")
    if not isinstance(value, dict):
        return _unavailable(f"Report has an invalid shape: {name}")
    return {"available": True, "source": f"reports/{path.name}", "report": sanitize(value)}


def _report(name: str) -> dict[str, Any] | None:
    result = _load_report(name)
    return result.get("report") if result.get("available") else None


def _security_summary(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return _unavailable("Security report unavailable")
    scores = report.get("scores", {})
    categories = scores.get("categories", {})
    return {
        "available": True,
        "scan_id": report.get("scan_id"),
        "timestamp": report.get("timestamp"),
        "model": report.get("model", {}),
        "execution": report.get("execution", {}),
        "overall": scores.get("overall", {}),
        "categories": categories,
        "target": report.get("target", {}),
    }


def _failure_paths() -> list[Path]:
    if not FAILURE_ROOT.is_dir():
        return []
    return sorted(
        path / "bundle.json"
        for path in FAILURE_ROOT.iterdir()
        if path.is_dir() and (path / "bundle.json").is_file()
    )


def _load_bundle(bundle_id: str) -> dict[str, Any] | None:
    if not SAFE_BUNDLE_ID.fullmatch(bundle_id):
        return None
    path = FAILURE_ROOT / bundle_id / "bundle.json"
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return sanitize(value) if isinstance(value, dict) else None


def _runtime_status(status: str, detail: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {"status": status}
    if detail:
        value["detail"] = detail
    return value


def _runtime() -> dict[str, Any]:
    settings = app_config()
    rag = settings.get("rag", {})
    documents = ROOT / str(rag.get("documents_path", "app/rag/documents"))
    persist = Path(str(rag.get("persist_directory", "data/chroma")))
    if not persist.is_absolute():
        persist = ROOT / persist

    model = model_config()
    ollama_url = str(model.get("base_url", "")).rstrip("/")
    try:
        response = httpx.get(f"{ollama_url}/api/tags", timeout=2)
        response.raise_for_status()
        ollama = _runtime_status("Connected")
    except (httpx.HTTPError, ValueError) as exc:
        ollama = _runtime_status("Unavailable", str(exc))

    document_count = len(list(documents.glob("*.md"))) if documents.is_dir() else 0
    return {
        "available": True,
        "application": _runtime_status("Healthy"),
        "fastapi": _runtime_status("Healthy"),
        "ollama": ollama,
        "rag": _runtime_status("Available" if document_count else "Unavailable", f"{document_count} documents"),
        "chromadb": _runtime_status("Available" if persist.exists() else "Unavailable"),
        "docker": _runtime_status("Running" if Path("/.dockerenv").exists() else "Unavailable"),
        "container": _runtime_status("Running" if Path("/.dockerenv").exists() else "Unavailable"),
        "ollama_endpoint": _safe_endpoint(ollama_url),
    }


def _safe_endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value)
        return f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else "configured"
    except ValueError:
        return "configured"


def _git_commits(limit: int = 20) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "log", f"-{limit}", "--format=%H%x1f%h%x1f%s%x1f%an%x1f%aI"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
    except (OSError, subprocess.TimeoutExpired):
        return _unavailable("Git history is unavailable")
    if result.returncode != 0:
        return _unavailable("Git history is unavailable")
    commits = []
    for line in result.stdout.splitlines():
        fields = line.split("\x1f")
        if len(fields) == 5:
            commits.append({"sha": fields[0], "short_sha": fields[1], "message": fields[2], "author": fields[3], "timestamp": fields[4]})
    return {"available": True, "commits": commits}


def _jenkins() -> dict[str, Any]:
    base_url = os.getenv("TRACEGUARD_JENKINS_URL", "http://127.0.0.1:8080").rstrip("/")
    job_name = os.getenv("TRACEGUARD_JENKINS_JOB", "traceguard").strip("/")
    endpoint = f"{base_url}/job/{quote(job_name, safe='/')}/lastBuild/api/json"
    auth_user = os.getenv("TRACEGUARD_JENKINS_USER")
    auth_token = os.getenv("TRACEGUARD_JENKINS_TOKEN")
    auth = (auth_user, auth_token) if auth_user and auth_token else None
    try:
        response = httpx.get(
            endpoint,
            params={"tree": "number,result,building,timestamp,duration,url,displayName,fullDisplayName,artifacts[fileName,relativePath]"},
            auth=auth,
            timeout=3,
        )
        response.raise_for_status()
        build = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        reason = "Jenkins is unavailable"
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403}:
            reason = "Jenkins authentication is required; configure TRACEGUARD_JENKINS_USER and TRACEGUARD_JENKINS_TOKEN"
        return _unavailable(reason)
    if not isinstance(build, dict):
        return _unavailable("Jenkins returned an invalid build response")
    return {
        "available": True,
        "url": _safe_endpoint(base_url),
        "job": job_name,
        "build": sanitize(build),
        "policy": _load_report("policy"),
    }


@router.get("/dashboard/overview")
def overview() -> dict[str, Any]:
    security = _report("security")
    regression = _load_report("regression")
    changes = _load_report("changes")
    policy = _load_report("policy")
    return {
        "available": True,
        "security": _security_summary(security),
        "regression": regression,
        "changes": changes,
        "policy": policy,
        "runtime": _runtime(),
    }


@router.get("/security/tests")
def security_tests(
    category: str | None = Query(default=None),
    status: str | None = Query(default=None),
    severity: str | None = Query(default=None),
    test_id: str | None = Query(default=None),
) -> dict[str, Any]:
    report = _report("security")
    if not report:
        return _unavailable("Security report unavailable")
    results = report.get("results", [])
    filtered = [
        sanitize(item)
        for item in results
        if isinstance(item, dict)
        and (not category or item.get("category") == category)
        and (not status or item.get("status") == status)
        and (not severity or item.get("severity") == severity)
        and (not test_id or item.get("test_id") == test_id)
    ]
    return {"available": True, "timestamp": report.get("timestamp"), "total": len(filtered), "results": filtered}


@router.get("/security/tests/{test_id}")
def security_test_detail(test_id: str) -> dict[str, Any]:
    result = security_tests(category=None, status=None, severity=None, test_id=test_id)
    if not result.get("available"):
        return result
    if not result["results"]:
        raise HTTPException(status_code=404, detail="Security test not found")
    return {"available": True, "result": result["results"][0]}


@router.get("/changes")
def changes() -> dict[str, Any]:
    result = _load_report("changes")
    if not result.get("available"):
        return result
    report = result["report"]
    return {
        "available": True,
        "selection": report.get("selection", {}),
        "changes": report.get("changed_files", report.get("changes", [])),
        "base": report.get("base"),
        "current": report.get("current"),
        "reason": report.get("selection", {}).get("reason"),
    }


@router.get("/regression")
def regression() -> dict[str, Any]:
    result = _load_report("regression")
    if not result.get("available"):
        return result
    return {"available": True, **result["report"]}


@router.get("/mutations")
def mutations() -> dict[str, Any]:
    result = _load_report("mutation")
    if not result.get("available"):
        return result
    return {"available": True, **result["report"]}


@router.get("/failures")
def failures() -> dict[str, Any]:
    bundles = []
    for path in _failure_paths():
        bundle = _load_bundle(path.parent.name)
        if bundle:
            bundles.append({
                "bundle_id": bundle.get("bundle_id"),
                "test_id": bundle.get("test_id"),
                "category": bundle.get("category"),
                "severity": bundle.get("severity"),
                "original_status": bundle.get("original_status"),
                "created_at": bundle.get("created_at"),
            })
    return {"available": True, "total": len(bundles), "bundles": bundles}


@router.get("/failures/{bundle_id}")
def failure_detail(bundle_id: str) -> dict[str, Any]:
    bundle = _load_bundle(bundle_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail="Failure bundle not found")
    replay = _report("replay")
    return {"available": True, "bundle": bundle, "replay": replay}


@router.get("/policy")
def policy() -> dict[str, Any]:
    policy_path = ROOT / "config/policy.yaml"
    try:
        configuration = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        configuration = {}
    result = _load_report("policy")
    return {
        "available": True,
        "configuration": sanitize(configuration),
        "result": result,
    }


@router.get("/cicd")
def cicd() -> dict[str, Any]:
    jenkins = _jenkins()
    history = _git_commits()
    if not jenkins.get("available"):
        return {**jenkins, "git_history": history}
    return {**jenkins, "git_history": history}


@router.get("/commits")
def commits() -> dict[str, Any]:
    return _git_commits()


@router.get("/runtime")
def runtime() -> dict[str, Any]:
    return _runtime()


@router.get("/settings")
def settings() -> dict[str, Any]:
    app_settings = app_config()
    model = model_config()
    policy_path = ROOT / "config/policy.yaml"
    try:
        policy_settings = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        policy_settings = {}
    return {
        "available": True,
        "application": {
            "name": app_settings.get("application", {}).get("name"),
            "host": app_settings.get("application", {}).get("host"),
            "port": app_settings.get("application", {}).get("port"),
        },
        "model": {
            "provider": model.get("provider"),
            "chat_model": model.get("chat_model"),
            "embedding_model": model.get("embedding_model"),
            "ollama_endpoint": _safe_endpoint(str(model.get("base_url", ""))),
        },
        "policy": sanitize(policy_settings),
        "environment": "container" if Path("/.dockerenv").exists() else "local",
    }

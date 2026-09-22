import json

from fastapi.testclient import TestClient

from app.main import app
from app.api import dashboard


client = TestClient(app)


def test_dashboard_overview_uses_real_report_data():
    response = client.get("/api/dashboard/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["security"]["overall"]["score"] == 100.0
    assert body["policy"]["report"]["decision"] == "ALLOW"


def test_dashboard_report_endpoints_and_failure_detail():
    assert client.get("/api/security/tests").json()["total"] == 13
    assert client.get("/api/regression").json()["regression"]["status"] == "UNCHANGED"
    assert client.get("/api/mutations").json()["detected_mutations"] == 1
    assert client.get("/api/failures").json()["total"] >= 1
    assert client.get("/api/policy").json()["result"]["report"]["decision"] == "ALLOW"


def test_dashboard_rejects_arbitrary_bundle_paths():
    response = client.get("/api/failures/%2E%2E/%2E%2E/etc/passwd")
    assert response.status_code == 404


def test_dashboard_sanitizes_secret_like_metadata(tmp_path, monkeypatch):
    report_path = tmp_path / "security.json"
    report_path.write_text(json.dumps({
        "timestamp": "2026-01-01T00:00:00Z",
        "results": [{
            "test_id": "TEST-1", "category": "data_leakage", "severity": "high",
            "status": "PASS", "score": 100, "request": "synthetic request",
            "response": "synthetic response", "evidence": "safe",
            "metadata": {"api_token": "never-return-this"},
        }],
    }), encoding="utf-8")
    monkeypatch.setitem(dashboard.REPORT_PATHS, "security", report_path)

    response = client.get("/api/security/tests/TEST-1")
    assert response.status_code == 200
    assert response.json()["result"]["metadata"]["api_token"] == "[REDACTED]"


def test_missing_report_is_explicitly_unavailable(tmp_path, monkeypatch):
    monkeypatch.setitem(dashboard.REPORT_PATHS, "regression", tmp_path / "missing.json")
    response = client.get("/api/regression")
    assert response.status_code == 200
    assert response.json() == {"available": False, "reason": "Report unavailable: regression"}


def test_cicd_exposes_git_history_even_when_jenkins_is_unavailable(monkeypatch):
    def unavailable(*args, **kwargs):
        raise dashboard.httpx.ConnectError("connection refused")

    monkeypatch.setattr(dashboard.httpx, "get", unavailable)
    response = client.get("/api/cicd")
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is False
    assert body["git_history"]["available"] is True
    assert body["git_history"]["commits"]


def test_cicd_sanitizes_live_jenkins_build(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"number": 9, "result": "SUCCESS", "building": False, "url": "http://jenkins/job/traceguard/9/", "token": "do-not-return"}

    monkeypatch.setenv("TRACEGUARD_JENKINS_URL", "http://jenkins.test")
    monkeypatch.setattr(dashboard.httpx, "get", lambda *args, **kwargs: FakeResponse())
    body = client.get("/api/cicd").json()
    assert body["available"] is True
    assert body["build"]["result"] == "SUCCESS"
    assert body["build"]["token"] == "[REDACTED]"

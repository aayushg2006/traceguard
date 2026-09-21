from pathlib import Path


JENKINSFILE = Path(__file__).resolve().parents[1] / "Jenkinsfile"


def test_jenkinsfile_orchestrates_existing_traceguard_clis():
    text = JENKINSFILE.read_text(encoding="utf-8")
    for command in (
        "scripts/analyze_changes.py",
        "scripts/run_security_tests.py",
        "scripts/compare_regression.py",
        "scripts/evaluate_policy.py",
    ):
        assert command in text
    assert "reports/policy-exit-code.txt" in text
    assert "reports/traceguard-mode.txt" in text
    assert "reports/traceguard-categories.txt" in text
    assert "writeFile" in text
    assert "readFile('reports/policy-exit-code.txt')" in text
    assert "--junitxml=reports/pytest.xml" in text


def test_jenkinsfile_does_not_duplicate_policy_or_deployment_logic():
    text = JENKINSFILE.read_text(encoding="utf-8")
    assert "security_score" not in text
    assert "docker build --tag" in text
    assert "TRACEGUARD_DOCKER_DEPLOY_VALUE" in text
    assert "readFile('reports/policy-exit-code.txt').trim() == '0'" in text
    assert "kubectl" not in text
    assert "credentials(" not in text

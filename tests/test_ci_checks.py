"""El gate debe fallar ante suites incompletas, skips y reportes inválidos."""
import json

import pytest
from scripts.ci_checks import CRITICAL_TESTS, prepare_env, validate_db, verify_tests, verify_trivy


def report(tmp_path, extra="", complete=True):
    names = CRITICAL_TESTS if complete else {"test_only_unit"}
    path = tmp_path / "junit.xml"
    path.write_text('<testsuites><testsuite>' + ''.join(f'<testcase name="{name}">{extra if index == 0 else ""}</testcase>' for index, name in enumerate(sorted(names))) + '</testsuite></testsuites>')
    return path


def test_ci_rejects_missing_database(monkeypatch):
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(ValueError, match="exige PostgreSQL"):
        validate_db()


def test_ci_generated_env_is_private_and_valid(tmp_path, monkeypatch):
    path = tmp_path / "ci.env"
    prepare_env(path)
    values = dict(line.split('=', 1) for line in path.read_text().splitlines())
    monkeypatch.setenv("TEST_DATABASE_URL", values["TEST_DATABASE_URL"])
    validate_db()
    assert path.stat().st_mode & 0o777 == 0o600
    assert len(values['POSTGRES_PASSWORD']) >= 32


@pytest.mark.parametrize("extra,complete", [("<skipped/>", True), ("<failure/>", True), ("", False)])
def test_ci_rejects_skips_failures_and_missing_critical(tmp_path, extra, complete):
    with pytest.raises(ValueError, match="incompleta"):
        verify_tests(report(tmp_path, extra, complete))


def test_ci_complete_suite_and_redacted_report(tmp_path, monkeypatch):
    path = report(tmp_path)
    monkeypatch.setenv("JWT_SECRET", "ci-private-sentinel")
    path.write_text(path.read_text().replace('</testsuites>', '<system-out>ci-private-sentinel</system-out></testsuites>'))
    verify_tests(path)
    assert 'ci-private-sentinel' not in path.read_text()


@pytest.mark.parametrize("severity,blocked", [("MEDIUM", False), ("HIGH", True), ("CRITICAL", True)])
def test_trivy_policy_includes_unfixed(tmp_path, severity, blocked):
    path = tmp_path / "scan.json"
    path.write_text(json.dumps({'SchemaVersion': 2, 'Results': [{'Vulnerabilities': [{'Severity': severity, 'VulnerabilityID': 'TEST-ADVISORY', 'PkgName': 'fixture'}]}]}))
    if blocked:
        with pytest.raises(ValueError, match='Política Trivy'):
            verify_trivy([path])
    else:
        verify_trivy([path])


def test_trivy_missing_result_is_not_success(tmp_path):
    path = tmp_path / "scan.json"
    path.write_text('{}')
    with pytest.raises(ValueError, match='inválido'):
        verify_trivy([path])

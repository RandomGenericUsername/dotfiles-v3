from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from provisioning.adapters.ansible_executor import ProvisionExecutorError
from provisioning.application import resolve_install_dir
from provisioning.domain.models import ProvisionResult
from tests.unit.cli.conftest import FakeDeps, _invoke


def _ok_result() -> ProvisionResult:
    return ProvisionResult(
        success=True,
        tasks=(("install base packages", "ok"),),
        returncode=0,
        stderr="",
    )


def _assert_success_payload(result: Result, command: str) -> None:
    payload = json.loads(result.stdout)
    assert payload["success"] is True
    assert payload["command"] == command
    assert payload["install_dir"] == str(resolve_install_dir())
    assert payload["returncode"] == 0
    assert payload["tasks"] == {"install base packages": "ok"}


def _expected_call(playbook: str, check: bool) -> tuple[Path, bool, dict[str, str]]:
    return (
        Path(playbook),
        check,
        {"install_dir": str(resolve_install_dir()), "os_family": "arch"},
    )


class TestPlanCommand:
    def test_plan_records_provision_check_true(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result())
        result = _invoke(runner, deps, ["plan"], monkeypatch)
        assert result.exit_code == 0, result.stderr
        assert deps.plan_executor.calls == [_expected_call("bootstrap.yaml", True)]
        _assert_success_payload(result, "plan")

    def test_plan_adapter_error_renders_error_view(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result(), error=ProvisionExecutorError("ansible-playbook failed"))
        result = _invoke(runner, deps, ["plan"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionExecutorError"
        assert "ansible-playbook failed" in error_payload["message"]

    def test_plan_failed_result_renders_contextual_error(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(ProvisionResult(success=False, tasks=(), returncode=2, stderr="boom"))
        result = _invoke(runner, deps, ["plan"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionFailed"
        assert "plan failed" in error_payload["message"]
        assert error_payload["details"]["stderr"] == "boom"


class TestApplyCommand:
    def test_apply_records_provision_check_false(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result())
        result = _invoke(runner, deps, ["apply"], monkeypatch)
        assert result.exit_code == 0, result.stderr
        assert deps.apply_executor.calls == [_expected_call("bootstrap.yaml", False)]
        _assert_success_payload(result, "apply")

    def test_apply_adapter_error_renders_error_view(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result(), error=ProvisionExecutorError("ansible-playbook failed"))
        result = _invoke(runner, deps, ["apply"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionExecutorError"

    def test_apply_failed_result_renders_contextual_error(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(ProvisionResult(success=False, tasks=(), returncode=2, stderr="boom"))
        result = _invoke(runner, deps, ["apply"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionFailed"
        assert "apply failed" in error_payload["message"]


class TestVerifyCommand:
    def test_verify_records_verify_call(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result())
        result = _invoke(runner, deps, ["verify"], monkeypatch)
        assert result.exit_code == 0, result.stderr
        assert deps.verify_executor.calls == [_expected_call("verify.yaml", False)]
        _assert_success_payload(result, "verify")

    def test_verify_adapter_error_renders_error_view(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result(), error=ProvisionExecutorError("ansible-playbook failed"))
        result = _invoke(runner, deps, ["verify"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionExecutorError"

    def test_verify_failed_result_renders_contextual_error(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(ProvisionResult(success=False, tasks=(), returncode=2, stderr="boom"))
        result = _invoke(runner, deps, ["verify"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionFailed"
        assert "verify failed" in error_payload["message"]


class TestBootstrapCommand:
    def test_bootstrap_defaults_to_check_false(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result())
        result = _invoke(runner, deps, ["bootstrap"], monkeypatch)
        assert result.exit_code == 0, result.stderr
        assert deps.bootstrap_executor.calls == [_expected_call("bootstrap.yaml", False)]
        _assert_success_payload(result, "bootstrap")

    def test_bootstrap_check_flag_records_check_true(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result())
        result = _invoke(runner, deps, ["bootstrap", "--check"], monkeypatch)
        assert result.exit_code == 0, result.stderr
        assert deps.bootstrap_executor.calls == [_expected_call("bootstrap.yaml", True)]

    def test_bootstrap_adapter_error_renders_error_view(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(_ok_result(), error=ProvisionExecutorError("ansible-playbook failed"))
        result = _invoke(runner, deps, ["bootstrap"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionExecutorError"

    def test_bootstrap_failed_result_renders_contextual_error(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        deps = FakeDeps(ProvisionResult(success=False, tasks=(), returncode=2, stderr="boom"))
        result = _invoke(runner, deps, ["bootstrap"], monkeypatch)
        assert result.exit_code != 0
        error_payload = json.loads(result.stderr)
        assert error_payload["kind"] == "ProvisionFailed"
        assert "bootstrap failed" in error_payload["message"]

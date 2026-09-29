from __future__ import annotations

import io
import json
import logging
import os
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

from provisioning.adapters.ansible_executor import (
    AnsibleExecutor,
    ProvisionExecutorError,
    ProvisionTimeoutError,
    _ansible_env,
)
from provisioning.domain.models import ProvisionResult


def _completed(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess[str](
        args=["ansible-playbook"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


class _FakePopen:
    """Minimal ``Popen`` double for the default runner: serves canned pipes,
    records its kwargs (notably ``env``), and honors ``kill``."""

    def __init__(self, command: list[str], **kwargs: object) -> None:
        self.command = command
        self.kwargs = {key: value for key, value in kwargs.items() if not key.startswith("canned_")}
        self._stdout = io.BytesIO(str(kwargs.get("canned_stdout", "")).encode())
        self._stderr = io.BytesIO(str(kwargs.get("canned_stderr", "")).encode())
        self.returncode: int | None = int(str(kwargs.get("canned_returncode", 0)))
        self.killed = False

    @property
    def stdout(self) -> io.BytesIO:
        return self._stdout

    @property
    def stderr(self) -> io.BytesIO:
        return self._stderr

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int | None:
        return self.returncode

    def kill(self) -> None:
        self.killed = True


def _install_fake_popen(
    monkeypatch: pytest.MonkeyPatch,
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> list[_FakePopen]:
    """Patch ``Popen`` in the executor module; returns the created doubles."""
    created: list[_FakePopen] = []

    def factory(command: list[str], **kwargs: object) -> _FakePopen:
        proc = _FakePopen(
            command,
            **kwargs,
            canned_stdout=stdout,
            canned_stderr=stderr,
            canned_returncode=returncode,
        )
        created.append(proc)
        return proc

    monkeypatch.setattr("provisioning.adapters.ansible_executor.subprocess.Popen", factory)
    return created


class TestAnsibleExecutor:
    def _executor(
        self,
        commands: list[list[str]],
        *,
        returncode: int = 0,
        stdout: str = "",
        stderr: str = "",
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
        timeout: float | None = None,
    ) -> AnsibleExecutor:
        if runner is None:

            def default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
                commands.append(command)
                return _completed(returncode, stdout, stderr)

            runner = default_runner
        return AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"),
            tags="all",
            timeout=timeout,
            runner=runner,
        )

    def test_check_flag_present_when_check_true(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(
            Path("bootstrap.yaml"),
            check=True,
            extra_vars={"install_dir": "/x", "os_family": "arch"},
        )
        assert "--check" in commands[0]

    def test_check_flag_absent_when_check_false(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(Path("bootstrap.yaml"), check=False, extra_vars={})
        assert "--check" not in commands[0]

    def test_inventory_tags_and_playbook_present(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(Path("playbooks/packages.yaml"), check=True, extra_vars={})
        command = commands[0]
        assert command[0] == "ansible-playbook"
        assert command[command.index("-i") + 1] == "inventory/localhost.yaml"
        assert command[command.index("--tags") + 1] == "all"
        assert command[-1] == "playbooks/packages.yaml"

    def test_extra_vars_carry_exactly_install_dir_and_os_family(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(
            Path("bootstrap.yaml"),
            check=True,
            extra_vars={"install_dir": "/x", "os_family": "arch"},
        )
        command = commands[0]
        extra_vars = command[command.index("--extra-vars") + 1]
        assert json.loads(extra_vars) == {"install_dir": "/x", "os_family": "arch"}

    def test_extra_vars_values_with_spaces_survive_round_trip(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands)
        executor.run(
            Path("bootstrap.yaml"),
            check=True,
            extra_vars={"install_dir": "/home/me/My Documents", "os_family": "arch"},
        )
        command = commands[0]
        extra_vars = command[command.index("--extra-vars") + 1]
        assert json.loads(extra_vars) == {
            "install_dir": "/home/me/My Documents",
            "os_family": "arch",
        }

    def test_parses_tasks_from_stdout(self) -> None:
        stdout = (
            "PLAY [Provision localhost]\n\n"
            "TASK [packages : install hyprland] *************************\n"
            "changed: [localhost]\n\n"
            "TASK [packages : install ags] ****************************\n"
            "ok: [localhost]\n\n"
            "PLAY RECAP ***************************************************\n"
            "localhost : ok=1 changed=1 unreachable=0 failed=0\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (
            ("packages : install hyprland", "changed"),
            ("packages : install ags", "ok"),
        )

    def test_fatal_failure_recorded_as_failed(self) -> None:
        stdout = (
            "TASK [packages : install hyprland] *************************\n"
            'fatal: [localhost]: FAILED! => {"changed": false}\n'
            "PLAY RECAP ***************************************************\n"
            "localhost : ok=0 changed=0 unreachable=0 failed=1\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout, returncode=2)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (("packages : install hyprland", "failed"),)
        assert result.success is False

    def test_failure_detail_captures_stdout_fatal_when_stderr_empty(self) -> None:
        """A failed command's error text lives on stdout (ansible's stderr is
        empty for task failures), so failure_detail must surface it — otherwise
        the CLI reports a blank cause."""
        stdout = (
            "TASK [packages : Refresh pacman databases before install] ***\n"
            'fatal: [localhost]: FAILED! => {"changed": true, '
            '"msg": "non-zero return code", "rc": 1, "stderr": "", '
            '"stdout": "error: failed to synchronize all databases"}\n'
            "PLAY RECAP ***************************************************\n"
            "localhost : ok=0 changed=0 unreachable=0 failed=1\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout, returncode=2, stderr="")
        result = executor.run(Path("bootstrap.yaml"), check=False, extra_vars={})
        assert result.stderr == ""
        assert result.failure_detail.startswith("fatal: [localhost]")
        assert "failed to synchronize all databases" in result.failure_detail

    def test_failure_detail_includes_failed_status_lines(self) -> None:
        stdout = (
            "TASK [packages : install hyprland] *************************\n"
            'failed: [localhost] (item=hyprland) => {"msg": "No space left on device"}\n'
            "TASK [packages : install ags] ****************************\n"
            "changed: [localhost]\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout, returncode=0, stderr="")
        result = executor.run(Path("bootstrap.yaml"), check=False, extra_vars={})
        assert "No space left on device" in result.failure_detail
        assert "changed:" not in result.failure_detail

    def test_failure_detail_empty_on_clean_run(self) -> None:
        stdout = (
            "TASK [packages : install hyprland] *************************\nchanged: [localhost]\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.failure_detail == ""

    def test_warnings_captured_from_both_streams_deduped(self) -> None:
        """`[WARNING]`/`[DEPRECATION WARNING]` headers from either stream must
        land on the result (deduped, first-seen order) — a green run's
        warnings must not scroll by unnoticed the way the INJECT_FACTS
        deprecation did."""
        stdout = (
            "TASK [zsh_config : Ensure zsh is the login shell] ************\n"
            "changed: [localhost]\n"
        )
        stderr = (
            "[WARNING]: Deprecation warnings can be disabled by setting `deprecation_warnings=False` in ansible.cfg.\n"
            "[DEPRECATION WARNING]: INJECT_FACTS_AS_VARS default to `True` is deprecated.\n"
            "[DEPRECATION WARNING]: INJECT_FACTS_AS_VARS default to `True` is deprecated.\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout, stderr=stderr)
        result = executor.run(Path("bootstrap.yaml"), check=False, extra_vars={})
        assert result.success is True
        assert result.warnings == (
            "[WARNING]: Deprecation warnings can be disabled by setting `deprecation_warnings=False` in ansible.cfg.",
            "[DEPRECATION WARNING]: INJECT_FACTS_AS_VARS default to `True` is deprecated.",
        )

    def test_warnings_empty_on_clean_run(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout="ok: [localhost]\n", stderr="")
        result = executor.run(Path("bootstrap.yaml"), check=False, extra_vars={})
        assert result.warnings == ()

    def test_failed_task_with_ignore_errors_yields_success_false(self) -> None:
        stdout = (
            "TASK [packages : install hyprland] *************************\n"
            "failed: [localhost]\n"
            "PLAY RECAP ***************************************************\n"
            "localhost : ok=0 changed=0 unreachable=0 failed=1\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout, returncode=0)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (("packages : install hyprland", "failed"),)
        assert result.success is False

    def test_gathering_facts_task_is_omitted(self) -> None:
        stdout = (
            "TASK [Gathering Facts] *************************************\n"
            "ok: [localhost]\n\n"
            "TASK [packages : install hyprland] *************************\n"
            "changed: [localhost]\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (("packages : install hyprland", "changed"),)

    def test_multihost_status_collapses_to_worst_per_task(self) -> None:
        stdout = (
            "TASK [packages : install hyprland] *************************\n"
            "ok: [host1]\n"
            "changed: [host2]\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (("packages : install hyprland", "changed"),)

    def test_ansi_colored_output_is_parsed(self) -> None:
        stdout = (
            "\x1b[0;36mTASK [packages : install hyprland]\x1b[0m\n"
            "\x1b[0;32mchanged: [localhost]\x1b[0m\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (("packages : install hyprland", "changed"),)

    def test_zero_returncode_yields_success(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands, returncode=0)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result is not None
        assert isinstance(result, ProvisionResult)
        assert result.success is True
        assert result.returncode == 0

    def test_non_zero_returncode_yields_success_false(self) -> None:
        commands: list[list[str]] = []
        executor = self._executor(commands, returncode=2, stderr="boom")
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.success is False
        assert result.returncode == 2
        assert result.stderr == "boom"

    def test_timeout_raises_provision_timeout_error(self) -> None:
        def timing_out(command: list[str]) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(command, timeout=5)

        executor = self._executor([], runner=timing_out, timeout=5)
        with pytest.raises(ProvisionTimeoutError):
            executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})

    def test_missing_binary_raises_provision_executor_error(self) -> None:
        def missing_binary(command: list[str]) -> subprocess.CompletedProcess[str]:
            raise FileNotFoundError("ansible-playbook not found")

        executor = self._executor([], runner=missing_binary)
        with pytest.raises(ProvisionExecutorError, match="failed to run"):
            executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})

    def test_empty_tags_rejected_at_construction(self) -> None:
        with pytest.raises(ValueError, match="non-empty"):
            AnsibleExecutor(inventory=Path("inventory.yaml"), tags="  ")


class TestAnsibleEnv:
    def test_none_config_file_returns_none(self) -> None:
        assert _ansible_env(None) is None

    def test_config_file_sets_ansible_config_and_preserves_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("EXISTING_VAR", "preserved")
        env = _ansible_env(Path("ansible.cfg"))
        assert env is not None
        assert env["ANSIBLE_CONFIG"] == "ansible.cfg"
        assert env["EXISTING_VAR"] == "preserved"

    def test_become_password_injected_as_ansible_sudo_pass(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        env = _ansible_env(Path("ansible.cfg"), become_password="secret")
        assert env is not None
        assert env["ANSIBLE_SUDO_PASS"] == "secret"
        assert env["ANSIBLE_CONFIG"] == "ansible.cfg"

    def test_no_become_password_means_no_sudo_pass_env(self) -> None:
        env = _ansible_env(Path("ansible.cfg"))
        assert env is not None
        assert "ANSIBLE_SUDO_PASS" not in env

    def test_config_file_does_not_mutate_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXISTING_VAR", "preserved")
        _ansible_env(Path("ansible.cfg"))
        assert "ANSIBLE_CONFIG" not in dict(os.environ)

    def test_config_file_warns_when_overriding_existing_ansible_config(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("ANSIBLE_CONFIG", "/custom/ansible.cfg")
        with caplog.at_level(logging.WARNING, logger="provisioning.adapters.ansible_executor"):
            env = _ansible_env(Path("ansible.cfg"))
        assert env is not None
        assert env["ANSIBLE_CONFIG"] == "ansible.cfg"
        assert any("Overriding ANSIBLE_CONFIG" in record.message for record in caplog.records)

    def test_config_file_warns_only_when_value_differs(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        monkeypatch.setenv("ANSIBLE_CONFIG", "ansible.cfg")
        with caplog.at_level(logging.WARNING, logger="provisioning.adapters.ansible_executor"):
            env = _ansible_env(Path("ansible.cfg"))
        assert env is not None
        assert env["ANSIBLE_CONFIG"] == "ansible.cfg"
        assert not any("Overriding ANSIBLE_CONFIG" in record.message for record in caplog.records)

    def test_default_runner_forwards_ansible_config_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        procs = _install_fake_popen(monkeypatch)
        executor = AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"),
            tags="all",
            config_file=Path("ansible.cfg"),
        )
        executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert len(procs) == 1
        env = procs[0].kwargs.get("env")
        assert isinstance(env, dict)
        assert env["ANSIBLE_CONFIG"] == "ansible.cfg"

    def test_default_runner_forwards_become_password_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        procs = _install_fake_popen(monkeypatch)
        executor = AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"),
            tags="all",
            config_file=Path("ansible.cfg"),
            become_password="secret",
        )
        executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert len(procs) == 1
        env = procs[0].kwargs.get("env")
        assert isinstance(env, dict)
        assert env["ANSIBLE_CONFIG"] == "ansible.cfg"
        assert env["ANSIBLE_SUDO_PASS"] == "secret"

    def test_default_runner_inherits_env_without_config_file(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        procs = _install_fake_popen(monkeypatch)
        executor = AnsibleExecutor(inventory=Path("inventory/localhost.yaml"), tags="all")
        executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert len(procs) == 1
        env = procs[0].kwargs.get("env")
        assert isinstance(env, dict)
        assert env["PYTHONUNBUFFERED"] == "1"
        assert env["PATH"] == os.environ["PATH"]
        assert "ANSIBLE_CONFIG" not in env

    def test_default_runner_forces_unbuffered_child_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Live streaming needs writer-side unbuffered output — a piped
        ansible-playbook would otherwise block-buffer and arrive in bursts."""
        procs = _install_fake_popen(monkeypatch)
        executor = AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"),
            tags="all",
            config_file=Path("ansible.cfg"),
        )
        executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        env = procs[0].kwargs.get("env")
        assert isinstance(env, dict)
        assert env["PYTHONUNBUFFERED"] == "1"
        assert env["ANSIBLE_CONFIG"] == "ansible.cfg"

    def test_default_runner_streams_transcript_to_stderr_live(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The playbook transcript must reach stderr while the run is in
        flight (not just in the parsed result) — and parsing still works off
        the accumulated transcript. Stdout stays clean for the result views."""
        stdout = (
            "TASK [packages : install hyprland] *************************\nchanged: [localhost]\n"
        )
        _install_fake_popen(monkeypatch, stdout=stdout, stderr="some warning\n")
        executor = AnsibleExecutor(inventory=Path("inventory/localhost.yaml"), tags="all")
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        captured = capsys.readouterr()
        assert "TASK [packages : install hyprland]" in captured.err
        assert "changed: [localhost]" in captured.err
        assert "some warning" in captured.err
        assert captured.out == ""
        assert result.tasks == (("packages : install hyprland", "changed"),)
        assert result.success is True

    def test_default_runner_timeout_kills_and_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A hung playbook is killed and surfaces as ProvisionTimeoutError,
        exactly like the old subprocess.run path."""

        class HangingPopen(_FakePopen):
            def wait(self, timeout: float | None = None) -> int | None:
                raise subprocess.TimeoutExpired(self.command, timeout or 0)

        created: list[_FakePopen] = []

        def factory(command: list[str], **kwargs: object) -> HangingPopen:
            proc = HangingPopen(command, **kwargs)
            created.append(proc)
            return proc

        monkeypatch.setattr("provisioning.adapters.ansible_executor.subprocess.Popen", factory)
        executor = AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"), tags="all", timeout=5
        )
        with pytest.raises(ProvisionTimeoutError):
            executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert created[0].killed is True

    def test_injected_runner_does_not_stream(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Streaming is a default-runner behavior only — injected fakes stay
        silent so unit tests never pollute captured output."""

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            return _completed(0, stdout="TASK [x] ***\nchanged: [localhost]\n")

        executor = AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"), tags="all", runner=runner
        )
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.success is True
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_config_file_with_injected_runner_keeps_injected_contract(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            return _completed(0, stdout="ok", stderr="")

        executor = AnsibleExecutor(
            inventory=Path("inventory/localhost.yaml"),
            tags="all",
            runner=runner,
            config_file=Path("ansible.cfg"),
        )
        result = executor.run(
            Path("bootstrap.yaml"),
            check=True,
            extra_vars={"install_dir": "/x", "os_family": "arch"},
        )
        assert result.success is True
        command, kwargs = calls[0]
        assert command[0] == "ansible-playbook"
        assert command[-1] == "bootstrap.yaml"
        assert kwargs == {}, (
            "injected runner must receive no env — contract stays "
            "Callable[[list[str]], CompletedProcess]"
        )

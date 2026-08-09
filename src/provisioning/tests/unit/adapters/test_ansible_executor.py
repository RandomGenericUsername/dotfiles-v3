from __future__ import annotations

import json
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
            "TASK [packages : install waybar] ****************************\n"
            "ok: [localhost]\n\n"
            "PLAY RECAP ***************************************************\n"
            "localhost : ok=1 changed=1 unreachable=0 failed=0\n"
        )
        commands: list[list[str]] = []
        executor = self._executor(commands, stdout=stdout)
        result = executor.run(Path("bootstrap.yaml"), check=True, extra_vars={})
        assert result.tasks == (
            ("packages : install hyprland", "changed"),
            ("packages : install waybar", "ok"),
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

    def test_config_file_does_not_mutate_os_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EXISTING_VAR", "preserved")
        _ansible_env(Path("ansible.cfg"))
        assert "ANSIBLE_CONFIG" not in dict(os.environ)

    def test_config_file_with_injected_runner_keeps_injected_contract(self) -> None:
        commands: list[list[str]] = []

        def runner(command: list[str]) -> subprocess.CompletedProcess[str]:
            commands.append(command)
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
        assert commands[0][0] == "ansible-playbook"
        assert commands[0][-1] == "bootstrap.yaml"

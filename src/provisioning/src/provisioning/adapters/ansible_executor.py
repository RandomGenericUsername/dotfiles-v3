"""Ansible-playbook executor adapter.

Shells to ``ansible-playbook`` with ``-i``, ``--tags``, ``--check`` (plan mode)
and ``--extra-vars``, surfacing per-task ``changed``/``ok`` results in
``ProvisionResult``. The ``extra_vars`` mapping is a sealed seam: exactly the
keys the caller supplies are passed through — no additions, no removal (AC 4).
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from provisioning.domain.models import ProvisionResult
from provisioning.ports import IProvisionExecutor

_TASK_HEADER_RE = re.compile(r"^TASK \[(.+)\]")
_RESULT_STATUS_RE = re.compile(r"^(ok|changed|failed|skipped|unreachable|ignored|rescued):")


def _default_runner(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True)


def _extra_vars_arg(extra_vars: Mapping[str, str]) -> str:
    return " ".join(f"{key}={value}" for key, value in extra_vars.items())


def _parse_tasks(stdout: str) -> tuple[tuple[str, str], ...]:
    """Extract ``(task_label, status)`` pairs from the play recap output."""
    tasks: list[tuple[str, str]] = []
    current: str | None = None
    for line in stdout.splitlines():
        stripped = line.strip()
        header = _TASK_HEADER_RE.match(stripped)
        if header:
            current = header.group(1)
            continue
        status = _RESULT_STATUS_RE.match(stripped)
        if status and current is not None:
            tasks.append((current, status.group(1)))
    return tuple(tasks)


class AnsibleExecutor(IProvisionExecutor):
    """Drive ``ansible-playbook`` against the local host.

    Inventory and tags are constructor configuration (the port only passes
    ``playbook`` / ``check`` / ``extra_vars``). The command runner is injectable
    so tests never invoke a real playbook.
    """

    def __init__(
        self,
        inventory: Path,
        tags: str,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self._inventory = inventory
        self._tags = tags
        self._runner = runner if runner is not None else _default_runner

    def run(
        self,
        playbook: Path,
        check: bool,
        extra_vars: Mapping[str, str],
    ) -> ProvisionResult:
        command = [
            "ansible-playbook",
            "-i",
            str(self._inventory),
            "--tags",
            self._tags,
        ]
        if check:
            command.append("--check")
        command.append("--extra-vars")
        command.append(_extra_vars_arg(extra_vars))
        command.append(str(playbook))
        proc = self._runner(command)
        return ProvisionResult(
            success=proc.returncode == 0,
            tasks=_parse_tasks(proc.stdout),
        )


__all__ = ["AnsibleExecutor"]

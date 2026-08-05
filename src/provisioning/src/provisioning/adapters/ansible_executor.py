"""Ansible-playbook executor adapter.

Shells to ``ansible-playbook`` with ``-i``, ``--tags``, ``--check`` (plan mode)
and ``--extra-vars``, surfacing per-task ``changed``/``ok`` results in
``ProvisionResult``. The ``extra_vars`` mapping is a sealed seam: exactly the
keys the caller supplies are passed through — no additions, no removal (AC 4).
"""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path

from provisioning.domain.models import ProvisionResult
from provisioning.ports import IProvisionExecutor

_TASK_HEADER_RE = re.compile(r"^TASK \[(.+)\]")
_RESULT_STATUS_RE = re.compile(r"^(ok|changed|failed|skipped|unreachable|ignored|rescued):")
_FATAL_RE = re.compile(r"^fatal: \[[^\]]+\]: (FAILED!|UNREACHABLE!)")
_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")
_STATUS_PRIORITY = {
    "failed": 0,
    "unreachable": 1,
    "rescued": 2,
    "ignored": 3,
    "changed": 4,
    "skipped": 5,
    "ok": 6,
}


class ProvisionExecutorError(ValueError):
    """Raised when ``ansible-playbook`` cannot be run or its output read."""


class ProvisionTimeoutError(ProvisionExecutorError):
    """Raised when ``ansible-playbook`` exceeds the configured timeout."""


def _default_runner(
    command: list[str], timeout: float | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout)


def _extra_vars_arg(extra_vars: Mapping[str, str]) -> str:
    return json.dumps(dict(extra_vars))


def _strip_ansi(line: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", line)


def _parse_tasks(stdout: str) -> tuple[tuple[str, str], ...]:
    """Extract ``(task_label, status)`` pairs from the play output.

    The implicit "Gathering Facts" task is omitted and per-host status lines
    are collapsed to a single entry per task (worst status wins) so the surface
    stays per-task. ANSI color codes are stripped before matching, and hard
    failures printed as ``fatal: ... FAILED!`` are recorded as ``failed``.
    """
    tasks: dict[str, str] = {}
    order: list[str] = []
    current: str | None = None

    def record(label: str, status: str) -> None:
        if label not in tasks:
            tasks[label] = status
            order.append(label)
        elif _STATUS_PRIORITY[status] < _STATUS_PRIORITY[tasks[label]]:
            tasks[label] = status

    for raw_line in stdout.splitlines():
        line = _strip_ansi(raw_line.strip())
        header = _TASK_HEADER_RE.match(line)
        if header:
            current = header.group(1)
            if current == "Gathering Facts":
                current = None
            continue
        if current is None:
            continue
        fatal = _FATAL_RE.match(line)
        if fatal:
            record(current, fatal.group(1).lower().rstrip("!"))
            current = None
            continue
        status = _RESULT_STATUS_RE.match(line)
        if status:
            record(current, status.group(1))
    return tuple((label, tasks[label]) for label in order)


class AnsibleExecutor(IProvisionExecutor):
    """Drive ``ansible-playbook`` against the local host.

    Inventory and tags are constructor configuration (the port only passes
    ``playbook`` / ``check`` / ``extra_vars``). The command runner is injectable
    so tests never invoke a real playbook; ``timeout`` bounds a hung run.
    """

    def __init__(
        self,
        inventory: Path,
        tags: str,
        timeout: float | None = None,
        runner: Callable[[list[str]], subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        if not tags.strip():
            raise ValueError("tags must be a non-empty string")
        self._inventory = inventory
        self._tags = tags
        self._timeout = timeout
        if runner is not None:
            self._runner = runner
        else:
            self._runner = lambda command: _default_runner(command, timeout)

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
        try:
            proc = self._runner(command)
        except subprocess.TimeoutExpired as exc:
            raise ProvisionTimeoutError(
                f"ansible-playbook exceeded {self._timeout}s timeout for {playbook}"
            ) from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise ProvisionExecutorError(
                f"failed to run ansible-playbook for {playbook}: {exc}"
            ) from exc
        tasks = _parse_tasks(proc.stdout)
        success = proc.returncode == 0 and not any(
            status in ("failed", "unreachable") for _, status in tasks
        )
        return ProvisionResult(
            success=success,
            tasks=tasks,
            returncode=proc.returncode,
            stderr=proc.stderr or "",
        )


__all__ = [
    "AnsibleExecutor",
    "ProvisionExecutorError",
    "ProvisionTimeoutError",
]

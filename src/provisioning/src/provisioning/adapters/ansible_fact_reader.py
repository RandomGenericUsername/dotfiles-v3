"""Ansible fact adapter.

Runs ``ansible -m setup`` and extracts ``ansible_os_family``, mapping it to the
``group_vars`` basename (``"arch"`` | ``"debian-family"``). This is the only
distro seam the Python side uses — it selects which ``group_vars`` apply and
never inspects packages.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable

from provisioning.domain.enums import Distro
from provisioning.ports import IFactReader


class UnknownOsFamilyError(ValueError):
    """Raised when ``ansible -m setup`` reports an unsupported ``os_family``."""


class InvalidFactOutputError(ValueError):
    """Raised when the ``ansible -m setup`` output cannot be parsed."""


# Explicit, exhaustive mapping from ansible_os_family to group_vars basename.
# No silent fallback: any value not listed here fails loudly (AC 5).
_OS_FAMILY_TO_GROUP_VARS: dict[str, str] = {
    "Archlinux": Distro.ARCH.value,
    "Debian": Distro.DEBIAN_FAMILY.value,
    "Ubuntu": Distro.DEBIAN_FAMILY.value,
}

_SUPPORTED_FAMILIES = ", ".join(sorted(_OS_FAMILY_TO_GROUP_VARS))

_EMBEDDED_PAYLOAD_LIMIT = 200


def _default_runner(command: list[str], timeout: float | None = None) -> str:
    proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise InvalidFactOutputError(
            f"ansible -m setup exited with {proc.returncode}: {_truncate(proc.stderr or '')}"
        )
    return proc.stdout


def _truncate(text: str, limit: int = _EMBEDDED_PAYLOAD_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"... ({len(text) - limit} chars truncated)"


def _extract_os_family(output: str) -> str:
    """Parse the ``ansible -m setup`` JSON payload for ``ansible_os_family``.

    Locates the JSON object line-by-line, tolerating a leading ``host | SUCCESS
    => `` prefix and ``[WARNING]`` lines that may themselves contain braces:
    each candidate line is tried until one parses as a JSON object.
    """
    lines = output.splitlines()
    payload: object | None = None
    for index, line in enumerate(lines):
        start = line.find("{")
        if start == -1:
            continue
        candidate = line[start:] + "".join(lines[index + 1 :])
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        break
    if not isinstance(payload, dict):
        raise InvalidFactOutputError(
            f"ansible -m setup produced no JSON object in output: {_truncate(output)}"
        )
    facts = payload.get("ansible_facts")
    if not isinstance(facts, dict):
        raise InvalidFactOutputError(
            f"ansible -m setup output is missing 'ansible_facts': {_truncate(str(payload))}"
        )
    family = facts.get("ansible_os_family")
    if not isinstance(family, str):
        raise InvalidFactOutputError(
            f"ansible -m setup output is missing 'ansible_os_family': {_truncate(str(facts))}"
        )
    return family


class AnsibleFactReader(IFactReader):
    """Read the target machine's OS family by running ``ansible -m setup``."""

    def __init__(
        self,
        host: str = "localhost",
        timeout: float | None = None,
        runner: Callable[[list[str]], str] | None = None,
    ) -> None:
        self._host = host
        self._timeout = timeout
        if runner is not None:
            self._runner = runner
        else:
            self._runner = lambda command: _default_runner(command, timeout)

    def os_family(self) -> str:
        try:
            output = self._runner(["ansible", "-m", "setup", self._host])
        except subprocess.TimeoutExpired as exc:
            raise InvalidFactOutputError(
                f"ansible -m setup exceeded {self._timeout}s timeout for host {self._host!r}"
            ) from exc
        except (OSError, UnicodeDecodeError) as exc:
            raise InvalidFactOutputError(
                f"failed to run ansible -m setup for host {self._host!r}: {exc}"
            ) from exc
        family = _extract_os_family(output)
        group_vars = _OS_FAMILY_TO_GROUP_VARS.get(family)
        if group_vars is None:
            raise UnknownOsFamilyError(
                f"unsupported ansible_os_family {family!r}; supported values: {_SUPPORTED_FAMILIES}"
            )
        return group_vars


__all__ = ["AnsibleFactReader", "InvalidFactOutputError", "UnknownOsFamilyError"]

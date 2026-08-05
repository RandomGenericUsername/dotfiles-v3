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


def _default_runner(command: list[str]) -> str:
    proc = subprocess.run(command, capture_output=True, text=True, check=True)
    return proc.stdout


def _extract_os_family(output: str) -> str:
    """Parse the ``ansible -m setup`` JSON payload for ``ansible_os_family``."""
    start = output.find("{")
    end = output.rfind("}")
    if start == -1 or end <= start:
        raise InvalidFactOutputError(
            f"ansible -m setup produced no JSON object in output: {output!r}"
        )
    try:
        payload = json.loads(output[start : end + 1])
    except json.JSONDecodeError as exc:
        raise InvalidFactOutputError(f"ansible -m setup produced invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise InvalidFactOutputError(
            f"ansible -m setup output must be a JSON object, got {type(payload).__name__}"
        )
    facts = payload.get("ansible_facts")
    if not isinstance(facts, dict):
        raise InvalidFactOutputError(
            f"ansible -m setup output is missing 'ansible_facts': {payload!r}"
        )
    family = facts.get("ansible_os_family")
    if not isinstance(family, str):
        raise InvalidFactOutputError(
            f"ansible -m setup output is missing 'ansible_os_family': {facts!r}"
        )
    return family


class AnsibleFactReader(IFactReader):
    """Read the target machine's OS family by running ``ansible -m setup``."""

    def __init__(
        self,
        host: str = "localhost",
        runner: Callable[[list[str]], str] | None = None,
    ) -> None:
        self._host = host
        self._runner = runner if runner is not None else _default_runner

    def os_family(self) -> str:
        output = self._runner(["ansible", "-m", "setup", self._host])
        family = _extract_os_family(output)
        group_vars = _OS_FAMILY_TO_GROUP_VARS.get(family)
        if group_vars is None:
            raise UnknownOsFamilyError(
                f"unsupported ansible_os_family {family!r}; supported values: {_SUPPORTED_FAMILIES}"
            )
        return group_vars


__all__ = ["AnsibleFactReader", "InvalidFactOutputError", "UnknownOsFamilyError"]

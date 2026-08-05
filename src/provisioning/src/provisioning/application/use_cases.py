"""Use cases for the provisioning orchestrator.

The application layer wires the locked ports (Story 1.4) into three use
cases that run playbooks through ``IProvisionExecutor``:

- ``ProvisionMachineUseCase`` plans (``check=True``) or applies
  (``check=False``) machine state.
- ``VerifyCapabilityUseCase`` asserts the §12 runtime preconditions via the
  verify playbook (always a real check, never ``--check``).
- ``BootstrapUseCase`` runs the aggregate bootstrap playbook end-to-end
  (``check=True`` supports ``bootstrap --check``).

All three resolve the two seam extra-vars — ``install_dir`` and
``os_family`` — via the shared ``_seam_extra_vars`` helper and hand them to
the executor.
"""

from __future__ import annotations

import os
from pathlib import Path

from provisioning.domain.models import ProvisionResult
from provisioning.ports import IFactReader, IProvisionExecutor


def resolve_install_dir() -> Path:
    """Resolve the install spine root: ``$XDG_DATA_HOME/dotfiles/``.

    Defaults to ``~/.local/share/dotfiles/`` when ``XDG_DATA_HOME`` is unset
    (SPEC / chaining-spine contract). The result is an absolute path.
    """
    data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(data_home) if data_home else Path.home() / ".local" / "share"
    return (base / "dotfiles").expanduser().resolve()


def _seam_extra_vars(fact_reader: IFactReader) -> dict[str, str]:
    """Resolve the two locked seam extra-vars for a provisioning run.

    Returns exactly ``install_dir`` (resolved spine root) and ``os_family``
    (the ``group_vars`` basename) — the keys Story 1.5's seam contract test
    pins and no others.
    """
    return {
        "install_dir": str(resolve_install_dir()),
        "os_family": fact_reader.os_family(),
    }


class ProvisionMachineUseCase:
    """Plan or apply machine state through the locked provisioning ports.

    ``check=True`` is plan mode (no system changes); ``check=False`` is apply
    mode. The ``os_family`` seam is read from ``IFactReader`` and the install
    dir is resolved here, then both are passed via the ``extra_vars`` seam —
    exactly the ``install_dir`` + ``os_family`` keys Story 1.5's seam contract
    locks.
    """

    def __init__(
        self,
        executor: IProvisionExecutor,
        fact_reader: IFactReader,
        playbook: Path = Path("bootstrap.yaml"),
    ) -> None:
        self._executor = executor
        self._fact_reader = fact_reader
        self._playbook = playbook

    def provision(self, check: bool) -> ProvisionResult:
        return self._executor.run(self._playbook, check, _seam_extra_vars(self._fact_reader))


class VerifyCapabilityUseCase:
    """Assert the §12 runtime preconditions via the verify playbook.

    The four preconditions (binaries installed, assets placed, filesystem
    structure exists, settings files parseable) are asserted by the Ansible
    ``verify.yaml`` playbook (Epic 2 content) — this use case is the Python
    orchestration seam that runs it through ``IProvisionExecutor`` with a real
    check (never ``--check``), without reaching into provisioning internals.
    """

    def __init__(
        self,
        executor: IProvisionExecutor,
        fact_reader: IFactReader,
        playbook: Path = Path("verify.yaml"),
    ) -> None:
        self._executor = executor
        self._fact_reader = fact_reader
        self._playbook = playbook

    def verify(self) -> ProvisionResult:
        return self._executor.run(self._playbook, False, _seam_extra_vars(self._fact_reader))


class BootstrapUseCase:
    """Run the aggregate ``bootstrap.yaml`` playbook end-to-end.

    ``check=True`` supports ``dotfiles-provision bootstrap --check``; the
    default ``check=False`` is the full end-to-end provisioning run (FR-4).
    """

    def __init__(
        self,
        executor: IProvisionExecutor,
        fact_reader: IFactReader,
        playbook: Path = Path("bootstrap.yaml"),
    ) -> None:
        self._executor = executor
        self._fact_reader = fact_reader
        self._playbook = playbook

    def bootstrap(self, check: bool = False) -> ProvisionResult:
        return self._executor.run(self._playbook, check, _seam_extra_vars(self._fact_reader))


__all__ = [
    "BootstrapUseCase",
    "ProvisionMachineUseCase",
    "VerifyCapabilityUseCase",
    "resolve_install_dir",
]

"""Use cases for the provisioning orchestrator.

The application layer wires the locked ports (Story 1.4) into a
``ProvisionMachineUseCase`` that plans (``check=True``) or applies
(``check=False``) machine state. It resolves the two seam extra-vars —
``install_dir`` and ``os_family`` — and hands them to the executor.
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
        os_family = self._fact_reader.os_family()
        install_dir = resolve_install_dir()
        return self._executor.run(
            self._playbook,
            check,
            {"install_dir": str(install_dir), "os_family": os_family},
        )


__all__ = ["ProvisionMachineUseCase", "resolve_install_dir"]

"""Pure, zero-I/O domain models for the provisioning orchestrator.

This module imports nothing from the standard library that performs I/O
(no ``os``, ``subprocess``, ``shutil``, ``pathlib``) and nothing from other
packages. It is the innermost ring of the provisioning hexagon.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from provisioning.domain.enums import Distro, ManifestKind


@dataclass(frozen=True)
class Spec:
    """A single desired machine-state entry (package, asset, symlink, CLI tool)."""

    name: str
    version: str | None = None


@dataclass(frozen=True)
class MachineState:
    """The desired machine state provisioning reconciles against."""

    distro: Distro
    install_dir: str


@dataclass(frozen=True)
class ProvisionManifest:
    """A parsed declarative manifest (``dotfiles/provisioning/*.yaml``)."""

    kind: ManifestKind
    entries: tuple[Spec, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProvisionResult:
    """The outcome of a provisioning run, surfaced per task.

    ``returncode`` and ``stderr`` carry the raw ``ansible-playbook`` outcome so
    the application layer can surface the cause of a failed run without
    re-reaching into the adapter. ``failure_detail`` carries the per-task
    failure lines ansible writes to *stdout* (``fatal:`` / ``failed:``) — the
    only place a task's error text lives, since ansible's stderr is typically
    empty for a failed task.
    """

    success: bool
    tasks: tuple[tuple[str, str], ...] = field(default_factory=tuple)
    returncode: int = 0
    stderr: str = ""
    failure_detail: str = ""


__all__ = [
    "MachineState",
    "ProvisionManifest",
    "ProvisionResult",
    "Spec",
]

"""Pure, zero-I/O domain models for the provisioning orchestrator.

This module imports nothing from the standard library that performs I/O
(no ``os``, ``subprocess``, ``shutil``, ``pathlib``) and nothing from other
packages. It is the innermost ring of the provisioning hexagon.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from provisioning.domain.enums import Distro


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

    kind: str
    entries: tuple[Spec, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProvisionResult:
    """The outcome of a provisioning run, surfaced per task."""

    success: bool
    tasks: tuple[tuple[str, str], ...] = field(default_factory=tuple)


__all__ = [
    "MachineState",
    "ProvisionManifest",
    "ProvisionResult",
    "Spec",
]

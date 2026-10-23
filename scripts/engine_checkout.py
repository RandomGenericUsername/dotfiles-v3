#!/usr/bin/env python3
"""Resolve the pinned installer-engine checkout used by composition gates.

The installer engine (`dotfiles-provision`) is an external repo pinned by TAG.
`dotfiles/provisioning/installer.pin` is the one source of truth: bootstrap.sh
reads it in shell, and the Python gates read it here. A tag is never moved, so a
cached checkout at that tag is immutable.

The composition gates (`deploy-coverage`, `ansible-embedded-template-lint`) read
the engine's Ansible tree (roles, playbooks) instead of authoring one in this
repo. They resolve `.dev/dotfiles-provision-<tag>/` (gitignored) and fetch it on
demand. `DOTFILES_PROVISION_CACHE_DIR` overrides the parent dir for a read-only
composition checkout (the dev VM mounts the repo read-only).

Offline behaviour: an ABSENT cache fails loudly with the pin and the exact cache
path — the gates never fall back to a stale in-repo copy (there is none). Set
`DOTFILES_PROVISION_OFFLINE=1` to turn a miss into one sentence and guarantee no
clone attempt (a sealed runner with a pre-populated cache still gates).
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

ENGINE_REPO = "https://github.com/RandomGenericUsername/dotfiles-provision"
PIN_FILE = "dotfiles/provisioning/installer.pin"
_PIN_RE = re.compile(r"^v\d+\.\d+\.\d+$")


class EngineCheckoutError(RuntimeError):
    """The pin is missing/invalid or the pinned checkout cannot be fetched."""


def read_engine_pin(repo_root: Path) -> str:
    """Return the pinned engine tag, asserting it is a semver tag.

    A branch, `latest`, or a commit SHA would make "the pinned engine" a moving
    target; the repo discipline is annotated, monotonic tags (`ARCHITECTURE.md`
    section 4).
    """
    path = repo_root / PIN_FILE
    try:
        tag = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise EngineCheckoutError(
            f"cannot read the installer pin {PIN_FILE}: {exc}"
        ) from exc
    if not _PIN_RE.fullmatch(tag):
        raise EngineCheckoutError(
            f"{PIN_FILE} must contain one semver tag (vX.Y.Z, never a branch, "
            f"`latest`, or a SHA); got {tag!r}"
        )
    return tag


def cache_root(repo_root: Path) -> Path:
    """The cache parent: `.dev/` by default, overridable for read-only checkouts."""
    override = os.environ.get("DOTFILES_PROVISION_CACHE_DIR")
    if override:
        return Path(override).expanduser()
    return repo_root / ".dev"


def offline() -> bool:
    """True when the caller forbids network fetches (R-16)."""
    return os.environ.get("DOTFILES_PROVISION_OFFLINE", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def engine_checkout(repo_root: Path, fetch: bool = True) -> Path:
    """Return a checkout of the engine at the pin, fetching it when absent.

    A present cache is validated at the git level when possible: a checkout
    whose HEAD is not the pinned tag is replaced, so a hand-edited or stale
    cache can never silently become the gate's input. With
    `DOTFILES_PROVISION_OFFLINE=1` (or `fetch=False`) a miss never attempts a
    clone: it fails with the one-sentence pre-populate instruction.
    """
    tag = read_engine_pin(repo_root)
    dest = cache_root(repo_root) / f"dotfiles-provision-{tag}"
    no_fetch = not fetch or offline()

    if _checkout_matches_pin(dest, tag):
        return dest
    if dest.exists():
        if no_fetch:
            raise EngineCheckoutError(
                f"offline: the cached engine checkout {dest} is not at {tag}; "
                f"pre-populate it at {tag} or unset DOTFILES_PROVISION_OFFLINE"
            )
        _remove(dest)

    if no_fetch:
        raise EngineCheckoutError(
            f"offline: the pinned engine checkout is missing at {dest}; "
            f"pre-populate that directory at {tag} or unset DOTFILES_PROVISION_OFFLINE"
        )

    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        proc = subprocess.run(
            [
                "git",
                "clone",
                "--quiet",
                "--depth",
                "1",
                "--branch",
                tag,
                ENGINE_REPO,
                str(dest),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise EngineCheckoutError(
            f"cannot run git to fetch the pinned engine {tag}: {exc}"
        ) from exc
    if proc.returncode != 0:
        _remove(dest)
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        reason = detail[-1] if detail else f"git exit {proc.returncode}"
        raise EngineCheckoutError(
            f"cannot fetch the pinned installer engine {tag} into {dest} "
            f"({reason}). The composition gates need the engine checkout; "
            f"connect once, or pre-populate {dest} at {tag}. Offline is a hard "
            f"failure, never a silent pass."
        )
    if not _checkout_matches_pin(dest, tag):
        raise EngineCheckoutError(
            f"fetched {dest} but it does not look like the {tag} engine checkout "
            f"(missing ansible/ or src/provisioning/, or HEAD != tag)"
        )
    return dest


def _checkout_matches_pin(path: Path, tag: str) -> bool:
    if not (path / "ansible" / "inventory" / "localhost.yaml").is_file():
        return False
    if not (path / "src" / "provisioning").is_dir():
        return False
    if not (path / ".git").exists():
        # A vendored/pre-populated tree without git metadata is accepted on
        # content shape; the pin file still records what it must be.
        return True
    try:
        head = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        pinned = subprocess.run(
            ["git", "-C", str(path), "rev-parse", f"{tag}^{{commit}}"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return False
    return head == pinned


def _remove(path: Path) -> None:
    import shutil

    shutil.rmtree(path, ignore_errors=True)

"""Locate the source repo used as a container image build context.

A CLI installed via ``uv tool install`` (or ``pip install``) from a repo path
has no build context of its own: the image build needs the *source tree* (the
``src/cli-tools/...`` and ``src/shared/...`` directories) as ``docker build`` /
``podman build`` context. When running from a source checkout the package files
already resolve to the repo, but from an installed tool they resolve to the
tool's site-packages, which contains only the packaged Python code.

This module rediscovers the repo root from, in priority order:

1. an explicit ``override`` path (CLI ``--source-root`` flag),
2. an env var named by the caller (``CSG_SOURCE_ROOT`` / ``WEG_SOURCE_ROOT``),
3. the PEP 610 ``direct_url.json`` the installer wrote into the package's
   ``.dist-info`` (uv and pip both record the original ``file://`` source path),
4. a legacy walk up from the package location (source checkout / editable
   install, where the repo is still on disk).

If nothing resolves, :class:`SourceRootNotFoundError` is raised — the image
build cannot proceed, so the CLI must fail loudly instead of silently producing
a stale image.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, distribution
from importlib.resources import files as resource_files
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import url2pathname

from oci_runtime.domain.exceptions import SourceRootNotFoundError

# The monorepo layout marker: a repo root contains both `src/cli-tools` and
# `src/shared` as directories.
_REPO_MARKER_DIRS = ("src", "cli-tools"), ("src", "shared")


@dataclass(frozen=True)
class SourceRoot:
    """The resolved source repo root plus how it was discovered."""

    root: Path
    source: str


def _repo_root_from_candidate(candidate: Path) -> Path | None:
    """Return the repo root that contains ``candidate``, or None.

    Walks up from ``candidate`` looking for the first ancestor that carries the
    monorepo layout marker (``src/cli-tools`` and ``src/shared``). Works both
    when ``candidate`` is the repo root itself and when it is any directory
    inside the repo (package dir, ``src/``, etc.).
    """
    for parent in (candidate, *candidate.parents):
        if all((parent.joinpath(*part)).is_dir() for part in _REPO_MARKER_DIRS):
            return parent
    return None


def _direct_url_package_dir(package: str) -> Path | None:
    """Return the install-source directory recorded by PEP 610, or None."""
    try:
        dist = distribution(package)
    except PackageNotFoundError:
        return None
    try:
        raw = dist.read_text("direct_url.json")
    except (OSError, AttributeError):
        return None
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    url = data.get("url")
    if not url:
        return None
    parsed = urlparse(url)
    if parsed.scheme != "file":
        return None
    return Path(url2pathname(parsed.path))


def _resource_package_dir(package: str) -> Path | None:
    """Return the on-disk package directory from ``importlib.resources``.

    Only meaningful for source checkouts and editable installs, where the
    package files live inside the repo. From a regular installed tool this
    returns the site-packages package dir, which carries no repo marker.
    """
    try:
        res = resource_files(package)
    except (ModuleNotFoundError, TypeError, NotImplementedError):
        return None
    try:
        pkg_path = Path(str(res))
    except (TypeError, ValueError):
        return None
    if not pkg_path.is_dir():
        return None
    return pkg_path


def resolve_source_root(
    *,
    package: str,
    override: str | Path | None = None,
    env_var: str | None = None,
    env: dict[str, str] | None = None,
) -> SourceRoot:
    """Resolve the repo root used as the container build context.

    Priority: ``override`` > ``env_var`` > PEP 610 ``direct_url.json`` > package
    walk. Raises :class:`SourceRootNotFoundError` when nothing resolves.
    """
    candidates: list[tuple[str, Path]] = []

    if override is not None:
        candidates.append(("override", Path(override)))

    if env_var is not None:
        value = (env if env is not None else os.environ).get(env_var)
        if value:
            candidates.append(("env", Path(value)))

    pkg_dir = _direct_url_package_dir(package)
    if pkg_dir is not None:
        candidates.append(("direct_url", pkg_dir))

    pkg_dir = _resource_package_dir(package)
    if pkg_dir is not None:
        candidates.append(("package", pkg_dir))

    for source, candidate in candidates:
        root = _repo_root_from_candidate(candidate)
        if root is not None:
            return SourceRoot(root=root, source=source)

    raise SourceRootNotFoundError(package=package, env_var=env_var)

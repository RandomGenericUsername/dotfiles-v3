"""Resolve the pinned `dotfiles-assets` `templates` class from a dev checkout or a spine.

S3 moved every Jinja source out of this repository: the five rendering roles read
`<install>/assets/<tag>/templates/…` from the checkout the assets role materializes.
A unit test therefore cannot read the template bodies from its own checkout, and it
must not vendor a copy (a second source of truth drifts by construction).

Resolution order, mirroring `test_compositor_configs_role.py`'s
`_assets_configs_file` / `_authored_icons_yaml`:

1. ``$DOTFILES_ASSETS_TEMPLATES_DIR`` — an explicit templates-class directory;
2. a local ``dotfiles-assets`` checkout — ``$DOTFILES_ASSETS_REPO`` else
   ``/home/inumaki/Development/dotfiles/dotfiles-assets`` (the sibling-checkout
   convention `_AGS_APPS_REPO` already uses for the ags-apps unit);
3. the provisioned spine — ``$DOTFILES_INSTALL_SPINE`` else
   ``$XDG_DATA_HOME/dotfiles``, then ``assets/<role's pinned tag>/templates``.

``None`` means "not provided": the caller must SKIP LOUDLY rather than seed a stub,
because a stub would test the stub. CI has no assets checkout, so most of these
tests skip there — which is why `test_template_vars_parity.py` reports its coverage
instead of pretending a skip is a pass.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[4]
ANSIBLE_DIR = REPO_ROOT / "src" / "provisioning" / "ansible"
ROLES_DIR = ANSIBLE_DIR / "roles"

#: The sibling checkout convention (see `_AGS_APPS_REPO` in
#: `test_compositor_configs_role.py`).
DEFAULT_ASSETS_REPO = Path("/home/inumaki/Development/dotfiles/dotfiles-assets")


def role_vars(role: str) -> dict[str, Any]:
    """Load a role's `vars/main.yml` (the mirror a render task reads from)."""
    data = yaml.safe_load((ROLES_DIR / role / "vars" / "main.yml").read_text())
    assert isinstance(data, dict), f"{role}/vars/main.yml must be a mapping"
    return data


def role_tasks(role: str) -> list[dict[str, Any]]:
    data = yaml.safe_load((ROLES_DIR / role / "tasks" / "main.yml").read_text())
    assert isinstance(data, list), f"{role}/tasks/main.yml must be a list"
    return data


def assets_tag(role: str) -> str:
    """The role's AD-6 pin mirror (`<role>_assets_pinned_tag`)."""
    data = role_vars(role)
    key = f"{role}_assets_pinned_tag"
    assert key in data, f"{role}/vars/main.yml must carry the {key} mirror of assets.tag"
    return str(data[key])


def _candidates(role: str | None) -> list[Path]:
    candidates: list[Path] = []
    explicit = os.environ.get("DOTFILES_ASSETS_TEMPLATES_DIR")
    if explicit:
        candidates.append(Path(explicit).expanduser())
    checkout = Path(os.environ.get("DOTFILES_ASSETS_REPO", DEFAULT_ASSETS_REPO)).expanduser()
    candidates.append(checkout / "templates")
    spine = os.environ.get("DOTFILES_INSTALL_SPINE")
    if spine:
        base = Path(spine).expanduser()
    else:
        xdg_data = Path(
            os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share"
        )
        base = xdg_data / "dotfiles"
    if role is not None:
        candidates.append(base / "assets" / assets_tag(role) / "templates")
    return candidates


def _holds_templates(base: Path) -> bool:
    """True when `base` is a templates-class directory with at least one source."""
    if not base.is_dir():
        return False
    return any(base.rglob("*.j2")) or any(base.rglob("*.tpl"))


def templates_root(role: str | None = None) -> Path | None:
    """The first candidate that holds at least one Jinja source, else `None`."""
    for base in _candidates(role):
        if _holds_templates(base):
            return base
    return None


def require_templates_root(role: str | None = None) -> Path:
    root = templates_root(role)
    if root is None:
        tried = ", ".join(str(p) for p in _candidates(role))
        pytest.skip(
            "the pinned dotfiles-assets `templates` class is not available; the "
            "template body lives in the corpus, not in this checkout. Set "
            f"DOTFILES_ASSETS_TEMPLATES_DIR or clone dotfiles-assets. Tried: {tried}"
        )
    return root


def template_file(relative: str, role: str | None = None) -> Path:
    """Resolve one template inside the corpus; SKIP loudly when the corpus is absent."""
    root = require_templates_root(role)
    path = root / relative
    if not path.is_file():
        pytest.skip(
            f"{relative} is missing from the resolved templates class at {root} "
            f"(is the checkout at the pinned tag?)"
        )
    return path


def schema_for(relative: str, role: str | None = None) -> dict[str, Any]:
    """Load the vars schema that sits beside `relative`."""
    import json

    stem = relative
    for suffix in (".j2", ".tpl"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    path = require_templates_root(role) / f"{stem}.vars.schema.json"
    if not path.is_file():
        pytest.skip(f"no vars schema beside {relative} at {path.parent}")
    return json.loads(path.read_text())


def seed_install(install: Path, role: str) -> Path:
    """Materialize `<install>/assets/<tag>/templates` so a role can render in isolation.

    Execution tests run ONE role against a temp spine; the assets role (which clones
    the corpus) does not run. Copying the resolved class into the tag-shaped path is
    what makes the render read the REAL bodies — a stub would test the stub.
    """
    root = require_templates_root(role)
    tag = assets_tag(role)
    target = install / "assets" / tag / "templates"
    if not target.is_dir():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(root, target)
    return target

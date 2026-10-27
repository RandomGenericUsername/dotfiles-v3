#!/usr/bin/env python3
"""Composition-side validation for the per-app AGS consumption program.

The `contracts` repo owns the canonical JSON Schemas (v0.3.0):
`schemas/ags-apps-install-list.schema.json` and
`schemas/program-tuple.schema.json`. The composition gate must run on a stock
checkout without a `contracts` checkout, so this module mirrors the schemas'
structural rules — including the cross-entry `x-uniqueKeys` check that draft-07
cannot express — and exercises them against committed fixtures before it reads
the real list.

What it proves:

* every app appears exactly once with exactly one owner (`legacy|standalone`);
* `legacy` entries carry no repo/tag and `standalone` entries carry both;
* app/installDir/instance/configDir/configLink/spineLink/xdgLink are unique;
* the seven current apps are all present (the gate's inventory check);
* exactly the bar owns `barPalettePointer`;
* the program tuple names exactly `ags-platform`, `contracts` and
  `dotfiles-assets`, is a semver tag triple, and agrees with `assets.tag`;
* for the current legacy entries, every config link is a managed dir in the
  pinned engine's `config_links` role, every instance is in `gui_tools`, the
  launch policy matches `always_on`, every launcher has a real `cli_tools`
  template, and every bin link names an engine `*_bin_link` surface;
* the fixtures accept fully legacy, mixed and all-standalone lists and reject
  duplicate apps/instances/config links, invalid owners and repo/tag
  contradictions; the tuple fixtures reject missing/extra/non-semver records.

A standalone entry is intentionally not checked against the old monorepo role's
surfaces. The provision mirror ticket owns that half; until it lands, a
standalone flip is blocked by the engine tuple equality check below.
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

APPS_MANIFEST = "dotfiles/provisioning/apps.yaml"
PROGRAM_TUPLE = "dotfiles/provisioning/program-tuple.yaml"
ASSETS_MANIFEST = "dotfiles/provisioning/assets.yaml"
FIXTURE_ROOT = "scripts/fixtures/ags-app-consumption"

ENGINE_AGS_APPS_VARS = "ansible/roles/ags_apps/vars/main.yml"
ENGINE_CLI_TOOLS_TASKS = "ansible/roles/cli_tools/tasks/main.yml"
ENGINE_CLI_TOOLS_TEMPLATES = "ansible/roles/cli_tools/templates"
ENGINE_CONFIG_LINKS_VARS = "ansible/roles/config_links/vars/main.yml"
ENGINE_GUI_TOOLS_VARS = "ansible/roles/gui_tools/vars/main.yml"

# The seven apps the composition deploys today. This is an inventory assertion,
# not a second metadata list: every deployment field lives in apps.yaml.
EXPECTED_APPS = frozenset(
    {
        "bar",
        "hypr-pano",
        "notifications",
        "capture",
        "wallpaper-selector",
        "icme",
        "btop-theme-studio",
    }
)

OWNERS = frozenset({"legacy", "standalone"})
LAUNCH_POLICIES = frozenset({"always", "on-demand"})
UNIQUE_KEYS = (
    "app",
    "instance",
    "configDir",
    "configLink",
    "spineLink",
    "xdgLink",
    "installDir",
)

APP_ENTRY_KEYS = frozenset(
    {
        "app",
        "installDir",
        "owner",
        "repo",
        "tag",
        "instance",
        "configDir",
        "configLink",
        "spineLink",
        "xdgLink",
        "binLink",
        "launcher",
        "autostart",
        "launch",
        "barPalettePointer",
        "cutoverId",
    }
)
REQUIRED_APP_KEYS = frozenset(
    {
        "app",
        "installDir",
        "owner",
        "instance",
        "configDir",
        "configLink",
        "spineLink",
        "xdgLink",
        "launch",
        "cutoverId",
    }
)
PATH_SEGMENT_KEYS = frozenset(
    {
        "app",
        "installDir",
        "instance",
        "configDir",
        "configLink",
        "spineLink",
        "xdgLink",
        "binLink",
    }
)

PROGRAM_TUPLE_KEYS = frozenset(
    {"schemaVersion", "ags-platform", "contracts", "dotfiles-assets"}
)

_SEGMENT_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")
_TAG_RE = re.compile(r"^v[0-9]+\.[0-9]+\.[0-9]+(?:[-+][0-9A-Za-z.-]+)?$")

APP_FIXTURE_CASES: dict[str, dict[str, Any]] = {
    "legacy.apps.yaml": {"valid": True, "owners": {"legacy"}},
    "mixed.apps.yaml": {"valid": True, "owners": {"legacy", "standalone"}},
    "all-standalone.apps.yaml": {"valid": True, "owners": {"standalone"}},
    "duplicate-app.apps.yaml": {"valid": False, "needle": "duplicate"},
    "duplicate-instance.apps.yaml": {"valid": False, "needle": "duplicate"},
    "duplicate-config-link.apps.yaml": {"valid": False, "needle": "duplicate"},
    "invalid-owner.apps.yaml": {"valid": False, "needle": "owner"},
    "legacy-with-repo.apps.yaml": {"valid": False, "needle": "legacy"},
    "standalone-missing-repo.apps.yaml": {"valid": False, "needle": "repo"},
}

TUPLE_FIXTURE_CASES: dict[str, bool] = {
    "program-tuple.valid.yaml": True,
    "program-tuple.missing-contracts.yaml": False,
    "program-tuple.extra-tag.yaml": False,
    "program-tuple.invalid-tag.yaml": False,
}


def _load_yaml(path: Path) -> Any:
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - environment guard
        raise RuntimeError(
            f"PyYAML is not importable ({exc}); run this gate through "
            f"`uv run --no-project --with pyyaml python scripts/deploy-coverage.py`"
        ) from exc
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"{path} is not valid YAML: {exc}") from exc


def _fail(source: str, message: str) -> None:
    raise ValueError(f"{source}: {message}")


def _require_mapping(value: Any, source: str, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        _fail(source, f"{label} must be a mapping")
    return value


def _require_str(entry: dict[str, Any], key: str, source: str, index: int) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        _fail(source, f"apps[{index}].{key} must be a non-empty string")
    return value


def _check_path_segment(value: Any, source: str, label: str) -> None:
    if not isinstance(value, str) or not _SEGMENT_RE.fullmatch(value):
        _fail(
            source,
            f"{label} must be exactly one lowercase path segment "
            f"(a-z, 0-9, '-'); got {value!r}",
        )


def validate_app_list(document: Any, source: str) -> list[dict[str, Any]]:
    """Validate the install-list shape and return its entries."""
    data = _require_mapping(document, source, "the app list")
    extra = set(data) - {"apps"}
    if extra:
        _fail(source, f"unknown top-level key(s) {sorted(extra)}")
    apps = data.get("apps")
    if not isinstance(apps, list) or not apps:
        _fail(source, "`apps` must be a non-empty list")

    entries: list[dict[str, Any]] = []
    canonical: set[str] = set()
    for index, raw in enumerate(apps):
        entry = _require_mapping(raw, source, f"apps[{index}]")
        unknown = set(entry) - APP_ENTRY_KEYS
        if unknown:
            _fail(source, f"apps[{index}] has unknown key(s) {sorted(unknown)}")
        missing = REQUIRED_APP_KEYS - set(entry)
        if missing:
            _fail(source, f"apps[{index}] is missing {sorted(missing)}")

        for key in PATH_SEGMENT_KEYS:
            if key in entry:
                _check_path_segment(entry[key], source, f"apps[{index}].{key}")
        for key in ("launcher", "autostart"):
            if key in entry:
                _require_str(entry, key, source, index)
        _require_str(entry, "cutoverId", source, index)

        owner = entry.get("owner")
        if owner not in OWNERS:
            _fail(
                source,
                f"apps[{index}].owner must be one of {sorted(OWNERS)}; got {owner!r}",
            )
        if owner == "standalone":
            _require_str(entry, "repo", source, index)
            tag = _require_str(entry, "tag", source, index)
            if not _TAG_RE.fullmatch(tag):
                _fail(
                    source,
                    f"apps[{index}].tag must be an immutable semver tag "
                    f"(vX.Y.Z); got {tag!r}",
                )
        else:
            for forbidden in ("repo", "tag"):
                if forbidden in entry:
                    _fail(
                        source,
                        f"apps[{index}] is legacy and must not carry `{forbidden}` "
                        f"— the legacy unit has no per-app pin",
                    )

        launch = entry.get("launch")
        if launch not in LAUNCH_POLICIES:
            _fail(
                source,
                f"apps[{index}].launch must be one of "
                f"{sorted(LAUNCH_POLICIES)}; got {launch!r}",
            )
        if "barPalettePointer" in entry and type(entry["barPalettePointer"]) is not bool:
            _fail(source, f"apps[{index}].barPalettePointer must be a boolean")

        fingerprint = json.dumps(entry, sort_keys=True, default=str)
        if fingerprint in canonical:
            _fail(source, f"apps[{index}] duplicates an earlier entry verbatim")
        canonical.add(fingerprint)
        entries.append(entry)

    for key in UNIQUE_KEYS:
        seen: dict[str, int] = {}
        for index, entry in enumerate(entries):
            value = entry.get(key)
            if value in seen:
                _fail(
                    source,
                    f"duplicate {key}: apps[{index}].{key} repeats "
                    f"apps[{seen[value]}].{key} ({value!r}) — exactly one owner "
                    f"per app/instance/link is required",
                )
            seen[value] = index

    owners_by_app: dict[str, set[str]] = {}
    for entry in entries:
        owners_by_app.setdefault(entry["app"], set()).add(entry["owner"])
    for app, owners in owners_by_app.items():
        if len(owners) != 1:
            _fail(
                source,
                f"app {app!r} has {len(owners)} owners {sorted(owners)} — "
                f"exactly one is required",
            )

    for index, entry in enumerate(entries):
        if entry["configDir"] != entry["configLink"]:
            _fail(
                source,
                f"apps[{index}].configDir {entry['configDir']!r} must equal "
                f"configLink {entry['configLink']!r} (manifest identity == "
                f"deployed link basename)",
            )

    pointers = [entry for entry in entries if entry.get("barPalettePointer")]
    if len(pointers) != 1:
        _fail(
            source,
            f"exactly one entry must own barPalettePointer; found {len(pointers)}",
        )
    pointer = pointers[0]
    if pointer["app"] != "bar":
        _fail(
            source,
            f"barPalettePointer belongs to {pointer['app']!r}; only the bar "
            f"entry may own the stable palette pointer",
        )
    if pointer["launch"] != "always":
        _fail(source, "the bar entry with barPalettePointer must use launch: always")
    for index, entry in enumerate(entries):
        if entry["app"] != "bar" and entry.get("barPalettePointer"):
            _fail(
                source,
                f"apps[{index}].barPalettePointer must be unset/false for "
                f"{entry['app']!r}",
            )

    for field in ("launcher", "binLink"):
        seen: dict[str, str] = {}
        for entry in entries:
            value = entry.get(field)
            if value is None:
                continue
            if value in seen:
                _fail(
                    source,
                    f"{field} {value!r} is claimed by both {seen[value]!r} and "
                    f"{entry['app']!r} — one surface, one owner",
                )
            seen[value] = entry["app"]

    for index, entry in enumerate(entries):
        autostart = entry.get("autostart")
        if autostart is not None and autostart != entry["instance"]:
            _fail(
                source,
                f"apps[{index}].autostart {autostart!r} must name the app's own "
                f"instance {entry['instance']!r}",
            )

    return entries


def validate_program_tuple(document: Any, source: str) -> dict[str, Any]:
    """Validate the one program tuple record and return it."""
    data = _require_mapping(document, source, "the program tuple")
    if set(data) != PROGRAM_TUPLE_KEYS:
        _fail(
            source,
            f"the tuple must name exactly {sorted(PROGRAM_TUPLE_KEYS)}; got "
            f"{sorted(data)}",
        )
    if type(data.get("schemaVersion")) is not int or data["schemaVersion"] != 1:
        _fail(source, "schemaVersion must be the integer 1")
    for key in ("ags-platform", "contracts", "dotfiles-assets"):
        tag = data[key]
        if not isinstance(tag, str) or not _TAG_RE.fullmatch(tag):
            _fail(
                source,
                f"{key} must be an immutable semver tag (vX.Y.Z); got {tag!r}",
            )
    return data


def _basename(value: str) -> str:
    return value.rstrip("/").rsplit("/", 1)[-1]


def _engine_data(engine_root: Path, relative: str) -> dict[str, Any]:
    path = engine_root / relative
    if not path.is_file():
        raise ValueError(f"the pinned engine is missing {relative}")
    data = _load_yaml(path)
    if not isinstance(data, dict):
        raise ValueError(f"the pinned engine file {relative} is not a mapping")
    return data


def assert_engine_surfaces(
    entries: list[dict[str, Any]], engine_root: Path, tuple_data: dict[str, Any]
) -> None:
    """Prove every legacy entry names a surface the pinned engine deploys."""
    source = APPS_MANIFEST
    config_links = _engine_data(engine_root, ENGINE_CONFIG_LINKS_VARS)
    managed_dirs = set(config_links.get("config_links_managed_dirs") or [])
    if not managed_dirs:
        raise ValueError(
            f"{ENGINE_CONFIG_LINKS_VARS} has no `config_links_managed_dirs` list"
        )

    gui_tools = _engine_data(engine_root, ENGINE_GUI_TOOLS_VARS)
    instances = {
        str(entry.get("name")): bool(entry.get("always_on"))
        for entry in gui_tools.get("gui_tools_ags_instances") or []
        if isinstance(entry, dict) and entry.get("name")
    }
    if not instances:
        raise ValueError(
            f"{ENGINE_GUI_TOOLS_VARS} has no `gui_tools_ags_instances` entries"
        )

    ags_apps = _engine_data(engine_root, ENGINE_AGS_APPS_VARS)
    old_links = {
        _basename(value)
        for key, value in ags_apps.items()
        if key.startswith("ags_apps_live_")
        and key.endswith("_link")
        and isinstance(value, str)
    }
    old_bin_links = {
        _basename(value)
        for key, value in ags_apps.items()
        if key.endswith("_bin_link") and isinstance(value, str)
    }

    tasks_path = engine_root / ENGINE_CLI_TOOLS_TASKS
    if not tasks_path.is_file():
        raise ValueError(f"the pinned engine is missing {ENGINE_CLI_TOOLS_TASKS}")
    tasks_text = tasks_path.read_text(encoding="utf-8")
    templates_dir = engine_root / ENGINE_CLI_TOOLS_TEMPLATES

    standalone = [entry for entry in entries if entry["owner"] == "standalone"]
    if standalone:
        legacy_platform = ags_apps.get("ags_apps_platform_version")
        if (
            isinstance(legacy_platform, str)
            and legacy_platform != tuple_data["ags-platform"]
        ):
            raise ValueError(
                f"{source}: {len(standalone)} standalone entr"
                f"{'y' if len(standalone) == 1 else 'ies'} exist but the legacy "
                f"unit still resolves ags-platform {legacy_platform!r}, not the "
                f"program tuple {tuple_data['ags-platform']!r} — finish the "
                f"adoption release before any cutover"
            )

    for entry in entries:
        app = entry["app"]
        if entry["owner"] != "legacy":
            continue
        if entry["configDir"] not in managed_dirs:
            raise ValueError(
                f"{source}: app {app!r} configDir {entry['configDir']!r} is not "
                f"managed by {ENGINE_CONFIG_LINKS_VARS}; the XDG link would "
                f"dangle"
            )
        if entry["xdgLink"] not in managed_dirs:
            raise ValueError(
                f"{source}: app {app!r} xdgLink {entry['xdgLink']!r} is not "
                f"managed by {ENGINE_CONFIG_LINKS_VARS}"
            )
        if entry["spineLink"] not in old_links:
            raise ValueError(
                f"{source}: app {app!r} spineLink {entry['spineLink']!r} is not "
                f"one of the legacy unit's live links {sorted(old_links)} — the "
                f"entry describes a surface no role owns"
            )
        instance = entry["instance"]
        if instance not in instances:
            raise ValueError(
                f"{source}: app {app!r} instance {instance!r} is not managed by "
                f"{ENGINE_GUI_TOOLS_VARS}"
            )
        expected_always = entry["launch"] == "always"
        if instances[instance] != expected_always:
            raise ValueError(
                f"{source}: app {app!r} launch {entry['launch']!r} disagrees "
                f"with gui_tools always_on={instances[instance]} for "
                f"{instance!r}"
            )
        launcher = entry.get("launcher")
        if launcher is not None:
            if not (templates_dir / f"{launcher}.j2").is_file():
                raise ValueError(
                    f"{source}: app {app!r} launcher {launcher!r} has no "
                    f"{ENGINE_CLI_TOOLS_TEMPLATES}/{launcher}.j2 in the pinned "
                    f"engine"
                )
            if f"{{{{ cli_tools_bin_dir }}}}/{launcher}" not in tasks_text:
                raise ValueError(
                    f"{source}: app {app!r} launcher {launcher!r} is not installed "
                    f"by {ENGINE_CLI_TOOLS_TASKS}"
                )
        bin_link = entry.get("binLink")
        if bin_link is not None and bin_link not in old_bin_links:
            raise ValueError(
                f"{source}: app {app!r} binLink {bin_link!r} is not one of the "
                f"legacy unit's bin links {sorted(old_bin_links)}"
            )


def _assert_app_fixture(root: Path, name: str, spec: dict[str, Any]) -> None:
    source = f"{FIXTURE_ROOT}/{name}"
    document = _load_yaml(root / FIXTURE_ROOT / name)
    try:
        entries = validate_app_list(document, source)
    except ValueError as exc:
        if spec["valid"]:
            raise ValueError(f"fixture {name} should be accepted: {exc}") from exc
        needle = str(spec.get("needle") or "")
        if needle and needle not in str(exc):
            raise ValueError(
                f"fixture {name} failed for the wrong reason: expected "
                f"{needle!r} in {exc!s}"
            ) from exc
        return
    if not spec["valid"]:
        raise ValueError(f"fixture {name} should be rejected but was accepted")
    owners = {entry["owner"] for entry in entries}
    if owners != spec["owners"]:
        raise ValueError(
            f"fixture {name} owners are {sorted(owners)}; expected "
            f"{sorted(spec['owners'])}"
        )
    for entry in entries:
        if entry["owner"] not in OWNERS:
            raise ValueError(f"fixture {name} has an invalid owner")


def assert_fixtures(root: Path) -> dict[str, int]:
    """Exercise the structural validator against the committed fixtures."""
    fixture_dir = root / FIXTURE_ROOT
    if not fixture_dir.is_dir():
        raise ValueError(f"the app-consumption fixture dir {FIXTURE_ROOT} is missing")

    for name, spec in APP_FIXTURE_CASES.items():
        _assert_app_fixture(root, name, spec)

    accepted = 0
    rejected = 0
    for name, expected_valid in TUPLE_FIXTURE_CASES.items():
        source = f"{FIXTURE_ROOT}/{name}"
        document = _load_yaml(fixture_dir / name)
        try:
            validate_program_tuple(document, source)
            valid = True
        except ValueError:
            valid = False
        if valid != expected_valid:
            state = "accepted" if valid else "rejected"
            raise ValueError(
                f"fixture {name} was {state}; expected "
                f"{'accepted' if expected_valid else 'rejected'}"
            )
        if valid:
            accepted += 1
        else:
            rejected += 1

    return {
        "app_fixtures": len(APP_FIXTURE_CASES),
        "tuple_accepted": accepted,
        "tuple_rejected": rejected,
    }


def run_checks(root: Path, engine_root: Path) -> dict[str, Any]:
    """Run the real-list, tuple and fixture checks; return a summary."""
    apps_path = root / APPS_MANIFEST
    if not apps_path.is_file():
        raise ValueError(f"the app list {APPS_MANIFEST} is missing")
    entries = validate_app_list(_load_yaml(apps_path), APPS_MANIFEST)
    if {entry["app"] for entry in entries} != EXPECTED_APPS:
        missing = sorted(EXPECTED_APPS - {entry["app"] for entry in entries})
        extra = sorted({entry["app"] for entry in entries} - EXPECTED_APPS)
        raise ValueError(
            f"{APPS_MANIFEST}: app inventory mismatch — missing {missing}, "
            f"unexpected {extra}"
        )

    tuple_path = root / PROGRAM_TUPLE
    if not tuple_path.is_file():
        raise ValueError(f"the program tuple {PROGRAM_TUPLE} is missing")
    tuple_data = validate_program_tuple(_load_yaml(tuple_path), PROGRAM_TUPLE)

    assets_path = root / ASSETS_MANIFEST
    if not assets_path.is_file():
        raise ValueError(f"the assets manifest {ASSETS_MANIFEST} is missing")
    assets = _load_yaml(assets_path)
    assets_tag = (
        str((assets.get("assets") or {}).get("tag") or "")
        if isinstance(assets, dict)
        else ""
    )
    if tuple_data["dotfiles-assets"] != assets_tag:
        raise ValueError(
            f"{PROGRAM_TUPLE}: dotfiles-assets {tuple_data['dotfiles-assets']!r} "
            f"does not agree with {ASSETS_MANIFEST} assets.tag {assets_tag!r}"
        )

    assert_engine_surfaces(entries, engine_root, tuple_data)
    fixture_summary = assert_fixtures(root)

    owner_counts = Counter(entry["owner"] for entry in entries)
    return {
        "apps": len(entries),
        "owners": {owner: owner_counts.get(owner, 0) for owner in sorted(OWNERS)},
        "tuple": dict(tuple_data),
        **fixture_summary,
    }

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
* the adoption tuple is actually active: the pinned engine's `ags_apps`,
  `ags_platform`, `verify` and legacy-shortcut pins all resolve the tuple's
  `ags-platform` tag, and the installed `ags-apps` unit/verify mirror agree;
* the pinned engine's provision verify mirror consumes the same `apps.yaml` +
  `program-tuple.yaml` and asserts the same standalone surfaces (config/spine/
  XDG/bin, launcher, autostart, palette pointer, launch lock);
* the pinned engine carries the fake-app cutover fixture (quiesce → install/
  repoint/start → verify → rollback) and the legacy/mixed/all-standalone
  one-owner fixtures, which this gate revalidates with the same structural
  rules;
* for the current legacy entries, every config link is a managed dir in the
  pinned engine's `config_links` role, every instance is in `gui_tools`, the
  launch policy matches `always_on`, every launcher has a real `cli_tools`
  template, and every bin link names an engine `*_bin_link` surface;
* the fixtures accept fully legacy, mixed and all-standalone lists and reject
  duplicate apps/instances/config links, invalid owners and repo/tag
  contradictions; the tuple fixtures reject missing/extra/non-semver records.

A standalone entry is still not deployed by the old monorepo role; the engine's
generic `ags_apps_units` role owns it, and the gate asserts that role plus its
verify mirror are present in the pinned checkout before any cutover.
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
ENGINE_AGS_APPS_UNITS_VARS = "ansible/roles/ags_apps_units/vars/main.yml"
ENGINE_AGS_APPS_UNITS_TASKS = "ansible/roles/ags_apps_units/tasks"
ENGINE_AGS_PLATFORM_VARS = "ansible/roles/ags_platform/vars/main.yml"
ENGINE_CLI_TOOLS_TASKS = "ansible/roles/cli_tools/tasks/main.yml"
ENGINE_CLI_TOOLS_TEMPLATES = "ansible/roles/cli_tools/templates"
ENGINE_CONFIG_LINKS_VARS = "ansible/roles/config_links/vars/main.yml"
ENGINE_GUI_TOOLS_VARS = "ansible/roles/gui_tools/vars/main.yml"
ENGINE_VERIFY_VARS = "ansible/roles/verify/vars/main.yml"
ENGINE_VERIFY_TASKS = "ansible/roles/verify/tasks/main.yml"
ENGINE_VERIFY_STANDALONE = "ansible/roles/verify/tasks/_verify_standalone.yml"
ENGINE_APP_LIST_FIXTURES = "tests/fixtures/ags-apps/app-list"
ENGINE_FAKE_APP_FIXTURE = "tests/fixtures/ags-apps/fake-app"
ENGINE_UNITS_TEST = "tests/unit/test_ags_apps_units_role.py"

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


def _engine_text(engine_root: Path, relative: str) -> str:
    path = engine_root / relative
    if not path.is_file():
        raise ValueError(f"the pinned engine is missing {relative}")
    return path.read_text(encoding="utf-8")


def assert_engine_adoption_tuple(
    tuple_data: dict[str, Any], engine_root: Path
) -> str:
    """The engine must actually resolve the program tuple, not just record it.

    The composition owns `program-tuple.yaml`; the pinned engine owns the
    concrete role pins. Four engine legs consume `ags-platform`: the platform
    role, the legacy monorepo's per-unit shortcut, and both verify mirrors. A
    half-adoption (tuple v0.3.0, engine still v0.2.0) would install two platform
    generations and break the one-tuple rule, so the composition gate fails
    naming the leg that disagrees.
    """
    expected_platform = tuple_data["ags-platform"]
    apps_vars = _engine_data(engine_root, ENGINE_AGS_APPS_VARS)
    platform_vars = _engine_data(engine_root, ENGINE_AGS_PLATFORM_VARS)
    verify_vars = _engine_data(engine_root, ENGINE_VERIFY_VARS)

    legs = (
        (ENGINE_AGS_APPS_VARS, "ags_apps_platform_version", apps_vars),
        (ENGINE_AGS_PLATFORM_VARS, "ags_platform_version", platform_vars),
        (ENGINE_VERIFY_VARS, "verify_ags_platform_version", verify_vars),
        (ENGINE_VERIFY_VARS, "verify_ags_apps_platform_version", verify_vars),
    )
    for relative, key, data in legs:
        value = data.get(key)
        if value != expected_platform:
            raise ValueError(
                f"{PROGRAM_TUPLE}: ags-platform {expected_platform!r} is not "
                f"resolved by {relative} `{key}` = {value!r} — finish the "
                f"adoption re-pin before any cutover"
            )

    apps_version = apps_vars.get("ags_apps_version")
    if not isinstance(apps_version, str) or not _TAG_RE.fullmatch(apps_version):
        raise ValueError(
            f"{ENGINE_AGS_APPS_VARS}: ags_apps_version must be an immutable "
            f"semver tag; got {apps_version!r}"
        )
    verify_apps_version = verify_vars.get("verify_ags_apps_version")
    if verify_apps_version != apps_version:
        raise ValueError(
            f"{ENGINE_VERIFY_VARS}: verify_ags_apps_version "
            f"{verify_apps_version!r} does not mirror ags_apps_version "
            f"{apps_version!r}"
        )
    if verify_vars.get("verify_assets_pinned_tag") != tuple_data["dotfiles-assets"]:
        raise ValueError(
            f"{ENGINE_VERIFY_VARS}: verify_assets_pinned_tag "
            f"{verify_vars.get('verify_assets_pinned_tag')!r} does not mirror the "
            f"program tuple dotfiles-assets {tuple_data['dotfiles-assets']!r}"
        )

    units_vars = _engine_text(engine_root, ENGINE_AGS_APPS_UNITS_VARS)
    if "program-tuple.yaml" not in units_vars or (
        "ags_apps_units_tuple['ags-platform']" not in units_vars
    ):
        raise ValueError(
            f"{ENGINE_AGS_APPS_UNITS_VARS}: the generic role must consume the "
            f"shared program-tuple.yaml and resolve ags-platform from it, not "
            f"carry a second platform pin"
        )
    return str(apps_version)


def assert_engine_verify_mirror(engine_root: Path) -> None:
    """The engine's verify role must mirror the installer's app-list surfaces.

    This is the composition-side half of OpenSpec task 2.2: the generic
    installer (`ags_apps_units`) and `verify` read the SAME apps.yaml /
    program-tuple.yaml, and every ownership surface the installer creates is
    asserted again by verify. The task text below is deliberately token-level,
    not a second app list.
    """
    verify_vars = _engine_data(engine_root, ENGINE_VERIFY_VARS)
    expected = {
        "verify_ags_apps_units_apps_file": "{{ manifests_dir | trim }}/apps.yaml",
        "verify_ags_apps_units_tuple_file": (
            "{{ manifests_dir | trim }}/program-tuple.yaml"
        ),
        "verify_ags_apps_units_install_root": "{{ install_dir | trim }}/apps",
        "verify_ags_apps_units_platform_shortcut": (
            "{{ verify_ags_apps_units_install_root }}/node_modules/ags-platform"
        ),
        "verify_ags_apps_units_spine_config_dir": "{{ install_dir | trim }}/config",
        "verify_ags_apps_units_run_locked": (
            "{{ verify_cli_bin_dir | trim }}/ags-run-locked"
        ),
        "verify_ags_apps_units_autostart_file": (
            "{{ install_dir | trim }}/config/hypr/autostart.lua"
        ),
        "verify_ags_apps_units_colors_pointer": (
            "{{ verify_ags_apps_units_state_root }}/dotfiles/current/colors.gtk.css"
        ),
    }
    for key, value in expected.items():
        if verify_vars.get(key) != value:
            raise ValueError(
                f"{ENGINE_VERIFY_VARS}: {key} must be {value!r}; got "
                f"{verify_vars.get(key)!r} — the verify mirror drifted from the "
                f"composition app list/tuple seam"
            )

    installer_main = _engine_text(
        engine_root, f"{ENGINE_AGS_APPS_UNITS_TASKS}/main.yml"
    )
    for token in (
        "manifests_dir",
        "apps.yaml",
        "program-tuple.yaml",
        "selectattr('owner', 'equalto', 'standalone')",
        "node_modules",
    ):
        if token not in installer_main:
            raise ValueError(
                f"{ENGINE_AGS_APPS_UNITS_TASKS}/main.yml does not read {token!r} "
                f"— the generic role no longer consumes the single list/tuple"
            )

    verify_main = _engine_text(engine_root, ENGINE_VERIFY_TASKS)
    for token in (
        "verify_ags_apps_units_apps_file",
        "verify_ags_apps_units_tuple_file",
        "verify_ags_standalone_apps",
        "include_tasks: _verify_standalone.yml",
    ):
        if token not in verify_main:
            raise ValueError(
                f"{ENGINE_VERIFY_TASKS} does not mirror {token!r} — verify and "
                f"the installer no longer audit the same app list"
            )

    installer_surfaces = _engine_text(
        engine_root, f"{ENGINE_AGS_APPS_UNITS_TASKS}/_verify_surfaces.yml"
    )
    verify_standalone = _engine_text(engine_root, ENGINE_VERIFY_STANDALONE)
    common_surface_tokens = (
        "app.binLink",
        "app.launcher",
        "app.autostart",
        "ags-run-locked",
        "--expect-instance ",
        "| length - 1) == 1",
    )
    for label, text, link_tokens in (
        (
            "installer _verify_surfaces.yml",
            installer_surfaces,
            (
                "ags_apps_units_spine_link",
                "ags_apps_units_xdg_link",
                "ags_apps_units_bin_link",
            ),
        ),
        (
            "verify _verify_standalone.yml",
            verify_standalone,
            ("app.spineLink", "app.xdgLink"),
        ),
    ):
        for token in common_surface_tokens + link_tokens:
            if token not in text:
                raise ValueError(
                    f"{label}: missing {token!r} — the two gates no longer "
                    f"assert the same ownership surfaces"
                )

    for token in (
        "app.configDir",
        "app.configLink",
        "barPalettePointer",
        "palette-refresh",
        "colors.css",
        "icons.json",
    ):
        if token not in verify_standalone:
            raise ValueError(
                f"{ENGINE_VERIFY_STANDALONE}: missing {token!r} — the standalone "
                f"verify mirror is incomplete"
            )


def assert_engine_cutover_fixture(engine_root: Path) -> None:
    """Require the pinned engine's quiesce → flip → verify → rollback fixture.

    The engine owns the executable cutover; the composition gate locks that the
    pinned tag actually ships it rather than only documenting it. The fake-app
    tests are GUI-free and run with a fake `ags` CLI; this gate checks the
    structure and one-owner fixtures they consume.
    """
    task_dir = engine_root / ENGINE_AGS_APPS_UNITS_TASKS
    required_tasks = (
        "main.yml",
        "_one.yml",
        "_quiesce.yml",
        "_rollback.yml",
        "_verify_unit.yml",
        "_verify_surfaces.yml",
        "_verify_runtime.yml",
    )
    for name in required_tasks:
        if not (task_dir / name).is_file():
            raise ValueError(
                f"{ENGINE_AGS_APPS_UNITS_TASKS}/{name} is missing — the pinned "
                f"engine does not ship the generic cutover epoch"
            )

    one = _engine_text(engine_root, f"{ENGINE_AGS_APPS_UNITS_TASKS}/_one.yml")
    sequence = (
        "_quiesce.yml",
        "clone the standalone tag",
        "repoint the spine link",
        "_verify_surfaces.yml",
        "_verify_runtime.yml",
        "rescue:",
        "_rollback.yml",
    )
    positions = [one.find(token) for token in sequence]
    if any(position < 0 for position in positions) or positions != sorted(positions):
        raise ValueError(
            f"{ENGINE_AGS_APPS_UNITS_TASKS}/_one.yml does not keep the AD-32 "
            f"order quiesce → install → repoint → verify → rollback; found "
            f"{dict(zip(sequence, positions))}"
        )

    quiesce = _engine_text(engine_root, f"{ENGINE_AGS_APPS_UNITS_TASKS}/_quiesce.yml")
    for token in ("ags quit -i", "ags list", "ags-launch.lock"):
        if token not in quiesce:
            raise ValueError(
                f"{ENGINE_AGS_APPS_UNITS_TASKS}/_quiesce.yml does not confirm "
                f"the old instance is gone ({token!r} missing)"
            )
    rollback = _engine_text(engine_root, f"{ENGINE_AGS_APPS_UNITS_TASKS}/_rollback.yml")
    for token in (
        "previous_spine_target",
        "previous_xdg_target",
        "previous_bin_target",
        "was_running",
        "ags_apps_units_run_locked",
    ):
        if token not in rollback:
            raise ValueError(
                f"{ENGINE_AGS_APPS_UNITS_TASKS}/_rollback.yml does not restore "
                f"the previous owner ({token!r} missing)"
            )

    test_text = _engine_text(engine_root, ENGINE_UNITS_TEST)
    for name in (
        "test_every_fixture_has_exactly_one_owner",
        "test_owner_flip_quiesces_the_old_instance_then_installs_and_starts",
        "test_failure_rolls_back_links_and_restarts_the_previous_instance",
        "test_all_standalone_installs_full_topology_and_tags_stay_immutable",
    ):
        if name not in test_text:
            raise ValueError(
                f"{ENGINE_UNITS_TEST} is missing {name!r} — the pinned engine's "
                f"fake cutover/one-owner fixture is incomplete"
            )

    fixture_dir = engine_root / ENGINE_FAKE_APP_FIXTURE
    for relative in (
        "app.manifest.json",
        "app.tsx",
        "handler.ts",
        "icons.json",
        "bin/fake-app-tool",
    ):
        if not (fixture_dir / relative).is_file():
            raise ValueError(
                f"{ENGINE_FAKE_APP_FIXTURE}/{relative} is missing — the cutover "
                f"fixture cannot exercise a whole app"
            )


def assert_engine_fixtures(engine_root: Path) -> int:
    """Revalidate the engine's one-owner fixtures with the composition rules."""
    fixture_dir = engine_root / ENGINE_APP_LIST_FIXTURES
    expected = {
        "legacy.apps.yaml": {"legacy": 2, "standalone": 0},
        "mixed.apps.yaml": {"legacy": 1, "standalone": 1},
        "all-standalone.apps.yaml": {"legacy": 0, "standalone": 2},
    }
    for name, counts in expected.items():
        source = f"{ENGINE_APP_LIST_FIXTURES}/{name}"
        path = fixture_dir / name
        if not path.is_file():
            raise ValueError(f"the pinned engine is missing {source}")
        entries = validate_app_list(_load_yaml(path), source)
        got = Counter(entry["owner"] for entry in entries)
        if {owner: got.get(owner, 0) for owner in OWNERS} != counts:
            raise ValueError(
                f"{source}: owner partition "
                f"{ {owner: got.get(owner, 0) for owner in OWNERS} } does not "
                f"match {counts}"
            )
    return len(expected)


def assert_engine_surfaces(
    entries: list[dict[str, Any]], engine_root: Path
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

    assert_engine_surfaces(entries, engine_root)
    engine_apps_version = assert_engine_adoption_tuple(tuple_data, engine_root)
    assert_engine_verify_mirror(engine_root)
    assert_engine_cutover_fixture(engine_root)
    engine_fixture_count = assert_engine_fixtures(engine_root)
    fixture_summary = assert_fixtures(root)

    owner_counts = Counter(entry["owner"] for entry in entries)
    return {
        "apps": len(entries),
        "owners": {owner: owner_counts.get(owner, 0) for owner in sorted(OWNERS)},
        "tuple": dict(tuple_data),
        "engine_apps_version": engine_apps_version,
        "engine_fixtures": engine_fixture_count,
        **fixture_summary,
    }

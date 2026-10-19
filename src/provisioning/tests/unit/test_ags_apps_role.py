"""Tests for the ags_apps role (spine AD-1/AD-17/AD-23).

The role installs the AGS bar as ONE versioned unit, creates the per-unit
resolution shortcut the realpathed bar needs for its bare `ags-platform`
imports, and deploys the unit's bar/ as the live <install>/config/ags link.
These tests pin the STRUCTURE (the role, the playbook, the vars' shapes, the
presence guard, the check gating, the `.git` removal, the pin record, the
shortcuts, the legacy-bridge migration) and EXECUTE the playbook against a
pre-seeded unit so the pin + links are proven by a real run — without a
network clone (the clone is presence-guarded; the fetch is proven separately
by the deploy-coverage gate's role assertion and the simulated install).
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

_TASK_KEYWORDS = {
    "name",
    "when",
    "become",
    "become_user",
    "become_method",
    "become_flags",
    "args",
    "register",
    "changed_when",
    "failed_when",
    "creates",
    "vars",
    "loop",
    "until",
    "retries",
    "delay",
    "tags",
    "environment",
    "ignore_errors",
    "notify",
    "check_mode",
}


def _find_ansible_dir() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "ansible" / "inventory" / "localhost.yaml"
        if candidate.is_file() and (parent / "pyproject.toml").is_file():
            return parent / "ansible"
    raise FileNotFoundError("src/provisioning/ansible/ not found walking up from the test file")


_ANSIBLE_DIR = _find_ansible_dir()
_ROLES_DIR = _ANSIBLE_DIR / "roles" / "ags_apps"
_PLAYBOOKS_DIR = _ANSIBLE_DIR / "playbooks"


def _load_tasks() -> list[dict[str, object]]:
    data = yaml.safe_load((_ROLES_DIR / "tasks" / "main.yml").read_text())
    assert isinstance(data, list)
    return data


def _module_key(task: dict[str, object]) -> str | None:
    for key in task:
        if key not in _TASK_KEYWORDS and key != "with_items":
            return key
    return None


def _module(task: dict[str, object]) -> dict[str, object]:
    module = task.get(_module_key(task) or "", {})
    if isinstance(module, str):
        return {}
    assert isinstance(module, dict)
    return module


def _vars() -> dict[str, Any]:
    data = yaml.safe_load((_ROLES_DIR / "vars" / "main.yml").read_text())
    assert isinstance(data, dict)
    return data


def _named(name: str) -> dict[str, object]:
    task = next((t for t in _load_tasks() if t.get("name") == name), None)
    assert task is not None, f"missing task {name!r}"
    return task


class TestAgsAppsRoleTree:
    _REQUIRED_FILES = ("tasks/main.yml", "vars/main.yml")

    def test_role_tree_exists(self) -> None:
        for relative in self._REQUIRED_FILES:
            assert (_ROLES_DIR / relative).is_file(), f"missing {relative}"

    def test_playbook_exists(self) -> None:
        assert (_PLAYBOOKS_DIR / "ags-apps.yaml").is_file(), (
            "missing playbooks/ags-apps.yaml"
        )


class TestAgsAppsVars:
    def test_pins_one_monorepo_release(self) -> None:
        data = _vars()
        version = str(data["ags_apps_version"])
        # The unit is a MONOREPO deployed whole, so the pin names a monorepo
        # release tag (vX.Y.Z carrying bar/ + hypr-pano/), not a per-app
        # `bar-` tag. A `bar-`-prefixed pin here would name a tag the monorepo
        # no longer cuts.
        assert re.match(r"^v\d", version), (
            f"the pin must be a monorepo release tag (e.g. v0.3.1); got {version!r}"
        )
        assert data["ags_apps_repo_url"].startswith("https://github.com/"), (
            "the unit is cloned over anonymous HTTPS"
        )

    def test_unit_is_under_the_versioned_install_root(self) -> None:
        data = _vars()
        assert "install_dir" in str(data["ags_apps_install_root"])
        assert "ags-apps" in str(data["ags_apps_install_root"])
        assert "ags_apps_version" in str(data["ags_apps_unit_dir"])
        assert "ags_apps_install_root" in str(data["ags_apps_unit_dir"])

    def test_bar_is_the_unit_subdir(self) -> None:
        """The monorepo deviation: the repo root is NOT the package — the bar
        package is the unit's bar/ subdir (slice 1 moved dotfiles/config/ags/
        there verbatim)."""
        data = _vars()
        assert str(data["ags_apps_bar_dir"]).endswith("/bar")
        assert "ags_apps_unit_dir" in str(data["ags_apps_bar_dir"])

    def test_live_bar_link_deploys_the_unit_at_config_ags(self) -> None:
        data = _vars()
        live = str(data["ags_apps_live_bar_link"])
        assert "spine_config_dir" in live
        assert live.endswith("/ags")
        assert "ags_apps_bar_dir" not in live, (
            "the link DEST is the spine path; the link SRC (the unit bar dir) "
            "belongs in the tasks, not the vars"
        )

    def test_live_pano_link_deploys_the_unit_at_config_ags_hypr_pano(self) -> None:
        """Slice 3: the clipboard overlay deploys WHOLE like the bar — a symlink
        from the spine root into the unit's hypr-pano/ subdir."""
        data = _vars()
        pano = str(data["ags_apps_hypr_pano_dir"])
        assert pano.endswith("/hypr-pano")
        assert "ags_apps_unit_dir" in pano
        live = str(data["ags_apps_live_pano_link"])
        assert "spine_config_dir" in live
        assert live.endswith("/ags-hypr-pano")
        assert "ags_apps_hypr_pano_dir" not in live, (
            "the link DEST is the spine path; the link SRC (the unit pano dir) "
            "belongs in the tasks, not the vars"
        )

    def test_live_notifications_link_deploys_the_unit_at_config_ags_notifications(
        self,
    ) -> None:
        """Slice 4: the notification daemon deploys WHOLE like the bar — a
        symlink from the spine root into the unit's notifications/ subdir."""
        data = _vars()
        notifications = str(data["ags_apps_notifications_dir"])
        assert notifications.endswith("/notifications")
        assert "ags_apps_unit_dir" in notifications
        live = str(data["ags_apps_live_notifications_link"])
        assert "spine_config_dir" in live
        assert live.endswith("/ags-notifications")
        assert "ags_apps_notifications_dir" not in live, (
            "the link DEST is the spine path; the link SRC (the unit "
            "notifications dir) belongs in the tasks, not the vars"
        )

    def test_live_capture_link_deploys_the_unit_at_config_ags_capture(self) -> None:
        """Slice 5: the capture-tool AGS GUI deploys WHOLE like the bar — a
        symlink from the spine root into the unit's capture-tool/ subdir. The
        Python backend is NOT part of the unit and is not named here."""
        data = _vars()
        capture = str(data["ags_apps_capture_tool_dir"])
        assert capture.endswith("/capture-tool")
        assert "ags_apps_unit_dir" in capture
        live = str(data["ags_apps_live_capture_link"])
        assert "spine_config_dir" in live
        assert live.endswith("/ags-capture")
        assert "ags_apps_capture_tool_dir" not in live, (
            "the link DEST is the spine path; the link SRC (the unit "
            "capture-tool dir) belongs in the tasks, not the vars"
        )

    def test_live_wallpaper_selector_link_deploys_the_unit_at_config_ags_wallpaper_selector(
        self,
    ) -> None:
        """Slice 6: the wallpaper selector deploys WHOLE like the bar — a symlink
        from the spine root into the unit's wallpaper-selector/ subdir. The
        selector is a whole package, so no in-repo part is named here."""
        data = _vars()
        selector = str(data["ags_apps_wallpaper_selector_dir"])
        assert selector.endswith("/wallpaper-selector")
        assert "ags_apps_unit_dir" in selector
        live = str(data["ags_apps_live_wallpaper_selector_link"])
        assert "spine_config_dir" in live
        assert live.endswith("/ags-wallpaper-selector")
        assert "ags_apps_wallpaper_selector_dir" not in live, (
            "the link DEST is the spine path; the link SRC (the unit "
            "wallpaper-selector dir) belongs in the tasks, not the vars"
        )

    def test_resolution_shortcut_is_per_unit(self) -> None:
        """esbuild realpaths the live-bar link, so the shared-ancestor shortcut
        is not an ancestor of the real bar tree — the shortcut MUST live
        inside the unit."""
        data = _vars()
        assert "node_modules" in str(data["ags_apps_resolution_dir"])
        assert "ags_apps_unit_dir" in str(data["ags_apps_resolution_dir"])
        assert str(data["ags_apps_resolution_shortcut"]).endswith("/ags-platform")

    def test_unit_marker_guards_the_clone(self) -> None:
        data = _vars()
        assert str(data["ags_apps_unit_marker"]).endswith("/app.tsx")
        assert "ags_apps_bar_dir" in str(data["ags_apps_unit_marker"])

    def test_platform_pin_matches_the_platform_role(self) -> None:
        """The per-unit resolution shortcut points at the pinned platform unit.
        The two roles share no vars at runtime (different plays), so the
        structural test is the single source of truth for their equality — a
        platform bump fails loudly until both pins move together."""
        platform_vars = yaml.safe_load(
            (_ANSIBLE_DIR / "roles" / "ags_platform" / "vars" / "main.yml").read_text()
        )
        assert isinstance(platform_vars, dict)
        assert str(_vars()["ags_apps_platform_version"]) == str(
            platform_vars["ags_platform_version"]
        ), (
            "ags_apps_platform_version must equal ags_platform_version — the "
            "resolution shortcut targets the pinned platform unit"
        )


class TestAgsAppsTasks:
    def test_tasks_parse_to_named_tasks(self) -> None:
        tasks = _load_tasks()
        assert tasks, "tasks/main.yml must not be empty"
        for task in tasks:
            assert isinstance(task, dict)
            assert task["name"], "every task must carry a name"

    def test_first_task_is_fail_loud_install_dir_assert(self) -> None:
        first = _load_tasks()[0]
        assert _module_key(first) == "ansible.builtin.assert"
        assert "install_dir" in str(_module(first).get("that", ""))

    def test_clone_is_shallow_pinned_presence_guarded_and_check_gated(self) -> None:
        clone = _named("Clone the pinned ags-apps unit (shallow, anonymous HTTPS)")
        assert _module_key(clone) == "ansible.builtin.git"
        module = _module(clone)
        assert module["version"] == "{{ ags_apps_version }}"
        assert module["depth"] == 1, "the clone must be shallow"
        assert module["dest"] == "{{ ags_apps_unit_dir }}"
        when = clone.get("when")
        assert isinstance(when, list)
        assert "not ansible_check_mode" in when, "the clone must be --check-gated"
        assert any("ags_apps_unit_check" in str(w) for w in when), (
            "the clone must be presence-guarded via the stat register"
        )

    def test_git_dir_is_removed(self) -> None:
        task = _named(
            "Remove the clone's .git (deploy the unit as a source tree, not a checkout)"
        )
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "absent"
        assert str(module["path"]).endswith("/.git")

    def test_pin_is_recorded(self) -> None:
        task = _named("Record the pinned bar version")
        assert _module_key(task) == "ansible.builtin.copy"
        module = _module(task)
        assert module["dest"] == "{{ ags_apps_pin_file }}"
        assert "ags_apps_version" in str(module["content"])

    def test_resolution_shortcut_is_forced_symlink_into_the_platform_unit(
        self,
    ) -> None:
        task = _named(
            "Point the per-unit resolution shortcut at the pinned platform unit"
        )
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "link"
        assert module["force"] is True, "force makes a repoint converge"
        assert module["src"] == "{{ ags_apps_platform_unit_dir }}"
        assert module["dest"] == "{{ ags_apps_resolution_shortcut }}"

    def test_legacy_bridge_is_classified_before_displacement(self) -> None:
        """Upgrading from the per-file bridge displaces a real dir — the role
        must classify it (stat + children) BEFORE touching it, so an empty
        fresh-spine dir is removed while a non-empty legacy bridge is moved
        aside, never deleted."""
        stat = _named("Check whether the live-bar path already exists")
        assert _module_key(stat) == "ansible.builtin.stat"
        assert _module(stat).get("follow") is False, (
            "the stat must see the link itself, not its target"
        )
        find = _named("List the live-bar path's children when it is a real dir")
        assert _module_key(find) == "ansible.builtin.find"
        remove = _named("Remove the live-bar path when it is an empty real dir")
        assert _module(remove)["state"] == "absent"
        move = _named(
            "Move aside a non-empty legacy bridge dir blocking the live-bar link"
        )
        assert _module_key(move) == "ansible.builtin.command", (
            "the move-aside is a mutation and must stay a check-gated command"
        )
        for task in (remove, move):
            when = str(task.get("when", ""))
            assert "islnk" in when and "matched" in when, (
                f"task {task.get('name')!r} must branch on link-vs-dir and "
                "empty-vs-nonempty"
            )
            assert "not ansible_check_mode" in when

    def test_colors_pointer_is_ensured_unconditionally_after_the_live_bar_link(
        self,
    ) -> None:
        """THE REGRESSION FIX. The runtime-owned colors.css pointer must be
        ENSURED on the unit bar on EVERY deploy — not only when the live-bar
        path is a real dir. A version bump repoints the live-bar symlink at a
        NEW unit dir that never carried the pointer, so the old conditional
        seed was skipped on every bump, leaving <unit>/bar/colors.css dangling;
        wlogout's @import then failed, GTK dropped the whole stylesheet, and the
        power icon opened wlogout with no wallpaper and no icons."""
        names = [str(t.get("name", "")) for t in _load_tasks()]
        probe_name = "Read the live bar's pre-existing runtime colors.css pointer target"
        ensure_name = "Ensure the unit bar carries the runtime colors.css pointer"
        move_name = "Move aside a non-empty legacy bridge dir blocking the live-bar link"
        link_name = "Deploy the unit's bar as the live bar"
        for required in (probe_name, ensure_name, move_name, link_name):
            assert required in names, f"missing task {required!r}"
        # The pre-existing target is read BEFORE the legacy dir moves/repoints.
        assert names.index(probe_name) < names.index(move_name), (
            "the pointer target must be captured before the live bar is repointed"
        )
        # The ensure runs AFTER the live-bar link is (re)pointed at this unit.
        assert (
            names.index(move_name) < names.index(link_name) < names.index(ensure_name)
        ), "the ensure must run after the live-bar link is deployed"

        ensure = _named(ensure_name)
        assert _module_key(ensure) == "ansible.builtin.file"
        module = _module(ensure)
        assert module["state"] == "link", (
            "a symlink (not a copy) makes the ensure idempotent + check-safe"
        )
        assert module["force"] is True, "force makes a repoint converge in one run"
        assert module["dest"] == "{{ ags_apps_bar_dir }}/colors.css"
        # UNCONDITIONAL: no `when` gate at all. The bug was the gate
        # (`not islnk` + legacy-colors-exists) which skipped every version bump.
        assert "when" not in ensure, (
            "the ensure must run on EVERY deploy (fresh host AND version bump) — "
            "any `when` gate reintroduces the dangling-pointer regression"
        )
        # The source falls back to the runtime state pointer (fresh host) and
        # inherits the pre-existing target when the probe found one (bump).
        src = str(module["src"])
        assert "ags_apps_colors_pointer_source" in src
        fallback = str(_named(ensure_name)["vars"]["ags_apps_colors_pointer_source"])
        assert "ags_apps_runtime_colors_pointer" in fallback
        assert "ags_apps_pre_colors_readlink" in fallback

        probe = _named(probe_name)
        assert _module_key(probe) == "ansible.builtin.command"
        assert _module(probe)["argv"][0] == "readlink"
        assert probe.get("failed_when") is False, (
            "a missing/non-symlink pointer must fall back, not abort the run"
        )
        assert probe.get("changed_when") is False

    def test_live_bar_is_forced_symlink_into_the_unit_bar(self) -> None:
        task = _named("Deploy the unit's bar as the live bar")
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "link"
        assert module["force"] is True, "force makes a rollback repoint converge"
        assert module["src"] == "{{ ags_apps_bar_dir }}"
        assert module["dest"] == "{{ ags_apps_live_bar_link }}"

    def test_live_pano_is_forced_symlink_into_the_unit_pano(self) -> None:
        task = _named("Deploy the unit's hypr-pano as the live clipboard overlay")
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "link"
        assert module["force"] is True, "force makes a rollback repoint converge"
        assert module["src"] == "{{ ags_apps_hypr_pano_dir }}"
        assert module["dest"] == "{{ ags_apps_live_pano_link }}"

    def test_pano_legacy_bridge_is_classified_before_displacement(self) -> None:
        """Slice 3 mirrors the bar's migrate-then-symlink discipline: the role
        must classify the live-pano path (stat + children) BEFORE touching it,
        so an empty fresh-spine dir is removed while a non-empty legacy bridge
        is moved aside, never deleted."""
        stat = _named("Check whether the live-pano path already exists")
        assert _module_key(stat) == "ansible.builtin.stat"
        assert _module(stat).get("follow") is False, (
            "the stat must see the link itself, not its target"
        )
        find = _named("List the live-pano path's children when it is a real dir")
        assert _module_key(find) == "ansible.builtin.find"
        remove = _named("Remove the live-pano path when it is an empty real dir")
        assert _module(remove)["state"] == "absent"
        move = _named(
            "Move aside a non-empty legacy pano bridge dir blocking the live-pano link"
        )
        assert _module_key(move) == "ansible.builtin.command", (
            "the move-aside is a mutation and must stay a check-gated command"
        )
        for task in (remove, move):
            when = str(task.get("when", ""))
            assert "islnk" in when and "matched" in when, (
                f"task {task.get('name')!r} must branch on link-vs-dir and "
                "empty-vs-nonempty"
            )
            assert "not ansible_check_mode" in when
        names = [str(t.get("name", "")) for t in _load_tasks()]
        assert names.index(
            "Remove the live-pano path when it is an empty real dir"
        ) < names.index("Deploy the unit's hypr-pano as the live clipboard overlay"), (
            "ordering must be classify -> backup -> symlink"
        )

    def test_pano_backup_path_cannot_collide_with_the_bar_backup(self) -> None:
        """Both links share the bridge-backup root. A run that displaces BOTH
        legacy dirs must not move them onto the same timestamped path, so the
        pano backup carries an app suffix."""
        task = _named("Determine the legacy-pano-bridge backup path for this run")
        backup = str(_module(task)["ags_apps_pano_backup_path"])
        assert "ags_apps_backup_root" in backup, (
            f"the pano backup must live under the shared backup root; got {backup!r}"
        )
        assert "hypr-pano" in backup, (
            "the pano backup must be distinguishable from the bar's timestamp "
            f"dir; got {backup!r}"
        )

    def test_live_notifications_is_forced_symlink_into_the_unit_notifications(
        self,
    ) -> None:
        task = _named("Deploy the unit's notifications as the live notification overlay")
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "link"
        assert module["force"] is True, "force makes a rollback repoint converge"
        assert module["src"] == "{{ ags_apps_notifications_dir }}"
        assert module["dest"] == "{{ ags_apps_live_notifications_link }}"

    def test_notifications_legacy_bridge_is_classified_before_displacement(
        self,
    ) -> None:
        """Slice 4 mirrors the bar/pano migrate-then-symlink discipline: the role
        must classify the live-notifications path (stat + children) BEFORE
        touching it, so an empty fresh-spine dir is removed while a non-empty
        legacy bridge is moved aside, never deleted."""
        stat = _named("Check whether the live-notifications path already exists")
        assert _module_key(stat) == "ansible.builtin.stat"
        assert _module(stat).get("follow") is False, (
            "the stat must see the link itself, not its target"
        )
        find = _named("List the live-notifications path's children when it is a real dir")
        assert _module_key(find) == "ansible.builtin.find"
        remove = _named("Remove the live-notifications path when it is an empty real dir")
        assert _module(remove)["state"] == "absent"
        move = _named(
            "Move aside a non-empty legacy notifications bridge dir blocking the live-notifications link"
        )
        assert _module_key(move) == "ansible.builtin.command", (
            "the move-aside is a mutation and must stay a check-gated command"
        )
        for task in (remove, move):
            when = str(task.get("when", ""))
            assert "islnk" in when and "matched" in when, (
                f"task {task.get('name')!r} must branch on link-vs-dir and "
                "empty-vs-nonempty"
            )
            assert "not ansible_check_mode" in when
        names = [str(t.get("name", "")) for t in _load_tasks()]
        assert names.index(
            "Remove the live-notifications path when it is an empty real dir"
        ) < names.index(
            "Deploy the unit's notifications as the live notification overlay"
        ), "ordering must be classify -> backup -> symlink"

    def test_notifications_backup_path_cannot_collide_with_the_others(self) -> None:
        """The three links share the bridge-backup root. A run that displaces
        MULTIPLE legacy dirs must not move them onto the same timestamped path,
        so the notifications backup carries an app suffix."""
        task = _named("Determine the legacy-notifications-bridge backup path for this run")
        backup = str(_module(task)["ags_apps_notifications_backup_path"])
        assert "ags_apps_backup_root" in backup, (
            f"the notifications backup must live under the shared backup root; got {backup!r}"
        )
        assert "notifications" in backup, (
            "the notifications backup must be distinguishable from the bar/pano "
            f"timestamp dirs; got {backup!r}"
        )

    def test_live_capture_is_forced_symlink_into_the_unit_capture_tool(self) -> None:
        task = _named("Deploy the unit's capture-tool as the live capture GUI")
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "link"
        assert module["force"] is True, "force makes a rollback repoint converge"
        assert module["src"] == "{{ ags_apps_capture_tool_dir }}"
        assert module["dest"] == "{{ ags_apps_live_capture_link }}"

    def test_capture_legacy_bridge_is_classified_before_displacement(self) -> None:
        """Slice 5 mirrors the bar/pano/notifications migrate-then-symlink
        discipline: the role must classify the live-capture path (stat + children)
        BEFORE touching it, so an empty fresh-spine dir is removed while a
        non-empty legacy bridge is moved aside, never deleted."""
        stat = _named("Check whether the live-capture path already exists")
        assert _module_key(stat) == "ansible.builtin.stat"
        assert _module(stat).get("follow") is False, (
            "the stat must see the link itself, not its target"
        )
        find = _named("List the live-capture path's children when it is a real dir")
        assert _module_key(find) == "ansible.builtin.find"
        remove = _named("Remove the live-capture path when it is an empty real dir")
        assert _module(remove)["state"] == "absent"
        move = _named(
            "Move aside a non-empty legacy capture bridge dir blocking the live-capture link"
        )
        assert _module_key(move) == "ansible.builtin.command", (
            "the move-aside is a mutation and must stay a check-gated command"
        )
        for task in (remove, move):
            when = str(task.get("when", ""))
            assert "islnk" in when and "matched" in when, (
                f"task {task.get('name')!r} must branch on link-vs-dir and "
                "empty-vs-nonempty"
            )
            assert "not ansible_check_mode" in when
        names = [str(t.get("name", "")) for t in _load_tasks()]
        assert names.index(
            "Remove the live-capture path when it is an empty real dir"
        ) < names.index("Deploy the unit's capture-tool as the live capture GUI"), (
            "ordering must be classify -> backup -> symlink"
        )

    def test_capture_backup_path_cannot_collide_with_the_others(self) -> None:
        """The four links share the bridge-backup root. A run that displaces
        MULTIPLE legacy dirs must not move them onto the same timestamped path, so
        the capture backup carries an app suffix."""
        task = _named("Determine the legacy-capture-bridge backup path for this run")
        backup = str(_module(task)["ags_apps_capture_backup_path"])
        assert "ags_apps_backup_root" in backup, (
            f"the capture backup must live under the shared backup root; got {backup!r}"
        )
        assert "capture-tool" in backup, (
            "the capture backup must be distinguishable from the bar/pano/"
            f"notifications timestamp dirs; got {backup!r}"
        )

    def test_no_become_anywhere(self) -> None:
        for task in _load_tasks():
            assert not task.get("become", False), (
                f"ags_apps must not use become (task {task.get('name')!r})"
            )

    def test_live_wallpaper_selector_is_forced_symlink_into_the_unit(
        self,
    ) -> None:
        task = _named(
            "Deploy the unit's wallpaper-selector as the live wallpaper selector"
        )
        assert _module_key(task) == "ansible.builtin.file"
        module = _module(task)
        assert module["state"] == "link"
        assert module["force"] is True, "force makes a rollback repoint converge"
        assert module["src"] == "{{ ags_apps_wallpaper_selector_dir }}"
        assert module["dest"] == "{{ ags_apps_live_wallpaper_selector_link }}"

    def test_wallpaper_selector_legacy_bridge_is_classified_before_displacement(
        self,
    ) -> None:
        """Slice 6 mirrors the bar/pano/notifications/capture migrate-then-symlink
        discipline: the role must classify the live-wallpaper-selector path (stat +
        children) BEFORE touching it, so an empty fresh-spine dir is removed while
        a non-empty legacy bridge is moved aside, never deleted."""
        stat = _named("Check whether the live-wallpaper-selector path already exists")
        assert _module_key(stat) == "ansible.builtin.stat"
        assert _module(stat).get("follow") is False, (
            "the stat must see the link itself, not its target"
        )
        find = _named(
            "List the live-wallpaper-selector path's children when it is a real dir"
        )
        assert _module_key(find) == "ansible.builtin.find"
        remove = _named(
            "Remove the live-wallpaper-selector path when it is an empty real dir"
        )
        assert _module(remove)["state"] == "absent"
        move = _named(
            "Move aside a non-empty legacy wallpaper-selector bridge dir blocking the live-wallpaper-selector link"
        )
        assert _module_key(move) == "ansible.builtin.command", (
            "the move-aside is a mutation and must stay a check-gated command"
        )
        for task in (remove, move):
            when = str(task.get("when", ""))
            assert "islnk" in when and "matched" in when, (
                f"task {task.get('name')!r} must branch on link-vs-dir and "
                "empty-vs-nonempty"
            )
            assert "not ansible_check_mode" in when
        names = [str(t.get("name", "")) for t in _load_tasks()]
        assert names.index(
            "Remove the live-wallpaper-selector path when it is an empty real dir"
        ) < names.index(
            "Deploy the unit's wallpaper-selector as the live wallpaper selector"
        ), "ordering must be classify -> backup -> symlink"

    def test_wallpaper_selector_backup_path_cannot_collide_with_the_others(
        self,
    ) -> None:
        """The five links share the bridge-backup root. A run that displaces
        MULTIPLE legacy dirs must not move them onto the same timestamped path, so
        the selector backup carries an app suffix."""
        task = _named(
            "Determine the legacy-wallpaper-selector-bridge backup path for this run"
        )
        backup = str(_module(task)["ags_apps_wallpaper_selector_backup_path"])
        assert "ags_apps_backup_root" in backup, (
            f"the selector backup must live under the shared backup root; got "
            f"{backup!r}"
        )
        assert "wallpaper-selector" in backup, (
            "the selector backup must be distinguishable from the bar/pano/"
            f"notifications/capture timestamp dirs; got {backup!r}"
        )


class TestAgsAppsPlaybook:
    _PATH = _PLAYBOOKS_DIR / "ags-apps.yaml"

    def test_parses_with_simple_localhost_structure(self) -> None:
        plays = yaml.safe_load(self._PATH.read_text())
        assert isinstance(plays, list) and len(plays) == 1
        play = plays[0]
        assert play["hosts"] == "localhost"
        assert play["gather_facts"] is True
        assert play["roles"] == ["ags_apps"]
        assert "become" not in play

    def test_syntax_check_exits_zero(self) -> None:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping syntax-check")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        result = subprocess.run(
            [ansible_playbook, "--syntax-check", str(self._PATH)],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestAgsAppsExecution:
    """Run the real playbook against a pre-seeded unit (no network): the clone
    is presence-guarded, so the run exercises the pin + shortcuts + live link."""

    _PATH = _PLAYBOOKS_DIR / "ags-apps.yaml"

    def _run(self, install: Path, home: Path) -> subprocess.CompletedProcess[str]:
        ansible_playbook = shutil.which("ansible-playbook")
        if ansible_playbook is None:
            pytest.skip("ansible-playbook not installed; skipping execution test")
        env = {k: v for k, v in os.environ.items() if not k.startswith("ANSIBLE_")}
        env["HOME"] = str(home)
        # Pin the state root so the role's runtime colors.css pointer resolves
        # deterministically under the test home (the ambient XDG_STATE_HOME
        # would otherwise leak the developer's real state dir into the run).
        env["XDG_STATE_HOME"] = str(home / ".local" / "state")
        env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")
        return subprocess.run(
            [ansible_playbook, str(self._PATH), "-e", f"install_dir={install}"],
            capture_output=True,
            text=True,
            env=env,
            timeout=120,
        )

    @staticmethod
    def _seed_units(install: Path) -> tuple[Path, Path]:
        platform = install / "ags-platform" / "v0.2.0"
        (platform / "ports").mkdir(parents=True)
        (platform / "index.ts").write_text("export {}\n")
        # Derive the unit dir from the pin so a tag bump does not leave a
        # hardcoded `bar-v0.1.1` behind (the pin is a monorepo release now).
        unit = install / "ags-apps" / str(_vars()["ags_apps_version"])
        bar = unit / "bar"
        bar.mkdir(parents=True)
        (bar / "app.tsx").write_text("export {}\n")
        # The monorepo unit also ships hypr-pano/ (slice 3); the live-pano link
        # needs it present to resolve.
        pano = unit / "hypr-pano"
        pano.mkdir(parents=True)
        (pano / "app.tsx").write_text("export {}\n")
        # ... and notifications/ (slice 4); the live-notifications link needs it.
        notifications = unit / "notifications"
        notifications.mkdir(parents=True)
        (notifications / "app.tsx").write_text("export {}\n")
        # ... and capture-tool/ (slice 5); the live-capture link needs it.
        capture = unit / "capture-tool"
        capture.mkdir(parents=True)
        (capture / "app.tsx").write_text("export {}\n")
        # ... and wallpaper-selector/ (slice 6); the live-wallpaper-selector link
        # needs it.
        selector = unit / "wallpaper-selector"
        selector.mkdir(parents=True)
        (selector / "app.tsx").write_text("export {}\n")
        return platform, bar

    def test_places_pin_links_and_shortcut_for_a_present_unit(
        self, tmp_path: Path
    ) -> None:
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        platform, bar = self._seed_units(install)

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        pin = install / "ags-apps" / "pinned"
        assert pin.is_file(), "the pin must be recorded"
        assert pin.read_text().strip() == str(_vars()["ags_apps_version"])

        live = install / "config" / "ags"
        assert live.is_symlink(), "the live bar must be a symlink"
        assert live.resolve() == bar.resolve(), (
            "the live bar must point at the unit's bar/"
        )
        unit_dir = install / "ags-apps" / str(_vars()["ags_apps_version"])
        assert not (unit_dir / ".git").exists()

        live_pano = install / "config" / "ags-hypr-pano"
        assert live_pano.is_symlink(), "the live clipboard overlay must be a symlink"
        assert live_pano.resolve() == (unit_dir / "hypr-pano").resolve(), (
            "the live clipboard overlay must point at the unit's hypr-pano/"
        )

        live_notifications = install / "config" / "ags-notifications"
        assert live_notifications.is_symlink(), (
            "the live notification overlay must be a symlink"
        )
        assert live_notifications.resolve() == (unit_dir / "notifications").resolve(), (
            "the live notification overlay must point at the unit's notifications/"
        )

        live_capture = install / "config" / "ags-capture"
        assert live_capture.is_symlink(), "the live capture GUI must be a symlink"
        assert live_capture.resolve() == (unit_dir / "capture-tool").resolve(), (
            "the live capture GUI must point at the unit's capture-tool/"
        )

        live_selector = install / "config" / "ags-wallpaper-selector"
        assert live_selector.is_symlink(), (
            "the live wallpaper selector must be a symlink"
        )
        assert live_selector.resolve() == (unit_dir / "wallpaper-selector").resolve(), (
            "the live wallpaper selector must point at the unit's "
            "wallpaper-selector/"
        )

        shortcut = (
            unit_dir / "node_modules" / "ags-platform"
        )
        assert shortcut.is_symlink(), "the per-unit shortcut must be a symlink"
        assert shortcut.resolve() == platform.resolve(), (
            "the shortcut must point at the pinned platform unit"
        )

        # The runtime colors.css pointer is ensured on EVERY deploy — the live
        # bar's colors.css must resolve (never dangle), or wlogout's @import
        # fails and GTK drops the stylesheet.
        pointer = unit_dir / "bar" / "colors.css"
        assert pointer.is_symlink(), (
            "the unit bar must carry the runtime colors.css pointer"
        )
        assert os.readlink(pointer) == str(
            home / ".local" / "state" / "dotfiles" / "current" / "colors.gtk.css"
        ), "the pointer must target the runtime state pointer"

        # Idempotent: a second run converges to the same state.
        second = self._run(install, home)
        assert second.returncode == 0, second.stdout + second.stderr
        assert live.resolve() == bar.resolve()
        assert live_pano.resolve() == (unit_dir / "hypr-pano").resolve()
        assert live_notifications.resolve() == (unit_dir / "notifications").resolve()
        assert live_capture.resolve() == (unit_dir / "capture-tool").resolve()
        assert live_selector.resolve() == (unit_dir / "wallpaper-selector").resolve()
        assert shortcut.resolve() == platform.resolve()

    def test_pano_legacy_bridge_is_moved_aside(self, tmp_path: Path) -> None:
        """Slice 3 upgrade from the per-file clipboard-overlay bridge: the
        legacy <install>/config/ags-hypr-pano dir is preserved in a timestamped
        backup (never deleted) and the live-pano link takes its place. No
        colors.css seed applies (hypr-pano owns no runtime pointer)."""
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        self._seed_units(install)

        legacy = install / "config" / "ags-hypr-pano"
        (legacy / "ui").mkdir(parents=True)
        (legacy / "app.tsx").write_text("export {}\n")

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        unit_dir = install / "ags-apps" / str(_vars()["ags_apps_version"])
        assert legacy.is_symlink(), "the live-pano link must replace the legacy dir"
        assert legacy.resolve() == (unit_dir / "hypr-pano").resolve()

        backups = list((install / "ags-apps" / "bridge-backups").iterdir())
        assert len(backups) == 1, "exactly one timestamped backup must exist"
        assert "hypr-pano" in backups[0].name, (
            "the pano backup must be distinguishable from a bar backup"
        )
        assert (backups[0] / "app.tsx").is_file(), (
            "the backup must preserve the legacy bridge verbatim"
        )

    def test_notifications_legacy_bridge_is_moved_aside(self, tmp_path: Path) -> None:
        """Slice 4 upgrade from the per-file notification bridge: the legacy
        <install>/config/ags-notifications dir is preserved in a timestamped
        backup (never deleted) and the live-notifications link takes its place.
        No colors.css seed applies (the overlay owns no runtime pointer)."""
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        self._seed_units(install)

        legacy = install / "config" / "ags-notifications"
        (legacy / "ui").mkdir(parents=True)
        (legacy / "app.tsx").write_text("export {}\n")

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        unit_dir = install / "ags-apps" / str(_vars()["ags_apps_version"])
        assert legacy.is_symlink(), (
            "the live-notifications link must replace the legacy dir"
        )
        assert legacy.resolve() == (unit_dir / "notifications").resolve()

        backups = list((install / "ags-apps" / "bridge-backups").iterdir())
        assert len(backups) == 1, "exactly one timestamped backup must exist"
        assert "notifications" in backups[0].name, (
            "the notifications backup must be distinguishable from a bar/pano backup"
        )
        assert (backups[0] / "app.tsx").is_file(), (
            "the backup must preserve the legacy bridge verbatim"
        )

    def test_capture_legacy_bridge_is_moved_aside(self, tmp_path: Path) -> None:
        """Slice 5 upgrade from the per-file capture GUI bridge: the legacy
        <install>/config/ags-capture dir is preserved in a timestamped backup
        (never deleted) and the live-capture link takes its place. No colors.css
        seed applies (the GUI owns no runtime pointer)."""
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        self._seed_units(install)

        legacy = install / "config" / "ags-capture"
        (legacy / "ui").mkdir(parents=True)
        (legacy / "app.tsx").write_text("export {}\n")

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        unit_dir = install / "ags-apps" / str(_vars()["ags_apps_version"])
        assert legacy.is_symlink(), (
            "the live-capture link must replace the legacy dir"
        )
        assert legacy.resolve() == (unit_dir / "capture-tool").resolve()

        backups = list((install / "ags-apps" / "bridge-backups").iterdir())
        assert len(backups) == 1, "exactly one timestamped backup must exist"
        assert "capture-tool" in backups[0].name, (
            "the capture backup must be distinguishable from a bar/pano/"
            "notifications backup"
        )
        assert (backups[0] / "app.tsx").is_file(), (
            "the backup must preserve the legacy bridge verbatim"
        )

    def test_wallpaper_selector_legacy_bridge_is_moved_aside(
        self, tmp_path: Path
    ) -> None:
        """Slice 6 upgrade from the per-file wallpaper-selector bridge: the legacy
        <install>/config/ags-wallpaper-selector dir is preserved in a timestamped
        backup (never deleted) and the live-wallpaper-selector link takes its
        place. No colors.css seed applies (the selector owns no runtime pointer)."""
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        self._seed_units(install)

        legacy = install / "config" / "ags-wallpaper-selector"
        (legacy / "lib").mkdir(parents=True)
        (legacy / "app.tsx").write_text("export {}\n")

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        unit_dir = install / "ags-apps" / str(_vars()["ags_apps_version"])
        assert legacy.is_symlink(), (
            "the live-wallpaper-selector link must replace the legacy dir"
        )
        assert legacy.resolve() == (unit_dir / "wallpaper-selector").resolve()

        backups = list((install / "ags-apps" / "bridge-backups").iterdir())
        assert len(backups) == 1, "exactly one timestamped backup must exist"
        assert "wallpaper-selector" in backups[0].name, (
            "the selector backup must be distinguishable from a bar/pano/"
            "notifications/capture backup"
        )
        assert (backups[0] / "app.tsx").is_file(), (
            "the backup must preserve the legacy bridge verbatim"
        )

    def test_legacy_bridge_is_moved_aside_and_colors_seeded(
        self, tmp_path: Path
    ) -> None:
        """Upgrading from the per-file bridge: the legacy dir is preserved in
        a timestamped backup (never deleted), the runtime colors.css pointer is
        seeded into the unit, and the live link takes its place."""
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        platform, bar = self._seed_units(install)

        legacy = install / "config" / "ags"
        legacy.mkdir()
        (legacy / "app.tsx").write_text("export {}\n")
        (tmp_path / "colors-target.css").write_text("/* palette */\n")
        (legacy / "colors.css").symlink_to(tmp_path / "colors-target.css")

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        assert legacy.is_symlink(), "the live bar must replace the legacy dir"
        assert legacy.resolve() == bar.resolve()

        backups = list((install / "ags-apps" / "bridge-backups").iterdir())
        assert len(backups) == 1, "exactly one timestamped backup must exist"
        assert (backups[0] / "app.tsx").is_file(), (
            "the backup must preserve the legacy bridge verbatim"
        )

        seeded = bar / "colors.css"
        assert seeded.is_symlink(), (
            "the runtime colors.css pointer must be seeded into the unit"
        )
        assert seeded.resolve() == (tmp_path / "colors-target.css").resolve()

    def test_colors_pointer_is_seeded_on_a_fresh_deploy(self, tmp_path: Path) -> None:
        """FRESH HOST: no pre-existing pointer to inherit, so the ensure falls
        back to the runtime state pointer (<state>/dotfiles/current/
        colors.gtk.css) and the live bar's colors.css resolves through it."""
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        self._seed_units(install)

        state_current = home / ".local" / "state" / "dotfiles" / "current"
        state_current.mkdir(parents=True)
        (state_current / "colors.gtk.css").write_text(
            "@define-color color_background #0b0b1a;\n"
        )

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        unit_dir = install / "ags-apps" / str(_vars()["ags_apps_version"])
        pointer = unit_dir / "bar" / "colors.css"
        assert pointer.is_symlink(), (
            "a fresh deploy must seed the runtime colors.css pointer"
        )
        assert os.readlink(pointer) == str(state_current / "colors.gtk.css")
        # The consumer path wlogout imports resolves THROUGH the live-bar link.
        live = install / "config" / "ags"
        assert live.is_symlink()
        assert (live / "colors.css").read_text().startswith("@define-color")

        # Idempotent: a second run converges to the same pointer.
        second = self._run(install, home)
        assert second.returncode == 0, second.stdout + second.stderr
        assert pointer.is_symlink()
        assert os.readlink(pointer) == str(state_current / "colors.gtk.css")

    def test_colors_pointer_is_seeded_on_a_version_bump(self, tmp_path: Path) -> None:
        """THE REPORTED REGRESSION: the live-bar link is ALREADY a symlink into
        a previous unit when a new tag is deployed. The old seed was gated on the
        live-bar path being a REAL dir, so it was skipped on every bump and the
        NEW unit's bar/colors.css dangled — wlogout opened with no wallpaper and
        no icons. The ensure must inherit the previous pointer's target."""
        home = tmp_path / "home"
        install = tmp_path / "install"
        home.mkdir()
        install.mkdir()
        (install / "config").mkdir()
        self._seed_units(install)

        state_current = home / ".local" / "state" / "dotfiles" / "current"
        state_current.mkdir(parents=True)
        (state_current / "colors.gtk.css").write_text(
            "@define-color color_background #0b0b1a;\n"
        )

        # A PREVIOUS unit already carries the pointer, and the live-bar link
        # already points at it (the state left by the prior deploy).
        previous_bar = install / "ags-apps" / "v0.0.1" / "bar"
        previous_bar.mkdir(parents=True)
        (previous_bar / "app.tsx").write_text("export {}\n")
        (previous_bar / "colors.css").symlink_to(state_current / "colors.gtk.css")

        live = install / "config" / "ags"
        live.symlink_to(previous_bar)
        assert live.is_symlink()

        result = self._run(install, home)
        assert result.returncode == 0, result.stdout + result.stderr

        unit_dir = install / "ags-apps" / str(_vars()["ags_apps_version"])
        assert live.is_symlink(), "the live bar stays a symlink"
        assert live.resolve() == (unit_dir / "bar").resolve(), (
            "the live bar must repoint at the new unit"
        )
        pointer = unit_dir / "bar" / "colors.css"
        assert pointer.is_symlink(), (
            "a version bump must seed colors.css into the NEW unit — a dangling "
            "pointer here is the wlogout regression"
        )
        assert pointer.resolve() == (state_current / "colors.gtk.css").resolve()
        assert (live / "colors.css").read_text().startswith("@define-color")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

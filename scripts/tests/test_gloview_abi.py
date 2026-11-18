#!/usr/bin/env python3
"""Focused tests for the GloView ABI-resilience scripts.

Stdlib only (no pytest/uv/venv) so a fresh composition checkout can run:

    python3 scripts/tests/test_gloview_abi.py

The activator is a bash script; these tests drive it with a fake ``hyprctl``,
``expac`` and ``notify-send`` so the load/verify/state/notification contract is
proven without a live Hyprland session and without touching the host.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
ACTIVATOR = REPO_ROOT / "dotfiles" / "provisioning" / "scripts" / "gloview-activate"
REBUILD_HELPER = REPO_ROOT / "dotfiles" / "provisioning" / "scripts" / "gloview-rebuild"

FAKE_HYPRCTL = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import os, shutil, sys
    state = os.environ["FAKE_STATE"]
    args = sys.argv[1:]
    def read(name, default=""):
        path = os.path.join(state, name)
        if not os.path.exists(path):
            return default
        return open(path, encoding="utf-8").read()
    if args[:1] == ["version"]:
        if os.path.exists(os.path.join(state, "version_fail")):
            sys.exit(1)
        sys.stdout.write(read("version.json", "{}"))
    elif args[:2] == ["plugin", "list"]:
        sys.stdout.write(read("plugin_list.json", "[]"))
    elif args[:2] == ["plugin", "load"]:
        with open(os.path.join(state, "load_calls"), "a", encoding="utf-8") as fh:
            fh.write(" ".join(args) + "\\n")
        sys.stderr.write(read("load_output"))
        if os.path.exists(os.path.join(state, "load_flip")):
            shutil.copyfile(
                os.path.join(state, "plugin_list_after.json"),
                os.path.join(state, "plugin_list.json"),
            )
        sys.exit(int(read("load_rc", "0").strip() or "0"))
    elif args[:1] == ["reload"]:
        with open(os.path.join(state, "reload_calls"), "a", encoding="utf-8") as fh:
            fh.write("reload\\n")
    else:
        sys.exit(2)
    """
)

FAKE_EXPAC = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    data = json.load(open(os.environ["FAKE_EXPAC_JSON"], encoding="utf-8"))
    args = sys.argv[1:]
    if len(args) < 3 or args[0] != "-Q":
        sys.exit(2)
    if args[1] == "-t":
        field = args[3].lstrip("%")
        package = args[4]
    else:
        field = args[1].lstrip("%")
        package = args[2]
    value = data.get(package, {}).get(field)
    if value is None:
        sys.exit(1)
    print(value)
    """
)

FAKE_NOTIFY = textwrap.dedent(
    """\
    #!/usr/bin/env python3
    import json, os, sys
    path = os.environ["FAKE_NOTIFICATIONS"]
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(sys.argv[1:]) + "\\n")
    """
)


def _write_executable(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class GloViewFixture:
    """A temp HOME/state/runtime tree plus fake host tools."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="gloview-abi-")
        self.root = Path(self._tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state_home = self.root / "state"
        self.runtime = self.root / "runtime"
        self.fake_state = self.root / "fake"
        for directory in (self.state_home, self.runtime, self.fake_state):
            directory.mkdir()
        self.plugin_so = self.root / "gloview.so"
        self.plugin_so.write_text("not a real shared object\n", encoding="utf-8")
        self.notifications = self.root / "notifications.jsonl"
        self.expac_json = self.root / "expac.json"
        self.set_expac({})
        _write_executable(self.bin / "hyprctl", FAKE_HYPRCTL)
        _write_executable(self.bin / "expac", FAKE_EXPAC)
        _write_executable(self.bin / "notify-send", FAKE_NOTIFY)
        self.set_plugin_list([])
        self.set_version("0.57.2", "abi-current")

    def __enter__(self) -> "GloViewFixture":
        return self

    def __exit__(self, *exc: object) -> None:
        self._tmp.cleanup()

    def set_version(self, version: str, abi_hash: str) -> None:
        (self.fake_state / "version.json").write_text(
            json.dumps({"version": version, "abiHash": abi_hash}), encoding="utf-8"
        )

    def set_version_failure(self) -> None:
        (self.fake_state / "version_fail").write_text("1", encoding="utf-8")

    def set_plugin_list(self, plugins: list[dict[str, str]]) -> None:
        (self.fake_state / "plugin_list.json").write_text(
            json.dumps(plugins), encoding="utf-8"
        )

    def set_after_load(self, plugins: list[dict[str, str]], *, flip: bool = True) -> None:
        (self.fake_state / "plugin_list_after.json").write_text(
            json.dumps(plugins), encoding="utf-8"
        )
        if flip:
            (self.fake_state / "load_flip").write_text("1", encoding="utf-8")

    def set_load(self, *, output: str = "", rc: int = 0) -> None:
        (self.fake_state / "load_output").write_text(output, encoding="utf-8")
        (self.fake_state / "load_rc").write_text(str(rc), encoding="utf-8")

    def set_expac(self, packages: dict[str, dict[str, object]]) -> None:
        self.expac_json.write_text(json.dumps(packages), encoding="utf-8")

    def run(self, *, timeout: float = 20) -> subprocess.CompletedProcess[str]:
        env = {
            "PATH": f"{self.bin}:{os.environ.get('PATH', '')}",
            "HOME": str(self.root),
            "XDG_STATE_HOME": str(self.state_home),
            "XDG_RUNTIME_DIR": str(self.runtime),
            "HYPRLAND_INSTANCE_SIGNATURE": "test-signature",
            "GLOVIEW_PLUGIN_SO": str(self.plugin_so),
            "GLOVIEW_IPC_WAIT_SECS": "0",
            "GLOVIEW_VERIFY_WAIT_SECS": "1",
            "FAKE_STATE": str(self.fake_state),
            "FAKE_EXPAC_JSON": str(self.expac_json),
            "FAKE_NOTIFICATIONS": str(self.notifications),
        }
        return subprocess.run(
            [str(ACTIVATOR)],
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )

    @property
    def status_file(self) -> Path:
        return self.state_home / "dotfiles" / "gloview" / "status.json"

    @property
    def marker(self) -> Path:
        return self.state_home / "dotfiles" / "gloview-active"

    @property
    def log_file(self) -> Path:
        return self.state_home / "dotfiles" / "gloview" / "activate.log"

    def status(self) -> dict[str, object]:
        return json.loads(self.status_file.read_text(encoding="utf-8"))

    def notification_argv(self) -> list[list[str]]:
        if not self.notifications.exists():
            return []
        return [
            json.loads(line)
            for line in self.notifications.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def write_previous_status(self, abi_hash: str) -> None:
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        self.status_file.write_text(
            json.dumps({"schema": 1, "ok": True, "hyprland": {"abiHash": abi_hash}}),
            encoding="utf-8",
        )


class ActivatorTests(unittest.TestCase):
    def test_healthy_load_verifies_json_and_writes_stamp(self) -> None:
        with GloViewFixture() as fx:
            fx.set_after_load([{"name": "GloView", "version": "0.3.0"}])
            fx.set_load(output="")
            result = fx.run()
            self.assertEqual(result.returncode, 0, result.stderr)
            status = fx.status()
            self.assertTrue(status["ok"])
            self.assertEqual(status["status"], "ok")
            self.assertEqual(status["hyprland"]["abiHash"], "abi-current")
            self.assertTrue(fx.marker.exists())
            self.assertEqual(fx.notification_argv(), [])
            self.assertTrue((fx.fake_state / "reload_calls").exists())
            self.assertIn("OK:", fx.log_file.read_text(encoding="utf-8"))

    def test_load_exit_zero_with_failure_output_is_a_failure(self) -> None:
        with GloViewFixture() as fx:
            fx.set_load(
                output="Plugin /tmp/gloview.so could not be loaded: undefined symbol: _ZN9CConfigValue",
                rc=0,
            )
            fx.marker.parent.mkdir(parents=True, exist_ok=True)
            fx.marker.write_text("stale", encoding="utf-8")
            result = fx.run()
            self.assertNotEqual(result.returncode, 0)
            status = fx.status()
            self.assertFalse(status["ok"])
            self.assertEqual(status["status"], "failed")
            self.assertIn("undefined symbol", status["lastError"])
            self.assertIn("undefined symbol", status["loaderOutput"])
            self.assertFalse(fx.marker.exists())
            notifications = fx.notification_argv()
            self.assertEqual(len(notifications), 1, notifications)
            body = " ".join(notifications[0])
            self.assertIn("yay -S --rebuild gloview-git", body)
            self.assertIn("log out and back in", body)

    def test_abi_change_is_reported_and_success_updates_stamp(self) -> None:
        with GloViewFixture() as fx:
            fx.write_previous_status("abi-old")
            fx.set_plugin_list([{"name": "GloView", "version": "0.3.0"}])
            result = fx.run()
            self.assertEqual(result.returncode, 0, result.stderr)
            status = fx.status()
            self.assertTrue(status["ok"])
            self.assertTrue(status["abiChanged"])
            self.assertEqual(status["hyprland"]["abiHash"], "abi-current")
            self.assertEqual(fx.notification_argv(), [])

    def test_missing_ipc_is_fail_open(self) -> None:
        with GloViewFixture() as fx:
            fx.set_version_failure()
            result = fx.run()
            self.assertEqual(result.returncode, 0, result.stderr)
            status = fx.status()
            self.assertEqual(status["status"], "ipc_unavailable")
            self.assertEqual(fx.notification_argv(), [])

    def test_chronology_warning_only_when_gloview_build_is_older(self) -> None:
        with GloViewFixture() as fx:
            fx.set_plugin_list([{"name": "GloView"}])
            fx.set_expac(
                {
                    "gloview-git": {"v": "0.3.0", "b": 100, "l": 100},
                    "hyprland": {"v": "0.57.2", "l": 200},
                }
            )
            self.assertEqual(fx.run().returncode, 0)
            status = fx.status()
            self.assertTrue(status["chronologyWarning"])
            # Metadata is epoch seconds, not expac's human date string or the
            # %i install-scriptlet flag (G-4 regression guard).
            self.assertEqual(status["gloview"]["buildDate"], 100)
            self.assertEqual(status["gloview"]["installDate"], 100)

            fx.set_expac(
                {
                    "gloview-git": {"v": "0.3.0", "b": 300, "l": 300},
                    "hyprland": {"v": "0.57.2", "l": 200},
                }
            )
            self.assertEqual(fx.run().returncode, 0)
            self.assertFalse(fx.status()["chronologyWarning"])

    def test_missing_artifact_fails_with_remediation(self) -> None:
        with GloViewFixture() as fx:
            fx.plugin_so.unlink()
            result = fx.run()
            self.assertNotEqual(result.returncode, 0)
            status = fx.status()
            self.assertFalse(status["ok"])
            self.assertIn("missing", status["lastError"])
            self.assertEqual(len(fx.notification_argv()), 1)

    def test_second_run_is_idempotent(self) -> None:
        with GloViewFixture() as fx:
            fx.set_after_load([{"name": "GloView", "version": "0.3.0"}])
            self.assertEqual(fx.run().returncode, 0)
            self.assertEqual(fx.run().returncode, 0)
            self.assertTrue(fx.status()["ok"])
            # The second run sees GloView already listed and does not load again.
            load_calls = (fx.fake_state / "load_calls").read_text(encoding="utf-8")
            self.assertEqual(load_calls.count("plugin load"), 1)


class NoPrivilegeTests(unittest.TestCase):
    def _code_lines(self, path: Path) -> list[str]:
        lines = []
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            lines.append(line)
        return lines

    def test_activator_never_invokes_privilege_or_network_tools(self) -> None:
        code = "\n".join(self._code_lines(ACTIVATOR))
        for forbidden in ("sudo", "pacman", "curl", "wget", "http://", "https://"):
            self.assertNotIn(forbidden, code)
        # `yay` is allowed only inside the literal remediation string shown to
        # the user; it is never executed from this script.
        for line in code.splitlines():
            if "yay" in line:
                self.assertIn("rebuild_command=", line, line)

    def test_rebuild_helper_is_interactive_and_never_escalates(self) -> None:
        code = "\n".join(self._code_lines(REBUILD_HELPER))
        self.assertIn("yay -S --rebuild gloview-git", code)
        self.assertIn("Log out and back in", code)
        self.assertNotIn("sudo", code)
        self.assertNotIn("--noconfirm", code)
        self.assertNotIn("systemctl", code)
        # The activator must not execute the interactive helper; its only
        # mention is the remediation text in the notification.
        activator = ACTIVATOR.read_text(encoding="utf-8")
        for line in activator.splitlines():
            if "gloview-rebuild" in line:
                self.assertIn("message=", line, line)


if __name__ == "__main__":
    unittest.main(verbosity=2)

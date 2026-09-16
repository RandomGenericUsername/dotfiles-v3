"""Unit tests for the capture settings config contract
(add-capture-settings, design.md §1/§3/§4).

Mirrors test_capture_tool_cli.py: the launcher is a dependency-free script
loaded straight from ``bin/capture-tool`` via importlib; subprocess and the
detached spawn are fakes. Coverage mirrors the frozen contract: config
loading fallbacks (missing/corrupt/partial), pattern-based default save
paths, cursor plumb-through per backend (grim ``-c``, gsr ``-cursor yes``,
wf-recorder has no flag), explicit-output precedence, the notifications
toggle gating ALL emission, and the read-only backend readout.
"""

from __future__ import annotations

import importlib.util
import json
import logging
import shlex
from datetime import datetime
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin" / "capture-tool"


def _load():
    loader = SourceFileLoader("capture_tool_settings", str(_BIN))
    spec = importlib.util.spec_from_loader("capture_tool_settings", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture(autouse=True)
def _stub_detached_notifications(monkeypatch: pytest.MonkeyPatch):
    """Capture detached-helper spawns instead of forking real processes."""
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        mod, "_spawn_detached", lambda argv: spawned.append(list(argv))
    )
    return spawned


@pytest.fixture()
def config_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point XDG_CONFIG_HOME at a temp tree and expose a writer helper."""
    config_home = tmp_path / "config"
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config_home))

    def write(data=None, raw=None) -> Path:
        path = config_home / "capture-tool" / "config.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        if raw is not None:
            path.write_text(raw)
        elif data is not None:
            path.write_text(json.dumps(data))
        return path

    return write


class TestConfigLoading:
    def test_missing_file_is_first_run_defaults(self, config_env) -> None:
        config = mod.load_config()
        assert config["screenshot_dir"] == "~/Pictures/Screenshots"
        assert config["recording_dir"] == "~/Videos/Recordings"
        assert config["filename_pattern"] == mod.DEFAULT_FILENAME_PATTERN
        assert config["notifications"] is True
        assert config["screenshot"] == {"format": "png", "output": "clipboard", "cursor": False}
        assert config["recording"] == {"fps": 60, "quality": "high", "audio": "system", "cursor": True}

    def test_corrupt_json_degrades_and_logs_loudly(
        self, config_env, caplog: pytest.LogCaptureFixture
    ) -> None:
        config_env(raw="{ this is not json")
        with caplog.at_level(logging.WARNING, logger="capture-tool"):
            config = mod.load_config()
        assert config["screenshot_dir"] == "~/Pictures/Screenshots"
        assert any("unreadable config" in record.message for record in caplog.records)

    def test_partial_config_merges_with_defaults(self, config_env) -> None:
        config_env({"screenshot_dir": "/data/shots", "screenshot": {"format": "jpeg"}})
        config = mod.load_config()
        assert config["screenshot_dir"] == "/data/shots"
        assert config["screenshot"]["format"] == "jpeg"
        assert config["screenshot"]["output"] == "clipboard"
        assert config["recording"]["fps"] == 60

    def test_out_of_vocabulary_values_are_dropped(self, config_env) -> None:
        config_env(
            {
                "notifications": "yes",
                "filename_pattern": "   ",
                "recording": {"fps": 999, "quality": "ultra", "audio": "both", "cursor": "on"},
            }
        )
        config = mod.load_config()
        assert config["notifications"] is True
        assert config["filename_pattern"] == mod.DEFAULT_FILENAME_PATTERN
        assert config["recording"]["fps"] == 60
        assert config["recording"]["quality"] == "high"
        assert config["recording"]["audio"] == "system"
        assert config["recording"]["cursor"] is True

    def test_notifications_enabled_reads_toggle(self, config_env) -> None:
        assert mod.notifications_enabled() is True
        config_env({"notifications": False})
        assert mod.notifications_enabled() is False


class TestPatternPaths:
    def test_pattern_expands_kind_and_strftime(self) -> None:
        now = datetime(2026, 9, 16, 10, 24, 5)
        assert (
            mod.expand_filename_pattern("{kind}_%Y-%m-%d_%H-%M-%S", "recording", now=now)
            == "recording_2026-09-16_10-24-05"
        )

    def test_bad_pattern_falls_back(self) -> None:
        now = datetime(2026, 9, 16, 10, 24, 5)
        assert mod.expand_filename_pattern("", "screenshot", now=now) == (
            "screenshot_2026-09-16_10-24-05"
        )

    def test_recording_default_path_uses_config_dir_and_extension(self, tmp_path: Path) -> None:
        config = mod._merge_config(
            {"recording_dir": str(tmp_path / "recs"), "filename_pattern": "{kind}_%Y-%m-%d_%H-%M-%S"}
        )
        now = datetime(2026, 9, 16, 10, 24, 5)
        path = mod.default_recording_path(config, "mp4", now=now)
        assert path == str(tmp_path / "recs" / "recording_2026-09-16_10-24-05.mp4")

    def test_screenshot_default_path_uses_format_extension(self, tmp_path: Path) -> None:
        config = mod._merge_config({"screenshot_dir": str(tmp_path / "shots")})
        now = datetime(2026, 9, 16, 10, 24, 5)
        path = mod.default_screenshot_path(config, "jpeg", now=now)
        assert path == str(tmp_path / "shots" / "screenshot_2026-09-16_10-24-05.jpeg")

    def test_gif_default_path_has_gif_extension(self, tmp_path: Path) -> None:
        config = mod._merge_config({"recording_dir": str(tmp_path / "recs")})
        assert mod.default_recording_path(config, "gif").endswith(".gif")

    def test_tilde_is_expanded(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        config = mod._merge_config({"recording_dir": "~/Recordings"})
        assert mod.default_recording_path(config, "mp4").startswith(str(tmp_path / "Recordings"))


def _shot_args(**overrides):
    base = {
        "output": None,
        "target": "screen",
        "delay": 0,
        "format": "png",
        "save": False,
        "cursor": None,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _ShotHarness:
    """Capture grim argv + emitted payload for the screenshot path."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.commands: list[list[str]] = []
        self.popen: list[list[str]] = []
        self.payloads: list[dict] = []
        monkeypatch.setattr(
            mod.subprocess,
            "run",
            lambda command, **kwargs: self.commands.append(list(command))
            or SimpleNamespace(returncode=0),
        )
        monkeypatch.setattr(
            mod.subprocess,
            "Popen",
            lambda command, **kwargs: self.popen.append(list(command))
            or SimpleNamespace(
                stdout=SimpleNamespace(close=lambda: None), wait=lambda: 0
            ),
        )
        original_emit = mod.emit

        def _capture(payload, code):
            self.payloads.append(dict(payload))
            return original_emit(payload, code)

        monkeypatch.setattr(mod, "emit", _capture)


class TestScreenshotCursorAndPrecedence:
    def test_explicit_output_beats_config_save_path(
        self, config_env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_env({"screenshot_dir": str(tmp_path / "configured")})
        harness = _ShotHarness(monkeypatch)
        out = tmp_path / "explicit.png"
        with pytest.raises(SystemExit):
            mod.screenshot(_shot_args(output=str(out), save=True))
        assert str(out) in harness.commands[0]

    def test_save_uses_configured_dir(
        self, config_env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_env({"screenshot_dir": str(tmp_path / "configured")})
        harness = _ShotHarness(monkeypatch)
        with pytest.raises(SystemExit):
            mod.screenshot(_shot_args(save=True))
        assert harness.commands[0][-1].startswith(str(tmp_path / "configured"))

    def test_cursor_flag_reaches_grim(
        self, config_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_env({"screenshot": {"cursor": True}})
        harness = _ShotHarness(monkeypatch)
        with pytest.raises(SystemExit):
            mod.screenshot(_shot_args(save=True))
        assert "-c" in harness.commands[0]

    def test_no_cursor_flag_when_disabled(
        self, config_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_env({"screenshot": {"cursor": False}})
        harness = _ShotHarness(monkeypatch)
        with pytest.raises(SystemExit):
            mod.screenshot(_shot_args(save=True))
        assert "-c" not in harness.commands[0]

    def test_explicit_no_cursor_overrides_config(
        self, config_env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        config_env({"screenshot": {"cursor": True}})
        harness = _ShotHarness(monkeypatch)
        with pytest.raises(SystemExit):
            mod.screenshot(_shot_args(save=True, cursor=False))
        assert "-c" not in harness.commands[0]

    def test_no_save_keeps_clipboard(
        self, config_env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_env({"screenshot": {"output": "save"}})
        harness = _ShotHarness(monkeypatch)
        with pytest.raises(SystemExit):
            mod.screenshot(_shot_args(save=False))
        # Clipboard path pipes grim to stdout ("-") rather than a file.
        assert harness.popen[0][-1] == "-"
        assert not any(str(tmp_path) in part for part in harness.popen[0])


class TestRecordingCursor:
    def _args(self, **overrides):
        base = {
            "output": None,
            "target": "screen",
            "format": "mp4",
            "fps": 60,
            "quality": "high",
            "audio": "none",
            "duration": 0.0,
            "size": "original",
            "cursor": None,
        }
        base.update(overrides)
        return SimpleNamespace(**base)

    def test_gsr_cursor_flag_yes_and_no(self) -> None:
        on = mod._build_recording_command(
            "gpu-screen-recorder", "DP-1", self._args(), "o.mp4", cursor=True
        )
        off = mod._build_recording_command(
            "gpu-screen-recorder", "DP-1", self._args(), "o.mp4", cursor=False
        )
        assert on[on.index("-cursor") + 1] == "yes"
        assert off[off.index("-cursor") + 1] == "no"

    def test_wf_recorder_has_no_cursor_flag(self) -> None:
        command = mod._build_recording_command(
            "wf-recorder", "DP-1", self._args(), "o.mp4", cursor=True
        )
        assert "-cursor" not in command
        assert not any("cursor" in part.lower() for part in command)

    def test_config_cursor_flows_through_start_recording(
        self, config_env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_env(
            {
                "recording_dir": str(tmp_path / "recs"),
                "recording": {"cursor": True},
            }
        )
        spawned: list[list[str]] = []
        monkeypatch.setattr(mod, "choose_backend", lambda: "gpu-screen-recorder")
        monkeypatch.setattr(mod, "resolve_target", lambda _t: "DP-1")
        monkeypatch.setattr(mod, "resolve_audio_device", lambda _a, run=None: None)
        monkeypatch.setattr(
            mod.shutil,
            "which",
            lambda name: "/usr/bin/dotfiles-runtime" if name == "dotfiles-runtime" else None,
        )
        monkeypatch.setattr(
            mod.subprocess,
            "Popen",
            lambda argv, **kwargs: spawned.append(list(argv)) or SimpleNamespace(),
        )
        with pytest.raises(SystemExit):
            mod.start_recording(self._args())
        recorder_argv = shlex.split(spawned[0][spawned[0].index("--command") + 1])
        assert recorder_argv[recorder_argv.index("-cursor") + 1] == "yes"

    def test_explicit_cursor_overrides_config(
        self, config_env, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        config_env({"recording_dir": str(tmp_path / "recs"), "recording": {"cursor": False}})
        spawned: list[list[str]] = []
        monkeypatch.setattr(mod, "choose_backend", lambda: "gpu-screen-recorder")
        monkeypatch.setattr(mod, "resolve_target", lambda _t: "DP-1")
        monkeypatch.setattr(mod, "resolve_audio_device", lambda _a, run=None: None)
        monkeypatch.setattr(
            mod.shutil,
            "which",
            lambda name: "/usr/bin/dotfiles-runtime" if name == "dotfiles-runtime" else None,
        )
        monkeypatch.setattr(
            mod.subprocess,
            "Popen",
            lambda argv, **kwargs: spawned.append(list(argv)) or SimpleNamespace(),
        )
        with pytest.raises(SystemExit):
            mod.start_recording(self._args(cursor=True))
        recorder_argv = shlex.split(spawned[0][spawned[0].index("--command") + 1])
        assert recorder_argv[recorder_argv.index("-cursor") + 1] == "yes"


class TestNotificationGating:
    def test_toggle_off_suppresses_all_emission(
        self, config_env, _stub_detached_notifications
    ) -> None:
        config_env({"notifications": False})
        assert mod.notify_failed("boom") is None
        assert mod.notify_screenshot_saved(path="/tmp/a.png") is None
        assert mod.notify_recording_saved("/tmp/a.mp4", 5.0) is None
        assert _stub_detached_notifications == []

    def test_toggle_on_emits(self, config_env, _stub_detached_notifications) -> None:
        config_env({"notifications": True})
        assert mod.notify_failed("boom") is not None
        assert mod.notify_screenshot_saved(path="/tmp/a.png") is not None
        assert mod.notify_recording_saved("/tmp/a.mp4", 5.0) is not None
        assert len(_stub_detached_notifications) == 3

    def test_cmd_notify_rechecks_toggle(self, config_env, monkeypatch: pytest.MonkeyPatch) -> None:
        config_env({"notifications": False})
        called: list[list[str]] = []
        monkeypatch.setattr(
            mod, "emit_notification", lambda request, context: called.append([request["summary"]])
        )
        args = SimpleNamespace(
            kind="screenshot-saved",
            clipboard=True,
            path=None,
            duration=0.0,
            size=None,
            message="",
            error_kind=None,
            details=None,
        )
        assert mod.cmd_notify(args) is None
        assert called == []


class TestBackendReadout:
    def test_backend_name_reported(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        monkeypatch.setattr(mod, "choose_backend", lambda: "gpu-screen-recorder")
        with pytest.raises(SystemExit) as exc:
            mod.show_backend(SimpleNamespace())
        assert exc.value.code == 0
        assert json.loads(capsys.readouterr().out.strip()) == {"backend": "gpu-screen-recorder"}

    def test_backend_none_when_absent(self, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
        monkeypatch.setattr(mod, "choose_backend", lambda: None)
        with pytest.raises(SystemExit):
            mod.show_backend(SimpleNamespace())
        assert json.loads(capsys.readouterr().out.strip()) == {"backend": "none"}

    def test_backend_subcommand_is_wired(self) -> None:
        args = mod.parse_args(["backend"])
        assert args.func is mod.show_backend

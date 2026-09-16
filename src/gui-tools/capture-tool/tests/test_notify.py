"""Unit tests for the capture notification emission contract
(add-ags-notifd-notifications, design.md §2).

Mirrors test_capture_tool_cli.py: the launcher stays a dependency-free
script loaded straight from ``bin/capture-tool`` via importlib; subprocess
and the detached spawn are fakes. Coverage mirrors the design contract:
icon resolution through the AGS manifest scheme (no hardcoded paths),
concrete summary/body per outcome, actions + urgencies, the typed-error →
short-message mapping (never a traceback, cancelled emits nothing), the
dunstify --wait argv shape (timeout on normal, sticky critical), the
notify-send no-actions fallback, and ActionInvoked execution
(copy/open/reveal/details).
"""

from __future__ import annotations

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin" / "capture-tool"


def _load():
    loader = SourceFileLoader("capture_tool_notify", str(_BIN))
    spec = importlib.util.spec_from_loader("capture_tool_notify", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture()
def _no_spawn(monkeypatch: pytest.MonkeyPatch):
    """Capture detached-helper spawns instead of forking real processes."""
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        mod, "_spawn_detached", lambda argv: spawned.append(list(argv))
    )
    return spawned


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """A fake HOME/XDG tree with manifests + one rendered icon."""
    home = tmp_path / "home"
    config = home / ".config"
    icons = home / ".local" / "state" / "dotfiles" / "current" / "icons"
    (config / "ags-capture").mkdir(parents=True)
    (config / "ags").mkdir(parents=True)
    icons.mkdir(parents=True)
    (icons / "capture-tool-camera.svg").write_text("<svg/>\n")
    (icons / "capture-tool-warning.svg").write_text("<svg/>\n")
    (config / "ags-capture" / "icons.json").write_text(
        json.dumps(
            {
                "capture-tool": {
                    "variants": [
                        {"name": "camera", "output": "capture-tool-camera.svg"},
                        {"name": "warning", "output": "capture-tool-warning.svg"},
                    ]
                }
            }
        )
    )
    (config / "ags" / "icons.json").write_text(
        json.dumps({"other": {"variants": []}})
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    # os.path.expanduser caches nothing, but shutil.which results may vary;
    # tests control notifier presence explicitly via mod.which.
    return home


class TestIconResolution:
    def test_resolves_variant_through_own_manifest(self, fake_home: Path) -> None:
        path = mod.resolve_notify_icon("camera")
        assert path is not None
        assert path.endswith("current/icons/capture-tool-camera.svg")
        # No hardcoded paths: resolution stays inside the fake XDG tree.
        assert str(fake_home) in path or "state" in path

    def test_failure_variant_resolves(self, fake_home: Path) -> None:
        assert mod.resolve_notify_icon("warning") is not None

    def test_unknown_variant_yields_none(self, fake_home: Path) -> None:
        assert mod.resolve_notify_icon("nope") is None

    def test_missing_manifests_yield_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        home = tmp_path / "empty-home"
        home.mkdir()
        monkeypatch.setenv("HOME", str(home))
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.delenv("XDG_STATE_HOME", raising=False)
        assert mod.resolve_notify_icon("camera") is None

    def test_falls_back_to_bar_manifest(
        self, fake_home: Path
    ) -> None:
        config = fake_home / ".config"
        (config / "ags-capture" / "icons.json").write_text("{}")
        (config / "ags" / "icons.json").write_text(
            json.dumps(
                {
                    "capture-tool": {
                        "variants": [
                            {
                                "name": "video",
                                "output": "capture-tool-video.svg",
                            }
                        ]
                    }
                }
            )
        )
        icons = fake_home / ".local" / "state" / "dotfiles" / "current" / "icons"
        (icons / "capture-tool-video.svg").write_text("<svg/>\n")
        assert mod.resolve_notify_icon("video") is not None

    def test_missing_render_yields_none(self, fake_home: Path) -> None:
        # Manifest advertises `video` but no file was rendered.
        config = fake_home / ".config"
        (config / "ags-capture" / "icons.json").write_text(
            json.dumps(
                {
                    "capture-tool": {
                        "variants": [
                            {"name": "video", "output": "capture-tool-video.svg"}
                        ]
                    }
                }
            )
        )
        assert mod.resolve_notify_icon("video") is None


class TestFormatting:
    def test_duration_shapes_mm_ss(self) -> None:
        assert mod.format_notify_duration(42) == "00:42"
        assert mod.format_notify_duration(0) == "00:00"
        assert mod.format_notify_duration(125) == "02:05"

    def test_size_shapes_human(self) -> None:
        assert mod.format_notify_size(18.4 * 1024 * 1024) == "18.4 MB"
        assert mod.format_notify_size(512) == "512 B"
        assert mod.format_notify_size(2048) == "2 KB"
        assert mod.format_notify_size(None) is None


class TestShortMessage:
    def test_cancellation_suppresses_notification(self) -> None:
        assert mod.notify_short_message("cancelled", "whatever") is None

    def test_typed_kinds_prefer_concrete_message(self) -> None:
        assert (
            mod.notify_short_message("audio_unavailable", "no mic today")
            == "no mic today"
        )
        assert (
            mod.notify_short_message("backend_unavailable", "")
            == "No recording backend available."
        )

    def test_permission_denial_maps_to_mockup_card(self) -> None:
        short = mod.notify_short_message(None, "screencopy Permission DENIED")
        assert short == (
            "Screen capture permission denied. "
            "Check Hyprland screencopy permissions."
        )

    def test_untyped_carries_first_line_bounded(self) -> None:
        long_line = "x" * 300
        short = mod.notify_short_message(None, f"{long_line}\nsecond")
        assert short == "x" * mod.NOTIFY_MAX_BODY

    def test_empty_message_falls_back(self) -> None:
        assert mod.notify_short_message(None, "") == "Capture failed."


class TestRequestBuilders:
    def test_screenshot_request(self) -> None:
        request = mod.build_screenshot_request(path="/p/shot.png")
        assert request["app_name"] == "capture-tool"
        assert request["summary"] == "Screenshot captured"
        assert request["body"] == "/p/shot.png"
        assert request["icon_variant"] == "camera"
        assert request["actions"] == (("copy", "Copy again"), ("open", "Open"))
        assert request["urgency"] == "normal"

    def test_clipboard_screenshot_is_plain(self) -> None:
        request = mod.build_screenshot_request(clipboard=True)
        assert request["body"] == "Copied to clipboard"
        assert request["actions"] == ()
        assert request["urgency"] == "normal"

    def test_recording_request(self) -> None:
        request = mod.build_recording_request(
            "/v/rec.mp4", 42, int(18.4 * 1024 * 1024)
        )
        assert request["summary"] == "Recording saved \u00b7 00:42 \u00b7 18.4 MB"
        assert request["body"] == "/v/rec.mp4"
        assert request["icon_variant"] == "video"
        assert request["actions"] == (
            ("open", "Open"),
            ("reveal", "Show in folder"),
        )
        assert request["urgency"] == "normal"

    def test_failure_request_is_critical(self) -> None:
        request = mod.build_failure_request("boom")
        assert request["summary"] == "Capture failed"
        assert request["body"] == "boom"
        assert request["icon_variant"] == "warning"
        assert request["actions"] == (("details", "Details"),)
        assert request["urgency"] == "critical"


class TestNotifierArgv:
    def test_dunstify_argv_carries_actions_and_wait(self) -> None:
        request = mod.build_screenshot_request(path="/p/shot.png")
        argv = mod._dunstify_argv(request, icon="/i/camera.svg", wait=True)
        assert argv[0] == "dunstify"
        assert "-a" in argv and "capture-tool" in argv
        assert "-i" in argv and "/i/camera.svg" in argv
        assert "--wait" in argv
        assert argv.count("--action") == 2
        assert "copy,Copy again" in argv
        assert argv[-2:] == ["Screenshot captured", "/p/shot.png"]

    def test_normal_cards_expire_critical_stays_sticky(self) -> None:
        normal = mod._dunstify_argv(mod.build_screenshot_request(path="/p"))
        assert "--timeout" in normal
        critical = mod._dunstify_argv(mod.build_failure_request("x"))
        assert "--timeout" not in critical

    def test_notify_send_fallback_has_no_actions(self) -> None:
        request = mod.build_screenshot_request(path="/p/shot.png")
        argv = mod._notify_send_argv(request, icon="/i/camera.svg")
        assert argv[0] == "notify-send"
        assert "--action" not in argv and "--wait" not in argv


class _FakeRun:
    def __init__(self, stdout: str = "", rc: int = 0) -> None:
        self.argv: list[list[str]] = []
        self.stdout = stdout
        self.rc = rc

    def __call__(self, argv, **kwargs):
        self.argv.append(list(argv))
        from types import SimpleNamespace

        return SimpleNamespace(returncode=self.rc, stdout=self.stdout, stderr="")


class TestEmitNotification:
    def test_action_round_trip_executes(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _FakeRun(stdout="open\n")
        monkeypatch.setattr(mod, "which", lambda _name: "/usr/bin/dunstify")
        monkeypatch.setattr(mod.subprocess, "run", run)
        handled: list[tuple] = []
        monkeypatch.setattr(
            mod, "handle_notify_action", lambda *args: handled.append(args) or "open"
        )
        monkeypatch.setattr(mod, "resolve_notify_icon", lambda _v: None)
        request = mod.build_screenshot_request(path="/p/shot.png")
        assert mod.emit_notification(request, {"path": "/p/shot.png"}) == "action:open"
        assert handled and handled[0][0] == "open"

    def test_expired_close_reports_closed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # dunstify --wait prints the numeric close reason (1 = expired).
        run = _FakeRun(stdout="1\n")
        monkeypatch.setattr(mod, "which", lambda _name: "/usr/bin/dunstify")
        monkeypatch.setattr(mod.subprocess, "run", run)
        monkeypatch.setattr(mod, "resolve_notify_icon", lambda _v: None)
        request = mod.build_screenshot_request(path="/p/shot.png")
        assert mod.emit_notification(request, {"path": "/p"}) == "closed"

    def test_no_actions_takes_plain_path(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _FakeRun()
        monkeypatch.setattr(
            mod, "which", lambda name: "/usr/bin/notify-send" if name == "notify-send" else None
        )
        monkeypatch.setattr(mod.subprocess, "run", run)
        monkeypatch.setattr(mod, "resolve_notify_icon", lambda _v: None)
        request = mod.build_screenshot_request(clipboard=True)
        assert mod.emit_notification(request, {}) == "sent"
        assert run.argv and run.argv[0][0] == "notify-send"

    def test_no_notifier_reports_unsupported(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mod, "which", lambda _name: None)
        monkeypatch.setattr(mod, "resolve_notify_icon", lambda _v: None)
        request = mod.build_screenshot_request(path="/p")
        assert mod.emit_notification(request, {}) == "unsupported"

    def test_os_error_reports_failed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _boom(argv, **kwargs):
            raise OSError("no bus")

        monkeypatch.setattr(mod, "which", lambda _name: "/usr/bin/dunstify")
        monkeypatch.setattr(mod.subprocess, "run", _boom)
        monkeypatch.setattr(mod, "resolve_notify_icon", lambda _v: None)
        request = mod.build_screenshot_request(path="/p")
        assert mod.emit_notification(request, {}) == "failed"


class TestHandleAction:
    def test_copy_pipes_file_to_wl_copy(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        target = tmp_path / "shot.png"
        target.write_bytes(b"png-bytes")
        run = _FakeRun()
        monkeypatch.setattr(mod.subprocess, "run", run)
        request = mod.build_screenshot_request(path=str(target))
        assert (
            mod.handle_notify_action("copy", request, {"path": str(target)})
            == "copy"
        )
        assert run.argv[0][0] == "wl-copy"

    def test_open_and_reveal_use_xdg_open(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        target = tmp_path / "rec.mp4"
        target.write_bytes(b"mp4")
        run = _FakeRun()
        monkeypatch.setattr(mod.subprocess, "run", run)
        request = mod.build_recording_request(str(target), 1, 2)
        assert (
            mod.handle_notify_action("open", request, {"path": str(target)})
            == "open"
        )
        assert run.argv[0][:2] == ["xdg-open", str(target)]
        assert (
            mod.handle_notify_action("reveal", request, {"path": str(target)})
            == "reveal"
        )
        assert run.argv[1][:2] == ["xdg-open", str(tmp_path)]

    def test_details_reemits_full_text(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _FakeRun()
        monkeypatch.setattr(mod, "which", lambda _name: "/usr/bin/dunstify")
        monkeypatch.setattr(mod.subprocess, "run", run)
        monkeypatch.setattr(mod, "resolve_notify_icon", lambda _v: None)
        request = mod.build_failure_request("short")
        assert (
            mod.handle_notify_action(
                "details", request, {"details": "the full error text"}
            )
            == "details"
        )
        assert run.argv and run.argv[0][0] == "dunstify"
        assert "the full error text" in run.argv[0]

    def test_unknown_action_executes_nothing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run = _FakeRun()
        monkeypatch.setattr(mod.subprocess, "run", run)
        request = mod.build_screenshot_request(path="/p")
        assert mod.handle_notify_action("bogus", request, {"path": "/p"}) is None
        assert run.argv == []


class TestDetachedWiring:
    def test_screenshot_success_spawns_helper(self, _no_spawn) -> None:
        mod.notify_screenshot_saved("/p/shot.png")
        assert len(_no_spawn) == 1
        assert "notify" in _no_spawn[0] and "--kind" in _no_spawn[0]
        assert "screenshot-saved" in _no_spawn[0]

    def test_recording_success_spawns_helper(self, _no_spawn) -> None:
        mod.notify_recording_saved("/v/rec.mp4", 42, 1024)
        assert _no_spawn and "recording-saved" in _no_spawn[0]

    def test_failure_spawns_helper_with_short_text(self, _no_spawn) -> None:
        request = mod.notify_failed("no mic today", "audio_unavailable")
        assert request is not None and request["urgency"] == "critical"
        assert _no_spawn and "failed" in _no_spawn[0]

    def test_cancellation_spawns_nothing(self, _no_spawn) -> None:
        assert mod.notify_failed("cancelled", "cancelled") is None
        assert _no_spawn == []

    def test_error_channel_preserved_with_spawns(
        self, monkeypatch: pytest.MonkeyPatch, capsys, _no_spawn
    ) -> None:
        from types import SimpleNamespace

        def _boom(args):
            raise mod.AudioUnavailableError("no mic today")

        monkeypatch.setattr(
            mod, "parse_args", lambda argv=None: SimpleNamespace(func=_boom)
        )
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 1
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload["error_kind"] == "audio_unavailable"
        assert _no_spawn and "failed" in _no_spawn[0]

    def test_cmd_notify_parses_helper_argv(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[tuple] = []
        monkeypatch.setattr(
            mod, "emit_notification", lambda *args: seen.append(args) or "sent"
        )
        monkeypatch.setattr(mod, "resolve_notify_icon", lambda _v: None)
        args = mod.parse_args(
            ["notify", "--kind", "recording-saved", "--path", "/v/r.mp4",
             "--duration", "42", "--size", "1024"]
        )
        assert args.func(args) is None
        assert seen and seen[0][0]["summary"].startswith("Recording saved")

    def test_notify_help_lists_kinds(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            mod.parse_args(["notify", "--help"])
        assert exc.value.code == 0
        assert "screenshot-saved" in capsys.readouterr().out

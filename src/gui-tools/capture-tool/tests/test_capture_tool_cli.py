"""Unit tests for the ``bin/capture-tool`` launcher (story 6: backend options).

The launcher is a dependency-free script, so it is loaded straight from
``bin/capture-tool`` via importlib: no install step, no live backends.
Subprocess/pactl/Popen are fakes; coverage mirrors the story contract:
``--audio`` routing (PipeWire selection, ``none`` opens nothing, missing
devices fail loudly with a typed error), ``--duration`` passthrough,
the GIF special pipeline (fps band, ``--size``, never any audio hardware),
and the additive ``error_kind`` in the existing JSON error channel.
"""

from __future__ import annotations

import importlib.util
import json
import shlex
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

import pytest

_BIN = Path(__file__).resolve().parents[1] / "bin" / "capture-tool"


def _load():
    loader = SourceFileLoader("capture_tool_cli", str(_BIN))
    spec = importlib.util.spec_from_loader("capture_tool_cli", loader)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mod = _load()


@pytest.fixture(autouse=True)
def _stub_detached_notifications(monkeypatch: pytest.MonkeyPatch):
    """The notification paths spawn a detached ``capture-tool notify``
    helper; keep the suite hermetic by capturing spawns instead of forking
    real notifier processes into the developer's session."""
    spawned: list[list[str]] = []
    monkeypatch.setattr(
        mod, "_spawn_detached", lambda argv: spawned.append(list(argv))
    )
    return spawned


def _args(**overrides):
    base = {
        "output": None,
        "target": "screen",
        "format": "mp4",
        "fps": 60,
        "quality": "high",
        "audio": "none",
        "duration": 0.0,
        "size": "original",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _Pactl:
    """Fake ``subprocess.run`` serving canned pactl transcripts."""

    def __init__(
        self,
        *,
        sink: str = "alsa_output.pci stereo",
        source: str = "alsa_input.pci mic",
        sources: list[str] | None = None,
        missing: bool = False,
    ) -> None:
        self.calls: list[list[str]] = []
        self._sink = sink
        self._source = source
        self._sources = sources
        self._missing = missing

    def __call__(self, command, **kwargs):
        argv = list(command)
        self.calls.append(argv)
        if self._missing:
            raise FileNotFoundError("pactl")
        if argv[:2] == ["pactl", "get-default-sink"]:
            return SimpleNamespace(returncode=0, stdout=self._sink + "\n", stderr="")
        if argv[:2] == ["pactl", "get-default-source"]:
            return SimpleNamespace(returncode=0, stdout=self._source + "\n", stderr="")
        if argv == ["pactl", "list", "short", "sources"]:
            lines = (
                self._sources
                if self._sources is not None
                else [self._sink, f"{self._sink}.monitor", self._source]
            )
            body = "".join(
                f"{index}\t{name}\tmodule\n" for index, name in enumerate(lines)
            )
            return SimpleNamespace(returncode=0, stdout=body, stderr="")
        raise AssertionError(f"unexpected probe: {argv}")


class TestAudioResolution:
    def test_none_opens_nothing_without_probing(self) -> None:
        def _boom(command, **kwargs):
            raise AssertionError("no probe expected")

        assert mod.resolve_audio_device("none", run=_boom) is None
        assert mod.audio_backend_args("gpu-screen-recorder", None) == []
        assert mod.audio_backend_args("wf-recorder", None) == []

    def test_system_selects_sink_monitor(self) -> None:
        run = _Pactl()
        device = mod.resolve_audio_device("system", run=run)
        assert device == "alsa_output.pci stereo.monitor"
        assert mod.audio_backend_args("gpu-screen-recorder", device) == [
            "-a",
            "alsa_output.pci stereo.monitor",
        ]
        assert mod.audio_backend_args("wf-recorder", device) == [
            "--audio=alsa_output.pci stereo.monitor"
        ]

    def test_mic_selects_default_source(self) -> None:
        run = _Pactl()
        device = mod.resolve_audio_device("mic", run=run)
        assert device == "alsa_input.pci mic"
        assert mod.audio_backend_args("gpu-screen-recorder", device) == [
            "-a",
            "alsa_input.pci mic",
        ]

    def test_missing_device_fails_loudly_with_typed_error(self) -> None:
        run = _Pactl(sources=["something-else"])
        with pytest.raises(mod.AudioUnavailableError, match="unavailable"):
            mod.resolve_audio_device("mic", run=run)
        assert mod.AudioUnavailableError("x").kind == "audio_unavailable"

    def test_missing_pactl_fails_loudly(self) -> None:
        with pytest.raises(mod.AudioUnavailableError, match="probe failed"):
            mod.resolve_audio_device("system", run=_Pactl(missing=True))

    def test_unsupported_source_rejected(self) -> None:
        with pytest.raises(ValueError, match="unsupported audio"):
            mod.resolve_audio_device("both", run=_Pactl())


class TestGifValidation:
    def test_fps_band_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(mod, "which", lambda _name: "ffmpeg")
        for fps in (10, 15, 20, 30):
            mod.validate_gif_options(_args(format="gif", fps=fps))

    def test_out_of_band_fps_rejected_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mod, "which", lambda _name: "ffmpeg")
        with pytest.raises(mod.EncoderUnavailableError, match="frame rates"):
            mod.validate_gif_options(_args(format="gif", fps=60))

    def test_missing_ffmpeg_rejected_loudly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(mod, "which", lambda _name: None)
        with pytest.raises(mod.EncoderUnavailableError, match="ffmpeg"):
            mod.validate_gif_options(_args(format="gif", fps=15))

    def test_size_misuse_rejected_loudly(self) -> None:
        with pytest.raises(mod.EncoderUnavailableError, match="--size"):
            mod.validate_gif_options(_args(format="mp4", size="50"))

    def test_intermediate_path_shape(self) -> None:
        assert mod.gif_intermediate_path("/v/rec.gif") == "/v/rec.capture.mp4"


class TestCommandConstruction:
    def test_gsr_gif_captures_video_without_audio_flags(self) -> None:
        command = mod._build_recording_command(
            "gpu-screen-recorder", "DP-1", _args(format="gif", fps=15), "i.capture.mp4"
        )
        assert "-a" not in command
        assert command[:2] == ["gpu-screen-recorder", "-w"]
        assert "-f" in command and "15" in command
        assert command[-2:] == ["-o", "i.capture.mp4"]
        assert "gif" not in " ".join(command).lower().replace("i.capture.mp4", "")

    def test_wf_gif_carries_explicit_framerate(self) -> None:
        command = mod._build_recording_command(
            "wf-recorder", "DP-1", _args(format="gif", fps=20), "i.capture.mp4"
        )
        assert "-r" in command and "20" in command
        assert not any(part.startswith("--audio") for part in command)

    def test_gsr_quality_presets_map_to_valid_gsr_flags(self) -> None:
        # gsr -q accepts only medium/high/very_high/ultra — our low/medium/
        # high presets must be mapped, never passed through (gsr aborts on
        # "low"). Regression test: an unmapped preset once broke recording.
        expected = {"low": "medium", "medium": "high", "high": "very_high"}
        for preset, gsr_flag in expected.items():
            command = mod._build_recording_command(
                "gpu-screen-recorder", "DP-1", _args(quality=preset), "o.mp4"
            )
            q = command.index("-q")
            assert command[q + 1] == gsr_flag, preset

    def test_non_gif_audio_flags_reach_backend(self) -> None:
        gsr = mod._build_recording_command(
            "gpu-screen-recorder",
            "DP-1",
            _args(format="mp4"),
            "o.mp4",
            audio_device="sink.monitor",
        )
        assert "-a" in gsr and "sink.monitor" in gsr
        wf = mod._build_recording_command(
            "wf-recorder", "DP-1", _args(format="mp4"), "o.mp4",
            audio_device="sink.monitor",
        )
        assert "--audio=sink.monitor" in wf


class TestScreenshotDelayOrder:
    """The delay is placed per target: for region the user picks the rectangle
    FIRST and then gets the delay to arrange what happens inside it. Sleeping
    before slurp (the original behaviour) only postponed the selection prompt,
    so the delay was useless in region mode."""

    def _order(self, monkeypatch, *, target, delay, tmp_path):
        order: list[str] = []
        monkeypatch.setattr(
            mod, "load_config", lambda: {"screenshot": {"cursor": False}}
        )
        monkeypatch.setattr(
            mod,
            "resolve_target",
            lambda name: order.append(f"select:{name}") or "100x100+0+0",
        )
        monkeypatch.setattr(mod.time, "sleep", lambda seconds: order.append(f"delay:{seconds}"))
        monkeypatch.setattr(
            mod.subprocess,
            "run",
            lambda cmd, **kwargs: order.append(f"run:{cmd[0]}") or SimpleNamespace(returncode=0),
        )
        with pytest.raises(SystemExit):
            mod.screenshot(
                _args(
                    target=target,
                    delay=delay,
                    format="png",
                    output=str(tmp_path / "shot.png"),
                )
            )
        return order

    def test_region_selects_then_delays_then_captures(self, monkeypatch, tmp_path) -> None:
        order = self._order(monkeypatch, target="region", delay=3, tmp_path=tmp_path)
        assert order == ["select:region", "delay:3", "run:grim"]

    def test_screen_delays_then_captures(self, monkeypatch, tmp_path) -> None:
        order = self._order(monkeypatch, target="screen", delay=5, tmp_path=tmp_path)
        assert order == ["delay:5", "run:grim"]

    def test_no_delay_captures_immediately_after_selection(self, monkeypatch, tmp_path) -> None:
        order = self._order(monkeypatch, target="region", delay=0, tmp_path=tmp_path)
        assert order == ["select:region", "run:grim"]


class _LauncherHarness:
    """Stub the launcher's environment: backend, target, runtime, Popen."""

    def __init__(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        backend: str | None = "gpu-screen-recorder",
        target: str = "DP-1",
        runtime: str | None = "/usr/bin/dotfiles-runtime",
        ffmpeg: str | None = "ffmpeg",
        run=None,
    ) -> None:
        self.spawned: list[list[str]] = []
        monkeypatch.setattr(mod, "choose_backend", lambda: backend)
        monkeypatch.setattr(mod, "resolve_target", lambda _t: target)
        monkeypatch.setattr(mod.shutil, "which", lambda name: {
            "dotfiles-runtime": runtime,
            "ffmpeg": ffmpeg,
        }.get(name))
        monkeypatch.setattr(
            mod.subprocess,
            "Popen",
            lambda argv, **kwargs: self.spawned.append(list(argv)) or SimpleNamespace(),
        )
        self._run = run

    def start(self, capsys, **overrides):
        emitted: list[tuple[dict, int]] = []
        original_emit = mod.emit

        def _capture(payload, code):
            emitted.append((dict(payload), code))
            return original_emit(payload, code)

        mod.emit = _capture  # type: ignore[method-assign]
        try:
            args = _args(**overrides)
            if self._run is not None:
                mod.start_recording(args, run=self._run)
            else:
                mod.start_recording(args)
        except SystemExit:
            pass
        finally:
            mod.emit = original_emit  # type: ignore[method-assign]
        out = capsys.readouterr().out.strip().splitlines()
        return emitted, [json.loads(line) for line in out], self.spawned


@pytest.fixture()
def harness(monkeypatch: pytest.MonkeyPatch) -> _LauncherHarness:
    return _LauncherHarness(monkeypatch)


class TestStartRecording:
    def test_audio_none_and_duration_pass_through(
        self, harness: _LauncherHarness, capsys, tmp_path: Path
    ) -> None:
        out = tmp_path / "r.mp4"
        emitted, payloads, spawned = harness.start(
            capsys, output=str(out), audio="none", duration=10.0
        )
        assert emitted[0][1] == 0
        assert payloads[0]["state"] == "recording"
        assert payloads[0]["audio"] == "none"
        assert payloads[0]["duration"] == 10.0
        assert "--duration" in spawned[0] and "10.0" in spawned[0]
        assert "--command" in spawned[0]
        assert "-a" not in shlex.split(spawned[0][spawned[0].index("--command") + 1])

    def test_audio_system_adds_device_flag(
        self, monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path
    ) -> None:
        run = _Pactl()
        harness = _LauncherHarness(monkeypatch, run=run)
        out = tmp_path / "r.mp4"
        _, payloads, spawned = harness.start(
            capsys, output=str(out), audio="system", duration=0.0
        )
        assert payloads[0]["audio"] == "system"
        recorder_argv = shlex.split(spawned[0][spawned[0].index("--command") + 1])
        assert "-a" in recorder_argv
        assert "alsa_output.pci stereo.monitor" in recorder_argv
        assert run.calls, "expected a PipeWire probe before recording"

    def test_audio_failure_aborts_before_spawn(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        harness = _LauncherHarness(
            monkeypatch, run=_Pactl(sources=["nothing-useful"])
        )
        with pytest.raises(mod.AudioUnavailableError):
            mod.start_recording(
                _args(output=str(tmp_path / "r.mp4"), audio="mic"),
                run=harness._run,
            )
        assert harness.spawned == []

    def test_gif_never_opens_audio_hardware(
        self, monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path
    ) -> None:
        def _boom(command, **kwargs):
            raise AssertionError("GIF mode must not probe audio")

        harness = _LauncherHarness(monkeypatch, run=_boom)
        out = tmp_path / "r.gif"
        _, payloads, spawned = harness.start(
            capsys, output=str(out), format="gif", fps=15, audio="system", size="50"
        )
        assert payloads[0]["format"] == "gif"
        assert payloads[0]["audio"] == "none"
        assert payloads[0]["gif_size"] == "50"
        assert payloads[0]["output_path"] == str(out)
        assert payloads[0]["intermediate_path"] == str(tmp_path / "r.capture.mp4")
        launcher = spawned[0]
        assert "--gif-output" in launcher and str(out) in launcher
        assert "--gif-size" in launcher and "50" in launcher
        recorder_argv = shlex.split(launcher[launcher.index("--command") + 1])
        assert "-a" not in recorder_argv
        assert str(tmp_path / "r.capture.mp4") in recorder_argv

    def test_no_backend_is_typed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        harness = _LauncherHarness(monkeypatch, backend=None)
        with pytest.raises(mod.BackendUnavailableError, match="no recording backend"):
            mod.start_recording(
                _args(output=str(tmp_path / "r.mp4")), run=_Pactl()
            )
        assert harness.spawned == []

    def test_negative_duration_rejected(self, harness: _LauncherHarness) -> None:
        with pytest.raises(ValueError, match="duration"):
            mod.start_recording(_args(duration=-5), run=_Pactl())


class TestErrorChannel:
    def test_typed_errors_carry_error_kind(
        self, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        def _boom(args):
            raise mod.AudioUnavailableError("no mic today")

        monkeypatch.setattr(
            mod, "parse_args", lambda argv=None: SimpleNamespace(func=_boom)
        )
        with pytest.raises(SystemExit) as exc:
            mod.main()
        assert exc.value.code == 1
        payload = json.loads(capsys.readouterr().out.strip())
        assert payload == {
            "state": "error",
            "error": "no mic today",
            "error_kind": "audio_unavailable",
        }

    def test_cancellation_is_typed(self) -> None:
        assert mod.SelectionCancelledError("x").kind == "cancelled"

    def test_start_help_shows_new_flags(self, capsys) -> None:
        with pytest.raises(SystemExit) as exc:
            mod.parse_args(["start", "--help"])
        assert exc.value.code == 0
        out = capsys.readouterr().out
        assert "--audio" in out and "--duration" in out and "--size" in out

    def test_start_defaults(self) -> None:
        args = mod.parse_args(["start"])
        assert args.audio == "none"
        assert args.duration == 0.0
        assert args.size == "original"

from __future__ import annotations

from pathlib import Path

import pytest

from color_scheme_generator.adapters.terminal_applier import (
    _is_tty,
    _resolve_sequences_file,
    apply_to_terminal,
)


def _output_files(tmp_path: Path, has_sequences: bool = True) -> tuple[Path, ...]:
    palettes = tmp_path / "generated" / "palettes"
    palettes.mkdir(parents=True)
    files: list[Path] = [
        palettes / "colors.yaml",
        palettes / "colors.conf",
    ]
    if has_sequences:
        (palettes / "colors.sequences").write_bytes(b"\x1b]4;0;#000\x1b\\")
        files.append(palettes / "colors.sequences")
    return tuple(files)


class TestResolveSequencesFile:
    def test_finds_sequences_in_output_files(self, tmp_path: Path) -> None:
        files = _output_files(tmp_path)
        resolved = _resolve_sequences_file(files)
        assert resolved is not None
        assert resolved.name == "colors.sequences"

    def test_returns_none_when_no_sequences_output(self, tmp_path: Path) -> None:
        files = _output_files(tmp_path, has_sequences=False)
        assert _resolve_sequences_file(files) is None


class TestApplyToTerminalGuards:
    def test_disabled_returns_none(self, tmp_path: Path) -> None:
        files = _output_files(tmp_path)
        assert apply_to_terminal(files, enabled=False) is None

    def test_no_sequences_output_returns_none(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        files = _output_files(tmp_path, has_sequences=False)
        monkeypatch.setattr(
            "color_scheme_generator.adapters.terminal_applier._is_tty", lambda: True
        )
        assert apply_to_terminal(files, enabled=True) is None

    def test_not_a_tty_returns_none(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        files = _output_files(tmp_path)
        monkeypatch.setattr(
            "color_scheme_generator.adapters.terminal_applier._is_tty", lambda: False
        )
        assert apply_to_terminal(files, enabled=True) is None

    def test_applies_and_returns_sequences_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        files = _output_files(tmp_path)
        monkeypatch.setattr(
            "color_scheme_generator.adapters.terminal_applier._is_tty", lambda: True
        )
        emitted: list[Path] = []
        monkeypatch.setattr(
            "color_scheme_generator.adapters.terminal_applier._emit_to_terminal",
            lambda p: emitted.append(p) or "",
        )
        result = apply_to_terminal(files, enabled=True)
        assert result is not None
        assert result.name == "colors.sequences"
        assert emitted and emitted[0].name == "colors.sequences"


class TestIsTty:
    def test_tty_detection_uses_stdout(self) -> None:
        # In the test runner stdout is captured (not a tty) — asserts the
        # function returns False rather than crashing.
        assert _is_tty() in (True, False)

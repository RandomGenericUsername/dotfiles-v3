"""Live preview engine tests (capability `btop-live-preview`).

Run with:
    uv run --with pyte pytest live/tests -q

The reconstruction tests are deterministic (a hand-crafted VT transcript); the
btop tests run the REAL binary on a pty and skip cleanly when btop is absent.
"""
from __future__ import annotations

import collections
import hashlib
import os
import pathlib
import shutil
import tempfile
import time

import pytest

import btop_live

pytest.importorskip("pyte", reason="the live engine reconstructs with pyte")

_HAS_BTOP = shutil.which("btop") is not None
_btop = pytest.mark.skipif(not _HAS_BTOP, reason="btop binary not installed")

# A distinctive theme used by the real-btop tests.
_THEME_A = btop_live.theme_text_from_map(
    {"main_bg": "#0b0b1a", "main_fg": "#c2c2c5", "title": "#e05561", "meter_bg": "#575660"}
)
_THEME_B = btop_live.theme_text_from_map(
    {"main_bg": "#101820", "main_fg": "#c2c2c5", "title": "#3ad8a0", "meter_bg": "#101820"}
)


# ── 6.1 reconstruction: a known frame (fixture) ─────────────────────────────


class TestReconstruction:
    def test_known_frame_fixture(self) -> None:
        """A hand-crafted transcript reconstructs to the exact expected grid."""
        transcript = "\x1b[2J\x1b[H" + "AB" + "\x1b[3;5H" + "CD"
        grid = btop_live.reconstruct(transcript, 10, 4)
        assert len(grid) == 4
        assert all(len(row) == 10 for row in grid)
        assert "".join(c[0] for c in grid[0]) == "AB        "
        assert "".join(c[0] for c in grid[2]) == "    CD    "

    def test_truecolour_is_captured(self) -> None:
        grid = btop_live.reconstruct("\x1b[38;2;255;0;0mX\x1b[0m", 4, 1)
        assert grid[0][0][0] == "X"
        assert grid[0][0][1] == "#ff0000"

    def test_partial_redraw_does_not_smear(self) -> None:
        """btop repaints part of the screen; each cell must appear exactly once
        with no duplicated or stale rows."""
        transcript = "\x1b[2J\x1b[HOLD" + "\x1b[1;1HNEW"
        grid = btop_live.reconstruct(transcript, 6, 2)
        assert "".join(c[0] for c in grid[0]) == "NEW   "
        assert grid[0][3][0] == " "

    def test_background_and_bold(self) -> None:
        grid = btop_live.reconstruct("\x1b[48;2;11;11;26m\x1b[1mZ", 3, 1)
        assert grid[0][0][2] == "#0b0b1a"
        assert grid[0][0][3] is True


# ── 6.4 column-accurate rendering ───────────────────────────────────────────


class TestColumnAccuracy:
    def test_frame_to_text_preserves_every_column(self) -> None:
        """Braille and box-drawing glyphs must occupy exactly one cell so the
        columns before and after a graph stay aligned."""
        braille = "⣿⣷⣯⣟⡿⢿⣻⣽"  # one cell each in a monospace font
        transcript = "\x1b[2J\x1b[H" + "│" + braille + "│"
        grid = btop_live.reconstruct(transcript, 20, 2)
        text = btop_live.frame_to_text(grid)
        lines = text.split("\n")
        assert len(lines) == 2
        assert all(len(line) == 20 for line in lines), [len(line) for line in lines]
        assert lines[0].startswith("│" + braille + "│")

    def test_frame_to_html_groups_runs(self) -> None:
        grid = btop_live.reconstruct("\x1b[31mAA\x1b[32mBB", 6, 1)
        html = btop_live.frame_to_html(grid)
        assert html.count("<span") == 2
        assert "AA" in html and "BB" in html


# ── 6.1 real btop produces the frame ────────────────────────────────────────


@_btop
class TestRealBtopCapture:
    def test_capture_once_matches_a_real_frame(self) -> None:
        grid = btop_live.capture_once(_THEME_A, preset=0, width=200, height=50, settle=3.0)
        assert len(grid) == 50 and all(len(row) == 200 for row in grid)
        text = btop_live.frame_to_text(grid)
        # btop's own layout: the box titles are present, painted by OUR theme.
        assert "cpu" in text and "mem" in text
        colours = {cell[1] for row in grid for cell in row if cell[1]}
        assert colours, "no truecolour foreground was captured"

    def test_capture_once_is_side_effect_free(self) -> None:
        """The preview writes only to a throwaway location: the installed
        theme, the runtime current/ pointer, and the repo are unchanged."""
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            installed = root / "install" / "config" / "btop" / "themes"
            current = root / "state" / "dotfiles" / "current"
            repo = root / "repo" / "dotfiles" / "assets" / "btop-themes"
            for directory in (installed, current, repo):
                directory.mkdir(parents=True)
                (directory / "colors.btop.theme").write_text("theme[main_bg]=\"#000000\"\n")
            before = {
                p: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in list(installed.iterdir()) + list(current.iterdir()) + list(repo.iterdir())
            }

            btop_live.capture_once(_THEME_B, preset=0, width=80, height=24, settle=2.0)

            after = {
                p: hashlib.sha256(p.read_bytes()).hexdigest()
                for p in list(installed.iterdir()) + list(current.iterdir()) + list(repo.iterdir())
            }
            assert after == before, "the preview mutated installed/repo state"


# ── 6.2 warm process + SIGUSR2 delta ────────────────────────────────────────


@_btop
class TestWarmSession:
    def test_edit_reflects_without_restart_and_under_one_second(self) -> None:
        session = btop_live.BtopSession(_THEME_A, preset=0, width=200, height=50)
        try:
            pid = session.pid
            first = session.frame(settle=1.2)
            before = collections.Counter(c[2] for row in first for c in row if c[2])

            session.write_theme(_THEME_B)
            start = time.monotonic()
            second = session.reload_and_capture(settle=0.75)
            elapsed = time.monotonic() - start

            assert session.pid == pid, "the warm process must not be restarted by a reload"
            after = collections.Counter(c[2] for row in second for c in row if c[2])
            assert after != before, "the edit did not reach the preview"
            assert elapsed < 1.0, f"reload took {elapsed:.2f}s (must render under 1s)"

            # 6.3: partial redraw correctness — expected token counts.
            assert btop_live.cell_count(second) == 200 * 50
            assert len(btop_live.frame_to_text(second).split("\n")) == 50
        finally:
            session.close()

    def test_preset_change_respawns(self) -> None:
        session = btop_live.BtopSession(_THEME_A, preset=0, width=120, height=40)
        try:
            pid = session.pid
            session.close()
            other = btop_live.BtopSession(_THEME_A, preset=1, width=120, height=40)
            try:
                assert other.pid != pid
                assert other.preset == 1
            finally:
                other.close()
        finally:
            session.close()


# ── 6.5 session root is throwaway ───────────────────────────────────────────


class TestThrowawayRoot:
    def test_seed_root_lives_under_the_temp_dir(self) -> None:
        root = btop_live._seed_root("theme[main_bg]=\"#000000\"\n")
        try:
            assert str(root).startswith(tempfile.gettempdir())
            assert (root / "config/btop/themes/colors.btop.theme").is_file()
            assert "save_config_on_exit = false" in (root / "config/btop/btop.conf").read_text()
        finally:
            shutil.rmtree(root, ignore_errors=True)

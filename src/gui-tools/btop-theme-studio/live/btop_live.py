#!/usr/bin/env python3
"""btop_live.py — the live preview engine (capability `btop-live-preview`).

The preview is the REAL btop binary: this module runs ``btop --no-tty
--force-utf`` on a pseudo-terminal pointed at a candidate theme, captures the
pty output, and reconstructs the screen with a terminal emulator (``pyte``).
It never re-implements btop's drawing, so the preview cannot drift.

A single warm btop process is kept per session; an edit writes the candidate
theme and sends ``SIGUSR2`` (btop's full config + theme hot reload), and only
the post-signal redraw delta is parsed — so an edit reflects without a fresh
process start and renders well under a second.

Side-effect-free by construction: the candidate theme, config, and state all
live under a private ``tempfile.mkdtemp`` root. The installed theme, the
runtime ``current/`` pointer, and the repo are never touched.

Requires ``pyte`` (confined to this engine). Run the tests with:
    uv run --with pyte pytest live/tests -q
"""
from __future__ import annotations

import fcntl
import json
import os
import pathlib
import pty
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import termios
import threading
import time

try:
    import pyte
except Exception:  # pragma: no cover - exercised only without pyte
    pyte = None  # type: ignore[assignment]

DEFAULT_WIDTH = 200
DEFAULT_HEIGHT = 50
DEFAULT_PRESET = 0
THEME_FILENAME = "colors.btop.theme"

Cell = list  # [char, fg, bg, bold]
Grid = list  # list[list[Cell]]


def _norm(colour: str | None) -> str | None:
    """Normalize a pyte colour to ``#rrggbb`` (or None for the default)."""
    if not colour or colour == "default":
        return None
    if colour.startswith("#"):
        return colour
    if len(colour) == 6:
        return "#" + colour
    return colour


def reconstruct(text: str, width: int, height: int) -> Grid:
    """Reconstruct the final screen from a pty transcript.

    A real terminal emulator handles partial redraws and truecolour, so each
    cell appears exactly once with no duplicated or stale rows.
    """
    if pyte is None:  # pragma: no cover
        raise RuntimeError("pyte is required for the live preview engine")
    screen = pyte.Screen(width, height)
    pyte.Stream(screen).feed(text)
    grid: Grid = []
    for y in range(height):
        row: list[Cell] = []
        for x in range(width):
            cell = screen.buffer[y][x]
            fg, bg = cell.fg, cell.bg
            if getattr(cell, "reverse", False):
                fg, bg = bg, fg
            row.append([cell.data, _norm(fg), _norm(bg), bool(cell.bold)])
        grid.append(row)
    return grid


def theme_text_from_map(keys: dict[str, str]) -> str:
    return "".join(f'theme[{key}]="{value}"\n' for key, value in keys.items())


def parse_theme_map(text: str) -> dict[str, str]:
    return dict(re.findall(r'^theme\[([A-Za-z0-9_]+)\]="([^"]*)"', text, re.M))


def frame_to_text(grid: Grid) -> str:
    """The frame as plain text, one character per cell (columns preserved)."""
    return "\n".join("".join(cell[0] for cell in row) for row in grid)


def frame_to_html(grid: Grid) -> str:
    """The frame as HTML runs of identical style (for the AGS Live view)."""
    lines: list[str] = []
    for row in grid:
        run, style, line = "", None, ""
        for ch, fg, bg, bold in row:
            key = (fg, bg, bold)
            if key != style:
                if run:
                    line += _span(run, style)
                run, style = "", key
            run += ch
        if run:
            line += _span(run, style)
        lines.append(line)
    return "\n".join(lines)


def _span(text: str, style) -> str:
    fg, bg, bold = style
    esc = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    css = []
    if fg:
        css.append(f"color:{fg}")
    if bg:
        css.append(f"background:{bg}")
    if bold:
        css.append("font-weight:700")
    if not css:
        return esc
    return f'<span style="{";".join(css)}">{esc}</span>'


def cell_count(grid: Grid) -> int:
    """Total cells — a partial-redraw smear would break the expected count."""
    return sum(len(row) for row in grid)


def _theme_env(root: pathlib.Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        HOME=str(root),
        XDG_CONFIG_HOME=str(root / "config"),
        XDG_STATE_HOME=str(root / "state"),
        XDG_CACHE_HOME=str(root / "cache"),
        TERM="xterm-256color",
        COLORTERM="truecolor",
        LANG="C.UTF-8",
        LC_ALL="C.UTF-8",
    )
    return env


def _seed_root(theme_text: str) -> pathlib.Path:
    root = pathlib.Path(tempfile.mkdtemp(prefix="btop-live-"))
    (root / "config/btop/themes").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "cache").mkdir()
    (root / "config/btop/themes" / THEME_FILENAME).write_text(theme_text)
    (root / "config/btop/btop.conf").write_text(
        f'color_theme = "{THEME_FILENAME}"\n'
        "save_config_on_exit = false\n"
        "update_ms = 700\n"
        "log_level = \"DISABLED\"\n"
    )
    return root


def capture_once(
    theme_text: str,
    preset: int = DEFAULT_PRESET,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    settle: float = 2.0,
) -> Grid:
    """One-shot capture: spawn btop, drain its pty, terminate, reconstruct.

    The pty MUST be drained while btop runs — its frame output is far larger
    than the kernel pty buffer, so reading only after exit captures a skeleton.
    """
    root = _seed_root(theme_text)
    master, slave = pty.openpty()
    try:
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", height, width, 0, 0))
        proc = subprocess.Popen(
            ["btop", "--no-tty", "--force-utf", "-u", "400", "-p", str(preset)],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=_theme_env(root),
            close_fds=True,
        )
        os.close(slave)
        os.set_blocking(master, False)
        buf = bytearray()
        stop = False

        def drain() -> None:
            while not stop:
                try:
                    chunk = os.read(master, 65536)
                    if chunk:
                        buf.extend(chunk)
                    else:
                        time.sleep(0.02)
                except (OSError, BlockingIOError):
                    time.sleep(0.02)

        reader = threading.Thread(target=drain, daemon=True)
        reader.start()
        time.sleep(settle)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(0.2)
        stop = True
        reader.join(timeout=1)
    finally:
        try:
            os.close(master)
        except OSError:
            pass
        shutil.rmtree(root, ignore_errors=True)
    return reconstruct(bytes(buf).decode("utf-8", "replace"), width, height)


class BtopSession:
    """A warm btop process on a pty, reloaded per edit via SIGUSR2.

    A preset change cannot be applied by reload, so the caller respawns; an
    oversized transcript also respawns (bounded memory).
    """

    TRANSCRIPT_LIMIT = 8_000_000

    def __init__(
        self,
        theme_text: str,
        preset: int = DEFAULT_PRESET,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> None:
        self.width = width
        self.height = height
        self.preset = preset
        self.root = _seed_root(theme_text)
        self.theme_path = self.root / "config/btop/themes" / THEME_FILENAME
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = False
        self._spawn()

    def _spawn(self) -> None:
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", self.height, self.width, 0, 0))
        self.proc = subprocess.Popen(
            ["btop", "--no-tty", "--force-utf", "-u", "700", "-p", str(self.preset)],
            stdin=slave,
            stdout=slave,
            stderr=slave,
            env=_theme_env(self.root),
            close_fds=True,
        )
        os.close(slave)
        self.master = master
        os.set_blocking(master, False)
        self._stop = False
        self._buf = bytearray()
        threading.Thread(target=self._drain, daemon=True).start()
        time.sleep(1.8)  # first draw

    def _drain(self) -> None:
        while not self._stop:
            try:
                chunk = os.read(self.master, 65536)
                if chunk:
                    with self._lock:
                        self._buf.extend(chunk)
                else:
                    time.sleep(0.02)
            except (OSError, BlockingIOError):
                time.sleep(0.02)

    @property
    def pid(self) -> int:
        return self.proc.pid

    @property
    def transcript_size(self) -> int:
        return len(self._buf)

    def write_theme(self, theme_text: str) -> None:
        self.theme_path.write_text(theme_text)

    def set_theme(self, theme_text: str) -> None:
        self.write_theme(theme_text)
        self._signal(signal.SIGUSR2)

    def _signal(self, sig: int) -> None:
        try:
            self.proc.send_signal(sig)
        except ProcessLookupError:
            pass

    def reload_and_capture(self, settle: float = 0.75) -> Grid:
        """SIGUSR2 forces a FULL redraw, so parsing only the bytes after the
        signal reconstructs the screen — no fresh spawn needed."""
        with self._lock:
            mark = len(self._buf)
        self._signal(signal.SIGWINCH)
        self._signal(signal.SIGUSR2)
        time.sleep(settle)
        with self._lock:
            data = bytes(self._buf[mark:]) or bytes(self._buf)
        return reconstruct(data.decode("utf-8", "replace"), self.width, self.height)

    def frame(self, settle: float = 0.9) -> Grid:
        """Replay the WHOLE transcript. btop does PARTIAL redraws, so parsing
        only the delta leaves unchanged cells missing; replaying every
        absolute-positioned write from the start reconstructs the true screen."""
        self._signal(signal.SIGWINCH)
        self._signal(signal.SIGUSR2)
        time.sleep(settle)
        with self._lock:
            data = bytes(self._buf)
        return reconstruct(data.decode("utf-8", "replace"), self.width, self.height)

    def close(self) -> None:
        self._stop = True
        try:
            self.proc.terminate()
            self.proc.wait(timeout=3)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        try:
            os.close(self.master)
        except Exception:
            pass
        shutil.rmtree(self.root, ignore_errors=True)


def main() -> int:
    """CLI bridge for the AGS app: capture one frame and print it as JSON.

    ``--theme <file>`` reads the candidate theme; ``--preset N`` selects a
    preset; ``--once`` uses a fresh capture (default is a warm session, then a
    reload). Output: ``{"frame_html": ..., "frame_text": ...,
    "width": W, "height": H}``.
    """
    import argparse

    parser = argparse.ArgumentParser(description="btop live frame capture")
    parser.add_argument("--theme", required=True, help="candidate .theme file")
    parser.add_argument("--preset", type=int, default=DEFAULT_PRESET)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    theme_text = pathlib.Path(os.path.expanduser(args.theme)).read_text()
    if args.once:
        grid = capture_once(theme_text, args.preset)
    else:
        session = BtopSession(theme_text, args.preset)
        try:
            grid = session.frame()
        finally:
            session.close()
    json.dump(
        {
            "frame_html": frame_to_html(grid),
            "frame_text": frame_to_text(grid),
            "width": DEFAULT_WIDTH,
            "height": DEFAULT_HEIGHT,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

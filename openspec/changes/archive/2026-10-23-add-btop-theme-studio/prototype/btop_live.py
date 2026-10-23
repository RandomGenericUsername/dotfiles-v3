#!/usr/bin/env python3
"""btop_live.py — a LIVE btop preview engine.

Owns a persistent btop process on a pty, pointed at a candidate theme file.
On every edit the caller pushes the new .theme; we SIGUSR2 btop (it hot-reloads
its theme + forces a full redraw), re-capture the frame, and parse it into a
screen we can render. This is the "single live pane" the studio needs -- one
place, real btop, updating as you edit.
"""
from __future__ import annotations

import fcntl
import importlib.util
import os
import pathlib
import pty
import shutil
import signal
import struct
import subprocess
import tempfile
import termios
import threading
import time

HERE = pathlib.Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("cap", HERE / "capture_btop.py")
cap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cap)

try:  # a real terminal emulator beats a hand-rolled VT parser
    import pyte
    _HAVE_PYTE = True
except Exception:  # pragma: no cover
    _HAVE_PYTE = False


def _norm(c):
    if not c or c == "default":
        return None
    return c if c.startswith("#") else (("#" + c) if len(c) == 6 else c)


def pyte_grid(text: str, w: int, h: int) -> list[list[list]]:
    """Reconstruct the screen with a real terminal emulator (correct partial
    redraws, no ghost rows). Returns [char, fg, bg, bold] cells."""
    screen = pyte.Screen(w, h)
    pyte.Stream(screen).feed(text)
    grid = []
    for y in range(h):
        row = []
        for x in range(w):
            c = screen.buffer[y][x]
            fg, bg = c.fg, c.bg
            if getattr(c, "reverse", False):
                fg, bg = bg, fg
            row.append([c.data, _norm(fg), _norm(bg), bool(c.bold)])
        grid.append(row)
    return grid

W, H, PRESET = 200, 50, 0


class BtopSession:
    def __init__(self, theme_text: str, preset: int = 0, w: int = W, h: int = H) -> None:
        self.w, self.h, self.preset = w, h, preset
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="btop-live-"))
        (self.root / "config/btop/themes").mkdir(parents=True)
        (self.root / "state").mkdir()
        (self.root / "cache").mkdir()
        self.theme_path = self.root / "config/btop/themes/colors.btop.theme"
        self.theme_path.write_text(theme_text)
        (self.root / "config/btop/btop.conf").write_text(
            'color_theme = "colors.btop.theme"\n' "save_config_on_exit = false\n" "update_ms = 700\n")
        self.env = dict(
            os.environ, HOME=str(self.root), XDG_CONFIG_HOME=str(self.root / "config"),
            XDG_STATE_HOME=str(self.root / "state"), XDG_CACHE_HOME=str(self.root / "cache"),
            TERM="xterm-256color", COLORTERM="truecolor", LANG="C.UTF-8", LC_ALL="C.UTF-8")
        self._buf = bytearray()
        self._lock = threading.Lock()
        self._stop = False
        self._spawn()

    def _spawn(self) -> None:
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", self.h, self.w, 0, 0))
        self.proc = subprocess.Popen(
            ["btop", "--no-tty", "--force-utf", "-u", "700", "-p", str(self.preset)],
            stdin=slave, stdout=slave, stderr=slave, env=self.env, close_fds=True)
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

    def set_theme(self, theme_text: str) -> None:
        self.theme_path.write_text(theme_text)
        try:
            self.proc.send_signal(signal.SIGUSR2)  # btop re-scans themes + full redraw
        except ProcessLookupError:
            pass

    def write_theme(self, theme_text: str) -> None:
        self.theme_path.write_text(theme_text)

    def reload_and_capture(self, settle: float = 0.75) -> list[list[list]]:
        """SIGUSR2 forces a FULL redraw, so parsing only the bytes AFTER the
        signal reconstructs the screen correctly -- no fresh spawn needed."""
        with self._lock:
            mark = len(self._buf)
        try:
            self.proc.send_signal(signal.SIGWINCH)
            self.proc.send_signal(signal.SIGUSR2)
        except ProcessLookupError:
            pass
        time.sleep(settle)
        with self._lock:
            data = bytes(self._buf[mark:]) or bytes(self._buf)
        text = data.decode("utf-8", "replace")
        if _HAVE_PYTE:
            return pyte_grid(text, self.w, self.h)
        return cap.parse(text, self.w, self.h)

    def frame(self, settle: float = 0.9) -> list[list[list]]:
        try:
            self.proc.send_signal(signal.SIGWINCH)
            self.proc.send_signal(signal.SIGUSR2)
        except ProcessLookupError:
            pass
        time.sleep(settle)
        # Replay the WHOLE transcript, not the delta: btop does PARTIAL redraws,
        # so parsing only bytes since the last capture leaves unchanged cells
        # missing and stacks new ones ("phased" duplicate rows). Replaying every
        # absolute-positioned write from the start reconstructs the true screen.
        with self._lock:
            data = bytes(self._buf)
        text = data.decode("utf-8", "replace")
        if _HAVE_PYTE:
            return pyte_grid(text, self.w, self.h)
        return cap.parse(text, self.w, self.h)

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


def theme_text_from_map(keys: dict) -> str:
    return "".join(f'theme[{k}]="{v}"\n' for k, v in keys.items())


def parse_theme_map(text: str) -> dict:
    import re
    return dict(re.findall(r'^theme\[([A-Za-z0-9_]+)\]="([^"]*)"', text, re.M))


if __name__ == "__main__":
    # smoke: load current theme, capture; fix meter_bg, capture; prove the frame changed
    import collections
    tp = pathlib.Path.home() / ".local/state/dotfiles/current/colors.btop.theme"
    text = tp.read_text()
    s = BtopSession(text, 0)
    f1 = s.frame()
    keys = parse_theme_map(text)
    keys["meter_bg"] = keys.get("main_bg", "#0b0b1a")
    s.set_theme(theme_text_from_map(keys))
    f2 = s.frame()
    c1 = collections.Counter(c[2] for row in f1 for c in row if c[2])
    c2 = collections.Counter(c[2] for row in f2 for c in row if c[2])
    print("top bg colors BEFORE:", c1.most_common(3))
    print("top bg colors AFTER :", c2.most_common(3))
    print("frames differ:", f1 != f2)
    s.close()

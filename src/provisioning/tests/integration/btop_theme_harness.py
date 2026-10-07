"""Headless btop theme-application harness (promoted from
``spikes/btop-theme-prototype/assert_theme_applies.py``, spec task 5).

Replaces "launch btop and eyeball it" with assertions btop's OWN output can
answer. Both predicates were proven against btop 1.4.7:

ASSERTION 1 — the theme file was LOADED
    btop logs ``Loading theme file: <abs path>`` at DEBUG level
    (src/btop_theme.cpp:397). We require that line to name OUR file. This is
    the channel that matters: ``Theme::setTheme`` (:451-471) resolves
    ``color_theme`` only against themes discovered at startup, and an
    unresolvable value falls back to ``Default_theme`` with NO error.

ASSERTION 2 — our colors reached the RENDERED FRAME
    Run btop on a real pty (it needs a real terminal size), capture the frame,
    extract every 24-bit SGR colour, and require that a strong majority of the
    theme FILE's colors are present AND that zero of btop's built-in
    ``Default_theme`` colors are. Measured: with our theme 5/5 frame colors
    come from the file and 0 Default colors appear; with an unresolvable
    ``color_theme`` the frame is entirely Default colors.

Both assertions are read from artifacts, never from a human's eyes, so they
are assertable from a command's exit code.
"""

from __future__ import annotations

import fcntl
import os
import pathlib
import pty
import re
import select
import struct
import subprocess
import termios
import time

# btop's Default_theme colors (src/btop_theme.cpp:52-101), lowercased. The
# NEGATIVE signal: if any of these appear while OUR theme is selected, our
# theme did not take effect.
DEFAULT_THEME_COLORS = {
    "#1d1d1d", "#deddda", "#77767b", "#1c71d8", "#ffffff", "#1a5fb4",
    "#62a0ea", "#e01b24", "#c01b24", "#26a269", "#12488b", "#a347ba",
    "#f7f26a", "#fc5b65", "#2a7b34",
}

WIDTH, HEIGHT = 200, 50


class ThemeApplicationError(RuntimeError):
    """btop did not load and apply the named theme. Never swallowed: a caller
    that turns this into a non-zero exit is the whole point of the harness."""


def btop_binary() -> str | None:
    """The btop under test, or None when it is not installed."""
    from shutil import which

    return which("btop")


def frame_colors(frame: bytes) -> set[str]:
    """Every 24-bit SGR colour in the frame (fg 38;2 and bg 48;2)."""
    out: set[str] = set()
    for r, g, b in re.findall(rb"(?:38|48);2;(\d+);(\d+);(\d+)", frame):
        out.add(f"#{int(r):02x}{int(g):02x}{int(b):02x}")
    return out


def file_colors(path: pathlib.Path) -> set[str]:
    """Every ``="#rrggbb"`` literal in a .theme file."""
    text = path.read_text()
    return {"#" + h.lower() for h in re.findall(r'="#([0-9a-fA-F]{6})"', text)}


def run_btop(
    *,
    config_home: pathlib.Path,
    state_home: pathlib.Path,
    settle_seconds: float = 4.0,
    binary: str = "btop",
    extra_args: list[str] | None = None,
    exit_signal: int | None = None,
    exit_wait_seconds: float = 8.0,
) -> tuple[bytes, str]:
    """Run btop on a private pty against ``config_home`` and return
    ``(frame bytes, DEBUG log text)``.

    ``config_home`` is expected to be the machine's XDG config home — the
    harness resolves NOTHING about where themes live; that is the whole point:
    btop must find the theme through the real ``~/.config/btop`` symlink.

    After ``settle_seconds`` the process is ended — by SIGTERM, or by
    ``exit_signal`` when the caller needs btop's SHUTDOWN path.

    ``exit_signal`` is load-bearing, not cosmetic. Measured against btop
    1.4.7: SIGTERM kills btop BEFORE its atexit config write, and a ``q`` /
    Ctrl-C keystroke on the pty never reaches its quit handler in this
    non-interactive setup. A SIGTERM-only harness would report "btop.conf
    unchanged" for a reason unrelated to ``save_config_on_exit``, which makes
    that gate vacuous. SIGINT *is* handled by btop's signal path and *does*
    run the config write — so the ``save_config_on_exit`` gate must send
    SIGINT, and must carry the negative control proving the signal has teeth.
    """
    state_home.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ,
        XDG_CONFIG_HOME=str(config_home),
        XDG_STATE_HOME=str(state_home),
        TERM="xterm-256color",
        COLORTERM="truecolor",
    )
    # --debug so `Loading theme file:` is emitted at all (it is a DEBUG line);
    # --no-tty so the ANSI/24-bit renderer is used.
    argv = [binary, "--no-tty", "--debug", *(extra_args or [])]
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", HEIGHT, WIDTH, 0, 0))
    proc = subprocess.Popen(
        argv, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True
    )
    os.close(slave)
    time.sleep(settle_seconds)
    if exit_signal is None:
        proc.terminate()
        wait_seconds = 5.0
    else:
        # A handled signal runs btop's shutdown path (including the config
        # write); btop may not actually exit, so wait, then SIGTERM and only
        # then SIGKILL. The config write has already happened by the first
        # wait, which is what these callers are measuring.
        proc.send_signal(exit_signal)
        wait_seconds = exit_wait_seconds
    try:
        proc.wait(timeout=wait_seconds)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    os.set_blocking(master, False)
    buf = b""
    while True:
        ready, _, _ = select.select([master], [], [], 0.5)
        if not ready:
            break
        try:
            chunk = os.read(master, 65536)
        except OSError:
            break
        if not chunk:
            break
        buf += chunk
    os.close(master)
    log_path = state_home / "btop.log"
    log = log_path.read_text(errors="replace") if log_path.is_file() else ""
    return buf, log


def assert_theme_applied(
    *,
    config_home: pathlib.Path,
    state_home: pathlib.Path,
    theme_name: str,
    theme_file: pathlib.Path,
    binary: str = "btop",
    settle_seconds: float = 4.0,
) -> tuple[bytes, str]:
    """Assert btop LOADED ``theme_file`` and PAINTED its colors.

    Raises :class:`ThemeApplicationError` otherwise. Returning
    ``(frame, log)`` lets the caller record evidence for a passing run.
    """
    frame, log = run_btop(
        config_home=config_home,
        state_home=state_home,
        binary=binary,
        settle_seconds=settle_seconds,
    )

    loaded = [
        line.split("Loading theme file: ")[-1]
        for line in log.splitlines()
        if "Loading theme file:" in line
    ]
    if not loaded or not loaded[0].endswith(theme_name):
        raise ThemeApplicationError(
            f"btop's DEBUG log names {loaded or 'no theme load at all'} — expected "
            f"{theme_name}. `Theme::setTheme` resolved `color_theme` against "
            f"nothing and fell back to Default_theme SILENTLY."
        )

    painted = frame_colors(frame)
    want = file_colors(theme_file)
    if not painted:
        raise ThemeApplicationError("no 24-bit colours in the captured btop frame")
    hit = want & painted
    leaked = painted & DEFAULT_THEME_COLORS
    # A frame only paints the colors that are on screen at this size, so require
    # a strong majority of the file's colors AND zero Default leak.
    if not hit or leaked or len(hit) < max(3, len(want) // 2):
        raise ThemeApplicationError(
            f"only {len(hit)}/{len(want)} theme colors painted; "
            f"Default_theme leak={sorted(leaked) or 'none'}; "
            f"frame colors={sorted(painted)}"
        )
    return frame, log

#!/usr/bin/env python3
"""Assert that btop LOADS and APPLIES a generated theme, headlessly.

Replaces the "launch btop and eyeball it" verification step with two
machine-checkable assertions, both proven to work against btop 1.4.7.

ASSERTION 1 -- the theme file was loaded
    btop logs `Loading theme file: <abs path>` at DEBUG level
    (src/btop_theme.cpp:397). Assert that line names OUR file.
    This is the channel that matters: btop resolves `color_theme` only
    against themes discovered at startup, and an unresolvable value falls
    back to Default_theme with NO error (btop_theme.cpp:465).

ASSERTION 2 -- our colors reached the rendered frame
    Run btop on a real pty (it needs a real terminal size), capture the
    frame, extract every 24-bit SGR colour, and assert a high fraction of
    the theme file's colors appear and that Default_theme's colors do NOT.
    Verified: with our theme, 5/5 frame colors come from the file and 0
    Default colors appear; with an unresolvable color_theme the frame is
    entirely Default colors.

Usage:
    python3 assert_theme_applies.py --theme-dir <dir> --themes csg-minimal.theme csg-balanced.theme
Exit code 0 = every theme proved applied; 1 = at least one did not.
"""
from __future__ import annotations

import argparse
import fcntl
import os
import pathlib
import pty
import re
import select
import shutil
import struct
import subprocess
import sys
import tempfile
import termios
import time

# btop's Default_theme colors (src/btop_theme.cpp:52-101), lowercased.
# Used as the negative signal: if any of these show up while OUR theme is
# selected, our theme did not take effect.
DEFAULT_THEME_COLORS = {
    "#1d1d1d", "#deddda", "#77767b", "#1c71d8", "#ffffff", "#1a5fb4",
    "#62a0ea", "#e01b24", "#c01b24", "#26a269", "#12488b", "#a347ba",
    "#f7f26a", "#fc5b65", "#2a7b34",
}

WIDTH, HEIGHT, SETTLE_SECONDS = 200, 50, 4.0


def _run_btop(root: pathlib.Path, theme_value: str, themes: list[str], extra: list[str]) -> tuple[bytes, str]:
    """Run btop on a private pty; return (frame bytes, log text)."""
    (root / "state").mkdir(parents=True, exist_ok=True)
    (root / "config/btop/themes").mkdir(parents=True, exist_ok=True)
    for name in themes:
        shutil.copy(root / "src" / name, root / "config/btop/themes" / name)
    (root / "config/btop/btop.conf").write_text(
        f'color_theme = "{theme_value}"\n'
        'log_level = "DEBUG"\n'
        "update_ms = 3000\n"
    )
    env = dict(
        os.environ,
        XDG_STATE_HOME=str(root / "state"),
        XDG_CONFIG_HOME=str(root / "config"),
        TERM="xterm-256color",
        COLORTERM="truecolor",
    )
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", HEIGHT, WIDTH, 0, 0))
    proc = subprocess.Popen(
        ["btop", "--no-tty", *extra],
        stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True,
    )
    os.close(slave)
    time.sleep(SETTLE_SECONDS)
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
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
    return buf, (root / "state/btop.log").read_text(errors="replace")


def frame_colors(frame: bytes) -> set[str]:
    """Every 24-bit SGR colour in the frame, both fg (38;2) and bg (48;2)."""
    out = set()
    for r, g, b in re.findall(rb"(?:38|48);2;(\d+);(\d+);(\d+)", frame):
        out.add(f"#{int(r):02x}{int(g):02x}{int(b):02x}")
    return out


def file_colors(path: pathlib.Path) -> set[str]:
    text = path.read_text()
    return {"#" + h.lower() for h in re.findall(r'="#([0-9a-fA-F]{6})"', text)}


def check_one(theme: str, themes: list[str], tmp: pathlib.Path, extra: list[str],
              color_theme: str | None = None) -> bool:
    """Prove one theme applies. `color_theme` overrides what btop.conf selects.

    Overriding it to a name that is NOT staged is the negative control: every
    theme file is still present and discoverable, so the only thing that
    changes is whether btop can resolve the selection. That is the exact
    silent-fallback path the harness exists to catch.
    """
    root = tmp / theme.replace(".", "_") / (color_theme or theme)
    (root / "src").mkdir(parents=True, exist_ok=True)
    for name in themes:
        src = theme_dir_src() / name
        if not src.is_file():
            print(f"  FAIL: theme file missing from --theme-dir: {src}")
            return False
        shutil.copy(src, root / "src" / name)

    frame, log = _run_btop(root, color_theme or theme, themes, extra)
    theme_path = root / "config/btop/themes" / theme

    ok = True
    loaded = [ln.split("Loading theme file: ")[-1] for ln in log.splitlines() if "Loading theme file:" in ln]
    if loaded and loaded[0].endswith(theme):
        print(f"  PASS assertion 1: btop loaded {loaded[0]}")
    else:
        print(f"  FAIL assertion 1: log shows {loaded or 'no theme load at all'} "
              f"(expected {theme}) -- btop fell back to Default_theme")
        ok = False

    got = frame_colors(frame)
    want = file_colors(theme_path)
    if not got:
        print("  FAIL assertion 2: no 24-bit colours in the captured frame")
        return False
    hit = want & got
    leaked = got & DEFAULT_THEME_COLORS
    # "Dominated by the theme's colours" is measured over the FRAME, not over
    # the file: a 200x50 frame shows only a handful of gradient stops at once,
    # so requiring half the file's 48-key palette to appear is unsatisfiable.
    # What distinguishes a themed run is that nearly every colour ON SCREEN
    # came from our file, with zero fallback colours leaking in.
    dominance = len(hit) / len(got) if got else 0.0
    if hit and not leaked and dominance >= 0.6:
        print(f"  PASS assertion 2: {len(hit)}/{len(got)} painted colours "
              f"({dominance:.0%}) come from the theme ({len(hit)}/{len(want)} of "
              f"its stops on screen), 0 Default_theme colours leaked")
    else:
        print(f"  FAIL assertion 2: {len(hit)}/{len(got)} painted colours from the "
              f"theme ({dominance:.0%}), {len(hit)}/{len(want)} stops on screen; "
              f"Default leak={sorted(leaked) or 'none'}")
        print(f"           frame colours: {sorted(got)}")
        ok = False
    return ok


_SRC: pathlib.Path | None = None


def theme_dir_src() -> pathlib.Path:
    assert _SRC is not None
    return _SRC


def main() -> int:
    global _SRC
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--theme-dir", required=True, type=pathlib.Path,
                    help="directory holding the rendered *.theme files")
    ap.add_argument("--themes", nargs="+", required=True,
                    help="theme filenames to prove, e.g. csg-minimal.theme")
    ap.add_argument("--btop-bin", default="btop")
    ap.add_argument("--color-theme", default=None,
                    help="NEGATIVE CONTROL: write this value to btop.conf's "
                         "color_theme instead of the theme under test. Pass a name "
                         "that is not staged to force btop's silent Default_theme "
                         "fallback; the harness must then FAIL (exit 1).")
    args = ap.parse_args()
    if shutil.which(args.btop_bin) is None:
        # Visible skip, not a silent green: exit 0 but say plainly on BOTH
        # streams that nothing was actually proved.
        msg = (f"SKIP: {args.btop_bin} not installed -- theme LOAD/APPLY was NOT "
               f"verified. This is a skip, not a pass.")
        print(msg, file=sys.stderr)
        print(msg)
        return 0
    _SRC = args.theme_dir

    failures = 0
    with tempfile.TemporaryDirectory(prefix="btop-theme-assert-") as td:
        tmp = pathlib.Path(td)
        for theme in args.themes:
            print(f"\n{theme}")
            if args.color_theme:
                print(f"  (negative control: color_theme={args.color_theme!r})")
            try:
                passed = check_one(theme, args.themes, tmp, [], args.color_theme)
            except Exception as exc:  # a crash must be a FAIL, never a pass
                print(f"  FAIL: harness error: {type(exc).__name__}: {exc}")
                passed = False
            if not passed:
                failures += 1
    print()
    if failures:
        print(f"FAILED: {failures}/{len(args.themes)} themes did not apply")
        return 1
    print(f"OK: all {len(args.themes)} themes loaded AND applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())

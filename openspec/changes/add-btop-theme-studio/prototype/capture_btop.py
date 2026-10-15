#!/usr/bin/env python3
"""Capture REAL btop frames on a pty and render them to HTML.

No dependencies: a small truecolor VT parser reconstructs the 200x50 screen
from btop's pty output, then we emit an HTML page with the captured frame(s).

This is a proof-of-concept for "the preview should BE btop": instead of
re-implementing btop's layout (which drifts), we run the real binary with a
candidate theme and show exactly what it paints -- same technique as
spikes/btop-theme-prototype/assert_theme_applies.py, minus the assertions.
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
import sys
import tempfile
import termios
import threading
import time

W, H, SETTLE = 200, 50, 5.0
BASE_FG, BASE_BG = "#c2c2c5", "#0b0b1a"

BASIC = ["#000000", "#cd0000", "#00cd00", "#cdcd00", "#0000ee", "#cd00cd", "#00cdcd", "#e5e5e5"]
BRIGHT = ["#7f7f7f", "#ff0000", "#00ff00", "#ffff00", "#5c5cff", "#ff00ff", "#00ffff", "#ffffff"]


def _xterm256(n: int) -> str:
    if n < 8:
        return BASIC[n]
    if n < 16:
        return BRIGHT[n - 8]
    if n < 232:
        n -= 16
        r, g, b = n // 36, (n % 36) // 6, n % 6
        lv = [0, 95, 135, 175, 215, 255]
        return "#%02x%02x%02x" % (lv[r], lv[g], lv[b])
    v = 8 + (n - 232) * 10
    return "#%02x%02x%02x" % (v, v, v)


def parse(data: str, width: int, height: int) -> list[list[list]]:
    """Reconstruct the final screen. Each cell = [char, fg, bg, bold]."""
    scr = [[[" ", None, None, False] for _ in range(width)] for _ in range(height)]
    cx = cy = 0
    fg = bg = None
    bold = False
    rt, rb = 0, height - 1
    i, n = 0, len(data)
    maxx = width

    def sgr(params: str) -> None:
        nonlocal fg, bg, bold
        parts = [p for p in params.split(";")] if params else ["0"]
        if parts == [""]:
            parts = ["0"]
        nums = [int(p) if p.isdigit() else 0 for p in parts]
        k = 0
        while k < len(nums):
            v = nums[k]
            if v == 0:
                fg = bg = None; bold = False
            elif v == 1:
                bold = True
            elif v == 22:
                bold = False
            elif 30 <= v <= 37:
                fg = BASIC[v - 30]
            elif 90 <= v <= 97:
                fg = BRIGHT[v - 90]
            elif v == 39:
                fg = None
            elif 40 <= v <= 47:
                bg = BASIC[v - 40]
            elif 100 <= v <= 107:
                bg = BRIGHT[v - 100]
            elif v == 49:
                bg = None
            elif v == 38 and k + 1 < len(nums):
                if nums[k + 1] == 5 and k + 2 < len(nums):
                    fg = _xterm256(nums[k + 2]); k += 2
                elif nums[k + 1] == 2 and k + 4 < len(nums):
                    fg = "#%02x%02x%02x" % (nums[k + 2], nums[k + 3], nums[k + 4]); k += 4
            elif v == 48 and k + 1 < len(nums):
                if nums[k + 1] == 5 and k + 2 < len(nums):
                    bg = _xterm256(nums[k + 2]); k += 2
                elif nums[k + 1] == 2 and k + 4 < len(nums):
                    bg = "#%02x%02x%02x" % (nums[k + 2], nums[k + 3], nums[k + 4]); k += 4
            k += 1

    def scroll(top: int, bot: int, line: int) -> None:
        del scr[top]
        scr.insert(bot, [[" ", None, None, False] for _ in range(width)])

    def put(ch: str) -> None:
        nonlocal cx, cy
        if 0 <= cy < height and 0 <= cx < width:
            scr[cy][cx] = [ch, fg, bg, bold]
        cx += 1
        if cx >= width:
            cx = 0
            cy += 1
            if cy > rb:
                scroll(rt, rb, 1)
                cy = rb

    while i < n:
        c = data[i]
        if c == "\x1b":
            j = i + 1
            if j >= n:
                break
            d = data[j]
            if d == "[":
                k = j + 1
                while k < n and not ("\x40" <= data[k] <= "\x7e"):
                    k += 1
                if k >= n:
                    break
                final, params = data[k], data[j + 1:k]
                nums = [int(p) if p.isdigit() else 0 for p in params.lstrip("?<>=").split(";") if p != ""] or []
                if final in ("H", "f"):
                    cy = (nums[0] if nums else 1) - 1
                    cx = (nums[1] if len(nums) > 1 else 1) - 1
                elif final == "A":
                    cy -= nums[0] if nums else 1
                elif final == "B":
                    cy += nums[0] if nums else 1
                elif final == "C":
                    cx += nums[0] if nums else 1
                elif final == "D":
                    cx -= nums[0] if nums else 1
                elif final == "G":
                    cx = (nums[0] if nums else 1) - 1
                elif final == "d":
                    cy = (nums[0] if nums else 1) - 1
                elif final == "J":
                    m = nums[0] if nums else 0
                    if m in (2, 3):
                        scr[:] = [[[" ", None, None, False] for _ in range(width)] for _ in range(height)]
                    elif m == 0:
                        for xx in range(cx, width):
                            scr[cy][xx] = [" ", None, None, False]
                        for yy in range(cy + 1, height):
                            scr[yy] = [[" ", None, None, False] for _ in range(width)]
                elif final == "K":
                    m = nums[0] if nums else 0
                    rng = range(cx, width) if m == 0 else (range(0, cx + 1) if m == 1 else range(0, width))
                    for xx in rng:
                        scr[cy][xx] = [" ", None, None, False]
                elif final == "m":
                    sgr(params)
                elif final in ("h", "l"):
                    pass
                elif final == "r":
                    rt = (nums[0] if nums else 1) - 1
                    rb = (nums[1] if len(nums) > 1 else height) - 1
                    cy = cx = 0
                elif final == "S":
                    for _ in range((nums[0] if nums else 1)):
                        scroll(rt, rb, 1)
                i = k + 1
                continue
            if d == "]":
                k = j + 1
                while k < n and data[k] != "\x07" and not (data[k] == "\x1b" and k + 1 < n and data[k + 1] == "\\"):
                    k += 1
                i = k + 2 if (k < n and data[k] == "\x1b") else k + 1
                continue
            if d in "()":
                i = j + 2
                continue
            if d in "P^_":
                k = j + 1
                while k < n and not (data[k] == "\x1b" and k + 1 < n and data[k + 1] == "\\"):
                    k += 1
                i = k + 2
                continue
            i = j + 1
            continue
        if c == "\r":
            cx = 0
        elif c == "\n":
            cy += 1
            if cy > rb:
                scroll(rt, rb, 1)
                cy = rb
        elif c == "\b":
            cx = max(0, cx - 1)
        elif c == "\t":
            cx = min(width - 1, (cx // 8 + 1) * 8)
        elif c == "\x07":
            pass
        else:
            put(c)
        i += 1
    return scr


def capture(theme_path: pathlib.Path, out_theme_name: str, preset: str | None) -> list[list[list]]:
    with tempfile.TemporaryDirectory() as td:
        root = pathlib.Path(td)
        (root / "config/btop/themes").mkdir(parents=True)
        (root / "state").mkdir()
        (root / "cache").mkdir()
        # btop matches color_theme by filename against discovered themes.
        name = "colors.btop.theme"
        (root / "config/btop/themes" / name).write_text(theme_path.read_text())
        (root / "config/btop/btop.conf").write_text(
            f'color_theme = "{name}"\n'
            'save_config_on_exit = false\n'
            'log_level = "DISABLED"\n'
            "update_ms = 2000\n"
        )
        env = dict(
            os.environ,
            HOME=td,
            XDG_CONFIG_HOME=str(root / "config"),
            XDG_STATE_HOME=str(root / "state"),
            XDG_CACHE_HOME=str(root / "cache"),
            TERM="xterm-256color",
            COLORTERM="truecolor",
            LANG="C.UTF-8",
            LC_ALL="C.UTF-8",
        )
        master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", H, W, 0, 0))
        argv = ["btop", "--no-tty", "--force-utf", "-u", "400"]
        if preset is not None:
            argv += ["-p", preset]
        proc = subprocess.Popen(argv, stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
        os.close(slave)
        # Drain the pty WHILE btop runs: its frame output is far larger than the
        # kernel pty buffer, so reading only after exit captures a skeleton and
        # misses every data frame (btop blocks on write).
        buf = bytearray()
        stop = False
        os.set_blocking(master, False)

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
        time.sleep(SETTLE)
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        time.sleep(0.2)
        stop = True
        reader.join(timeout=1)
        os.close(master)
        return parse(bytes(buf).decode("utf-8", "replace"), W, H)


def theme_to_html(scr: list[list[list]], title: str, subtitle: str) -> str:
    out = [f'<div class="frame"><div class="flabel"><b>{title}</b> — {subtitle}</div><pre class="btop">']
    for row in scr:
        # group runs of identical style
        run, style = "", None
        for ch, fg, bg, bold in row:
            key = (fg, bg, bold)
            if key != style:
                if run:
                    out.append(_span(run, style))
                run, style = "", key
            run += ch
        if run:
            out.append(_span(run, style))
        out.append("\n")
    out.append("</pre></div>")
    return "".join(out)


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


def fixed_theme(src: pathlib.Path) -> str:
    """The proposed meter fix: empty meter -> surface; raise the used floor."""
    d = dict(re.findall(r'^theme\[([A-Za-z0-9_]+)\]="([^"]*)"', src.read_text(), re.M))
    d["meter_bg"] = d.get("main_bg", BASE_BG)
    if d.get("used_mid"):
        d["used_start"] = d["used_mid"]
    keys = re.findall(r"^theme\[([A-Za-z0-9_]+)\]=", src.read_text(), re.M)
    return "".join(f'theme[{k}]="{d.get(k, "")}"\n' for k in keys)


def main() -> int:
    theme = pathlib.Path(os.path.expanduser(sys.argv[1])) if len(sys.argv) > 1 \
        else pathlib.Path.home() / ".local/state/dotfiles/current/colors.btop.theme"

    with tempfile.TemporaryDirectory() as td:
        fixed = pathlib.Path(td) / "colors.btop-fixed.theme"
        fixed.write_text(fixed_theme(theme))

        print(f"capturing current theme: {theme}")
        cur = capture(theme, "current", None)
        print("capturing meter-fixed theme…")
        fx = capture(fixed, "fixed", None)

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8">
<title>btop REAL frames — captured from the binary</title>
<style>
 body{{margin:0;background:#0f1013;color:#d7dbe2;font:13px/1.4 system-ui,sans-serif;padding:16px;}}
 h1{{font-size:15px;margin:0 0 4px;}} .sub{{color:#8b93a1;font-size:12px;margin-bottom:14px;max-width:1100px;}}
 .grid{{display:flex;gap:18px;flex-wrap:wrap;align-items:flex-start;}}
 .frame{{border:1px solid #313742;border-radius:8px;padding:10px;background:#00000040;}}
 .flabel{{font-size:11.5px;color:#8b93a1;margin-bottom:8px;}} .flabel b{{color:#fff;}}
 pre.btop{{margin:0;font-family:ui-monospace,"DejaVu Sans Mono",monospace;font-size:9.5px;line-height:1.02;
   white-space:pre;letter-spacing:0;}}
 code{{background:#262b33;padding:1px 4px;border-radius:3px;}}
</style></head><body>
<h1>btop — real captured frames (not a mock)</h1>
<div class="sub">Captured by running the real <code>btop --no-tty --force-utf</code> on a 200×50 pty with
<code>--themes-dir</code> pointed at each theme, then reconstructing the screen from its truecolor output.
This is <b>your</b> btop layout, painted by <b>your</b> generated theme.</div>
<div class="grid">
{theme_to_html(cur, "current generated theme", "as shipped — watch the meters at low load")}
{theme_to_html(fx, "meter-fixed theme", "empty meter = surface, used floor raised")}
</div>
</body></html>"""

    outp = pathlib.Path(__file__).with_name("btop-real-frame.html")
    outp.write_text(html)
    print("wrote", outp)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

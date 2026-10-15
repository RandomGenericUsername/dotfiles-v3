#!/usr/bin/env python3
"""studio_server.py — serves the LIVE btop studio.

  GET  /        -> live_editor.html
  GET  /state   -> {presets, shown_boxes, keys(hex), ramp, bg, fg}
  POST /edit    -> {preset, keys} -> re-render real btop, return {frame(html), boxes}

The page edits a key->hex map; each edit is pushed here, written to the candidate
.theme, btop hot-reloads (SIGUSR2), and the freshly captured frame is returned.
One pane, real btop, in sync with every keystroke.
"""
from __future__ import annotations

import http.server
import json
import pathlib
import re
import subprocess
import sys
import threading

import btop_live
from capture_btop import _span

HERE = pathlib.Path(__file__).resolve().parent
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8799


def default_cfg() -> tuple[str, str]:
    out = subprocess.run(["btop", "--default-config"], capture_output=True, text=True).stdout
    p = re.search(r'^presets = "(.*)"', out, re.M)
    s = re.search(r'^shown_boxes = "(.*)"', out, re.M)
    return (p.group(1) if p else ""), (s.group(1) if s else "cpu mem net proc")


def parse_presets(raw: str) -> dict:
    defs = {"0": {"label": "Preset 0 — all boxes shown (btop rule)",
                  "boxes": {"cpu": 0, "gpu": 0, "mem": 0, "net": 0, "disks": 0, "proc": 0}}}
    for i, group in enumerate(raw.split(), start=1):
        boxes = {}
        for entry in group.split(","):
            parts = entry.split(":")
            if not parts or not parts[0]:
                continue
            boxes[parts[0]] = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        if "cpu" in boxes and "gpu" not in boxes:
            boxes["gpu"] = boxes["cpu"]
        defs[str(i)] = {"label": f"Preset {i} — {group}", "boxes": boxes}
    return defs


def read_palette() -> tuple[str, str, list[str], list[str]]:
    txt = (pathlib.Path.home() / ".local/state/dotfiles/current/colors.yaml").read_text()
    bg = re.search(r'background:\s*"(#[0-9a-fA-F]{6})"', txt).group(1)
    fg = re.search(r'foreground:\s*"(#[0-9a-fA-F]{6})"', txt).group(1)
    raw = re.findall(r'-\s*"(#[0-9a-fA-F]{6})"', txt)
    colors16 = raw[:16]
    ramp: list[str] = []
    for c in colors16:  # collapse adjacent duplicates (pywal emits pairs)
        if not ramp or ramp[-1] != c:
            ramp.append(c)
    return bg, fg, ramp, colors16


PRESETS_RAW, SHOWN = default_cfg()
PRESETS = parse_presets(PRESETS_RAW)
BG, FG, RAMP, COLORS16 = read_palette()
BASE_TEXT = (pathlib.Path.home() / ".local/state/dotfiles/current/colors.btop.theme").read_text()
BASE_KEYS = btop_live.parse_theme_map(BASE_TEXT)


def frame_html(scr: list[list[list]]) -> str:
    lines = []
    for row in scr:
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


class Engine:
    """One warm btop process; a reload captures only the redraw delta.

    SIGUSR2 makes btop repaint fully, so parsing the post-signal bytes is clean
    and skips the ~1.8 s spawn+first-draw tax (≈0.9 s/edit). A preset change or
    an oversized transcript falls back to a fresh process.
    """

    TRANSCRIPT_LIMIT = 8_000_000

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.preset = 0
        self.session = btop_live.BtopSession(BASE_TEXT, 0)

    def _respawn(self, text: str, preset: int) -> list[list[list]]:
        self.session.close()
        self.session = btop_live.BtopSession(text, preset)
        self.preset = preset
        return self.session.frame()

    def render(self, preset: int, keys: dict) -> list[list[list]]:
        text = btop_live.theme_text_from_map(keys)
        if preset != self.preset:
            return self._respawn(text, preset)
        if len(self.session._buf) > self.TRANSCRIPT_LIMIT:
            return self._respawn(text, preset)
        self.session.write_theme(text)
        return self.session.reload_and_capture()

    def close(self) -> None:
        self.session.close()


ENGINE = Engine()


class Handler(http.server.BaseHTTPRequestHandler):
    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length", 0))
        return self.rfile.read(n) if n else b""

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802  (CORS preflight)
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._send(200, (HERE / "btop-theme-studio-v8.html").read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/state":
            payload = {"presets": PRESETS, "shown_boxes": SHOWN, "keys": BASE_KEYS,
                       "ramp": RAMP, "colors": COLORS16, "bg": BG, "fg": FG}
            self._send(200, json.dumps(payload).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        if self.path == "/edit":
            try:
                data = json.loads(self._body() or b"{}")
            except json.JSONDecodeError:
                self._send(400, b"bad json", "text/plain")
                return
            preset = int(data.get("preset", 0))
            keys = data.get("keys", {}) or BASE_KEYS
            with ENGINE.lock:
                scr = ENGINE.render(preset, keys)
            out = {"frame": frame_html(scr), "boxes": list(PRESETS[str(preset)]["boxes"])}
            self._send(200, json.dumps(out).encode(), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *a) -> None:  # quiet
        pass


if __name__ == "__main__":
    print(f"btop live studio on http://localhost:{PORT}  (presets={list(PRESETS)}, boxes0={list(PRESETS['0']['boxes'])})")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        ENGINE.close()

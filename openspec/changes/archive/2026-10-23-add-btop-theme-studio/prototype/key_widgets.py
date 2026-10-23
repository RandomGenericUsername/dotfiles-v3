#!/usr/bin/env python3
"""key_widgets.py — generate the COMPLETE btop theme-key -> component map FROM SOURCE.

btop's theme is a fixed set of keys defined in btop_theme.cpp's `Default_theme`.
We take that canonical list, then attribute each key to the boxes/modules that
draw it by parsing btop_draw.cpp:

  * `Theme::g("k")` / `Theme::c("k")` literals, by the namespace they sit in
    (btop groups draw code by module: Cpu, Gpu, Mem, Net, Proc, Draw);
  * the gradient NAME passed as a *variable* into `Draw::Graph{...}` /
    `Draw::Meter{...}` builders (the literal is at the call site, not the
    Theme::g line), handled across line breaks;
  * gradient-stop keys (cpu_start/mid/end) inherit their family's modules;
  * `*_box` keys attribute to their own box;
  * anything not referenced in btop_draw.cpp (e.g. main_bg, set in btop.cpp)
    falls back to all boxes and is flagged in its `sites`.

  python3 key_widgets.py btop_draw.v1.4.7.cpp btop_theme.cpp key_widgets.json
  python3 key_widgets.py btop_draw.v1.4.7.cpp btop_theme.cpp key_widgets.json --verify

--verify re-derives and compares; non-zero exit on drift, so the JSON is a
TESTED artifact pinned to the source, covering every key btop defines.

Honest limit: btop draws the mem AND disks boxes in one `Mem::draw`, so keys
there are attributed to both.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

NS_MODULES = {"Cpu": ["cpu"], "Gpu": ["gpu"], "Mem": ["mem", "disks"],
              "Net": ["net"], "Proc": ["proc"]}
ALL_BOXES = ["cpu", "gpu", "mem", "net", "disks", "proc"]
CALL = re.compile(r'Theme::[gc]\("([A-Za-z0-9_]+)"\)')
NS = re.compile(r'^namespace\s+(\w+)\s*\{')
GRAPH = re.compile(r'Draw::(?:Graph|Meter)\{(.*)')
GRADS = {"cpu", "temp", "cached", "available", "used", "free", "download", "upload", "process"}
STOP = ("_start", "_mid", "_end")


def grad_from(text: str) -> str | None:
    for q in re.findall(r'"([A-Za-z0-9_]+)"', text):
        if q in GRADS:
            return q
    return None


def modules_for(ns: str, key: str) -> list[str]:
    if key.endswith("_box"):
        return [key[:-4]]
    if ns in NS_MODULES:
        return NS_MODULES[ns]
    if ns == "Draw":
        return ALL_BOXES
    return []


def derive_draw(src: pathlib.Path) -> dict[str, dict]:
    keys: dict[str, dict] = {}

    def add(ns: str, key: str, line_no: int) -> None:
        rec = keys.setdefault(key, {"modules": set(), "sites": [], "calls": 0})
        rec["modules"].update(modules_for(ns, key))
        rec["sites"].append(f"{ns}:{line_no}")
        rec["calls"] += 1

    ns, pending, pending_ns = "?", None, "?"
    for i, line in enumerate(src.read_text().splitlines(), 1):
        m = NS.match(line)
        if m:
            ns = m.group(1)
        for key in CALL.findall(line):
            add(ns, key, i)
        if pending is not None:
            pending += " " + line
            if "}" in line:
                g = grad_from(pending)
                if g:
                    add(pending_ns, g, i)
                pending = None
            continue
        gm = GRAPH.search(line)
        if gm:
            rest = gm.group(1)
            if "}" in rest:
                g = grad_from(rest)
                if g:
                    add(ns, g, i)
            else:
                pending, pending_ns = rest, ns
    return keys


def theme_keys(src: pathlib.Path) -> list[str]:
    t = src.read_text()
    m = re.search(r'Default_theme\s*=\s*\{(.*?)\n\t\};', t, re.S)
    return re.findall(r'\{\s*"([A-Za-z0-9_]+)"', m.group(1))


def derive(draw_src: pathlib.Path, theme_src: pathlib.Path) -> dict:
    raw = derive_draw(draw_src)
    keys: dict[str, dict] = {}
    for k in theme_keys(theme_src):
        if k in raw:
            rec = raw[k]
        elif k.endswith(STOP) and k.rsplit("_", 1)[0] in raw:
            base = k.rsplit("_", 1)[0]
            rec = {"modules": raw[base]["modules"], "calls": 0, "sites": [f"gradient of {base}"]}
        elif k.endswith("_box"):
            rec = {"modules": [k[:-4]], "calls": 0, "sites": ["box outline"]}
        else:
            rec = {"modules": ALL_BOXES, "calls": 0,
                   "sites": ["not referenced in btop_draw.cpp (chrome/base surface)"]}
        keys[k] = {"modules": sorted(set(rec["modules"])), "calls": rec.get("calls", 0),
                   "sites": rec.get("sites", [])[:8]}
    return {"draw_source": draw_src.name, "theme_source": theme_src.name,
            "method": "namespace of Theme::g/c literals + Draw::Graph/Meter gradient args, "
                      "over the full Default_theme key set",
            "note": "used/free/available live in Mem::draw which paints mem AND disks",
            "keys": keys}


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    draw = pathlib.Path(args[0]) if args else pathlib.Path("btop_draw.v1.4.7.cpp")
    theme = pathlib.Path(args[1]) if len(args) > 1 else pathlib.Path("btop_theme.cpp")
    dst = pathlib.Path(args[2]) if len(args) > 2 else pathlib.Path("key_widgets.json")
    verify = "--verify" in sys.argv
    fresh = derive(draw, theme)
    if verify:
        if not dst.exists():
            print(f"FAIL: {dst} missing")
            return 1
        committed = json.loads(dst.read_text())
        if committed != fresh:
            print("FAIL: key_widgets.json drifted from source")
            return 1
        print(f"OK: {dst} matches source ({len(fresh['keys'])} keys)")
        return 0
    dst.write_text(json.dumps(fresh, indent=2, sort_keys=True) + "\n")
    print(f"wrote {dst}: {len(fresh['keys'])} keys")
    for k, v in fresh["keys"].items():
        print(f"  {k:16} -> {','.join(v['modules'])}  ({v['calls']} calls)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

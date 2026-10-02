#!/usr/bin/env python3
"""Render the three candidate btop themes against the live palette.

Preview harness only -- the real render path is CSG's JinjaTemplateRenderer,
which uses trim_blocks + lstrip_blocks + StrictUndefined. This mirrors that
exactly so the preview cannot diverge from production output.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

HERE = Path(__file__).parent
LIVE = Path("/home/inumaki/.local/state/dotfiles/current/colors.yaml")


class C:
    def __init__(self, hexstr: str) -> None:
        self.hex = hexstr


def load_palette() -> tuple[list[str], C, C, C]:
    hexes = re.findall(r'"(#[0-9a-fA-F]{6})"', LIVE.read_text())
    bg, fg, cur = hexes[0], hexes[1], hexes[2]
    pal = hexes[3:19]
    return pal, C(bg), C(fg), C(cur)


def distinct(pal: list[str]) -> list[str]:
    """Collapse adjacent duplicates left by luminance-sorted pywal output."""
    out: list[str] = []
    for h in pal:
        if not out or out[-1] != h:
            out.append(h)
    return out


def main() -> int:
    pal, bg, fg, cur = load_palette()
    uniq = distinct(pal)
    print(f"palette: {len(pal)} slots -> {len(uniq)} distinct")
    for i, h in enumerate(uniq):
        r, g, b = int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)
        print(f"  u[{i}] {h} lum={r+g+b:4d}")

    env = Environment(
        loader=FileSystemLoader(str(HERE)),
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
        keep_trailing_newline=True,
    )
    ctx = {
        "background": bg,
        "foreground": fg,
        "cursor": cur,
        "colors": [C(h) for h in pal],
        "uniq": [C(h) for h in uniq],
        "source_image": LIVE,
        "backend": "pywal",
        "generated_at": "preview",
    }
    for tpl in sorted(HERE.glob("colors.btop-*.theme.j2")):
        out = tpl.with_suffix("").with_suffix("")
        text = env.get_template(tpl.name).render(**ctx)
        dest = HERE / tpl.name[: -len(".j2")]
        dest.write_text(text)
        nkeys = len(re.findall(r"^theme\[", text, re.M))
        print(f"{tpl.name:34s} -> {dest.name:22s} {nkeys:2d} keys, {len(text.splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())

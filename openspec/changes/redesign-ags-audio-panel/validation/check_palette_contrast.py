#!/usr/bin/env python3
"""Measure proposed audio-panel token contrast against cached generated GTK palettes.

This is a token-level planning check, not a substitute for measuring GTK's
rendered/translucent surfaces on the compositor. It composites the specified
panel/card alpha values over color_00 and checks WCAG contrast roles.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

COLOR = re.compile(r"@define-color\s+(\w+)\s+#([0-9a-fA-F]{6})\s*;")


def rgb(value: str) -> tuple[float, float, float]:
    return tuple(int(value[i : i + 2], 16) / 255 for i in (0, 2, 4))


def blend(top: tuple[float, ...], bottom: tuple[float, ...], alpha: float) -> tuple[float, ...]:
    return tuple(alpha * a + (1 - alpha) * b for a, b in zip(top, bottom))


def luminance(color: tuple[float, ...]) -> float:
    channels = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in color]
    return sum(c * w for c, w in zip(channels, (0.2126, 0.7152, 0.0722)))


def contrast(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def load(path: Path) -> dict[str, tuple[float, ...]]:
    colors = {name: rgb(value) for name, value in COLOR.findall(path.read_text())}
    required = {"color_00", "color_01", "color_06", "color_10", "color_13", "color_14", "color_15", "color_background", "color_foreground"}
    missing = required - colors.keys()
    if missing:
        raise ValueError(f"{path}: missing {', '.join(sorted(missing))}")
    return colors


def assess(path: Path) -> list[tuple[str, float, float, bool]]:
    c = load(path)
    panel = blend(c["color_00"], c["color_background"], 0.94)
    card = blend(c["color_01"], panel, 0.18)
    results = [
        ("primary text / panel", contrast(c["color_foreground"], panel), 4.5, False),
        ("secondary text / panel (72%)", contrast(blend(c["color_foreground"], panel, 0.72), panel), 4.5, False),
        ("muted text / panel (64%)", contrast(blend(c["color_foreground"], panel, 0.64), panel), 4.5, False),
        ("primary text / card", contrast(c["color_foreground"], card), 4.5, False),
        ("secondary text / card (72%)", contrast(blend(c["color_foreground"], card, 0.72), card), 4.5, False),
        ("muted text / card (64%)", contrast(blend(c["color_foreground"], card, 0.64), card), 4.5, False),
        (
            f"selection text (background {contrast(c['color_background'], c['color_10']):.2f}:1; foreground {contrast(c['color_foreground'], c['color_10']):.2f}:1; choose {'background' if contrast(c['color_background'], c['color_10']) >= 4.5 else 'foreground'})",
            max(contrast(c["color_background"], c["color_10"]), contrast(c["color_foreground"], c["color_10"])),
            4.5,
            False,
        ),
        ("focus color / panel", contrast(c["color_10"], panel), 3.0, True),
        ("focus color / card", contrast(c["color_10"], card), 3.0, True),
        ("action color / panel", contrast(c["color_06"], panel), 3.0, True),
        ("slider thumb / track", contrast(c["color_15"], blend(c["color_foreground"], panel, 0.16)), 3.0, True),
        ("slider fill / track", contrast(c["color_13"], blend(c["color_foreground"], panel, 0.16)), 3.0, True),
    ]
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("palettes", nargs="+", type=Path)
    args = parser.parse_args()
    failures = 0
    for path in args.palettes:
        print(f"\n{path}")
        for label, actual, threshold, nontext in assess(path):
            ok = actual >= threshold
            failures += not ok
            print(f"{'PASS' if ok else 'FAIL'} {label}: {actual:.2f}:1 (minimum {threshold:.1f}:1{' non-text' if nontext else ' text'})")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

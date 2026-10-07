#!/usr/bin/env python3
"""Validate rendered .theme files against btop 1.4.7's REAL parser rules.

Mirrors src/btop_theme.cpp rather than reimplementing from memory:
  - Default_theme key set (:52-101), exact + case-sensitive
  - '#' is a comment ONLY at offset 0 -> leading ws before '[' mangles (:399-406)
  - values: #RRGGBB | #GG | "12 34 56"  (NO 8-digit) (:265-278)
  - <x>_mid / <x>_end empty -> 2-stop gradient (:260-264)
"""
import re, sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, "/tmp/opencode/btop-src/src")

KEYS = set("""main_bg main_fg title hi_fg selected_bg selected_fg inactive_fg
graph_text meter_bg proc_misc cpu_box mem_box net_box proc_box div_line
temp_start temp_mid temp_end cpu_start cpu_mid cpu_end
free_start free_mid free_end cached_start cached_mid cached_end
available_start available_mid available_end used_start used_mid used_end
download_start download_mid download_end upload_start upload_mid upload_end
process_start process_mid process_end
proc_pause_bg proc_follow_bg proc_banner_bg proc_banner_fg
followed_bg followed_fg""".split())

GRADS = ["temp", "cpu", "free", "cached", "available", "used",
         "download", "upload", "process"]

ok = True
for f in sorted(HERE.glob("colors.btop-*.theme")):
    errs, warns, seen = [], [], {}
    for n, line in enumerate(f.read_text().splitlines(), 1):
        if not line.strip():
            continue
        if line.startswith("#"):
            continue
        if line != line.lstrip():
            errs.append(f"L{n}: LEADING WHITESPACE - btop mangles this")
        if "[" not in line or "]" not in line:
            errs.append(f"L{n}: unparseable: {line!r}")
            continue
        key = line[line.index("[") + 1: line.index("]")]
        if key not in KEYS:
            errs.append(f"L{n}: UNKNOWN KEY {key!r} (silently ignored by btop)")
        else:
            seen[key] = True
        raw = line.split("=", 1)[1].strip() if "=" in line else ""
        val = raw[1:-1] if raw.startswith('"') and raw.endswith('"') else raw
        if val == "":
            continue
        if re.fullmatch(r"#[0-9a-fA-F]{6}", val):
            continue
        if re.fullmatch(r"#[0-9a-fA-F]{2}", val):
            continue
        if re.fullmatch(r"\d{1,3} \d{1,3} \d{1,3}", val):
            continue
        errs.append(f"L{n}: BAD VALUE {val!r} (need #RRGGBB, #GG, or '12 34 56')")

    for g in GRADS:
        for s in ("start", "mid", "end"):
            if f"{g}_{s}" not in seen:
                errs.append(f"gradient {g}: {s} missing")
    # the process_* trap: guarded on process_start only
    if "process_start" in seen and "process_end" not in seen:
        errs.append("process_start set but process_end missing -> fades to BLACK")

    n_distinct = len({v for v in re.findall(r'="#([0-9a-fA-F]{6})"',
                        f.read_text())})
    print(f"\n{f.name}: {len(seen)}/48 keys, {n_distinct} distinct colors")
    for e in errs:
        print(f"  ERROR  {e}")
        ok = False
    for w in warns:
        print(f"  WARN   {w}")
    if not errs:
        print("  OK - all keys valid, column-0 clean, no process_* trap")

sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""Recording stand-in for csg / weg / itr (S1 evidence probe).

Writes one JSON line per invocation to FAKE_CLI_LOG, capturing argv, cwd,
stdin target, and selected environment variables. Creates the minimum
artifacts each runtime adapter expects so the adapter proceeds past its
post-invocation checks.
"""

import json
import os
import sys
from pathlib import Path

log = Path(os.environ.get("FAKE_CLI_LOG", "/tmp/opencode/fake_cli_log.jsonl"))
record = {
    "argv": sys.argv,
    "cwd": os.getcwd(),
    "stdin_fd0": os.readlink("/proc/self/fd/0"),
    "env": {
        k: os.environ.get(k)
        for k in (
            "PATH",
            "HOME",
            "XDG_CONFIG_HOME",
            "XDG_STATE_HOME",
            "XDG_CACHE_HOME",
            "XDG_DATA_HOME",
            "COLORSCHEME__OUTPUT__DIRECTORY",
            "COLORSCHEME__OUTPUT__OVERWRITE",
            "WALLPAPER__OUTPUT__DIRECTORY",
            "ICON_RENDERER__OUTPUT__OUTPUT_DIR",
            "ICON_RENDERER__COLOR_SCHEME__PATH",
            "DOTFILES_INSTALL_SPINE",
        )
    },
    "env_all_keys": sorted(os.environ),
}
with log.open("a", encoding="utf-8") as fh:
    fh.write(json.dumps(record, sort_keys=True) + "\n")

sub = sys.argv[1] if len(sys.argv) > 1 else ""
if sub == "generate":
    out = Path(os.environ["COLORSCHEME__OUTPUT__DIRECTORY"])
    out.mkdir(parents=True, exist_ok=True)
    names = [
        "colors.yaml",
        "colors.conf",
        "colors.gtk.css",
        "colors.adw.css",
        "colors.sequences",
        "colors.rasi",
        "colors.kitty",
        "colors.btop.theme",
    ]
    for n in names:
        (out / n).write_text("x\n", encoding="utf-8")
elif sub == "batch":
    out = Path(os.environ["WALLPAPER__OUTPUT__DIRECTORY"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "blur.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
elif sub == "render":
    out = Path(os.environ["ICON_RENDERER__OUTPUT__OUTPUT_DIR"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "battery-0.svg").write_text("<svg/>\n", encoding="utf-8")
sys.exit(0)

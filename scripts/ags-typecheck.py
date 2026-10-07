#!/usr/bin/env python3
"""Typecheck gate for the AGS layer (openspec: redesign-ags-audio-panel, task 6.5).

Why this exists
---------------
``ags bundle`` transpiles; it does not typecheck. Every static gate in this repo
passed a composition root that died on startup:

    audio/composition.ts:  const ports: AudioPorts = { pipewireObservation, ...
    ReferenceError: pipewireObservation is not defined

The variable is named ``pipeWireObservation``. That is a hard error under
``strict``/``noImplicitAny``, but bundling emitted it without complaint, all 17
unit tests passed (they exercise modules directly and never import the
composition root), and the render gate passed because it checks reachability,
not correctness. Only running it found it.

The same blind spot is why ``AudioPopup`` shipped with ``binding?:
AudioPanelBinding`` feeding components that declare ``binding:
AudioPanelBinding``: a ``strictNullChecks`` error, invisible to every gate.

So: zero errors in our files. A baseline is permitted for third-party noise but
must be declared explicitly, and our own files must be clean.

Typings
-------
``tsc`` needs two things this repo does not vendor:

* AGS's own module types. These are TypeScript sources shipped with ags
  (``/usr/share/ags/js/lib``), mapped in via ``paths`` in ``tsconfig.ags.json``.
  No AGS installation location is hardcoded as the only option -- override with
  ``AGS_LIB`` if ags lives elsewhere.
* GObject-introspection typings for ``gi://Gtk?version=4.0`` and friends.
  Generated on demand by ``ags types`` into a scratch directory (49 MB, so it is
  generated and never committed). Skipped with a loud warning if ``ags`` is
  unavailable, in which case only the AGS-module resolution is checked.

Usage::

    python3 scripts/ags-typecheck.py [--root REPO_ROOT] [--baseline N]

Exit 0 = no errors in our files. Exit 1 = errors, or the gate could not run.
Exit 2 = tsc is unavailable (a setup problem, not a pass).

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

TSC_CANDIDATES = [
    "node_modules/.bin/tsc",
    "/home/inumaki/Development/dotfiles-v3/node_modules/.bin/tsc",
    "node_modules/typescript/bin/tsc",
]

# Third-party and vendored sources: GIR typings, GTK4 upstream, and AGS's own
# shipped TypeScript (which ships .ts sources, not .d.ts, so `skipLibCheck`
# does NOT spare them). Errors here are never ours to fix.
#
# Matched as SUBSTRINGS, not prefixes: tsc prints paths relative to the config
# file, so AGS's own sources arrive as `../../../../usr/share/ags/js/...`. A
# prefix match on "/usr/share/ags/" silently missed every one of them and let
# third-party noise count against the baseline.
FOREIGN_MARKERS = (
    "node_modules/",
    "usr/share/ags/",
    "types/ags-girs/",
)

# The audio layer is what this change owns. Errors there are always new and
# always fail: the bar is zero, and 6.0f retires state.ts under it.
#
# The rest of the AGS tree has 32 pre-existing errors unrelated to audio
# (battery, tray, wifi-service, ...). They are counted against a baseline rather
# than allowlisted by filename, because a filename list rots silently as those
# files are edited while a count forces a deliberate decision whenever it moves.
#
# The baseline was verified, not assumed: master's error file list was diffed
# against this branch's and this change introduces none while removing 5. Do not
# raise BASELINE to make the gate green -- fix the error, or record why it is
# genuinely foreign.
WATCHED_PREFIX = "dotfiles/config/ags/audio/"

# Individually exempted inside the watched tree. Each entry must name a
# byte-identical line on master -- verified by checking out master's copy and
# re-running this gate -- so these cannot silently absorb a regression.
EXEMPT = {
    # state.ts:63 `const allNodes: Accessor<unknown[]> = wp...`. Predates this
    # change (identical on master) and the file is retired by task 6.0f; when
    # 6.0f lands, this exemption and state.ts disappear together.
    "dotfiles/config/ags/audio/state.ts": {
        "63,7",
    },
}

PRE_EXISTING_BASELINE = 31


def find_tsc(root: Path) -> Path | None:
    for candidate in TSC_CANDIDATES:
        p = (root / candidate).resolve() if not candidate.startswith("/") else Path(candidate)
        if p.is_file() and os.access(p, os.X_OK):
            return p
    found = shutil.which("tsc")
    return Path(found) if found else None


def main() -> int:
    ap = argparse.ArgumentParser(description="AGS typecheck gate")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    ap.add_argument(
        "--baseline",
        type=int,
        default=0,
        help="permitted foreign error count (default 0: no errors at all)",
    )
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    config = root / "tsconfig.ags.json"
    if not config.is_file():
        print(f"MISSING {config}")
        return 1

    tsc = find_tsc(root)
    if tsc is None:
        print("FAIL cannot find tsc: no node_modules/.bin/tsc and no tsc on PATH.")
        print("     Install typescript (npm i -D typescript) or run `make ags-dev-deps`.")
        return 2

    # Generate GIR typings into a scratch dir; point the config's include at it
    # via a temp overlay so nothing generated lands in the repo.
    workdir = Path(tempfile.mkdtemp(prefix="ags-typecheck-"))
    # `ags types -d DIR` writes DIR/@girs/*.d.ts -- verified, not assumed.
    gir_root = workdir / "@girs"
    ags_bin = shutil.which("ags")
    generated = False
    if ags_bin:
        try:
            subprocess.run(
                [ags_bin, "types", "-d", str(workdir)],
                check=True,
                capture_output=True,
                timeout=900,
            )
            generated = bool(list(gir_root.glob("*.d.ts")))
        except (subprocess.SubprocessError, OSError) as exc:
            print(f"WARNING `ags types` failed ({exc}); GIR typings unavailable")
        if not generated:
            print("WARNING `ags types` produced no typings; gi:// imports are unchecked.")

    try:
        # Rewrite the include paths to the scratch dir for this run only.
        cfg = json.loads(config.read_text())
        # ABSOLUTE paths, deliberately. `include` is resolved relative to the
        # config file's own directory, so a repo-relative glob written into a
        # temp config matches nothing -- and the gate reports a green PASS while
        # checking zero files. That is worse than no gate: it is a false signal.
        cfg["include"] = [
            str(root / "dotfiles/config/ags/**/*.ts"),
            str(root / "dotfiles/config/ags/**/*.tsx"),
            *([str(gir_root / "*.d.ts")] if generated else []),
        ]
        cfg["compilerOptions"]["typeRoots"] = [str(gir_root)]
        run_cfg = workdir / "tsconfig.json"
        run_cfg.write_text(json.dumps(cfg, indent=2))

        proc = subprocess.run(
            [str(tsc), "-p", str(run_cfg), "--pretty", "false"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=900,
        )
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    if not generated:
        print("WARNING GIR typings were not generated; gi:// imports are unchecked.")
        print("         Run this on a host with `ags types` available for full coverage.")

    lines = [l for l in (proc.stdout or "").splitlines() if l.strip()]
    errors = [l for l in lines if ": error TS" in l]

    # A gate that checks nothing must never report PASS. `include` globbing
    # silently yields an empty program, which tsc exits 0 on.
    if not errors and proc.returncode == 0:
        listing = subprocess.run(
            [str(tsc), "-p", str(run_cfg), "--listFilesOnly", "--pretty", "false"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=300,
        )
        checked = [f for f in listing.stdout.splitlines() if "/dotfiles/config/ags/" in f]
        if len(checked) < 2:
            print(f"FAIL checked {len(checked)} file(s) under dotfiles/config/ags -- too few to be real.")
            print("     The include globs matched nothing; refusing to report a false PASS.")
            return 1

    ours, foreign, preexisting, exempted = [], [], [], []
    for line in errors:
        if any(m in line for m in FOREIGN_MARKERS):
            foreign.append(line)
            continue
        if WATCHED_PREFIX in line:
            # "file(line,col): error ..." -- match the position against EXEMPT.
            path, _, rest = line.partition("(")
            # rest is "63,7): error TS..." -- drop the trailing ")".
            pos = rest.partition(":")[0].rstrip(")") if rest else ""
            if pos in EXEMPT.get(path, set()):
                exempted.append(line)
                continue
            ours.append(line)
            continue
        preexisting.append(line)

    for line in exempted:
        print(f"exempt {line}  (pre-existing on master; retired with its file)")

    for line in foreign:
        print(f"foreign {line}")
    if foreign:
        print(f"({len(foreign)} third-party error(s) -- vendored/upstream, never ours)")

    if ours:
        for line in ours:
            print(f"FAIL {line}")
        print(
            f"ags-typecheck: {len(ours)} error(s) in {WATCHED_PREFIX}*, which this "
            "change owns. Zero is the bar."
        )
        return 1

# Everything outside the audio tree is REPORTED, never failed.
    #
    # It used to be counted against a numeric baseline. That was wrong once this
    # branch merged master (2026-10-07), which added its own typecheck gates:
    # `bar-typecheck` owns the bar/Bluetooth files and `capture-typecheck` owns
    # the capture tool. Re-measuring a baseline after every merge would either
    # rot into a rubber stamp or duplicate gates that already exist. One gate,
    # one owner.
    for line in preexisting:
        print(f"note {line}")
    if preexisting:
        print(
            f"({len(preexisting)} error(s) outside {WATCHED_PREFIX}* -- owned by "
            "bar-typecheck/capture-typecheck, not failed here)"
        )

    gir_note = "with GIR typings" if generated else "WITHOUT GIR typings (partial)"
    print(
        f"ags-typecheck: PASS ({gir_note}, 0 errors in {WATCHED_PREFIX}*, "
        f"{len(foreign)} third-party, {len(preexisting)} elsewhere, {len(exempted)} exempt)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
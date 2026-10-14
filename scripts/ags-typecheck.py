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

So: zero errors in our files. Third-party noise is tolerated BY LOCATION
(``FOREIGN_MARKERS`` below), never by a numeric baseline that could silently
absorb a regression of our own, and our own files must be clean.

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

    python3 scripts/ags-typecheck.py [--root REPO_ROOT]

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
# third-party noise count against our own errors.
FOREIGN_MARKERS = (
    "node_modules/",
    "usr/share/ags/",
    "types/ags-girs/",
)

# The bar tree this gate owns. `dotfiles/config/ags/` is the AGS platform being
# extracted in place (spine AD-19/AD-20). The named extraction surfaces are
# `kit/`, `lib/`, `domains/` and `bar/`, but a bad extraction can touch any
# non-test file here (components/, services/, settings-panel/, the top-level
# entry points), so the WHOLE tree is watched rather than an enumerated list
# that rots as directories are added -- the same reason the capture config uses
# globs, not a file list.
#
# This deliberately OVERLAPS bar-typecheck: AD-19 requires BOTH typechecks to
# cover the extracted surface, so a regression fails under either gate, not only
# the one whose name happens to match the file. (Historically this gate watched
# only `audio/` and REPORTED everything else, on the theory that bar-typecheck
# owned it; that is exactly the gap AD-19 closes -- a bad extraction in `kit/`
# or `bar/` passed this gate silently.)
BAR_ROOT = "dotfiles/config/ags/"

# `tests/` is a SEPARATE tsc project owned by `make ags-test`, which compiles it
# against its own config with `@types/node`. Under this app config
# (`"types": []`) its `node:test`/`node:assert` imports cannot resolve (TS2307);
# those errors are not the bar's, so they are reported and never failed here.
# Keyed to the TREE that owns them, not a filename allowlist: a new test file is
# covered the moment it appears, and the exemption cannot silently absorb a real
# regression in a shipped source file.
BAR_TESTS = "dotfiles/config/ags/tests/"

# Individually exempted inside the watched tree. Each entry must name a
# byte-identical line on master -- verified by checking out master's copy and
# re-running this gate -- so these cannot silently absorb a regression.
#
# Empty: the only entry (audio/state.ts:63) was retired by
# finish-audio-bar-migration, which deleted state.ts — the entry and the file
# disappeared together, as their comment promised.
EXEMPT: dict[str, set[str]] = {}


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

    ours, foreign, tests_owned, exempted = [], [], [], []
    for line in errors:
        if any(m in line for m in FOREIGN_MARKERS):
            foreign.append(line)
            continue
        if BAR_ROOT in line and BAR_TESTS not in line:
            # "file(line,col): error ..." -- match the position against EXEMPT.
            path, _, rest = line.partition("(")
            # rest is "63,7): error TS..." -- drop the trailing ")".
            pos = rest.partition(":")[0].rstrip(")") if rest else ""
            if pos in EXEMPT.get(path, set()):
                exempted.append(line)
                continue
            ours.append(line)
            continue
        tests_owned.append(line)

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
            f"ags-typecheck: {len(ours)} error(s) in the extracted bar tree "
            f"({BAR_ROOT}*, excluding {BAR_TESTS}). Zero is the bar."
        )
        return 1

    # Only the tests/ sub-project is REPORTED, never failed: it is a different
    # tsc project (owned by `make ags-test`), and its `node:test` imports cannot
    # resolve under this app config's `"types": []`. Everything else in the bar
    # tree above is `ours` and fails.
    for line in tests_owned:
        print(f"note {line}")
    if tests_owned:
        print(
            f"({len(tests_owned)} error(s) under {BAR_TESTS}* -- owned by "
            "`make ags-test`, which compiles them with its own config and "
            "@types/node; not failed here)"
        )

    gir_note = "with GIR typings" if generated else "WITHOUT GIR typings (partial)"
    print(
        f"ags-typecheck: PASS ({gir_note}, 0 errors in the extracted bar tree "
        f"({BAR_ROOT}*, excluding {BAR_TESTS}), {len(foreign)} third-party, "
        f"{len(tests_owned)} in tests/, {len(exempted)} exempt)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
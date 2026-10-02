#!/usr/bin/env python3
"""Hexagonal-layering gate for the capture tool GUI.

"Refactor only, zero behavior change" is otherwise unenforceable prose, so each
assertion here maps to a concrete way this refactor could quietly become a
rewrite:

  1. LAYERING -- ``domain/`` and ``ports/`` import no GTK, no GLib, no
     ``ags/*`` and no subprocess surface. The domain is pure data + pure
     functions; if it can reach the filesystem it is no longer testable
     without a live GLib.
  2. ADAPTER OWNERSHIP -- only ``adapters/`` (and the composition root) call
     ``execAsync`` / ``GLib.file_*``. A UI file shelling out directly is a
     second, un-gated capture path that bypasses the request->argv port.
  3. REQUEST->ARGV PURITY -- exactly ONE module translates a capture request
     into argv. Two layouts sharing an engine is only real while they share
     that translator; a second one is how the GIF size token ("75", not "75%")
     and the audio vocabulary (mic vs microphone) drift apart.
  4. NO DEAD SCAFFOLD -- ``ui/ScreenshotView.tsx``, ``ui/RecordingView.tsx``
     and ``controllers/*`` are the unused pre-hexagonal stubs. They are deleted
     by this refactor; leaving them re-creates a parallel, unimplemented
     abstraction next to the real one.
  5. PROVISIONING REGISTRATION -- every file under the capture tool appears in
     ``gui_tools_app_files``. Placement is PER-FILE, so an unregistered file
     silently never deploys (the exact silent-no-op class of bug the role's
     own header warns about).
  6. CLASSIC-LAYOUT PARITY -- the set of CSS class tokens the classic layout
     uses, and the set ``style.css`` styles, are snapshotted in
     ``capture-classic-parity.json`` and must be UNCHANGED. The refactor moves
     code between modules; it must not add, drop, or rename a single class.
     This is the mechanical form of "the current tool is unchanged".

Checks 1-4 are expected to FAIL against the pre-refactor tree (one 1865-line
inline file imports everything); that is the point -- the gate bites before it
bites you. Check 5 passes today and must keep passing.

Usage: ``python3 scripts/capture-hexagonal-gate.py [--root REPO_ROOT] [--update-parity]``
Exit 0 = gate green. Exit 1 = violations, each printed naming file and line.
Exit 2 = the parity baseline is missing (run with --update-parity once).

Stdlib only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOL = "src/gui-tools/capture-tool"
VARS = "src/provisioning/ansible/roles/gui_tools/vars/main.yml"
PARITY = "scripts/capture-classic-parity.json"

#: Files that must exist after the refactor. The layer dirs are the hexagon;
#: the absence of ``controllers/`` is check 4.
REQUIRED_LAYERS = ("domain", "ports", "adapters")

#: Dead pre-hexagonal scaffolding. Deliberately listed: the gate's job is to
#: keep it deleted, not to notice it later.
DEAD_SCAFFOLD = (
    f"{TOOL}/ui/ScreenshotView.tsx",
    f"{TOOL}/ui/RecordingView.tsx",
    f"{TOOL}/controllers/CaptureController.ts",
    f"{TOOL}/controllers/ScreenshotController.ts",
    f"{TOOL}/controllers/RecordingController.ts",
    f"{TOOL}/controllers/TargetResolver.ts",
)

#: Import specifiers forbidden in the pure layers. ``gi://`` covers GLib/Gio,
#: ``ags/`` covers the GTK bindings and the process module.
FORBIDDEN_IN_PURE = re.compile(r"""(?:from\s+["'](?:ags/|gi://)|require\(\s*["'](?:ags/|gi://))""")

#: I/O calls that belong to adapters only. ``GLib.getenv``/``get_home_dir`` are
#: environment reads, not persistence, and are allowed in the composition root.
IO_IN_ADAPTERS = re.compile(
    r"""execAsync|GLib\.file_(?:get_contents|set_contents|test)|GLib\.mkdir_with_parents"""
)

#: Noise tokens inside style.css that are prose or the palette recipe, not
#: class selectors (rofi colors.rasi, the GTK4 node-type suffix, the mockup
#: vocabulary named in the header comment).
CSS_NOISE = frozenset({"css", "html", "rasi", "on", "toggle", "Switch"})

CLASS_ATTR = re.compile(r'class="([^"]*)"')
ADD_CSS_CLASS = re.compile(r'add_css_class\(\s*"([^"]*)"\s*\)')
CSS_SELECTOR = re.compile(r"(?<![\w-])\.([a-zA-Z][\w-]*)")


class Report:
    """Collects violations so one run reports every problem, not just the first."""

    def __init__(self) -> None:
        self.violations: list[str] = []
        self.checks: list[str] = []

    def fail(self, check: str, path: str, detail: str) -> None:
        self.violations.append(f"[{check}] {path}: {detail}")

    def ok(self, message: str) -> None:
        self.checks.append(message)


def source_files(root: Path, layer: str) -> list[Path]:
    d = root / TOOL / layer
    if not d.is_dir():
        return []
    return sorted([*d.glob("*.ts"), *d.glob("*.tsx")])


def check_layering(root: Path, report: Report) -> None:
    """Check 1: domain/ and ports/ stay pure."""
    for layer in ("domain", "ports"):
        files = source_files(root, layer)
        if not files:
            report.fail(
                "layering",
                f"{TOOL}/{layer}/",
                f"layer directory is missing or empty -- the hexagon has no {layer}",
            )
            continue
        for path in files:
            rel = path.relative_to(root)
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                m = FORBIDDEN_IN_PURE.search(line)
                if m:
                    report.fail(
                        "layering",
                        f"{rel}:{lineno}",
                        f"pure layer imports {m.group(0)!r} -- no GTK/GLib/ags/* in {layer}/",
                    )
        report.ok(f"check 1: {layer}/ is pure ({len(files)} file(s))")


def check_adapter_ownership(root: Path, report: Report) -> None:
    """Check 2: persistence and process spawning live in adapters/."""
    leaks = 0
    for layer in ("ui", "domain", "ports"):
        for path in source_files(root, layer):
            rel = path.relative_to(root)
            for lineno, line in enumerate(path.read_text().splitlines(), 1):
                m = IO_IN_ADAPTERS.search(line)
                if m:
                    report.fail(
                        "adapter-ownership",
                        f"{rel}:{lineno}",
                        f"{m.group(0)!r} in {layer}/ -- persistence and spawning belong in adapters/",
                    )
                    leaks += 1
    adapters = source_files(root, "adapters")
    if not adapters:
        report.fail(
            "adapter-ownership",
            f"{TOOL}/adapters/",
            "no adapter module -- the ports have no implementation",
        )
    else:
        report.ok(f"check 2: adapter layer present ({len(adapters)} file(s)); {leaks} UI leak(s)")


def check_single_argv_translator(root: Path, report: Report) -> None:
    """Check 3: exactly one request->argv translator across the whole tool."""
    hits = []
    for path in sorted((root / TOOL).rglob("*.ts")) + sorted((root / TOOL).rglob("*.tsx")):
        rel = path.relative_to(root)
        # A translator names the binary as an argv element and is not itself the
        # launcher: the launcher receives an argv from its caller.
        if re.search(r'"capture-tool"\s*,\s*"screenshot"', path.read_text()) or re.search(
            r'"capture-tool"\s*,\s*"start"', path.read_text()
        ):
            hits.append(rel)
    if not hits:
        report.fail(
            "argv-translator",
            f"{TOOL}/",
            "no request->argv translator found -- expected a pure module that builds "
            "[capture-tool, screenshot|start, ...] from a request object",
        )
    elif len(hits) > 1:
        report.fail(
            "argv-translator",
            ", ".join(str(h) for h in hits),
            f"{len(hits)} modules build capture argv -- layouts must share ONE translator "
            "or the GIF size token and audio vocabulary drift",
        )
    else:
        report.ok(f"check 3: single argv translator at {hits[0]}")


def check_no_dead_scaffold(root: Path, report: Report) -> None:
    """Check 4: the unused pre-hexagonal stubs stay deleted."""
    present = [p for p in DEAD_SCAFFOLD if (root / p).exists()]
    if present:
        for p in present:
            report.fail(
                "no-dead-scaffold",
                p,
                "unused pre-hexagonal stub -- deleted by this refactor; keeping it "
                "re-creates a parallel unimplemented abstraction",
            )
    else:
        report.ok("check 4: dead scaffold absent")


def check_provisioning(root: Path, report: Report) -> None:
    """Check 5: every capture file is registered for per-file placement."""
    vars_text = (root / VARS).read_text()
    registered = set(re.findall(r"source:\s*(src/gui-tools/capture-tool/\S+?),\s*dest:", vars_text))
    on_disk = {
        str(p.relative_to(root))
        for p in (root / TOOL).rglob("*")
        if p.is_file()
        # tests/ and README are not deployed; the bin/ CLI is placed by cli_tools.
        and "tests" not in p.parts
        and p.name != "README.md"
        and "bin" not in p.parts
    }
    missing = sorted(on_disk - registered)
    stale = sorted(registered - on_disk)
    for m in missing:
        report.fail(
            "provisioning",
            m,
            "not in gui_tools_app_files -- per-file placement means it will NEVER deploy",
        )
    for s in stale:
        report.fail("provisioning", s, "registered in gui_tools_app_files but not on disk")
    if not missing and not stale:
        report.ok(f"check 5: all {len(on_disk)} deployed file(s) registered")


def snapshot_classes(root: Path) -> dict:
    """The class-token sets the classic layout uses and style.css styles."""
    tsx = (root / TOOL / "ui" / "CaptureWindow.tsx")
    sources = [tsx] if tsx.exists() else []
    # Post-refactor the classic view may live elsewhere; scan every TSX in ui/.
    if not sources:
        sources = sorted((root / TOOL / "ui").rglob("*.tsx"))
    used: set[str] = set()
    for path in sources:
        text = path.read_text()
        for m in CLASS_ATTR.finditer(text):
            used.update(m.group(1).split())
        for m in ADD_CSS_CLASS.finditer(text):
            used.update(m.group(1).split())
    css = (root / TOOL / "style.css").read_text()
    styled = set(CSS_SELECTOR.findall(css)) - CSS_NOISE
    return {
        "used": sorted(used),
        "styled": sorted(styled),
        "sources": sorted(str(p.relative_to(root)) for p in sources),
    }


def check_classic_parity(root: Path, report: Report, update: bool) -> int:
    """Check 6: the classic layout's class vocabulary is unchanged."""
    baseline_path = root / PARITY
    current = snapshot_classes(root)

    if update:
        baseline_path.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n")
        report.ok(f"check 6: parity baseline written to {PARITY}")
        return 0

    if not baseline_path.exists():
        report.violations.append(
            f"[classic-parity] {PARITY}: baseline missing -- run with --update-parity once "
            "to record the pre-refactor class vocabulary"
        )
        return 2

    baseline = json.loads(baseline_path.read_text())
    drift = False
    for key in ("used", "styled"):
        before = set(baseline.get(key, []))
        after = set(current[key])
        for token in sorted(after - before):
            report.fail("classic-parity", key, f"token {token!r} is new -- not in the baseline")
            drift = True
        for token in sorted(before - after):
            report.fail("classic-parity", key, f"token {token!r} disappeared -- refactor must not drop classes")
            drift = True
    if not drift:
        report.ok(
            f"check 6: classic layout vocabulary unchanged "
            f"({len(current['used'])} used / {len(current['styled'])} styled)"
        )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    ap.add_argument(
        "--update-parity",
        action="store_true",
        help="record the current class vocabulary as the parity baseline",
    )
    args = ap.parse_args()
    root = Path(args.root).resolve()

    if not (root / TOOL).is_dir():
        print(f"FAIL: {TOOL} not found under {root}", file=sys.stderr)
        return 1

    report = Report()
    print(f"capture hexagonal gate -- {root}")
    print()

    missing_layers = [l for l in REQUIRED_LAYERS if not (root / TOOL / l).is_dir()]
    if missing_layers:
        report.fail(
            "layering",
            f"{TOOL}/",
            f"missing layer director{'y' if len(missing_layers) == 1 else 'ies'}: "
            + ", ".join(missing_layers)
            + " -- the refactor has not been performed yet",
        )

    check_layering(root, report)
    check_adapter_ownership(root, report)
    check_single_argv_translator(root, report)
    check_no_dead_scaffold(root, report)
    check_provisioning(root, report)
    rc = check_classic_parity(root, report, args.update_parity)

    for line in report.checks:
        print(f"  ok   {line}")
    print()
    if report.violations:
        print(f"FAIL: {len(report.violations)} violation(s)")
        for v in report.violations:
            print(f"  {v}")
        return max(rc, 1)
    print("PASS: capture hexagonal gate green")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
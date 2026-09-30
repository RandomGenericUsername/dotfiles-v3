#!/usr/bin/env python3
"""Speed-test notification mock<->code parity harness.

Mechanical gate against mock/code drift: every ``class="..."`` token used by
each anchored mock state in
``openspec/changes/add-speedtest-notifications/mock.html`` must either

  1. be mock-only scaffolding (ALLOWLIST, with a reason), or
  2. resolve to a class shipped in the notifications ``style.css``
     (as a selector) or in the state's mapped source file(s) (as a class
     literal) -- directly, or via CLASS_MAP when the shipped code uses a
     renamed/restructured equivalent, or
  3. be a mock token the shipped code implements as a runtime CALL rather than
     a selector (RUNTIME_BEHAVIOUR: the literal must appear in the mapped
     sources), or
  4. be a tracked real gap (KNOWN_GAPS: mock concept with no shipped
     equivalent yet; printed as a loud warning with its owning change --
     the owning change must clear the entry when it ships the class).

Anything else -- a missing anchor id, a missing mapped file, or a token with
no coverage -- fails loudly (exit non-zero) naming the state and token.

Modelled line-for-line on ``scripts/wifi-mock-parity.py`` (same tables, same
per-token resolution order, same loud-failure wording, same report shape, same
exit codes) so the maintainer already knows how to read its output and how to
clear a gap. The three additions are each forced by something the wifi mock
does not have, and each is commented at its table.

DELIBERATE ASYMMETRY: this harness was written BEFORE its implementation
(Phase 1 gates Phase 3), so it had to be provable on day one. KNOWN_GAPS ships
PRE-SEEDED with every token the mock declares, so the first run exits 0 **with
every token reported as a known-gap warning**. That is the point: a parity gate
that passes because nothing matched is worse than no gate. Phases 2-4 drain
KNOWN_GAPS as each class ships, and the final gate requires zero entries.

Usage: ``python3 scripts/speedtest-mock-parity.py [--root REPO_ROOT]``
Exit 0 = gate green (known gaps, if any, are listed as warnings).
Exit 1 = missing anchor(s), missing mapped file(s), or uncovered token(s);
details on stdout.

Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Contract tables (also the living documentation of mock state -> code owner)
# --------------------------------------------------------------------------

# Stable mock anchors that MUST exist as id="...".
ANCHORS = [
    "state-stc-running",
    "state-stc-result",
    "state-stc-error",
    "state-stc-setting",
]

# State -> owning source file(s). Paths are repo-relative here, unlike the wifi
# harness's AGS-relative form, because this mock spans TWO roots: the
# notifications app under src/gui-tools/ and the panel under
# dotfiles/config/ags.
#
# Only files that CARRY CLASSES are mapped. `lib/speedtest-events.ts` is the
# event client and ships no classes (it mirrors `wallpaper-events.ts`, which the
# wifi harness never maps for the same reason), so listing it would add a
# mapped-file existence dependency the mock never exercises.
STATE_TSX = {
    "state-stc-running": [
        "src/gui-tools/notifications/ui/NotificationsWindow.tsx",  # the progress card
    ],
    "state-stc-result": [
        "src/gui-tools/notifications/ui/NotificationsWindow.tsx",
    ],
    "state-stc-error": [
        "src/gui-tools/notifications/ui/NotificationsWindow.tsx",
    ],
    "state-stc-setting": [
        "dotfiles/config/ags/components/wifi/WifiContent.tsx",  # the toggle row
        #: The switch's class lives on the primitive, not the row — the same
        #: split the wifi harness encodes by mapping several files per state.
        "dotfiles/config/ags/components/primitives/WifiSwitch.tsx",
    ],
}

# The stylesheet is checked globally for every state (as in the wifi harness,
# where style.css is "always checked globally as well").
CSS_FILE = "src/gui-tools/notifications/style.css"

# Mock-only scaffolding: mock page chrome / structural glue with no shipped
# counterpart. Anything here must NEVER represent a shippable feature. The wifi
# harness makes the same call for `net-info`/`divider`/`open`.
ALLOWLIST = {
    "col": "mock page per-state column wrapper; shipped as notif-stack",
    "state-label": "mock page per-state caption bar",
    "settings": "mock settings-panel frame; shipped as the settings-panel surface",
    "s-div": "mock hairline separator; shipped separation via container spacing",
    "sm": "mock-only small-toggle size; the shipped panel has ONE switch size (.settings-switch) for every row",
    "heading": "mock flex heading row; shipped card lays out via box spacing",
    "copy": "mock text column; shipped as the anonymous hexpand box (title/body mapped individually)",
    "note": "mock page design-rationale block, not a component",
    "warn": "mock page inline warning text colour, not a component",
}

# Mock token -> shipped equivalent class (mock is generic; shipped code follows
# the wallpaper/card naming conventions). The shipped class must exist in the
# notifications style.css or the state's mapped source file(s); a broken mapping
# fails the gate rather than being trusted. Format: token -> (shipped class,
# note).
CLASS_MAP = {
    "stack": ("notif-stack", "mock column renamed per the shipped stack class"),
    "notif-card": ("notif-card", "shipped verbatim; reused base class, not a new one"),
    "progress-card": ("speedtest-progress-card", "modelled on wallpaper-progress-card"),
    "tile": ("speedtest-progress-tile", "same plate treatment as the wallpaper card's icon tile"),
    "title": ("notif-title", "renamed per the shipped card naming"),
    "body": ("notif-body", "renamed per the shipped card naming"),
    "close": ("wallpaper-progress-close", "same close-button treatment as the wallpaper card"),
    "bar": ("speedtest-progress-bar", "modelled on wallpaper-progress-bar"),
    "steps": ("speedtest-progress-steps", "modelled on wallpaper-progress-steps"),
    "step": ("speedtest-progress-step", "modelled on wallpaper-progress-step"),
    "m": ("speedtest-progress-marker", "modelled on wallpaper-progress-marker"),
    "grid": ("speedtest-progress-grid", "the three-cell result grid"),
    "cell": ("speedtest-progress-cell", "shipped result cell"),
    "hl": ("speedtest-progress-cell.highlight", "accent-tinted measurement cell"),
    "ok": ("speedtest-progress-tile.busy", "the mock's result tint IS its in-flight tint (same accent), so the code ships one modifier, not a dead second one"),
    "fail": ("speedtest-progress-tile.failed", "caution slot, matching the wallpaper card's .failed naming"),
    "k": ("speedtest-progress-cell-key", "result cell's key line"),
    "v": ("speedtest-progress-cell-value", "result cell's value line"),
    "footer": ("speedtest-progress-footer", "modelled on wallpaper-progress-footer"),
    "s-title": ("settings-stc-title", "renamed per settings-* convention"),
    "s-row": ("settings-stc-row", "renamed per settings-* convention"),
    "s-label": ("settings-stc-label", "renamed per settings-* convention"),
    "s-sub": ("settings-stc-hint", "row sub-label reuses the shipped hint slot"),
    "toggle": ("settings-switch", "native Gtk.Switch restyle, not a custom div"),
}

# Mock state modifiers the shipped code expresses as a CSS state class on the
# SAME shipped class rather than as a selector block (the mock's
# `class="step active"` becomes `.speedtest-progress-step.active`). Resolved by
# construction so a NEW modifier in the mock is still caught — and only against
# bases whose mock token is actually present in that state, so a stray modifier
# cannot pass on an unrelated base's rule.
# mock base -> shipped base.
STATE_MODIFIER_BASES = {
    "tile": "speedtest-progress-tile",
    "step": "speedtest-progress-step",
    "cell": "speedtest-progress-cell",
    "toggle": "settings-switch",
}

# Mock tokens that are not classes at all: the mock DRAWS a behaviour the
# shipped code implements as a runtime call. Gated the same way as everything
# else (the literal must exist in the mapped sources), so a mock promise can
# never quietly drop out of the implementation.
# Format: mock token -> (search literal, note).
RUNTIME_BEHAVIOUR = {
    "pulse": (
        ".pulse()",
        "mock draws the indeterminate pulse as a CSS animation; shipped pulses "
        "the Gtk.ProgressBar from the 100ms timer, so the promise is a CALL",
    ),
}

# Real gaps: mock concepts with NO shipped class yet. Non-failing but printed as
# loud warnings; the owning change must ship the class and clear the entry
# (moving the token to CLASS_MAP). Format: token -> owner.
#
# DAY-ONE STATE: pre-seeded with every token the mock declares, so the first run
# proves the harness actually resolves and reports instead of passing vacuously.
# Phases 2-4 drain this table as each class ships; the final gate requires zero
# entries.
#
# KNOWN_GAPS is checked BEFORE CLASS_MAP, a deliberate deviation from the wifi
# harness (where KNOWN_GAPS is always empty, so the ordering never surfaces).
# It has to be: a day-one KNOWN_GAPS entry and a day-one CLASS_MAP entry for
# the same token say the same thing, and with CLASS_MAP first the mapping branch
# would FAIL on a class that has simply not shipped yet. The two tables are
# kept DISJOINT, so a token can never be reported as a warning while its
# mapping sits untested behind it.
# Real gaps: mock concepts with NO shipped class yet. Non-failing but printed as
# loud warnings; the owning change must ship the class and clear the entry
# (moving the token to CLASS_MAP). Format: token -> owner.
#
# DRAINED. Phase 3 shipped the card classes and phase 4 shipped the toggle row,
# so every token now resolves through CLASS_MAP, RUNTIME_BEHAVIOUR, the
# modifier resolver, or the ALLOWLIST — the table is empty and the final gate
# requires zero entries. Re-seed it if a later change adds a class: the harness
# must prove it still fails, and an empty table plus a passing run proves
# nothing on its own (see the three scenarios asserted against this harness).
KNOWN_GAPS = {
}

MOCK_FILE = "openspec/changes/add-speedtest-notifications/mock.html"

CLASS_ATTR_RE = re.compile(r'class="([^"]+)"')
CLASSLIST_OP_RE = re.compile(r"""classList\.(?:add|toggle|remove)\(\s*['"]([^'"]+)['"]""")
INNERHTML_CLASS_RE = re.compile(r"""class=\\?["']([^"'\\]+)""")


def css_has_class(css_text: str, token: str) -> bool:
    """True if ``.token`` appears as a CSS selector (incl. compounds)."""
    return re.search(r"\." + re.escape(token) + r"(?![\w-])", css_text) is not None


def source_tokens(text: str) -> set[str]:
    """Whole class tokens statically visible in a source file.

    Collects ``class="a b"`` / ``class={"a b"}`` / ``css_classes={["a"]}``
    literals and ``add_css_class("a")`` calls, plus tokens from any quoted
    string mentioning a ``settings-``/``notif-``/``speedtest-`` class, which
    covers computed class strings such as ``"settings-stc-run-btn running"``.
    (The wifi harness covers the settings-* half of that; the other two
    prefixes are this mock's conventions.)
    """
    toks: set[str] = set()
    for m in re.finditer(r'class(?:Name)?=\{?"([^"}]*)"\}?', text):
        toks.update(m.group(1).split())
    for m in re.finditer(r'css_classes=\{?\[([^\]]*)\]', text):
        toks.update(re.findall(r'"([^"]+)"', m.group(1)))
    for m in re.finditer(r'add_css_class\(\s*"([^"]+)"\s*\)', text):
        toks.add(m.group(1))
    for m in re.finditer(r'"([^"]*(?:settings-|notif-|speedtest-)[^"]*)"', text):
        toks.update(m.group(1).split())
    return toks


def main() -> int:
    ap = argparse.ArgumentParser(description="Speed-test notification mock<->code parity gate")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    mock_path = root / MOCK_FILE
    css_path = root / CSS_FILE

    failures: list[str] = []
    warnings: list[str] = []

    if not mock_path.is_file():
        print(f"MISSING mock file: {mock_path}")
        return 1
    html = mock_path.read_text()
    if not css_path.is_file():
        print(f"MISSING css file: {css_path}")
        return 1
    css_text = css_path.read_text()

    # --- 1. anchors -------------------------------------------------------
    missing_anchors = [a for a in ANCHORS if f'id="{a}"' not in html]
    for a in missing_anchors:
        failures.append(f'MISSING anchor id="{a}" in {MOCK_FILE}')

    # --- 2. per-state spans + class tokens --------------------------------
    positions = sorted((html.find(f'id="{a}"'), a) for a in ANCHORS if f'id="{a}"' in html)
    spans: dict[str, str] = {}
    for i, (pos, anchor) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(html)
        spans[anchor] = html[pos:end]

    state_tokens: dict[str, set[str]] = {}
    for anchor, span in spans.items():
        toks: set[str] = set()
        for m in CLASS_ATTR_RE.finditer(span):
            toks.update(m.group(1).split())
        state_tokens[anchor] = toks

    # demo <script>-added classes (the mock's `on` via classList.toggle) --
    # these must already appear in markup, but assert them explicitly.
    script_added: set[str] = set()
    for script in re.findall(r"<script>(.*?)</script>", html, re.S):
        for m in CLASSLIST_OP_RE.finditer(script):
            script_added.update(m.group(1).split())
        for m in INNERHTML_CLASS_RE.finditer(script):
            script_added.update(m.group(1).split())
    # (informational: every script-added class must be a markup token too)
    markup_all: set[str] = set().union(*state_tokens.values()) if state_tokens else set()
    for tok in sorted(script_added):
        if tok not in markup_all:
            warnings.append(f"demo-script class '{tok}' not present in markup (checked globally)")

    # --- 3. shipped-code token sets ----------------------------------------
    src_texts: dict[str, str] = {}
    for anchor, files in STATE_TSX.items():
        for f in files:
            if f not in src_texts:
                p = root / f
                if not p.is_file():
                    failures.append(f"MISSING mapped file: {f} (needed by {anchor})")
                    src_texts[f] = ""
                else:
                    src_texts[f] = p.read_text()
    src_sets = {f: source_tokens(t) for f, t in src_texts.items()}

    def shipped_in_state(token: str, anchor: str) -> bool:
        # A dotted token is a COMPOUND selector (`.base.modifier`): every part
        # must be present, so a mapping can name a state modifier without the
        # harness having to know which file it lives in.
        parts = token.split(".")
        if all(css_has_class(css_text, part) for part in parts):
            return True
        return any(
            all(part in src_sets[f] for part in parts)
            for f in STATE_TSX[anchor]
            if f in src_sets
        )

    def resolve_modifier(tok: str, anchor: str) -> str | None:
        """Resolve a bare state modifier (`active`, `done`, `on`, ...).

        Returns a human-readable note when the modifier resolves, else None.
        """
        present = state_tokens.get(anchor, set())
        for mock_base, shipped_base in STATE_MODIFIER_BASES.items():
            if mock_base not in present:
                continue
            if css_has_class(css_text, f"{shipped_base}.{tok}"):
                return f"mock '{tok}' on '{mock_base}'; shipped as {shipped_base}.{tok}"
        return None

    # --- 4. per-state, per-token assertions ---------------------------------
    n_checked = n_allow = 0
    for anchor in list(STATE_TSX):
        if anchor not in state_tokens:
            continue  # anchor already reported missing above
        for tok in sorted(state_tokens[anchor]):
            if tok in ALLOWLIST:
                n_allow += 1
                continue
            # KNOWN_GAPS before CLASS_MAP (see the table comment): a known gap
            # and a class mapping for the same token are the same statement, and
            # the tables are kept disjoint.
            if tok in KNOWN_GAPS:
                warnings.append(
                    f"KNOWN-GAP state={anchor} mock-token='{tok}' owner={KNOWN_GAPS[tok]}"
                )
                continue
            if tok in CLASS_MAP:
                shipped, _note = CLASS_MAP[tok]
                n_checked += 1
                if not shipped_in_state(shipped, anchor):
                    failures.append(
                        f"UNCOVERED state={anchor} mock-token='{tok}' "
                        f"(mapped to shipped '{shipped}', which is missing from "
                        f"{CSS_FILE} and {STATE_TSX[anchor]})"
                    )
                continue
            if tok in RUNTIME_BEHAVIOUR:
                literal, _note = RUNTIME_BEHAVIOUR[tok]
                n_checked += 1
                if not any(
                    literal in src_texts[f] for f in STATE_TSX[anchor] if f in src_texts
                ):
                    failures.append(
                        f"UNCOVERED state={anchor} token='{tok}' "
                        f"(expected the runtime call {literal} in {STATE_TSX[anchor]})"
                    )
                continue
            modifier = resolve_modifier(tok, anchor)
            if modifier is not None:
                n_checked += 1
                continue
            n_checked += 1
            if not shipped_in_state(tok, anchor):
                failures.append(
                    f"UNCOVERED state={anchor} token='{tok}' "
                    f"(absent from {CSS_FILE} and {STATE_TSX[anchor]})"
                )

    # --- 5. report ----------------------------------------------------------
    for w in warnings:
        print(f"WARNING {w}")
    if failures:
        for f in failures:
            print(f"FAIL {f}")
        print(
            f"speedtest-mock-parity: {len(failures)} failure(s), "
            f"{n_checked} token(s) checked"
        )
        return 1
    print(
        f"speedtest-mock-parity: PASS "
        f"({len(state_tokens)} state(s), {n_checked} token(s) checked, "
        f"{n_allow} scaffolding skipped, {len(warnings)} known-gap warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

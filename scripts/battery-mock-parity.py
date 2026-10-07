#!/usr/bin/env python3
"""Battery panel mock<->code parity harness (openspec: add-battery-status-panel).

Mechanical gate against mock/code drift: every ``class="..."`` token used by
each anchored mock state in ``battery-popup-mockup.html`` must either

  1. be mock-only scaffolding (ALLOWLIST, with a reason), or
  2. resolve to a class shipped in ``dotfiles/config/ags/style.css``
     (as a selector) or in the state's mapped TSX file(s) (as a class
     literal) -- directly, or via CLASS_MAP when the shipped code uses a
     renamed/restructured equivalent (the systematic ``settings-*`` /
     ``battery-*`` conventions), or
  3. be a mock state that the shipped code expresses as a PSEUDO-CLASS
     (PSEUDO_STATES: ``dim`` is ``.battery-profile:disabled``), or
  4. be a mock promise the shipped code keeps as a CALL or a table entry
     (PROMISES: the literal must exist in the named file), or
  5. be a tracked real gap (KNOWN_GAPS: mock concept with no shipped
     equivalent yet; printed as a loud warning with its owning change --
     the owning change must clear the entry when it ships the class).

Anything else -- a missing anchor id, a missing mapped file, or a token with
no coverage -- fails loudly (exit non-zero) naming the state and the token.

WHY A PANEL-ONLY GATE when ``scripts/wifi-mock-parity.py`` already exists.
The Wi-Fi gate proves the Wi-Fi mock against the Wi-Fi code. It cannot prove
anything about the battery panel: the two share ``style.css`` and the
``settings-*`` vocabulary, but the panel's own claims (the hero number, the
``++`` tier rendering, the deep-link footer, the bar icon's anchoring) live in
files the Wi-Fi gate does not map. A gate that only ever checks the mock it
was written next to is how a second mock arrives unguarded.

Modeled line-for-line on ``scripts/wifi-mock-parity.py`` -- same ANCHORS /
STATE_TSX / ALLOWLIST / CLASS_MAP / KNOWN_GAPS tables, same CSS path
resolution, same per-token resolution order, same loud-failure wording, same
report shape, same exit codes -- so the maintainer already knows how to read
its output. The three additions (PSEUDO_STATES, PROMISES, and the compound
selector handling lifted from ``speedtest-mock-parity.py``) are each forced by
something the Wi-Fi mock does not have, and each is commented at its table.

A GATE THAT HAS NEVER BEEN SEEN TO FAIL IS NOT A GATE. The negative case for
this harness -- a mock class with no CSS rule and no mapped TSX literal -- was
executed and fails loudly; see the report for the output.

Usage: ``python3 scripts/battery-mock-parity.py [--root REPO_ROOT]``
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

# Stable mock anchors that MUST exist as id="..." in the mock.
ANCHORS = [
    "state-1-discharging",
    "state-2-charging",
    "state-3-no-estimate",
    "state-4-daemon-absent",
    "state-5-tier-selected",
    "bar-battery-indicator",
]

# State -> owning TSX file(s). Paths are relative to the AGS root, exactly as in
# the Wi-Fi harness, because every mapped file here lives under
# dotfiles/config/ags/ -- this mock spans ONE root.
#
# Only files that CARRY CLASSES are mapped. `presentation.ts` carries none, so
# it appears only in PROMISES below (where it is checked for a literal, not for
# a class); listing it here too would add a mapped-file existence dependency
# the per-token check never exercises.
STATE_TSX = {
    "state-1-discharging": [
        "components/battery/BatteryContent.tsx",  # header, hero, rows, footer
        "components/battery/BatteryPopup.tsx",  # window chrome + surface
    ],
    "state-2-charging": [
        "components/battery/BatteryContent.tsx",
    ],
    "state-3-no-estimate": [
        "components/battery/BatteryContent.tsx",  # the no-estimate fallback
    ],
    "state-4-daemon-absent": [
        "components/battery/BatteryContent.tsx",  # insensitive rows
        "services/power-service.ts",  # powerReady / activeProfile=null
    ],
    "state-5-tier-selected": [
        "components/battery/BatteryContent.tsx",  # ProfileLabel's `++` split
    ],
    "bar-battery-indicator": [
        "bar/widgets/battery.tsx",  # the bar icon + its anchoring controller
    ],
}

# The stylesheet is checked globally for every state (as in the Wi-Fi harness,
# where style.css is "always checked globally as well").
CSS_FILE = "dotfiles/config/ags/style.css"
AGS_DIR = "dotfiles/config/ags"

# Mock-only scaffolding: mock page chrome / structural glue with no shipped
# counterpart. Anything here must NEVER represent a shippable feature.
ALLOWLIST = {
    "anchor-index": "mock page anchor legend block, not a component",
    "bottom-bar": "mock page layout wrapper for side-by-side states",
    "state-label": "mock page per-state caption bar",
    "mock-popup": "mock popup frame; shipped as window.settings-panel + .settings-surface",
    "deeplink-copy": "footer text column; shipped as an anonymous hexpand box (label/note mapped individually)",
    "bar-demo": "mock-only bar illustration wrapper (the shipped bar uses the shared .widget chrome)",
    "bar-caption": "mock-only caption for the bar illustration",
    "anchor-guide": "mock-only annotation of the anchoring/clamp rule",
}

# Mock token -> shipped equivalent class (the shipped code renames and
# restructures: every mock token is generic, every shipped class is in the
# `settings-*` / `battery-*` vocabulary). The shipped class must exist in
# style.css or the state's mapped TSX file(s); a broken mapping fails the gate
# rather than being trusted. A dotted shipped value is a COMPOUND selector
# (`.base.modifier`): every part must be present.
# Format: token -> (shipped class, note).
CLASS_MAP = {
    "mock-header": ("settings-nav-header", "renamed per the settings-* convention"),
    "mock-header-title": ("settings-nav-title", "renamed per the settings-* convention"),
    "mock-header-icon": ("battery-header-icon", "shipped verbatim"),
    "mock-pct": ("battery-header-pct", "shipped verbatim"),
    "hero": ("battery-hero", "shipped verbatim"),
    "hero-primary": ("battery-hero-primary", "shipped verbatim"),
    "hero-sub": ("battery-hero-sub", "shipped verbatim"),
    "divider": ("settings-divider", "renamed per the settings-* convention"),
    "section-label": ("settings-section-label", "renamed per the settings-* convention"),
    "profile-list": ("battery-profile-list", "shipped verbatim"),
    # The row is BOTH: `settings-net` supplies the row chrome and the `.sel`
    # selected treatment, `battery-profile` supplies this panel's tighter
    # metrics and the `:disabled` dimming. Naming only one of them would let
    # the panel drop the other unnoticed.
    "profile-row": ("settings-net.battery-profile", "row chrome + this panel's metrics"),
    "profile-icon": ("battery-profile-icon", "shipped verbatim"),
    "profile-label": ("battery-profile-label", "base name cell; the `++` suffix is a second label"),
    "profile-tier": ("battery-profile-tier", "the `++` suffix as a styled label, not a badge"),
    "selected": ("settings-net.sel", "the modifier `isActiveProfile` feeds"),
    "deeplink": ("battery-deeplink", "shipped verbatim"),
    "deeplink-label": ("settings-wifi-settings-label", "reuses the settings deep-link label slot"),
    "deeplink-note": ("settings-wifi-settings-note", "reuses the settings deep-link note slot"),
    "deeplink-arrow": ("settings-wifi-settings-arrow", "reuses the settings deep-link chevron"),
    "bar-icon": ("widget-icon", "the status-bar glyph uses the shared widget-icon class"),
}

# Mock states that the shipped code expresses as a GTK/ CSS PSEUDO-CLASS rather
# than as a class token. Resolved by requiring the exact compound selector in
# style.css, so a renamed rule still fails the gate.
# Format: mock token -> (required selector text in style.css, note).
PSEUDO_STATES = {
    "dim": (
        ".battery-profile:disabled",
        "mock opacity modifier; shipped as the insensitive-button pseudo-class "
        "gated by `sensitive={powerReady}`",
    ),
}

# Mock promises the shipped code keeps as a CALL, a table entry or a regex
# rather than as a CSS class. Gated the same way as everything else (the
# literal must exist in the named file), so the mock's promise can never
# quietly drop out of the implementation.
# Format: mock token -> LIST of (AGS-relative file, literal, note). A list, not
# a single tuple, because one mock token can carry more than one promise --
# `profile-tier` is BOTH "the glyph is the base profile's" (a regex in
# presentation.ts) and "the suffix is its own label" (a class literal in the
# widget). A dict of tuples would silently keep only the last of them.
PROMISES = {
    "profile-tier": [
        (
            "components/battery/presentation.ts",
            'return id.replace(/\\+\\+$/, "").toLowerCase()',
            "the `++` rows reuse the BASE profile's glyph, so the tier is "
            "carried by text alone; a distinct icon or a graphical badge would "
            "break this",
        ),
        (
            "components/battery/BatteryContent.tsx",
            'class="battery-profile-tier"',
            "the tier suffix is its own label so style.css can tint it "
            "@color_13, instead of a Pango string that would hard-code the "
            "colour",
        ),
    ],
    "selected": [
        (
            "components/battery/BatteryContent.tsx",
            "isActiveProfile(activeProfile() ??",
            "which row is lit is the pure predicate's decision, not the "
            "widget's",
        ),
    ],
    "hero-primary": [
        (
            "components/battery/BatteryContent.tsx",
            "formatBatteryTime(",
            "the hero number and its sub-word come from one presentation "
            "call, so the number and the word that gives it meaning cannot "
            "disagree",
        ),
    ],
}

# Real gaps: mock concepts with NO shipped class yet. Non-failing but printed as
# loud warnings; the owning change must ship the class and clear the entry
# (moving the token to CLASS_MAP). Format: token -> owner.
#
# EMPTY, and that is the claim the negative test checks: this harness has been
# seen to FAIL on an uncovered token, so an empty table plus a passing run is
# evidence the mock matches the code rather than evidence the gate is inert.
KNOWN_GAPS = {
}

MOCK_FILE = "battery-popup-mockup.html"

CLASS_ATTR_RE = re.compile(r'class="([^"]+)"')
CLASSLIST_OP_RE = re.compile(r"""classList\.(?:add|toggle|remove)\(\s*['"]([^'"]+)['"]""")
INNERHTML_CLASS_RE = re.compile(r"""class=\\?["']([^"'\\]+)""")


def css_has_class(css_text: str, token: str) -> bool:
    """True if ``.token`` appears as a CSS selector (incl. compounds)."""
    return re.search(r"\." + re.escape(token) + r"(?![\w-])", css_text) is not None


def tsx_tokens(text: str) -> set[str]:
    """Whole class tokens statically visible in a TSX file.

    Collects ``class="a b"`` / ``class={"a b"}`` literals plus tokens from any
    quoted string mentioning a ``settings-``/``battery-`` class (covers computed
    class strings such as ``"settings-net battery-profile sel"``).
    """
    toks: set[str] = set()
    for m in re.finditer(r'class(?:Name)?=\{?"([^"}]*)"\}?', text):
        toks.update(m.group(1).split())
    for m in re.finditer(r'"([^"]*(?:settings-|battery-)[^"]*)"', text):
        toks.update(m.group(1).split())
    return toks


def main() -> int:
    ap = argparse.ArgumentParser(description="Battery panel mock<->code parity gate")
    ap.add_argument("--root", default=None, help="repo root (default: parent of scripts/)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    mock_path = root / MOCK_FILE
    css_path = root / CSS_FILE
    ags_root = root / AGS_DIR

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

    # demo <script>-added classes -- these must already appear in markup, but
    # assert them explicitly.
    script_added: set[str] = set()
    for script in re.findall(r"<script>(.*?)</script>", html, re.S):
        for m in CLASSLIST_OP_RE.finditer(script):
            script_added.update(m.group(1).split())
        for m in INNERHTML_CLASS_RE.finditer(script):
            script_added.update(m.group(1).split())
    markup_all: set[str] = set().union(*state_tokens.values()) if state_tokens else set()
    for tok in sorted(script_added):
        if tok not in markup_all:
            warnings.append(f"demo-script class '{tok}' not present in markup (checked globally)")

    # --- 3. shipped-code token sets ----------------------------------------
    tsx_texts: dict[str, str] = {}
    for anchor, files in STATE_TSX.items():
        for f in files:
            if f not in tsx_texts:
                p = ags_root / f
                if not p.is_file():
                    failures.append(f"MISSING mapped TSX file: {AGS_DIR}/{f} (needed by {anchor})")
                    tsx_texts[f] = ""
                else:
                    tsx_texts[f] = p.read_text()
    tsx_sets = {f: tsx_tokens(t) for f, t in tsx_texts.items()}

    def shipped_in_state(token: str, anchor: str) -> bool:
        # A dotted token is a COMPOUND selector (`.base.modifier`): every part
        # must be present, so a mapping can name a state modifier without the
        # harness having to know which file it lives in.
        parts = token.split(".")
        if all(css_has_class(css_text, part) for part in parts):
            return True
        return any(
            all(part in tsx_sets[f] for part in parts)
            for f in STATE_TSX[anchor]
            if f in tsx_sets
        )

    # --- 4. per-state, per-token assertions ---------------------------------
    n_checked = n_allow = 0
    for anchor in list(STATE_TSX):
        if anchor not in state_tokens:
            continue  # anchor already reported missing above
        for tok in sorted(state_tokens[anchor]):
            if tok in ALLOWLIST:
                n_allow += 1
                continue
            if tok in KNOWN_GAPS:
                warnings.append(
                    f"KNOWN-GAP state={anchor} mock-token='{tok}' owner={KNOWN_GAPS[tok]}"
                )
                continue
            # A token can carry a CLASS promise, a PSEUDO-CLASS promise and a
            # LITERAL promise at once -- `profile-tier` is a shipped class AND a
            # promise that the glyph stays the BASE profile's. So the three
            # branches are ADDITIVE, never `elif`/`continue`, or an entry in one
            # table is silently swallowed by a hit in an earlier one. (Built
            # exclusive first and negative-tested: the CLASS_MAP branch
            # short-circuited the literal check and the gate stayed GREEN
            # against exactly the regression the promise exists to catch.)
            resolved = False

            if tok in PSEUDO_STATES:
                resolved = True
                selector, _note = PSEUDO_STATES[tok]
                n_checked += 1
                if selector not in css_text:
                    failures.append(
                        f"UNCOVERED state={anchor} token='{tok}' "
                        f"(expected the selector '{selector}' in {CSS_FILE})"
                    )

            if tok in CLASS_MAP:
                resolved = True
                shipped, _note = CLASS_MAP[tok]
                n_checked += 1
                if not shipped_in_state(shipped, anchor):
                    failures.append(
                        f"UNCOVERED state={anchor} mock-token='{tok}' "
                        f"(mapped to shipped '{shipped}', which is missing from "
                        f"{CSS_FILE} and {STATE_TSX[anchor]})"
                    )

            if tok in PROMISES:
                resolved = True
                for rel, literal, _why in PROMISES[tok]:
                    n_checked += 1
                    p = ags_root / rel
                    if not p.is_file():
                        failures.append(
                            f"MISSING promise file: {AGS_DIR}/{rel} (promised by token '{tok}')"
                        )
                    elif literal not in p.read_text():
                        failures.append(
                            f"UNCOVERED state={anchor} token='{tok}' "
                            f"(expected the literal {literal!r} in {AGS_DIR}/{rel})"
                        )

            if resolved:
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
        print(f"battery-mock-parity: {len(failures)} failure(s), {n_checked} token(s) checked")
        return 1
    print(
        f"battery-mock-parity: PASS "
        f"({len(state_tokens)} state(s), {n_checked} token(s) checked, "
        f"{n_allow} scaffolding skipped, {len(warnings)} known-gap warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
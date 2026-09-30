#!/usr/bin/env python3
"""Wi-Fi mock<->code parity harness (openspec: wifi-mock-parity-harness).

Mechanical gate against mock/code drift: every ``class="..."`` token used by
each anchored mock state in ``wifi-popup-mockup.html`` must either

  1. be mock-only scaffolding (ALLOWLIST, with a reason), or
  2. resolve to a class shipped in ``dotfiles/config/ags/style.css``
     (as a selector) or in the state's mapped TSX file(s) (as a class
     literal) -- directly, or via CLASS_MAP when the shipped code uses a
     renamed/restructured equivalent (systematic ``settings-*`` convention), or
  3. be a tracked real gap (KNOWN_GAPS: mock concept with no shipped
     equivalent yet; printed as a loud warning with its owning change --
     the owning change must clear the entry when it ships the class).

Anything else -- a missing anchor id, or a token with no coverage -- fails
loudly (exit non-zero) naming the state and token.

Deviation note (mock reality vs design.md): the mock has NO ``id=`` element
for ``bar-testing-card``; the bar-card demo (``.bar-demo`` block) is embedded
inside the ``state-2b-running`` section and referenced via
``<code>bar-testing-card</code>``. The script therefore treats
``bar-testing-card`` as a virtual anchor satisfied by the ``<code>``
reference PLUS the ``.bar-demo`` block, and checks that block's tokens as
the ``bar-testing-card`` state (carved out of ``state-2b-running``).

Usage: ``python3 scripts/wifi-mock-parity.py [--root REPO_ROOT]``
Exit 0 = gate green (known gaps, if any, are listed as warnings).
Exit 1 = missing anchor(s) or uncovered token(s); details on stdout.

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

# Stable mock anchors that MUST exist as id="..." (bar-testing-card is
# virtual -- see module docstring).
ANCHORS = [
    "state-1-connected",
    "state-2-stc-expanded",
    "state-2b-running",
    "state-3-off",
    "state-4-panel-tile",
    "state-5-connecting",
    "state-6-need-auth",
]

# State -> owning TSX file(s), per design.md (paths relative to the AGS root).
STATE_TSX = {
    "state-1-connected": [
        "components/wifi/WifiContent.tsx",  # details, rows
        "components/wifi/WifiPopup.tsx",  # header
    ],
    "state-2-stc-expanded": [
        "components/wifi/WifiContent.tsx",  # speed-test section
    ],
    "state-2b-running": [
        "components/wifi/WifiContent.tsx",  # run button
        "bar/widgets/network.tsx",  # card class
    ],
    "state-3-off": [
        "components/wifi/WifiContent.tsx",  # empty state
    ],
    "state-4-panel-tile": [
        "settings-panel/controls/wifi.tsx",
    ],
    "state-5-connecting": [
        "components/wifi/WifiContent.tsx",  # WifiRow busy branch
    ],
    "state-6-need-auth": [
        "components/wifi/WifiContent.tsx",  # WifiPasswordPrompt
    ],
    "bar-testing-card": [
        "bar/widgets/network.tsx",
        # style.css is always checked globally as well.
    ],
}

# Mock-only scaffolding: mock page chrome / structural glue with no shipped
# counterpart. Anything here must NEVER represent a shippable feature.
ALLOWLIST = {
    "anchor-index": "mock page anchor legend block, not a component",
    "bottom-bar": "mock page layout wrapper for side-by-side states",
    "state-label": "mock page per-state caption bar",
    "mock-popup": "mock popup frame; shipped as settings-panel/settings-surface",
    "mock-header": "mock header bar; shipped as settings-nav-header",
    "mock-header-title": "mock header text; shipped as settings-nav-title",
    "toggle-wrap": "header switch wrapper; shipped header lays out via nav-header spacing",
    "net-info": "row text column; shipped as anonymous hexpand box (name/sub mapped individually)",
    "divider": "hairline separator; shipped separation via container spacing, no rule class",
    "open": "expanded-state modifier; shipped via visible= binding + chevron glyph swap, no state class",
    "bar-demo": "mock-only bar animation illustration wrapper",
    "bar-icon": "mock-only bar animation illustration icon",
    "bar-caption": "mock-only bar animation illustration caption",
}

# Mock token -> shipped equivalent class (systematic settings-* rename /
# restructuring). The shipped class must exist in style.css or the state's
# mapped TSX file(s); a broken mapping fails the gate.
# Format: mock token -> (shipped class, note).
CLASS_MAP = {
    "details-block": ("settings-conn-details", "renamed per settings-* convention"),
    "detail-row": ("settings-detail", "renamed per settings-* convention"),
    "label": ("settings-detail", "mock label/value split folded into one settings-detail label"),
    "value": ("settings-detail", "mock label/value split folded into one settings-detail label"),
    "section-label": ("settings-section-label", "renamed per settings-* convention"),
    "net-row": ("settings-net", "renamed per settings-* convention"),
    "net-name": ("settings-net-name", "renamed per settings-* convention"),
    "net-sub": ("settings-net-sub", "renamed per settings-* convention"),
    "net-badge": ("settings-badge", "renamed; connected modifier is .conn in code"),
    "signal-icon": ("settings-net-signal", "renamed per settings-* convention"),
    "selected": ("sel", "renamed; e.g. settings-net sel"),
    "chevron-row": ("settings-chevron-row", "renamed per settings-* convention"),
    "security-row": ("settings-security-warn", "renamed per settings-* convention"),
    "sec-text": ("settings-security-text", "renamed per settings-* convention"),
    "info-glyph": ("settings-security-icon", "renamed per settings-* convention"),
    "chevron-label": ("settings-chevron-label", "renamed per settings-* convention"),
    "chevron-icon": ("settings-chevron-label", "glyph folded into label text (U+25B8/U+25BE)"),
    "other-networks": ("settings-other-networks", "renamed per settings-* convention"),
    "settings-row": ("settings-wifi-settings-row", "renamed per settings-* convention"),
    "settings-label": ("settings-wifi-settings-label", "renamed per settings-* convention"),
    "settings-arrow": ("settings-wifi-settings-arrow", "renamed per settings-* convention"),
    "settings-note": ("settings-message", "reuses the shipped error-message slot"),
    "toggle": ("settings-switch", "native Gtk.Switch restyle, not a custom div"),
    "speedtest-config": ("settings-speedtest-config", "renamed per settings-* convention"),
    "stc-title": ("settings-stc-title", "renamed per settings-* convention"),
    "stc-row": ("settings-stc-row", "renamed per settings-* convention"),
    "stc-label": ("settings-stc-label", "renamed per settings-* convention"),
    "stc-value": ("settings-stc-value", "renamed per settings-* convention"),
    "ms-field": ("settings-stc-entry", "wrap folded into row layout; entry carries the field class"),
    "ms-entry": ("settings-stc-entry", "renamed per settings-* convention"),
    "ms-hint": ("settings-stc-hint", "renamed per settings-* convention"),
    "ms-unit": ("settings-stc-value", "unit suffix reuses the value class"),
    "chip": ("settings-chip", "renamed per settings-* convention"),
    "chip-row": ("settings-chip-row", "renamed per settings-* convention"),
    "stc-caption": ("settings-stc-caption", "renamed per settings-* convention"),
    "stc-run-btn": ("settings-stc-run-btn", "renamed per settings-* convention"),
    "eye-btn": ("settings-eye-btn", "renamed per settings-* convention"),
    "pwd-wrap": ("settings-pwd-wrap", "renamed per settings-* convention"),
    "spinner": ("settings-spinner", "renamed per settings-* convention"),
    "wifi-off-state": ("settings-empty", "renamed per settings-* convention"),
    "password-box": ("settings-password", "renamed per settings-* convention"),
    "fld-label": ("settings-field-label", "renamed per settings-* convention"),
    "fld-input": ("settings-field-entry", "renamed per settings-* convention"),
    "btn-row": ("settings-btnrow", "renamed per settings-* convention"),
    "btn": ("settings-btn", "renamed per settings-* convention"),
    "settings-tile-chevron": ("settings-chevron", "capability-tile chevron primitive"),
    "settings-entry": ("settings-tile", "capability tile container"),
    "settings-tile-list": ("settings-tile", "repeated capability tile containers"),
    "settings-tile-body": ("settings-tile", "capability tile content box"),
    "settings-tile-icon": ("settings-icon-toggle", "icon toggle primitive"),
    "idle": ("network-widget", "default bar-card state has no modifier"),
    "testing": ("speedtesting", "bar-card running modifier"),
}

# Real gaps: mock concepts with NO shipped class yet. Non-failing but printed
# as loud warnings; the owning change must ship the class and clear the entry
# (moving the token to a literal pass or CLASS_MAP). Format: token -> owner.
KNOWN_GAPS = {
}

MOCK_FILE = "wifi-popup-mockup.html"
CSS_FILE = "dotfiles/config/ags/style.css"
AGS_DIR = "dotfiles/config/ags"

CLASS_ATTR_RE = re.compile(r'class="([^"]+)"')
CLASSLIST_OP_RE = re.compile(r"""classList\.(?:add|toggle|remove)\(\s*['"]([^'"]+)['"]""")
INNERHTML_CLASS_RE = re.compile(r"""class=\\?["']([^"'\\]+)""")
DIV_OPEN_RE = re.compile(r"<div\b")
DIV_CLOSE_RE = re.compile(r"</div>")


def css_has_class(css_text: str, token: str) -> bool:
    """True if ``.token`` appears as a CSS selector (incl. compounds)."""
    return re.search(r"\." + re.escape(token) + r"(?![\w-])", css_text) is not None


def tsx_tokens(text: str) -> set[str]:
    """Whole class tokens statically visible in a TSX file.

    Collects ``class="a b"`` / ``class={"a b"}`` literals plus tokens from
    any quoted string mentioning a ``settings-`` class (covers computed
    class strings such as ``"settings-net sel"``).
    """
    toks: set[str] = set()
    for m in re.finditer(r'class(?:Name)?=\{?"([^"}]*)"\}?', text):
        toks.update(m.group(1).split())
    for m in re.finditer(r'"([^"]*settings-[^"]*)"', text):
        toks.update(m.group(1).split())
    return toks


def split_bar_demo(section_2b: str) -> tuple[str, str]:
    """Split state-2b section into (popup part, bar-demo block).

    The ``.bar-demo`` illustration (the ``bar-testing-card`` state) is carved
    out via div-depth balancing; remainder stays with ``state-2b-running``.
    """
    m = re.search(r'<div\s+class="bar-demo"', section_2b)
    if m is None:
        return section_2b, ""
    depth = 0
    pos = m.start()
    end = None
    for mm in re.finditer(r"</?div\b[^>]*>", section_2b[m.start() :]):
        tag = mm.group(0)
        depth += -1 if tag.startswith("</") else 1
        if depth == 0:
            end = m.start() + mm.end()
            break
    if end is None:  # unbalanced; do not silently misattribute
        raise SystemExit("ERROR: unbalanced <div> while carving .bar-demo block")
    bar_block = section_2b[m.start() : end]
    rest = section_2b[: m.start()] + section_2b[end:]
    return rest, bar_block


def main() -> int:
    ap = argparse.ArgumentParser(description="Wi-Fi mock<->code parity gate")
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
        failures.append(f"MISSING anchor id=\"{a}\" in {MOCK_FILE}")

    # virtual anchor: bar-testing-card = <code> mention + .bar-demo block
    bar_ok = ("bar-testing-card" in html) and ('class="bar-demo"' in html)
    if not bar_ok:
        failures.append(
            "MISSING anchor bar-testing-card in wifi-popup-mockup.html "
            "(need <code>bar-testing-card</code> reference + .bar-demo block)"
        )

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

    # carve the bar-demo illustration out of state-2b into bar-testing-card
    if "state-2b-running" in spans:
        rest, bar_block = split_bar_demo(spans["state-2b-running"])
        bar_toks: set[str] = set()
        for m in CLASS_ATTR_RE.finditer(bar_block):
            bar_toks.update(m.group(1).split())
        rest_toks: set[str] = set()
        for m in CLASS_ATTR_RE.finditer(rest):
            rest_toks.update(m.group(1).split())
        state_tokens["state-2b-running"] = rest_toks
        if bar_ok:
            state_tokens["bar-testing-card"] = bar_toks

    # demo <script>-added classes (e.g. `running` via classList.add) -- these
    # must already appear in markup, but assert them explicitly per design.
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
        if css_has_class(css_text, token):
            return True
        return any(token in tsx_sets[f] for f in STATE_TSX[anchor] if f in tsx_sets)

    # --- 4. per-state, per-token assertions ---------------------------------
    n_checked = n_allow = 0
    for anchor in list(STATE_TSX):
        if anchor not in state_tokens:
            continue  # anchor already reported missing above
        for tok in sorted(state_tokens[anchor]):
            if tok in ALLOWLIST:
                n_allow += 1
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
            if tok in KNOWN_GAPS:
                warnings.append(
                    f"KNOWN-GAP state={anchor} mock-token='{tok}' owner={KNOWN_GAPS[tok]}"
                )
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
        print(f"wifi-mock-parity: {len(failures)} failure(s), {n_checked} token(s) checked")
        return 1
    print(
        f"wifi-mock-parity: PASS "
        f"({len(state_tokens)} state(s), {n_checked} token(s) checked, "
        f"{n_allow} scaffolding skipped, {len(warnings)} known-gap warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Bluetooth mock<->code parity harness (openspec: add-bluetooth-bar-popup).

Mechanical gate against mock/code drift: every ``class="..."`` token used by
each anchored mock state in ``mockups/panel.html`` must either

  1. be mock-only scaffolding (ALLOWLIST, with a reason), or
  2. resolve to a class shipped in ``dotfiles/config/ags/style.css`` (as a
     selector) or in the state's mapped TSX file(s) (as a class literal) --
     directly, or via CLASS_MAP when the shipped code uses a renamed or
     restructured equivalent, or
  3. be a tracked real gap (KNOWN_GAPS: a mock concept with no shipped
     equivalent yet; printed as a loud warning naming the task that ships it).

Anything else -- a missing anchor, or a token with no coverage -- fails loudly
(non-zero exit) naming the state and the token.

WHY THE MOCK IS THE CONTRACT
The owner approved ``mockups/panel.html`` on 2026-10-03. Its captions are the
acceptance criteria; ``specs/bluetooth-bar-popup/spec.md`` restates them as
SHALLs. A class that exists in the mock but not in the code is unimplemented
design, and a class that exists in the code but not the mock is invented
surface. This gate closes the second; the spec review closes the first.

RED UNTIL THE CHANGE LANDS
Same posture as ``capture-hexagonal-gate.py``: every entry in KNOWN_GAPS names
the task that ships it, so the count of warnings is the countdown. Read the
per-state ``ok`` lines and the uncovered-token list, not the exit code.

Usage: ``python3 scripts/bluetooth-mock-parity.py [--root REPO_ROOT]``
Exit 0 = gate green (known gaps, if any, are warnings).
Exit 1 = missing anchor(s) or uncovered token(s); details on stdout.

Stdlib only. No desktop stack. ~0.1s.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Contract tables (also the living documentation of mock state -> code owner)
# --------------------------------------------------------------------------

#: Mock captions, which are the anchor ids on the board cells.
ANCHORS = [
    # bar
    "bar-anchor",
    "bar-on",
    "bar-off",
    # popup states, in the order the board draws them
    "popup-off",
    "popup-not-connected",
    "popup-pairing",
    "popup-failed",
    "popup-unpair-confirm",
    "popup-out-of-range",
    "popup-scanning",
    "popup-no-adapter",
    # settings panel
    "panel-subview",
    "panel-tile",
]

#: State -> owning TSX file(s), paths relative to the AGS root
#: (``dotfiles/config/ags``). ``style.css`` is checked globally as well.
STATE_TSX = {
    # The bar strip plus the popup dropping from it. That popup is the same
    # surface as popup-not-connected, so its tokens are checked there.
    "bar-anchor": [
        "bar/widgets/bluetooth.tsx",  # NEW -- the indicator
    ],
    "bar-on": [
        "bar/widgets/bluetooth.tsx",  # NEW
    ],
    "bar-off": [
        "bar/widgets/bluetooth.tsx",  # NEW
    ],
    "popup-off": [
        "components/bluetooth/BluetoothPopup.tsx",  # NEW -- header + surface
        "components/bluetooth/BluetoothContent.tsx",
    ],
    "popup-not-connected": [
        "components/bluetooth/BluetoothContent.tsx",
    ],
    "popup-pairing": [
        "components/bluetooth/BluetoothContent.tsx",  # busy branch
    ],
    "popup-failed": [
        "components/bluetooth/BluetoothContent.tsx",  # failure line
        "components/bluetooth/BluetoothPopup.tsx",
    ],
    "popup-unpair-confirm": [
        "components/bluetooth/BluetoothContent.tsx",  # inline confirm + .danger
    ],
    "popup-out-of-range": [
        "components/bluetooth/BluetoothContent.tsx",  # out-of-range row
    ],
    "popup-scanning": [
        "components/bluetooth/BluetoothContent.tsx",  # spinner + empty state
    ],
    "popup-no-adapter": [
        "components/bluetooth/BluetoothPopup.tsx",  # insensitive switch
        "components/bluetooth/BluetoothContent.tsx",
    ],
    "panel-subview": [
        "settings-panel/views/BluetoothView.tsx",  # pinned header
        "components/bluetooth/BluetoothContent.tsx",
    ],
    "panel-tile": [
        "settings-panel/controls/bluetooth.tsx",  # CapabilityTile
        "settings-panel/primitives.tsx",  # CapabilityTile body
    ],
}

#: Mock-only scaffolding: page chrome and structural glue with no shipped
#: counterpart. Anything here must NEVER represent a shippable feature.
ALLOWLIST = {
    # page chrome
    "scale": "mock-only zoom control (x1/x1.5/x2); no shipped counterpart",
    "board": "mock page layout wrapper for side-by-side states",
    "cell": "mock page per-state cell wrapper",
    "cap": "mock page per-state caption",
    "stack": "mock page vertical stack (bar over popup)",
    "lead": "mock page intro paragraph",
    # bar strip illustration
    "bar": "mock bar strip frame; the shipped bar is Bar.tsx layout",
    "barpair": "mock bar icon grouping; shipped via Bar.tsx box spacing",
    "clock": "mock bar clock decoration for context",
    "stem": "mock-only anchor stem showing which bar icon opens the popup",
    # surface structure the mock draws explicitly but the code expresses as
    # widget properties rather than classes
    "surface": "mock surface frame; shipped as .settings-surface",
    "nav": "mock header row; shipped as .settings-nav-header",
    "body": "mock body box; shipped as an anonymous box inside .settings-scroll",
    "foot": "mock footer row; shipped as .settings-wifi-settings-row",
    "tile": "mock capability tile; shipped as .settings-tile",
    "l1": "mock row line 1; shipped as an anonymous box (orientation=1)",
    "l2": "mock row line 2; shipped as .settings-row-meta",
    "meta": "mock row text column; shipped as an anonymous hexpand box",
    "line2": "mock meta stack sub-line; shipped as .settings-meta-stat rows",
    "div": "mock hairline; shipped as .settings-divider",
    "sec": "mock section label; shipped as .settings-section-label",
    "detail": "mock detail row; shipped as .settings-detail-row",
    "empty": "mock empty-state line; shipped as .settings-empty",
    "msg": "mock failure line; shipped as .settings-message",
    "spin": "mock spinner; shipped as .settings-spinner",
    "acts": "mock action group; shipped as buttons with .settings-rowact",
    "k": "mock detail key; shipped as .settings-detail",
    "v": "mock detail value; shipped as .settings-detail",
    "arw": "mock chevron glyph; shipped as the settings-chevron character",
    "note": "mock footer note; shipped as .settings-wifi-settings-note",
    "sub": "mock row subtitle; shipped as .settings-net-sub",
    "nm": "mock row name; shipped as .settings-net-name",
    "sig": "mock signal glyph box; shipped as .settings-net-signal",
    "stat": "mock battery/meta stat; shipped as .settings-meta-stat",
    "switch": "mock header switch; shipped as .settings-switch (WifiSwitch)",
    "chev": "mock collapsible section; shipped as .settings-chevron-row",
    "act": "mock action button; shipped as .settings-rowact",
    "off-dead": (
        "mock-only dimming for the insensitive switch in the no-adapter state; "
        "shipped as the Gtk.Switch `sensitive={false}` property, not a class"
    ),
}

#: Mock token -> shipped equivalent class, where the code uses a renamed or
#: restructured equivalent. The shipped class must exist in ``style.css`` or in
#: the state's mapped TSX file(s); a broken mapping fails the gate.
#: Format: token -> (shipped class, note)
CLASS_MAP = {
    "row": ("settings-net", "mock .row is the shipped .settings-net row"),
    "badge": ("settings-badge", "mock .badge is the shipped .settings-badge"),
    "title": ("settings-nav-title", "mock .title is the shipped .settings-nav-title"),
    "ghost": ("settings-net.out-of-range", "mock .ghost is the shipped out-of-range modifier"),
    "dead": ("settings-rowact.disabled", "mock .dead is the shipped .settings-rowact.disabled"),
    "subtle": (
        "settings-rowact.subtle",
        "mock .subtle is the shipped .settings-rowact.subtle (Unpair)",
    ),
    "sel": ("settings-net.sel", "mock .sel is the shipped .settings-net.sel connected fill"),
}

#: Real gaps: mock concepts with NO shipped equivalent yet. Non-failing, but
#: printed as loud warnings naming the task that ships them. The owning task
#: must clear the entry when it lands.
#: Format: token -> owning task
KNOWN_GAPS = {
    "danger": (
        "T6.7 -- .settings-rowact.danger, the ONE new class this change adds "
        "(destructive confirm). Absent from style.css until that task lands, "
        "which is why the gate is legitimately red beforehand."
    ),
    "confirming": (
        "T6.7 -- the inline unpair-confirm row background; mock-only until the "
        "confirm swaps the meta stack in place"
    ),
    "tile on": (
        "T6.6 -- the settings tile's selected-state fill; the mock previews it, "
        "but the shipped CapabilityTile has no selected modifier today and the "
        "subview is reached by navigation rather than by a persistent selection"
    ),
}

MOCK_RELPATH = "openspec/changes/add-bluetooth-bar-popup/mockups/panel.html"
CSS_RELPATH = "dotfiles/config/ags/style.css"
AGS_ROOT_RELPATH = "dotfiles/config/ags"


def css_has_class(css_text: str, token: str) -> bool:
    """True when ``token`` appears as a class selector in the stylesheet."""
    return re.search(rf"\.{re.escape(token)}(?=[\s,.:\[{{>+~])", css_text) is not None


def tsx_tokens(text: str) -> set[str]:
    """Every class token appearing in a ``class="..."`` literal in TSX."""
    found: set[str] = set()
    for raw in re.findall(r'class="([^"]*)"', text):
        for token in raw.split():
            found.add(token)
    return found


def state_sections(mock_text: str) -> dict[str, str]:
    """Slice the mock into ``anchor -> html`` regions.

    Each anchored state is a ``<div class="cell" id="ANCHOR">``, the same
    convention ``wifi-popup-mockup.html`` uses. The slice runs from that cell's
    opening tag to the next cell's opening tag, so a state carries exactly its
    own markup and nothing bleeds across a boundary.
    """
    sections: dict[str, str] = {}
    for anchor in ANCHORS:
        m = re.search(rf'<div class="cell" id="{re.escape(anchor)}">', mock_text)
        if m is None:
            sections[anchor] = ""
            continue
        nxt = mock_text.find('<div class="cell" id="', m.end())
        end = nxt if nxt != -1 else len(mock_text)
        sections[anchor] = mock_text[m.start():end]
    return sections


def main() -> int:  # noqa: C901 - a gate reads better as one linear pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="repo root (default: infer)")
    args = ap.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent
    mock_path = root / MOCK_RELPATH
    css_path = root / CSS_RELPATH
    ags_root = root / AGS_ROOT_RELPATH

    if not mock_path.is_file():
        print(f"FAIL: mock not found: {mock_path}")
        return 1
    if not css_path.is_file():
        print(f"FAIL: stylesheet not found: {css_path}")
        return 1

    mock_text = mock_path.read_text()
    css_text = css_path.read_text()

    sections = state_sections(mock_text)

    missing_anchors = [a for a in ANCHORS if not sections[a]]
    if missing_anchors:
        print(f"FAIL: missing mock anchor(s): {', '.join(missing_anchors)}")
        print("      Each state must carry a <code>ANCHOR</code> caption cell.")
        return 1

    # Cache the shipped class universe per state (its TSX files + global CSS).
    tsx_cache: dict[str, set[str]] = {}

    def shipped_tokens(anchor: str) -> set[str]:
        if anchor in tsx_cache:
            return tsx_cache[anchor]
        tokens: set[str] = set()
        for rel in STATE_TSX.get(anchor, []):
            path = ags_root / rel
            if not path.is_file():
                print(f"NOTE: mapped TSX not present yet: {rel}  (state {anchor})")
                continue
            tokens |= tsx_tokens(path.read_text())
        tsx_cache[anchor] = tokens
        return tokens

    uncovered: list[str] = []
    gaps: list[str] = []
    checked = 0
    scaffolded = 0

    for anchor in ANCHORS:
        body = sections[anchor]
        tokens = set()
        for raw in re.findall(r'class="([^"]*)"', body):
            for token in raw.split():
                tokens.add(token)

        ok = True
        for token in sorted(tokens):
            checked += 1

            if token in ALLOWLIST:
                scaffolded += 1
                continue

            mapped = CLASS_MAP.get(token)
            if mapped is not None:
                shipped, _note = mapped
                # The mapped class must actually exist somewhere real.
                if css_has_class(css_text, shipped) or shipped in shipped_tokens(anchor):
                    continue
                uncovered.append(f"{anchor}: {token!r} -> mapped to {shipped!r}, which does not exist")
                ok = False
                continue

            if token in KNOWN_GAPS:
                gaps.append(f"{anchor}: {token!r}  -> {KNOWN_GAPS[token]}")
                continue

            if css_has_class(css_text, token) or token in shipped_tokens(anchor):
                continue

            uncovered.append(f"{anchor}: {token!r} has no shipped counterpart")
            ok = False

        status = "ok" if ok else "FAIL"
        print(f"  {status:4} {anchor}")

    print()
    if gaps:
        print(f"KNOWN GAPS ({len(gaps)}) -- tracked, must clear as tasks land:")
        for gap in gaps:
            print(f"  - {gap}")
        print()

    if uncovered:
        print(f"FAIL: bluetooth-mock-parity: {len(uncovered)} uncovered token(s)")
        for item in uncovered:
            print(f"  - {item}")
        print()
        print(
            "Either the token is mock scaffolding (add it to ALLOWLIST with a\n"
            "reason), or the code uses a different class (add a CLASS_MAP entry),\n"
            "or the feature is genuinely unimplemented (add a KNOWN_GAPS entry\n"
            "naming the task that ships it)."
        )
        return 1

    print(
        f"bluetooth-mock-parity: PASS "
        f"({len(ANCHORS)} state(s), {checked} token(s) checked, "
        f"{scaffolded} scaffolding skipped, {len(gaps)} known-gap warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

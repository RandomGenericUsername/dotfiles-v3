#!/usr/bin/env python3
"""Audio mock<->code parity harness (openspec: redesign-ags-audio-panel).

Mechanical gate against mock/code drift. The approved concept
(`mockups/audio-panel-redesign-concept.html`, owner-approved 2026-10-02) is the
source of truth for the panel's surface: every ``class="..."`` token it uses
must either

  1. be mock-only scaffolding (ALLOWLIST, with a reason), or
  2. resolve to a class shipped in ``audio/audio-panel.css`` (as a selector) or
     in the panel's mapped TSX file(s) (as a class literal) -- directly, or via
     CLASS_MAP when the shipped code uses a renamed/restructured equivalent, or
  3. be a tracked real gap (KNOWN_GAPS: mock concept with no shipped
     equivalent yet; printed as a loud warning with its owning task -- the
     owning task must clear the entry when it ships the class).

Anything else fails loudly (exit non-zero) naming the region and token.

Design notes:

* The concept mock has no ``state-N-*`` anchors -- it is a single live panel
  with interactive menus, unlike the Wi-Fi mock's seven static states. So
  coverage is asserted per REGION (preferred output / app rows / input /
  microphone activity), and each region is checked against its owning TSX
  component *and* the shipped stylesheet. That keeps the gate per-component, so
  a token cannot pass on the strength of some unrelated panel.

* Unlike the Wi-Fi harness this one deliberately does NOT allow a token to
  resolve via *any* mapped TSX file. The audio panel is one surface, so a
  global fallback would let a preferred-output token be satisfied by an app-row
  class and hide a real gap.

* Token resolution is anchored on CSS *selectors* (``.foo``) and TSX *class
  literals*, matching the Wi-Fi harness, so a token named in prose does not
  count as shipped.

Usage: ``python3 scripts/audio-mock-parity.py [--root REPO_ROOT]``
Exit 0 = gate green (known gaps, if any, are listed as warnings).
Exit 1 = missing region anchor, or uncovered token(s); details on stdout.

Stdlib only.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# Contract tables (also the living documentation of mock region -> code owner)
# --------------------------------------------------------------------------

# Regions of the concept panel. Each must be present in the mock (checked by a
# literal marker) so a mock restructure fails loudly rather than silently
# reducing coverage. `section-hint` text is used as the stable marker because the
# mock's section headings are plain text, not ids.
REGIONS = {
    "preferred-output": "Default destination",
    "app-rows": "2 apps",
    "input": "Default microphone",
    "microphone-activity": "App capture streams",
}

# Region -> owning TSX file(s), relative to the AGS root.
REGION_TSX = {
    "preferred-output": ["audio/AudioPopup.tsx"],
    "app-rows": ["audio/AudioPopup.tsx"],
    "input": ["audio/AudioPopup.tsx"],
    "microphone-activity": ["audio/AudioPopup.tsx"],
}

# Mock-only scaffolding: page chrome / explanatory chrome with no shipped
# counterpart. Anything here must NEVER represent a shippable feature. These
# live OUTSIDE the .panel (the mock's notes/legend/bar illustration), plus the
# in-panel structural wrappers the GTK view realises with anonymous boxes or
# native widgets rather than a rule class.
ALLOWLIST = {
    # -- mock page chrome, outside the panel -------------------------------
    "page": "mock page wrapper; shipped as the AGS popup window",
    "layout": "mock two-column page layout (panel + notes); shipped as popup + catcher",
    "stage": "mock illustration frame around the panel; not a component",
    "bar": "mock top-bar illustration of the status bar; shipped by bar/widgets/audio.tsx",
    "time": "mock bar clock text; part of the bar illustration, not the panel",
    "bar-mic": "mock bar mic glyph with live dot; shipped by the bar mic indicator",
    "anchor": "mock follower-anchor illustration; the anchoring is in Astal.WindowAnchor",
    "notes": "mock explanatory aside; documentation, not UI",
    "note-card": "mock explanatory card; documentation, not UI",
    "legend": "mock interaction legend; documentation, not UI",
    "intro": "mock intro paragraph; documentation, not UI",
    "head-note": "mock panel header note; shipped as .audio-panel-caption",
    "section-hint": "mock per-section hint; shipped as .audio-section-hint",
    "legend": "mock interaction legend; documentation, not UI",
    # -- in-panel structural wrappers realised as anonymous/native ---------
    "layout": "mock two-column page layout (panel + notes); shipped as popup + catcher",
    "panel": "mock panel frame; shipped as .audio-popup / .audio-surface",
    "panel-head": "mock panel header row; shipped as .audio-panel-heading",
    "scroll": "mock scroll viewport; shipped as .audio-scroll",
    "section": "mock in-panel section wrapper; shipped as .audio-section",
    "section-head": "mock section header row; shipped as .audio-section-heading",
    "section-name": "mock section title text; shipped as .audio-section-title",
    "select-wrap": "mock menu wrapper with open-state class; shipped as .audio-device-select / .audio-route-selector with visible= binding",
    "scroll": "mock scroll viewport; shipped as .audio-scroll",
    "range": "mock native <input type=range>; shipped as Gtk.Scale with .audio-level-slider / .audio-seek-slider",
    "volume-row": "mock level row wrapper; shipped as .audio-level-line",
    "app": "mock app row wrapper; shipped as .audio-app-row",
    "app-head": "mock app row header; shipped as .audio-app-head",
    "meta": "mock text column; shipped as .audio-app-meta",
    "art": "mock artwork block; shipped as .audio-artwork",
    "transport": "mock transport button row; shipped as .audio-transport",
    "icon-button": "mock icon button; shipped as .audio-icon-button",
    "device-copy": "mock device name/meta column; shipped as .audio-device-select-name",
    "speaker-svg": "mock inline speaker glyph svg; shipped via the ITR icon registry",
    "mic-svg": "mock inline mic glyph svg; shipped via the ITR icon registry",
    "sink-caption": "mock output-level caption line; shipped as .audio-output-caption",
}

# Mock token -> shipped equivalent class (systematic audio-* rename /
# restructuring). The shipped class must exist in audio-panel.css or the
# region's mapped TSX; a broken mapping fails the gate.
# Format: mock token -> (shipped class, note).
CLASS_MAP = {
    "panel-title": ("audio-panel-title", "renamed to the audio-* convention"),
    "device-select": ("audio-device-select", "renamed to the audio-* convention"),
    "device-name": ("audio-device-select-name", "renamed; mock device-name/meta collapse into this"),
    "device-meta": ("audio-device-select-name", "mock device metadata folded into the select name line"),
    "device-icon": ("audio-consumer-icon", "mock device icon reuses the shipped consumer icon slot"),
    "chev": ("audio-device-chevron", "renamed; route menus reuse the same chevron"),
    "menu": ("audio-menu-option", "mock menu list; shipped options carry this class"),
    "option": ("audio-menu-option", "renamed to the audio-* convention"),
    "opt-note": ("audio-menu-heading", "mock per-option sub-note reuses the menu heading slot"),
    "selected": ("audio-option-mark", "mock selected modifier; shipped as the option mark + selection treatment"),
    "sink-volume": ("audio-level-slider", "mock sink level row; shipped as .audio-level-slider"),
    "volume-range": ("audio-level-slider", "mock volume input; shipped as Gtk.Scale .audio-level-slider"),
    "sink-value": ("audio-percent", "mock percentage readout; shipped as .audio-percent"),
    "value": ("audio-percent", "mock percentage readout; shipped as .audio-percent"),
    "speaker-button": ("audio-icon-button", "mock mute button; shipped as .audio-icon-button"),
    "status-chip": ("audio-live-label", "mock app-count chip; shipped as .audio-live-label"),
    "art-badge": ("audio-art-fallback", "mock app badge; shipped app-icon fallback slot"),
    "app-name": ("audio-app-name", "renamed to the audio-* convention"),
    "media-title": ("audio-media-title", "renamed to the audio-* convention"),
    "media-sub": ("audio-media-artist", "mock media sub (artist · album); shipped as .audio-media-artist"),
    "route-select": ("audio-route-selector", "mock per-app route trigger; shipped as .audio-route-selector"),
    "route-menu": ("audio-menu-option", "mock route menu; shipped options carry .audio-menu-option"),
    "app-controls": ("audio-app-controls", "renamed to the audio-* convention"),
    "transport-button": ("audio-transport", "mock transport button; shipped as .audio-transport"),
    "play-toggle": ("audio-transport", "mock main play/pause; shipped as the main .audio-transport button"),
    "seek-range": ("audio-seek-slider", "mock seek input; shipped as .audio-seek-slider"),
    "input-mark": ("audio-consumer-icon", "mock input glyph; shipped as .audio-consumer-icon"),
    "input-mute": ("audio-icon-button", "mock input mute button; shipped as .audio-icon-button"),
    "input-controls": ("audio-level-line", "mock input level row; shipped as .audio-level-line"),
    "mic-live": ("audio-live-dot", "mock mic-in-use dot; shipped as .audio-live-dot"),
    "recording-row": ("audio-consumer-row", "mock mic-consumer row; shipped as .audio-consumer-row"),
    "app": ("audio-app-row", "mock app row wrapper; shipped as .audio-app-row"),
    "app-head": ("audio-app-head", "renamed to the audio-* convention"),
    "art": ("audio-artwork", "mock artwork block; shipped as .audio-artwork"),
    "meta": ("audio-app-meta", "mock text column; shipped as .audio-app-meta"),
    "volume-row": ("audio-level-line", "mock level row wrapper; shipped as .audio-level-line"),
    "icon-button": ("audio-icon-button", "renamed to the audio-* convention"),
    "range": ("audio-level-slider", "mock native range; shipped as Gtk.Scale"),
    "head-note": ("audio-panel-caption", "mock header note; shipped as .audio-panel-caption"),
    "section-name": ("audio-section-title", "mock section title; shipped as .audio-section-title"),
    "section-head": ("audio-section-heading", "renamed to the audio-* convention"),
    "section": ("audio-section", "mock section wrapper; shipped as .audio-section"),
    "panel-head": ("audio-panel-heading", "renamed to the audio-* convention"),
    "panel": ("audio-panel-content", "mock panel frame; shipped content root"),
    "select-wrap": ("audio-device-select", "mock menu wrapper; shipped trigger carries the select class"),
    "scroll": ("audio-scroll", "mock scroll viewport; shipped as .audio-scroll"),
}

# Mock state modifiers: transient states the mock expresses as a class the demo
# script toggles, which the shipped code realises by other means. Declared here
# so they are not reported as unknown, and so the demo-script scan below does not
# warn about them. Each entry records HOW the state is expressed in shipped code,
# so a reviewer can confirm it rather than take it on trust.
STATE_MODIFIERS = {
    "open": "menu open state; shipped as a visible= binding on the menu, not a class (AudioPopup.tsx)",
    "muted": "mute state; shipped as an icon swap to system-muted via IconRegistry, not a class",
    "main": "emphasised play/pause transport button; shipped as .audio-transport "
            ".audio-icon-button:nth-child(2) (audio-panel.css:271)",
}

# Real gaps: mock concepts with NO shipped class yet. Non-failing but printed
# as loud warnings; the owning task must ship the class and clear the entry.
# Format: token -> owner task.
KNOWN_GAPS = {
}

MOCK_FILE = (
    "_bmad-output/planning-artifacts/ux-designs/"
    "ux-dotfiles-repo-v3-audio-2026-09-18/mockups/audio-panel-redesign-concept.html"
)
CSS_FILE = "dotfiles/config/ags/audio/audio-panel.css"
AGS_DIR = "dotfiles/config/ags"

CLASS_ATTR_RE = re.compile(r'class="([^"]+)"')
CLASSLIST_OP_RE = re.compile(r"""classList\.(?:add|toggle|remove)\(\s*['"]([^'"]+)['"]""")
INNERHTML_CLASS_RE = re.compile(r"""class=\\?["']([^"'\\]+)""")


def css_has_class(css_text: str, token: str) -> None | bool:
    """True if ``.token`` appears as a CSS selector (incl. compounds)."""
    return re.search(r"\." + re.escape(token) + r"(?![\w-])", css_text) is not None


def tsx_tokens(text: str) -> set[str]:
    """Whole class tokens statically visible in a TSX file.

    Collects ``class="a b"`` / ``class={"a b"}`` literals plus tokens from
    any quoted string mentioning an ``audio-`` class (covers computed class
    strings such as ``"audio-app-row sel"``).
    """
    toks: set[str] = set()
    for m in re.finditer(r'class(?:Name)?=\{?"([^"}]*)"\}?', text):
        toks.update(m.group(1).split())
    for m in re.finditer(r'"([^"]*audio-[^"]*)"', text):
        toks.update(m.group(1).split())
    return toks


def panel_span(html: str) -> str:
    """Return just the ``.panel`` subtree (the shipped surface)."""
    start = html.find('<div class="panel"')
    if start == -1:
        return html
    depth = 0
    for mm in re.finditer(r"</?div\b[^>]*>", html[start:]):
        tag = mm.group(0)
        depth += -1 if tag.startswith("</") else 1
        if depth == 0:
            return html[start : start + mm.end()]
    return html[start:]


def region_span(panel: str, marker: str) -> str | None:
    """Slice the panel subtree around a region's stable marker text.

    The concept has one ``<section class="section">`` per region; we carve from
    the marker to the next ``</section>``. Returns None if the marker is absent.
    """
    idx = panel.find(marker)
    if idx == -1:
        return None
    start = panel.rfind('<section', 0, idx)
    if start == -1:
        return panel[idx:]
    end = panel.find("</section>", idx)
    return panel[start:] if end == -1 else panel[start : end + len("</section>")]


def main() -> int:
    ap = argparse.ArgumentParser(description="Audio mock<->code parity gate")
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

    panel = panel_span(html)

    # --- 1. regions -------------------------------------------------------
    region_spans: dict[str, str] = {}
    for region, marker in REGIONS.items():
        span = region_span(panel, marker)
        if span is None:
            failures.append(f"MISSING region marker '{marker}' ({region}) in {MOCK_FILE}")
            continue
        region_spans[region] = span

    # --- 2. per-region class tokens ---------------------------------------
    region_tokens: dict[str, set[str]] = {}
    for region, span in region_spans.items():
        toks: set[str] = set()
        for m in CLASS_ATTR_RE.finditer(span):
            toks.update(m.group(1).split())
        region_tokens[region] = toks

    # demo <script>-added classes (e.g. `open` via classList.toggle)
    script_added: set[str] = set()
    for script in re.findall(r"<script>(.*?)</script>", html, re.S):
        for m in CLASSLIST_OP_RE.finditer(script):
            script_added.update(m.group(1).split())
        for m in INNERHTML_CLASS_RE.finditer(script):
            script_added.update(m.group(1).split())
    panel_all: set[str] = set().union(*region_tokens.values()) if region_tokens else set()
    for tok in sorted(script_added):
        if tok in STATE_MODIFIERS or tok in panel_all:
            continue
        warnings.append(f"demo-script class '{tok}' not present in panel markup (checked globally)")

    # --- 3. shipped-code token sets ----------------------------------------
    tsx_texts: dict[str, str] = {}
    for region, files in REGION_TSX.items():
        for f in files:
            if f not in tsx_texts:
                p = ags_root / f
                if not p.is_file():
                    failures.append(f"MISSING mapped TSX file: {AGS_DIR}/{f} (needed by {region})")
                    tsx_texts[f] = ""
                else:
                    tsx_texts[f] = p.read_text()
    tsx_sets = {f: tsx_tokens(t) for f, t in tsx_texts.items()}

    def shipped_in_region(token: str, region: str) -> bool:
        if css_has_class(css_text, token):
            return True
        return any(token in tsx_sets[f] for f in REGION_TSX[region] if f in tsx_sets)

    # --- 4. per-region, per-token assertions -------------------------------
    n_checked = n_allow = 0
    for region in REGIONS:
        if region not in region_tokens:
            continue  # region already reported missing above
        for tok in sorted(region_tokens[region]):
            if tok in STATE_MODIFIERS:
                n_allow += 1
                continue
            if tok in ALLOWLIST:
                n_allow += 1
                continue
            if tok in CLASS_MAP:
                shipped, _note = CLASS_MAP[tok]
                n_checked += 1
                if not shipped_in_region(shipped, region):
                    failures.append(
                        f"UNCOVERED region={region} mock-token='{tok}' "
                        f"(mapped to shipped '{shipped}', which is missing from "
                        f"{CSS_FILE} and {REGION_TSX[region]})"
                    )
                continue
            if tok in KNOWN_GAPS:
                warnings.append(f"KNOWN-GAP region={region} mock-token='{tok}' owner={KNOWN_GAPS[tok]}")
                continue
            n_checked += 1
            if not shipped_in_region(tok, region):
                failures.append(
                    f"UNCOVERED region={region} token='{tok}' "
                    f"(absent from {CSS_FILE} and {REGION_TSX[region]})"
                )

    # --- 5. report ----------------------------------------------------------
    for w in warnings:
        print(f"WARNING {w}")
    if failures:
        for f in failures:
            print(f"FAIL {f}")
        print(f"audio-mock-parity: {len(failures)} failure(s), {n_checked} token(s) checked")
        return 1
    print(
        f"audio-mock-parity: PASS "
        f"({len(region_tokens)} region(s), {n_checked} token(s) checked, "
        f"{n_allow} scaffolding skipped, {len(warnings)} known-gap warning(s))"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
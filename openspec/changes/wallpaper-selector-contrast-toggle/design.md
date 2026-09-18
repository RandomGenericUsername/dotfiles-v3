## Context

`src/gui-tools/wallpaper-selector/`: L1 grid (`wallpaperCard` — thumb,
LIVE badge, hover quick-Apply, click drills down) → L2 variant gallery
(`variantCard` — thumb + name + Apply pill; crumb header with Back).
`doApply` shells `dotfiles-runtime wallpaper set` via `lib/apply.ts` and
listens to `wallpaper.state` (`applying`/`done`/`error`) for status +
`rescan`/`refreshChrome`. Local `applying()` state already gates re-entry.
Styling in `style.css` (`ws-*` classes). Backend for this change comes from
`icon-contrast-opt-out` (pref store, `--contrast`, `icons regenerate`).

## Goals / Non-Goals

**Goals**

- The checkbox is legible at a glance, impossible to misattribute to the
  wrong wallpaper, and honest about busy state.
- Zero new GUI→runtime protocols: `execAsync` of documented CLI commands +
  the existing event topic only.

**Non-Goals**

- See proposal. Additionally: no AGS widget library changes; no thumbnail
  or scan pipeline changes (preference lookup is a cheap hash-map read at
  render time).

## Decisions

### D1. Placement: L2 crumb header (primary) + L1 hover swatch (indicator AND control)

- **L2 (primary):** checkbox row under the crumb header —
  "Auto high-contrast icons" with a sublabel naming the wallpaper
  ("for <name>"). Unambiguous attribution; visible exactly when deciding
  on variants (req 3.2 context).
- **L1 (control + indicator):** on card hover, beside the quick-Apply
  button, a CSS-drawn ◐ swatch. **Amendment 2026-09-18 (user sign-off
  after live review):** clicking the swatch now TOGGLES high-contrast for
  that wallpaper in place (no drill) — it is both the indicator and the
  control from the main grid. An optimistic local flip repaints every
  visible card for that wallpaper and mirrors the L2 checkbox; the shared
  persist path then does the real work (live ⇒ `icons regenerate`,
  non-live ⇒ store only, never-applied ⇒ carried to the next set). This
  supersedes the original "drills to L2, never toggles inline" rationale
  (the misattribution concern is mitigated by the per-card file sublabel
  and the tooltip naming the wallpaper).

### D2. Wiring (both levels, one helper)

`setContrastPref(hash, enabled)` helper in `lib/`: writes the store via the
backend's `dotfiles-runtime icons preference <hash> --set on|off` accessor
and reads via `icons preference <hash>` (GUI never writes state files
directly), then:
- target IS live (card/variant `live`) ⇒ `execAsync(["dotfiles-runtime",
  "icons", "regenerate", "--contrast", enabled ? "on" : "off"])` (req 3a;
  icons-only, no flicker);
- applying (L1 quick-Apply / L2 pill) ⇒ persist pref first, then
  `wallpaper set` in `auto` (req 3.2; identical resolution guaranteed
  because the store write precedes the set — no flag threading needed,
  though the helper also accepts threading the explicit flag). For variant
  applies the runtime resolves the *governing* (parent) hash (backend D2a),
  so persisting `prefs[H]` is sufficient — the GUI never computes hashes.

### D3. Busy treatment + early collapse on `visible`

Extend the existing `applying()` gate to event-driven busy
(`applying`/`visible` ⇒ busy): Apply buttons/pills `set_sensitive(false)`;
checkbox stays sensitive (preference edits always allowed) but while busy
it ONLY writes the pref — the regenerate arm is deferred until
`done`/`error` (status line says "saved — will apply when ready" if live).
Grid/search/drill untouched. This implements the decided interaction
(browse-live, set-locked) with no new event kinds beyond `visible`.

**Amendment 2026-09-18 (post-live-review):** for a set THIS instance
initiated, the selector collapses as soon as the `visible` event arrives
(pixels swapped) instead of blocking on the whole derivation until `done`.
An external set (not initiated here) never dismisses the window — the
collapse is gated on the local in-flight flag. `done`/`error` still rescan,
refresh chrome, and unlock the controls (window stays hidden).

### D4. Mockups before code (`mock.html`, Sally-owned)

Static HTML in this change dir reusing the tool's `ws-*` class names and
palette slots: (1) L1 card hover with shortcut glyph, (2) L2 header with
checkbox ON/OFF, (3) busy state (disabled Apply, live checkbox + deferred
note), (4) status-line copy for each transition. Implementation starts only
after user sign-off on the mockups.

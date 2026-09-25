## Context

`BluetoothRow` (`dotfiles/config/ags/components/bluetooth/BluetoothContent.tsx:107-151`)
is a single horizontal line: name label, status label, `Connected` badge,
spinner, `Connect/Disconnect` button, `Unpair` button. The name label carries
no `ellipsize` / `maxWidthChars`, so a long device name pushes the trailing
controls past the panel's right edge. `SettingsPanel` fixes the width at
`PANEL_WIDTH = 312` and sets `hscrollbarPolicy = NEVER`, so the overflow is
clipped, not scrollable — the right side of the row is unreachable.

The service already exposes what the row does not show:
`bluetooth-service.ts` publishes per-device `battery` (BlueZ `Battery1`,
0 = absent/unknown) and `rssi` (dBm, `0` / ≥0 = never seen). The row's
`settings-net-sub` label currently inlines `· N%` only when connected.

Icon pipeline facts this change must respect (verified):

- **One render serves bar + panel.** `~/.local/state/dotfiles/current/icons/`
  is read by the bar (via `getBarMappings("battery").states[stateKey]` →
  `registry.resolve`) and by the panel (via direct `registry.resolve`).
- **The contrast guard rewrites only group-level `color_mappings` of
  `BAR_GROUPS`** (`src/runtime/src/runtime/domain/icon_contrast.py:22` —
  `battery` IS a member; `settings-panel` is NOT). Variant-level mappings
  (indent 6) and `bar_mappings` are structurally unreachable
  (`derive.py::_scan_group_color_mappings`). Therefore bare `battery-*` is
  guard-subject and must NOT be used in the panel; `settings-panel` group
  mappings are never retargeted.
- **`icons.yaml` is the manifest ITR consumes**
  (`runtime/adapters/itr_adapter.py:413`). The sibling `battery.yaml`,
  `network.yaml`, … files are verify-listed but stale (their `battery` block
  already differs from `icons.yaml`) and are not rendered — this change edits
  `icons.yaml` only.
- **`icons.json` is generated** by the `compositor_configs` role
  (`icons.yaml → json.dumps(indent=2, sort_keys=True)`); never hand-edited.
- Precedent for label truncation: `.audio-routing label` in
  `style.css:853-860` (`maxWidthChars` + `ellipsize`; GTK ignores CSS
  `max-width`).

Stakeholders: the owner (approves the mock as the contract), the AGS panel
(consumer), the status bar (must not regress).

## Goals / Non-Goals

**Goals:**

- Zero right-edge overflow in the Bluetooth row for any device name length.
- Show live battery level and RSSI-derived signal strength in the approved
  two-line layout, with values coming from the service model — never
  hardcoded.
- New icons render identically on light and dark wallpapers (panel stays
  `foreground`; bar's battery stays guard-controlled).
- Deploy through the narrow path (assets → compositor-configs →
  `icons regenerate`) instead of a full `make bootstrap`, with `verify` as
  the gate.

**Non-Goals:**

- No guard v2, no `BAR_GROUPS` change, no threshold change, no per-consumer
  cache keys, no registry API change.
- No CSS `max-width` reliance (GTK does not honor it).
- No charging-variant battery glyphs for BT peripherals (BlueZ exposes no
  charging state for them); no numeric battery level < 1% rounding rules
  beyond the existing buckets.
- No change to discovery/connect/pair/unpair behavior, no D-Bus schema
  change, no new service fields.
- No edits to the stale sibling mapping files (`battery.yaml`, …).
- No `panel-*` naming (rejected earlier; `system-` prefix already locked by
  `add-system-icon-variants`).

## Decisions

### D1 — Two-line row, `space-between` on line 2

Line 1: ellipsized name (tooltip = full name) + `Connected` badge.
Line 2: `justify-content: space-between`; left = stacked meta
(`[battery glyph + N%]` over `[signal glyph + −N dBm]`); right = the
existing action buttons, `valign=CENTER`.

*Alternatives considered:* (a) keep single line and truncate the name — keeps
overflow (badge + two buttons still exceed 312px); (b) enable horizontal
scroll — contradicts the deliberate `NEVER` policy and hides actions;
(c) drop the `Connected` badge — rejected by the owner, it is part of the
approved mock. Chosen: the owner-approved V1 mock, which moves the actions
onto their own line so truncation only competes with the badge.

### D2 — Truncation through label properties, not CSS

`maxWidthChars` + `ellipsize={Pango.EllipsizeMode.END}` on the name label,
matching `.audio-routing`. GTK4 `Label` ignores CSS `max-width`, so a
CSS-only fix would silently fail. The name cell must be allowed to shrink
(`hexpand` + no fixed width) so `space-between` can do its job.

### D3 — Signal icons live in the `settings-panel` group

Four new templates
`dotfiles/assets/icon-templates/settings-panel/signal/{low,medium,good,high}/default/icon.svg`,
converted from the owner's `~/Downloads/signal {low,medium,good,high}.svg`
(1024 viewBox, `fill="black"` → `{{COLOR_FOREGROUND}}`, inactive bars keep
`fill-opacity="0.5"` — same idiom as
`status-bar/network/wifi-low/default/icon.svg`). Exposed as
`settings-panel-signal-{low,medium,good,high}.svg`.

*Why this group:* `settings-panel` already declares group-level
`COLOR_FOREGROUND: foreground` and is **not** in `BAR_GROUPS`, so the guard
never touches it — the glyphs render the palette `foreground` on every
wallpaper, which is exactly what the dark-glass panel needs. *Alternative
considered:* a bare `signal-*` group — rejected: a new top-level group would
invite future bar consumption and inherits no established contrast policy.

### D4 — Battery glyphs are `system-battery-*` variants inside the `battery` group

Five variants (`system-battery-{0,25,50,75,100}`) reuse the existing
`status-bar/battery/*` templates, output `system-battery-*.svg`, each with a
**variant-level** `COLOR_FOREGROUND: foreground` pin.

*Why not bare `battery-*`:* `battery` IS in `BAR_GROUPS`, so bare outputs are
rewritten on light wallpapers — correct on the bar, unreadable on dark glass.
One render serves both surfaces (the `add-system-icon-variants` finding), and
the guard cannot reach variant-level mappings — same mechanism as the shipped
`volume-system-*` / `microphone-system-*`. The bar is untouched: it keeps
resolving bare variants through `bar_mappings.states`.

*Alternatives considered:* separate group for panel battery (breaks template
reuse and splits the battery family); CSS tinting (can't recolor an external
SVG reliably) — both rejected.

### D5 — Fixed RSSI → icon mapping, live values only

`signalVariant(rssi)`: `≥ −60 → high`, `≥ −70 → good`, `≥ −80 → medium`,
else `low`; row hidden when `rssi` is absent (`>= 0`, BlueZ "not seen").
`batteryVariant(level)` buckets mirror the bar's existing boundaries
(`<25→0, <50→25, <75→50, <100→75, else 100`); the battery line is hidden
when the level is `0`/unknown — the same gate the current `· N%` text uses.

*Why fixed thresholds:* they are the agreed contract in the mock and the
spec (testable); deriving them from the palette or a config file would add a
tuning surface with no owner demand. Labels render the live service values
(`N%`, `−N dBm`) — no literal numbers are written into the component.

### D6 — Narrow deploy path with `verify` as the gate

1. `ansible-playbook -i ansible/inventory/localhost.yaml assets.yaml`
   (user-scoped, no become) — syncs new templates + `icons.yaml` to the
   spine.
2. `ansible-playbook … compositor-configs.yaml` — regenerates `icons.json`
   from `icons.yaml` and places `BluetoothContent.tsx` / `style.css`.
3. `dotfiles-runtime icons regenerate` — re-derives icons from the **live**
   palette (contrast `auto`, no wallpaper switch → no flicker), repoints
   `current/icons`, restarts AGS instances so the new row code re-bundles
   (`ags_reloader.py`: `ags quit -i` + `ags run`).
4. `dotfiles-provision verify` — asserts `verify_icons_samples` (extended)
   and the AGS config file list.

`make bootstrap` remains the final owner-accept gate for the change as a
whole; steps 1–4 are the iteration loop.

*Why not `dotfiles-provision apply`:* its only playbook is the aggregate
`bootstrap.yaml` (`cli/main.py:86`); the executor offers no playbook/tag
switch, so invoking the individual playbooks directly is the honest narrow
path rather than adding CLI surface this change does not need.

## Risks / Trade-offs

- [Two-line rows make the list taller (less vertical room for devices)] →
  Accepted by the owner in the mock; row padding stays as-is.
- [`ellipsize` still needs a width budget that the badge+actions reserve] →
  Actions moved to line 2, so the name only competes with the badge;
  `space-between` + `hexpand` guarantees the name absorbs the remainder.
- [`system-battery-*` duplicates five outputs in one cache entry] → Same
  content-addressed entry as the bare variants (`icons_entry_hash` over the
  overlay bytes); no cache-layout change.
- [New signal templates converted by hand could drift from the owner's
  Downloads art] → Files are converted once, committed, and shown in the
  live panel for owner sign-off against the mock.
- [Guard pin could regress silently if someone moves the pin to group level
  under `battery`] → Overlay-exemption unit test + `icons.json`
  addition-only byte check + light-wallpaper proof in tasks.
- [Partial deploy could ship icons.json while leaving the spine's
  `icons.yaml` stale (or vice versa)] → The two playbooks are run as a pair
  in one task, then `verify` fails loud on missing samples.
- [AGS keeps serving the old bundle after files land] → `icons regenerate`
  restarts AGS; the live gate checks the log for TS/bundle errors, because
  a green `ags bundle` alone does not prove the row renders.

## Migration Plan

1. Land the change in the repo (templates, `icons.yaml`, `icons.json`, TSX,
   CSS, tests, verify samples).
2. Run the narrow deploy (D6 steps 1–4); confirm on a dark and a light
   wallpaper.
3. Owner visual sign-off against
   `openspec/changes/bluetooth-row-battery-signal/mockups/bluetooth-row-final.html`.
4. Full `make bootstrap` green = change accepted; then `/opsx-archive`.

Rollback: revert the commit and re-run D6 steps 1–4 — the change is entirely
additive (new variants/outputs), so the previous render restores cleanly.

## Open Questions

- None blocking. (Whether to also expose a tooltip on the meta lines is
  explicitly deferred to owner sign-off.)

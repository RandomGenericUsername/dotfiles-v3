---
name: AGS Bluetooth Control
description: BlueZ control for the Hyprland dotfiles desktop — a bar Bluetooth indicator, a follower-anchored 312px Bluetooth popup, and the reworked settings-panel Bluetooth subview. Full parity with the Wi-Fi popup, which is the mandated reference for geometry, components, styling and interaction. Visual identity inherits the AGS settings-panel design system; the runtime wallpaper palette is the only ink.
status: draft
updated: 2026-10-02
sources:
  - dotfiles/config/ags/components/wifi/WifiPopup.tsx          # THE REFERENCE
  - dotfiles/config/ags/components/wifi/WifiContent.tsx
  - dotfiles/config/ags/components/wifi/state.ts
  - dotfiles/config/ags/components/bluetooth/BluetoothContent.tsx
  - dotfiles/config/ags/services/bluetooth-service.ts
  - dotfiles/config/ags/settings-panel/{SettingsPanel.tsx,primitives.tsx,state.ts}
  - dotfiles/config/ags/settings-panel/views/{SubviewHeader.tsx,BluetoothView.tsx,WifiView.tsx,MainView.tsx}
  - dotfiles/config/ags/settings-panel/controls/bluetooth.tsx
  - dotfiles/config/ags/audio/AudioPopup.tsx                   # SECOND popup precedent
  - dotfiles/config/ags/{app.tsx,style.css,lib/icon-registry.ts,lib/wifi-signal.ts,lib/event-bus-core.ts}
  - dotfiles/config/icon-template-color-scheme-mappings/icons.yaml
  - src/runtime/src/runtime/domain/icon_contrast.py             # BAR_GROUPS
  - contracts/event-contract.json
  - openspec/changes/add-ags-settings-panel/design.md
  - openspec/changes/archive/2026-09-25-bluetooth-row-battery-signal/design.md
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-bluetooth-2026-10-02/mockups/
colors:
  # Semantic roles map onto runtime palette slots 1:1. The values below are the
  # LIVE palette the staged SVG assets in mockups/assets/ were ITR-rendered
  # against (2026-10-02). The palette is live — a wallpaper swap re-derives it
  # and re-renders every icon — so these are a snapshot, not a fixed theme.
  surface-panel: '{color_00} @ 0.94 alpha'          # #0b0b1a — glass panel body
  surface-panel-border: '{color_04}'                 # #2d6596 — 1.5px
  surface-row: '{color_01} @ 0.18 alpha'             # #575660 — cards / fields
  hairline: '{color_foreground} @ 0.10 alpha'
  divider: '{color_foreground} @ 0.06 alpha'
  ink-primary: '{color_foreground}'                  # #c2c2c5
  ink-muted: '{color_foreground} @ 0.62 alpha'
  ink-faint: '{color_foreground} @ 0.40 alpha'
  row-selected: '{color_10}'                         # #549ec8 — "where you are"
  action-accent: '{color_13}'                        # #dbab67 — the ON / accent
  caution: '{color_03}'                              # #5a5a6f — failure + danger text
  caution-strong: '{color_11}'                       # #dbab67 family, caution slot
  switch-on: '{color_10}'                            # #549ec8 — Gtk.Switch ON track
typography:
  # Inherited verbatim from the settings panel. No new type scale.
  nav-title:      { fontSize: 13.5px, fontWeight: '650' }
  row-name:       { fontSize: 12.5px, fontWeight: '600' }
  row-sub:        { fontSize: 10.5px, color: '{colors.ink-muted}' }
  section-label:  { fontSize: 11px, fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em' }
  detail:         { fontSize: 11px, color: '{color_foreground} @ 0.50 alpha' }
  meta-stat:      { fontSize: 10.5px, opacity: 0.72, lineHeight: '14px' }
  row-action:     { fontSize: 11px, fontWeight: '600' }
  badge:          { fontSize: 9.5px, letterSpacing: '0.05em' }
  bar-icon:       { pixelSize: 28 }
rounded:
  panel: 12px
  card: 9px
  row: 7px
  pill: 20px
  switch: 12px
spacing:
  surface-padding: 11px
  row-padding: '8px 9px'
  row-line-gap: 3px
  body-gap: 8px
geometry:
  popup-width: 312px          # identical to the Wi-Fi popup and the settings panel
  popup-scroll-max: 420px     # maxContentHeight on the scrolledwindow
  popup-margin-top: 52px      # clears the bar
  subview-scroll-height: 339px
components:
  panel:
    background: '{colors.surface-panel}'
    border: '1.5px solid {colors.surface-panel-border}'
    radius: '{rounded.panel}'
  nav-header:
    min-height: 26px
    padding-bottom: 7px
    trailing-control: 'Gtk.Switch (.settings-switch)'
  row:
    background: transparent
    radius: '{rounded.row}'
    hover: '{color_foreground} @ 0.08 alpha'
    selected: '{colors.row-selected}'
    out-of-range: { opacity: 0.45 }
  row-action:
    border: '1px solid {color_foreground} @ 0.26 alpha'
    radius: 7px
    hover-border: '{colors.row-selected}'
    disabled: { opacity: 0.5 }
    subtle: { opacity: 0.68 }
    danger: { border-color: '{colors.caution}', color: '{colors.caution}' }   # ADDITION — see §New CSS
  badge:
    radius: '{rounded.pill}'
    connected: { background: '{color_13} @ 0.18 alpha', border: '1px solid {color_13} @ 0.45 alpha' }
  bar-indicator:
    background: transparent
    glyph: bare, 28px, guard-managed tint
---

## Brand & Style

Bluetooth control is not a new product. It is a new **door into a house that already has a style** — and, more precisely, it is the closing of a hole in the house's floor plan. Today the Wi-Fi panel has a bar indicator, a follower-anchored popup, a settings tile and a subview; Bluetooth has only the last two. A user with Bluetooth headphones has to open the settings panel from the far right of the bar, navigate to a tile, and read the same glyph in a different control. That asymmetry is the whole problem this design solves.

The governing posture, inherited verbatim from the Wi-Fi redesign it must match:

> **AGS is a frontend to BlueZ, never a second Bluetooth-management system.** BlueZ owns adapter power, discovery, pairing and connection; the UI is generated from the live device collection rather than from a list anyone maintains.

This surface therefore **mirrors `WifiPopup.tsx` / `WifiContent.tsx` component-for-component** wherever the domain allows. Where the domains differ, the divergence is named and justified rather than smuggled in. It adds no new type scale, no new accent, and — with exactly one documented exception — no new CSS class.

## Colors

The palette is the runtime wallpaper palette. **No literal colours appear in any Bluetooth surface.** The staged SVG assets in `mockups/assets/` are real ITR renders, so they already carry the resolved hex: `settings-panel-bluetooth.svg` renders `color13` = `#dbab67` (amber), `settings-panel-bluetooth-off.svg` renders `foreground` = `#c2c2c5`. The ON/OFF distinction is carried **by the rendered tint**, exactly as `IconToggle` expects — there is no CSS filter and no recolouring layer anywhere in this design.

- **`surface-panel` (`@color_00` at 0.94)** — the glass body of the popup and of the settings panel. Translucency is for the surface only; cards and rows are opaque-ish tints over it.
- **`surface-row` (`@color_01` at 0.18)** — the fields/cards inside the surface.
- **`row-selected` (`@color_10`)** — the connected row, filled solid, text in `ink-primary`. This is the house "where you are" accent and is inherited verbatim from `.settings-net.sel`.
- **`action-accent` (`@color_13`)** — the ON state of the capability glyph and the `Connected` badge. Distinct from selection on purpose.
- **`caution` (`@color_03`)** — failure text (`.settings-message`) and the destructive confirm button.
- Do **not** introduce a Bluetooth-blue, a "pairing green", or a per-device hue. Hue carries exactly two meanings in this family (accent, selected) and Bluetooth adds neither.

## Typography

No new type scale. The popup and the subview use the settings panel's `.settings-nav-title` (13.5/650), `.settings-net-name` (12.5/600), `.settings-net-sub` (10.5/muted), `.settings-meta-stat` (10.5/0.72) and `.settings-detail` (11/0.50) verbatim. Device names truncate with an ellipsis at **26 chars** — never wrap, because a wrapping name reflows the two-line row and drags the action buttons with it.

## Layout & Spacing

Both Bluetooth surfaces are a single **312px** column: the popup and the settings subview are the same width by construction, which is what lets the design honestly claim Wi-Fi parity.

**Popup geometry** (mirrors `WifiPopup.tsx`):

| Property | Value | Source of the rule |
|---|---|---|
| `widthRequest` | `312` | `SettingsPanel.PANEL_WIDTH` |
| anchor | `TOP \| LEFT`, `exclusivity: IGNORE`, `layer: OVERLAY` | `WifiPopup` (IGNORE is mandatory — NORMAL makes Hyprland double-offset below the bar) |
| `marginTop` | `52` | `WifiPopup` |
| `marginLeft` | `iconCentre − 156`, clamped to `[8, monitorWidth − 320]` | `WifiPopup` |
| scroll | `propagateNaturalHeight`, `maxContentHeight={420}`, `vscrollbar AUTOMATIC`, `hscrollbar NEVER` | `WifiPopup` |
| `propagateNaturalWidth` | `false` | **settings panel** — Bluetooth rows carry a 26-char name plus two action buttons, the exact overflow shape the Wi-Fi popup does not have |
| scroll reset | on open, via `viewEpoch` | **audio popup** — see §Scroll reset |

**Body order is fixed** (the structural twin of `WifiContent`'s order):

```
nav-header  "Bluetooth"  ··················  [ Gtk.Switch ]      ← PINNED, sibling of the scrolledwindow
─────────────────────────────────────────────────────────────────
adapter detail block          .settings-detail-row ×2
divider                       .settings-divider
"Paired"                      .settings-section-label
  connected row               .settings-net.sel
  paired-not-connected row    .settings-net
  out-of-range row            .settings-net.out-of-range
divider                       .settings-divider
"Available Devices ▸/▾"       .settings-chevron-row
  nearby rows                 .settings-net
divider                       .settings-divider
"Bluetooth Settings ›"        footer row (.settings-wifi-settings-row shape)
─────────────────────────────────────────────────────────────────
```

Two structural rules, both inherited rather than invented:

1. **The header is a SIBLING of the scrolledwindow, never a child.** This is the single lesson the settings panel learned the hard way (`SubviewHeader.tsx`): a header inside the scrolled window scrolls away, so two surfaces sharing one `NavHeader` behave differently. Both Bluetooth surfaces put the header outside.
2. **The power control is always the trailing slot of the header, and it is always a `Gtk.Switch`.** Wi-Fi's popup and subview both do this. Bluetooth's subview currently uses a bare `BluetoothToggle` glyph — that is the parity break this design fixes (see §Header control).

Every device row uses one layout rule, unchanged from the owner-approved 2026-09-25 row:

- **Line 1** — leading signal glyph · device name (ellipsized, tooltip = full name) · `Connected` badge (when connected)
- **Line 2** — leading meta stack (words on the first line, battery on the second) · trailing action pair (`settings-rowact` + `settings-rowact subtle`)

## Shapes

Panels 12px, cards and rows 9px / 7px, badges and chips fully round (20px), switch 12px on a 24px track. No shape changes on navigation. The spinner is a 14px ring in `action-accent`.

## Components

Every glyph resolves through `registry.resolve(group, variant)` — never a raw path. Full icon plan in §Icon plan.

- **Bluetooth bar indicator** — a bare glyph, no pill, no background, no label, 28px, in the `end` box of `bar/Bar.tsx` **immediately left of `NetworkStatus`**. Four states (§Bar indicator states). Left-click opens the popup; the motion controller records the pointer x for follower anchoring, exactly like `bar/widgets/network.tsx`.
- **Bluetooth catcher** — `BluetoothPopupCatcher`, a full-screen `settings-catcher` window created **before** the popup in `app.tsx` so the popup stacks above it. Click-outside closes.
- **Bluetooth popup** — the 312px glass surface described above, with the pinned header and the fixed body order. Dismissed by click-outside and by `ags request popup-close`.
- **Device row** — `BluetoothRow`. Line 1 / line 2 as above. The **whole row is the primary action** (`Gtk.GestureClick` on the row, exactly like `WifiRow`), with the action button claiming its own click first. Wi-Fi made the row the target; Bluetooth must too — a 312px row with a 46px button is a bad hit target, and cross-surface muscle memory is the point of parity.
- **Leading signal glyph** — a NEW element on the row and the single biggest parity gap. Wi-Fi rows lead with `.settings-net-signal`; Bluetooth rows led with nothing. The row now leads with `settings-panel/signal-*`, resolved by the **existing** `signalVariant()` thresholds — zero new art.
- **Meta stack** — the word subtitle (`.settings-net-sub`) plus battery. The `−N dBm` number that shipped in the meta stack moves to a **tooltip on the signal glyph**: Wi-Fi prints words (`Saved` / `Secured` / `Open network`), never strength numbers, and two encodings of one number is noise. *This changes one already-approved row detail — owner sign-off required.*
- **Row action pair** — primary `settings-rowact` (`Pair` / `Connect` / `Disconnect`, label swaps to `<Action>ing…` while busy) and secondary `settings-rowact subtle` (`Unpair`, paired devices only).
- **Unpair confirm** — inline, in the row's action slot, so the row does not reflow: the meta stack is replaced by one `settings-meta-stat` line reading `Remove from paired devices`, and the pair becomes `Keep` (`settings-rowact`) / `Unpair device` (`settings-rowact danger`). See §Unpair.
- **Adapter detail block** — the structural twin of `WifiContent`'s `ConnectionDetails`, carrying the two facts that live on no row: `Adapter` (the hci address) and `Audio output` (the PipeWire endpoint `routeAudioToDevice` actually landed on). Two rows, `.settings-detail-row`. Hidden while powered off, exactly as `OtherNetworksExpand` hides its own details when Wi-Fi is off.
- **Discovering indicator** — `.settings-empty` + `.settings-spinner` reading `Scanning…`, plus the collapsed `Available Devices` chevron row.
- **Failure line** — `.settings-message` carrying `bluetoothFailure()` verbatim, including the service's watchdog strings (`Pairing timed out`, `Could not turn Bluetooth on (adapter may be soft-blocked)`). One line, no timer, no toast. Optional leading `settings-panel/info-caution` glyph for adapter-absent and soft-block failures, reusing the Wi-Fi weak-security precedent.

### Bar indicator states

| State key | Condition | Variant (`bluetooth` group) | Reads as |
|---|---|---|---|
| `off` | `!bluetoothPowered()` | `bluetooth-off-default` | slashed rune, guard-managed neutral tint |
| `idle` | powered, no connected device | `bluetooth-default` | bare rune |
| `connected` | powered, ≥1 connected, none routed | `bluetooth-connected-default` | rune + hollow dot |
| `active` | powered, the routed device is connected | `bluetooth-active-default` | rune + filled dot |

`active` is the one thing a Bluetooth bar indicator should say that Wi-Fi's cannot: **your audio is on Bluetooth right now.** It needs `bluetoothAudioTarget` from the service (see §Service additions). A second connection while one is routed keeps the indicator on `active` — the routed device wins.

## New CSS — the complete list

**One class is added:**

```css
/* Destructive confirm on the Unpair action. Border + text take the caution
   slot (@color_03); hover lifts to @color_11. Sits beside the existing
   `.settings-rowact.subtle` at the same geometry. */
.settings-rowact.danger {
  border-color: @color_03;
  color: @color_03;
}
.settings-rowact.danger:hover {
  border-color: @color_11;
  color: @color_11;
}
```

**And nothing else.** Every other element in this design resolves to an existing class:

| Element | Existing class |
|---|---|
| popup body / panel | `.settings-surface` |
| pinned header | `.settings-nav-header`, `.settings-nav-title` |
| power control | `.settings-switch` (`WifiSwitch`) |
| catchers | `.settings-catcher`, `.settings-catcher-fill` |
| scroll | `.settings-scroll` |
| device row | `.settings-net`, `.settings-net.sel`, `.settings-net.out-of-range` |
| row name / subtitle | `.settings-net-name`, `.settings-net-sub` |
| leading signal glyph | `.settings-net-signal` |
| badges | `.settings-badge`, `.settings-badge.conn` |
| row actions | `.settings-rowact`, `.settings-rowact.subtle`, `.settings-rowact.disabled` |
| meta lines | `.settings-row-meta`, `.settings-meta-stat`, `.settings-meta-icon` |
| spinner | `.settings-spinner` |
| detail block | `.settings-conn-details`, `.settings-detail-row`, `.settings-detail` |
| divider | `.settings-divider` |
| section label | `.settings-section-label` |
| collapsible section | `.settings-chevron-row`, `.settings-chevron-label` |
| empty / scanning | `.settings-empty` |
| failure | `.settings-message` |
| footer row | `.settings-wifi-settings-row`, `-label`, `-note`, `-arrow` (class names are Wi-Fi-specific but the rules are generic; **no rename in this change** — renaming would touch the Wi-Fi popup for no visual gain) |
| caution glyph | `.settings-security-warn`, `.settings-security-icon`, `.settings-security-text` |
| settings tile | `.settings-tile`, `.settings-tile-title`, `.settings-tile-sub`, `.settings-chevron` |
| tile power glyph | `.settings-icon-toggle`, `.settings-toggle-glyph` |

### Reused-but-not-new, deliberately

- **`.settings-icon-toggle`** stays on the **main-view tile only**. It is a `Gtk.Button`, so its `clicked` signal fires only on real user activation — it does **not** have the `notify::active` self-oscillation hazard `WifiSwitch` was written to solve. It is safe where it is; it is simply not the header-slot control.
- **`.settings-badge.conn`** is reused for `Connected` only. A second badge variant (e.g. `Paired`) is *not* introduced: the paired/not-connected state is a **subtitle word**, matching how Wi-Fi says `Saved`.

## Icon plan

Two groups, and the reasoning for each is different on purpose.

### 1. `settings-panel` — existing, no new variants

Bluetooth today has **no gap on the panel side**. Every glyph the popup and subview need already exists and is already staged in `mockups/assets/`:

| Where | group | variant | Renders |
|---|---|---|---|
| tile glyph, ON | `settings-panel` | `bluetooth` | `color13` `#dbab67` |
| tile glyph, OFF | `settings-panel` | `bluetooth-off` | `foreground` `#c2c2c5` |
| row leading signal (4) | `settings-panel` | `signal-low` / `signal-medium` / `signal-good` / `signal-high` | `foreground` |
| row battery (5) | `battery` | `system-battery-0/25/50/75/100` | `foreground` |
| adapter-absent caution | `settings-panel` | `info-caution` | `color15` |

Two rules that MUST hold and already hold today:

- The `settings-panel` group is **not** in `BAR_GROUPS`, so the contrast guard never retargets it. Panel glyphs are always the palette foreground on dark glass — correct on every wallpaper.
- The `battery` group **is** in `BAR_GROUPS`, so bare `battery-*` variants are guard-subject (bar-only). The panel must resolve **only** the guard-exempt `system-battery-*` variants — the variant-level `COLOR_FOREGROUND: foreground` pin is what exempts them. This is exactly what `batteryVariant()` in `BluetoothContent.tsx` already does and it must be preserved verbatim, including the `<25 / <50 / <75 / <100` buckets mirroring the bar's own `getBatteryStateKey`.

### 2. `bluetooth` — a NEW bar group (this is the gap)

There is **no Bluetooth icon group for the status bar at all** today. `bar_mappings` exist only on `battery`, `network`, `btop`, `power-menu`, `settings` — the Wi-Fi bar rides inside `network`'s states, which is why it could not be borrowed. A bar Bluetooth indicator therefore needs a brand-new group with its own templates.

**The load-bearing decision: bar state is carried by ART, never by TINT.**

`icon_contrast.py` rewrites only **group-level** `COLOR_FOREGROUND` / `COLOR_JOIN` of `BAR_GROUPS`; variant-level mappings and `bar_mappings` are structurally unreachable by the guard. So:

- A variant-level `COLOR_FOREGROUND` pin on a bar glyph **exempts it from the guard** — exactly the `system-*` mechanism, which exists for glyphs that must render *unretargeted* because they sit on opaque glass. A bar glyph is the opposite case: it floats over the wallpaper and **must stay guard-managed**.
- Therefore the `bluetooth` group declares `color_mappings` at **group level only** and adds **no variant-level pins**. All four states render through the guard, so on a light wallpaper the runtime retargets the group's foreground before ITR renders and all four stay legible.

This is why the bar and the panel use *different* mechanisms for the same idea, and it is correct for each: **the panel carries ON/OFF in the rendered tint (it is never retargeted); the bar carries state in the glyph's art (it is always retargeted).**

**Templates** — four new files, one weight:

```
dotfiles/assets/icon-templates/status-bar/bluetooth/off/default/icon.svg        → bluetooth-off-default.svg
dotfiles/assets/icon-templates/status-bar/bluetooth/default/icon.svg            → bluetooth-default.svg
dotfiles/assets/icon-templates/status-bar/bluetooth/connected/default/icon.svg   → bluetooth-connected-default.svg
dotfiles/assets/icon-templates/status-bar/bluetooth/active/default/icon.svg      → bluetooth-active-default.svg
```

Derived from the existing `settings-panel/bluetooth/default/icon.svg` rune (the circle-badge Bluetooth mark) with `fill="black"` → `{{COLOR_FOREGROUND}}`:

- `off` — the rune with a slash, so "off" reads as shape, not dimness.
- `default` — the bare rune, unchanged geometry.
- `connected` — the rune plus a **hollow** 8px-equivalent dot.
- `active` — the rune plus a **filled** dot.

A `bold`/`rounded` weight ladder is **deliberately omitted**. The `network` group carries three weights × six states because Wi-Fi strength genuinely needs weight to read at 24px; Bluetooth has four states, none of them a strength ladder, and the `settings` group already proves a single-`default` bar group is the house norm.

**Manifest** — `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (source of truth; `icons.json` is generated and must not be hand-edited):

```yaml
bluetooth:
  color_mappings:
    COLOR_FOREGROUND: color15      # group level ONLY — the guard retargets this
  variants:
    - name: bluetooth-off-default
      template: status-bar/bluetooth/off/default/icon.svg
      output: bluetooth-off-default.svg
    - name: bluetooth-default
      template: status-bar/bluetooth/default/icon.svg
      output: bluetooth-default.svg
    - name: bluetooth-connected-default
      template: status-bar/bluetooth/connected/default/icon.svg
      output: bluetooth-connected-default.svg
    - name: bluetooth-active-default
      template: status-bar/bluetooth/active/default/icon.svg
      output: bluetooth-active-default.svg
  bar_mappings:
    widget: bluetooth
    icon_size: 24
    states:
      off: bluetooth-off-default
      idle: bluetooth-default
      connected: bluetooth-connected-default
      active: bluetooth-active-default
```

**Guard allowlist** — one line in `src/runtime/src/runtime/domain/icon_contrast.py`:

```python
BAR_GROUPS: Final[tuple[str, ...]] = (
    "battery", "network", "btop", "thunderbird", "tray", "ui",
    "power-menu", "email-client", "wallpaper-selector", "settings",
    "volume", "microphone",
    "bluetooth",          # ← the Bluetooth bar indicator floats over the wallpaper
)
```

The runtime resolves the bar glyph through the exact same `getBarMappings("bluetooth").states[stateKey]` → `registry.resolve("bluetooth", variant)` path `bar/widgets/network.tsx` uses for `network`. No new registry API.

## Service additions

`bluetooth-service.ts` keeps owning every byte of Bluetooth state; the view gains nothing. Three accessors are added so the design can be honest about what it shows, and all three are plain reads of data BlueZ or PipeWire already hold:

1. `bluetoothAdapterAddress: Accessor<string>` — read from the adapter's `Address`/`Name` in `updateAdapterProps`. Feeds the `Adapter` detail row.
2. `bluetoothAudioTarget: Accessor<string | null>` — set by `routeAudioToDevice` to the endpoint it actually defaulted (`null` when the 16-attempt window expired). Feeds the `Audio output` detail row **and** the bar indicator's `active` state. Today that function's failure is completely invisible to the user, which is precisely the bug this closes: headphones read "Connected" while sound stays on the speakers.
3. `setBluetoothPowered(enabled: boolean)` — the mirror of `setWifiEnabled(enabled)`, so both the tile glyph and the header switch forward an **explicit** value instead of a blind `toggleBluetooth()` read-modify-write.

**Reference-counted discovery.** `startBluetoothDiscovery` / `stopBluetoothDiscovery` become reference-counted in the service: `start` increments, `stop` decrements, and `StopDiscovery` is issued only when the count reaches zero. Without this there is a real race — the popup and the settings subview are both mounted at all times (the panel renders all three views and toggles `visible`), so closing the popup while opening the panel can run the popup's cleanup and kill the scan the subview just started. The current early-return in `runStartDiscovery` (`if (bluetoothDiscovering()) return`) makes the leak half-invisible and the double-stop half-real.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Mirror `WifiPopup` / `WifiContent` component-for-component | Invent a Bluetooth-shaped surface vocabulary |
| Keep the nav header a **sibling** of the scrolledwindow | Render it inside and let it scroll away |
| Put a `Gtk.Switch` in the header slot on both surfaces | Leave a bare glyph in the subview header and a switch in the popup header |
| Make the whole row the primary action | Leave a 46px button as the only hit target |
| Lead the row with `settings-panel/signal-*` | Leave the row with no leading glyph |
| Print **words** on the subtitle; put numbers in tooltips | Print `−52 dBm` next to bars that already say it |
| Tie discovery to surface visibility | Poll, or scan with the surface closed |
| Set `propagateNaturalWidth={false}` | Let a long name grow the surface past 312px |
| Keep `keymode` at `NONE` and dismiss via catcher + `popup-close` | Grab the keyboard for a surface with no typed field |
| Carry bar state in glyph **art**; keep the group guard-managed | Pin a variant-level tint on a bar glyph and opt it out of the guard |
| Resolve `system-battery-*` only | Resolve bare `battery-*` from the panel |
| Route audio and then **report** the endpoint | Auto-route silently and leave the user guessing |
| Confirm unpair inline, in the row's action slot | Open a modal, or reflow the row |
| Read BlueZ live through the service | Add a hub topic (see EXPERIENCE.md §Hub) |

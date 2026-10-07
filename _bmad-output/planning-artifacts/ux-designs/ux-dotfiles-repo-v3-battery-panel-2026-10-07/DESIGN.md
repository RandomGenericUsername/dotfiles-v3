---
name: AGS Battery Panel
description: The battery status-bar icon's left-click surface — a follower-anchored 312px panel over the settings-panel vocabulary, whose power-mode selector is TWO-LEVEL. A MODE owns a glyph; a VARIANT is a selectable profile on a tier the mode declares. The tier (base_profile) is the stable key; the tier→mode grouping is an explicit declaration. Three glyphs, five selectable things.
status: draft
updated: 2026-10-07
sources:
  - dotfiles/config/ags/components/battery/BatteryContent.tsx      # the panel body this design reshapes
  - dotfiles/config/ags/components/battery/BatteryPopup.tsx        # window + catcher (unchanged)
  - dotfiles/config/ags/components/battery/presentation.ts         # formatBatteryTime, the tier vocabulary
  - dotfiles/config/ags/components/battery/battery-icon.ts         # battery state → bar glyph key
  - dotfiles/config/ags/components/battery/state.ts                # popup visibility / anchor x
  - dotfiles/config/ags/services/power-service.ts                  # D-Bus + the config.toml watch
  - dotfiles/config/ags/bar/widgets/battery.tsx                    # the bar indicator + click behaviour
  - dotfiles/config/ags/style.css                                  # the real settings-*/battery-* vocabulary
  - dotfiles/config/icon-template-color-scheme-mappings/icons.yaml # the power-mode group
  - dotfiles/assets/icon-templates/status-bar/battery/**           # the real rounded battery templates
  - dotfiles/assets/icon-templates/power-mode/**                   # three mode glyphs already exist
  - /home/inumaki/Downloads/power-modes/battery-empty-unplugged-default.svg  # Powersave mode glyph (leaf)
  - /home/inumaki/Downloads/power-modes/balance-law-svgrepo-com 1.svg        # Balanced mode glyph (scales)
  - /home/inumaki/Downloads/power-modes/car-engine-1 1.svg                   # Performance mode glyph (engine)
  # RETIRED as modes (no longer referenced by any mock): battery-saver-svgrepo-com.svg
  # and speedometer-svgrepo-com.svg — the previous run's per-tier Superpowersave/Ultraperformance art.
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-bluetooth-2026-10-02/DESIGN.md
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-bluetooth-2026-10-02/mockups/
colors:
  # Semantic roles map onto runtime palette slots 1:1. The values are the LIVE
  # palette the staged SVG assets in mockups/assets/ were rendered against
  # (2026-10-02 snapshot, copied from the sibling Bluetooth run). The palette is
  # live — a wallpaper swap re-derives it and re-renders every icon.
  surface-panel: '{color_00} @ 0.94 alpha'          # #0b0b1a — glass panel body
  surface-panel-border: '{color_04}'                 # #2d6596 — 1.5px
  surface-row: '{color_01} @ 0.18 alpha'             # #575660 — hover wash
  hairline: '{color_foreground} @ 0.10 alpha'
  divider: '{color_foreground} @ 0.06 alpha'
  ink-primary: '{color_foreground}'                  # #c2c2c5 — chrome text
  glyph-ink: '{color_foreground}'                    # #c5c8ce — the staged-asset value
  ink-muted: '{color_foreground} @ 0.62 alpha'
  ink-faint: '{color_foreground} @ 0.40 alpha'
  row-selected: '{color_10}'                         # #549ec8 — selected mode indicator + selected variant
  action-accent: '{color_13}'                        # #dbab67 — selected glyph + the charging bolt
  caution: '{color_03}'                              # #5a5a6f — failure text only
typography:
  # Inherited verbatim from the settings panel / the shipped battery block. No new scale.
  nav-title:      { fontSize: 13.5px, fontWeight: '650' }
  header-pct:     { fontSize: 12.5px, fontWeight: '600', fontVariantNumeric: 'tabular-nums', opacity: 0.72 }
  hero-primary:   { fontSize: 30px, fontWeight: '700', fontVariantNumeric: 'tabular-nums' }
  hero-sub:       { fontSize: 12px, color: '{colors.ink-muted}' }
  mode-label:     { fontSize: 9.5px, fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em', color: '{colors.ink-muted}' }
  variant-opt:    { fontSize: 11px, fontWeight: '600' }
  rail-name:      { fontSize: 12.5px, fontWeight: '600' }
  rail-tier:      { fontSize: 10.5px, color: '{colors.ink-muted}' }
  section-label:  { fontSize: 11px, fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.05em' }
  footer-label:   { fontSize: 13px, color: 'rgba(255,255,255,0.70)' }
  footer-note:    { fontSize: 10px, color: 'rgba(255,255,255,0.30)' }
rounded:
  panel: 12px
  cell: 7px
  row: 7px
  pill: 7px
spacing:
  surface-padding: 11px
  rail-gap: 8px
  rail-pad-x: 8px
  variant-gap: 6px
  hero-padding: '10px 16px 14px 16px'
geometry:
  popup-width: 312px          # SettingsPanel.PANEL_WIDTH
  popup-margin-top: 52px      # clears the bar
  anchor: 'TOP | LEFT, Exclusivity.IGNORE, Layer.OVERLAY'
  mode-cell: '72 × 54 px'
  rail-usable-width: 274px    # 312 − 2×11 (surface) − 2×8 (rail pad)
  modes-per-row: 3            # 3×72 + 2×8 = 232 ≤ 274; a 4th (unlisted) mode wraps
components:
  panel:                        # unchanged, mirrors WifiPopup / BatteryPopup
    background: '{colors.surface-panel}'
    border: '1.5px solid {colors.surface-panel-border}'
    radius: '{rounded.panel}'
  nav-header:                   # .settings-nav-header + .battery-header-icon + .battery-header-pct
    min-height: 26px
    leading: 'battery glyph, 18px, the SAME state key as the bar indicator'
    trailing: 'percentage, tabular-nums'
  hero:                         # .battery-hero / -primary / -sub
    primary: 'formatBatteryTime().primary — the only large type on the surface'
    sub: 'formatBatteryTime().sub — "remaining" / "full in" / the state word'
  mode-rail:                    # ADDITION — .battery-mode-rail
    layout: 'flex, gap 8px, centred; one 72×54 cell per declared MODE'
    cell: 'glyph 24px + mode label 9.5px; radius 7; a 4th cell (unlisted) wraps'
    hover: '{surface-row} wash'
    selected-glyph: '{colors.action-accent} — the -active asset'
    selected-indicator: '2px bottom border, {colors.row-selected}'
  variant:                      # ADDITION — .battery-variant (rendered ONLY when mode has >1 variant)
    layout: 'flex, wrap, gap 6px, pad 2px 16px 8px'
    option: 'button, .settings-rowact geometry (1px hairline, radius 7, 11/600)'
    selected: 'border {colors.row-selected} + faint {colors.row-selected} wash'
  rail-meta:                    # the selected profile named ONCE
    name: 'profile_name, {typography.rail-name}'
    tier: '<mode> mode · <base_profile> tier', {typography.rail-tier}
  deep-link:                    # .battery-deeplink, the button form of .settings-wifi-settings-row
    padding: '10px 16px'
    border-top: '1px solid {colors.divider}'
---

## Brand & Style

The battery panel is not a new product and this is not a new surface. The bar indicator, the
follower-anchored popup, the catcher/catcher-fill, the catch that the panel is a third overlay on the
`settings-panel` chrome — all of that shipped and stays. **What changes is the power-mode selector
inside it, and the change is the owner's two-level model:**

> **A MODE owns a glyph. A VARIANT is a selectable profile sitting on a tier the mode declares.**
> `Powersave` and `Powersave++` are two VARIANTS of the same mode and share one glyph; likewise
> `Performance` and `Performance++`. So the selector has **three glyphs for five selectable things** —
> the owner deliberately supplied only three icons for five profiles.

The declaration the panel consumes is exactly:

```
mode "Powersave"     glyph: leaf     tiers: [Powersave, Superpowersave]
mode "Balanced"      glyph: scales   tiers: [Balanced]
mode "Performance"  glyph: engine   tiers: [Performance, Ultraperformance]
```

Live values on this machine (2026-10-07), quoted as the source of truth:

| `profile_name` | `base_profile` (tier) | mode | variant |
|---|---|---|---|
| `Powersave++` | `Superpowersave` | Powersave (leaf) | yes |
| `Powersave` | `Powersave` | Powersave (leaf) | yes |
| `Balanced` | `Balanced` | Balanced (scales) | mono — no control |
| `Performance` | `Performance` | Performance (engine) | yes |
| `Performance++` | `Ultraperformance` | Performance (engine) | yes |

### Why the relation must be DECLARED, not inferred

Three facts force the tier→mode grouping to be an explicit declaration:

1. **`profile_name` is user-editable** (`UpdateProfileName`), so any rule that *strips a `++` suffix*
   to recover a mode breaks the moment a profile is renamed (`Performance++` → `Showtime` has nothing
   to strip). The name is the user's and it is editable.
2. **`base_profile` IS the stable key** — users cannot rename it — **but it yields five distinct
   tiers, not three.** The live values are `Powersave++` → `Superpowersave` and `Performance++` →
   `Ultraperformance`; the daemon treats them as genuinely different tiers. A rule that keys one
   glyph off the tier therefore asks for **five** glyphs, which is the wrong answer.
3. **Therefore the grouping is an explicit declaration.** The stable key that resolution uses is the
   **tier** (rename-proof); the declaration says **which tiers are variants of which mode**. A tier
   no mode lists falls back to the neutral glyph rather than disappearing.

The rejected model was a flat five-cell icon rail — one cell per profile, five distinct glyphs. This
run replaces it: the rail shows **one cell per MODE (three cells)**, and the selected mode's variant
is a **secondary control, shown only when that mode actually has more than one variant**.

## Colors

The palette is the runtime wallpaper palette; **no literal colour ships**. The staged SVG assets in
`mockups/assets/` already carry the resolved hex: the mode glyphs render `foreground = #c5c8ce`, and
the selected copies render `color13 = #dbab67`. ON/OFF and selected/unselected are carried **by the
rendered tint and the selected indicator**, exactly the `settings-panel-*` convention — there is no
CSS filter and no recolouring layer anywhere.

- **`ink` (`#c5c8ce`)** — every mode glyph at rest, and the battery header glyph.
- **`action-accent` (`@color_13` `#dbab67`)** — the **selected mode's** glyph (an `-active` asset
  copy), the charging bolt in the `battery-*-charging` assets, and the fallback marker. The same
  accent the icon system already uses for an ON capability.
- **`row-selected` (`@color_10` `#549ec8`)** — the selected mode's 2px bottom indicator **and** the
  selected variant option's border/wash. This is the house "where you are" token (`.settings-net.sel`,
  `.settings-switch:checked`).
- **`caution` (`@color_03`)** — reserved for a failure line. **This design adds no low-battery
  colour.**

Do **not** introduce a per-tier hue. There are three modes and two semantic colour roles
(accent = ON, `@color_10` = where you are); a rainbow would claim an ordering the daemon does not
state and reintroduce the five-glyph spread the owner rejected.

## Typography

No new type scale. The header is `.settings-nav-title` (13.5/650) with `.battery-header-pct`
(12.5/600, `tabular-nums`). The hero is `.battery-hero-primary` (**30px/700**) over
`.battery-hero-sub` (12/muted). The mode label is 9.5px/600 uppercase in `ink-muted`. The variant
option is the `.settings-rowact` 11px/600. The selected profile's name is 12.5/600; its mode·tier line
is 10.5/muted. Everything else is the existing 11/10.5 vocabulary.

The hero is 30px and nothing else is, deliberately: the panel exists to answer *“how long have I
got?”*; the selector answers *“in which mode?”*.

## Layout & Spacing

A single **312px** column, identical to the settings panel and the Wi-Fi popup, anchored under the
bar icon.

| Property | Value | Source of the rule |
|---|---|---|
| `widthRequest` | `312` | `SettingsPanel.PANEL_WIDTH`; `BatteryPopup` |
| anchor | `TOP \| LEFT`, `exclusivity: IGNORE`, `layer: OVERLAY` | `BatteryPopup` (`IGNORE` is mandatory) |
| `marginTop` | `52` | `BatteryPopup` |
| `marginLeft` | `iconCentre − 156`, clamped to `[8, monitorWidth − 320]` | `BatteryPopup` |
| keymode | `NONE`, constant | `BatteryPopup` — nothing here accepts typed input |
| dismiss | catcher click-outside + `Esc` controller + `ags request popup-close` | `BatteryPopup` / `app.tsx` |

**Body order is fixed:**

```
nav-header   [battery glyph]  Battery  ·····················  82%    ← PINNED, sibling of the body
────────────────────────────────────────────────────────────────
hero         2h 14m                                                  ← largest text
             remaining                                                ← the qualifier
divider       .settings-divider
"POWER MODE"  .settings-section-label
  MODE RAIL   one 72×54 cell per declared MODE (3), daemon-independent
"VARIANT"     .settings-section-label          ← ONLY when the selected mode has >1 variant
  VARIANT     one .settings-rowact pill per variant profile
  rail-meta   <profile_name>  /  <mode> mode · <base_profile> tier    ← stated ONCE
────────────────────────────────────────────────────────────────
footer        Power Options        opens power-options-gtk      ›     ← deep-link row
```

The rail's hard geometric rule: `312 − 2×11 − 2×8 = 274px` usable. Three 72px mode cells plus two 8px
gaps = **232px**: one row, centred, 42px of slack. A fourth mode (the Unlisted fallback) wraps to a
second row; the variant pills wrap within their row. The surface **never grows and never scrolls
horizontally**.

## Shapes

Panels 12px, mode cells and rows 7px, variant pills 7px, badges fully round. No shape changes on
selection: the selected mode cell keeps its 7px radius and gains a 2px bottom border in `@color_10`.
There is no fill behind the selected mode cell — a solid `@color_10` block behind a 24px glyph would
out-weigh the hero. The **selected variant** pill does take a faint `@color_10` wash, because it is a
small control and needs a second, denser "where you are" signal.

## Components

- **Panel** — unchanged from `BatteryPopup`: `class="settings-panel"`, the 312px `.settings-surface`,
  the full-screen `.settings-catcher` registered **before** it in `app.tsx`.
- **Nav header** — the battery glyph at the **current** state (same `batteryStateKey` the bar
  indicator resolves), the title `Battery`, and the percentage (`—` when unknown). Tabular figures.
- **Mode rail** — the first level. **One cell per declared mode** (three), each a `button` with the
  mode's glyph and a 9.5px mode label. The cell for the mode the active profile resolves into carries
  `.sel` (accent `-active` glyph + `@color_10` indicator). Tooltip names the mode and the tiers it
  declares. A fourth, neutral **Unlisted** cell appears only when an undeclared tier exists.
- **Variant control** — the second level. Rendered **only when the selected mode declares more than
  one variant**; each option is a `.settings-rowact`-geometry pill labelled with the variant's
  `profile_name`, the active one carrying `.sel` (border + wash in `@color_10`). A mono-variant mode
  renders **no control at all**.
- **Rail meta** — the selected `profile_name` and its resolution, e.g.
  `Performance++` / `Performance mode · Ultraperformance tier`. **Stated once.** For an undeclared
  tier: `Hyperdrive` / `unlisted mode · unmapped tier`.
- **Deep-link row** — `.battery-deeplink`, the `button` form of `.settings-wifi-settings-row`:
  `Power Options` + `opens power-options-gtk` + `›`. The whole row is the hit target. It mirrors the
  bar icon's **right-click** behaviour.

## The two-level selector — the load-bearing decision

**The glyph keys off the MODE, and the mode is resolved from the tier through the declaration.**

```
mode   = declaration.modeFor(profile.base_profile)        # tier → mode, via the declaration
glyph  = mode ? mode.glyph : FALLBACK                     # glyph hangs on the mode
variants = profiles.filter(p => declaration.modeFor(p.base_profile) === activeMode)
control  = variants.length > 1 ? <VariantControl/> : null  # only when it is a real choice
```

Properties the model must preserve:

- **The glyph lives on the MODE, so sharing is automatic.** Any tier a mode declares inherits its
  glyph with no extra art.
- **The key is the TIER, so renaming never breaks it.** `UpdateProfileName` changes the variant label
  and the meta line; the mode and its glyph do not move.
- **An unlisted tier falls back to the neutral glyph rather than disappearing.** A `base_profile` no
  mode declares renders under a neutral **Unlisted** pseudo-mode and writes `unmapped tier`. The
  profile stays selectable; the gap is visible on the surface rather than in a log.
- **A new profile on an existing tier joins that mode as a new variant.** `CreateProfile` on the
  `Powersave` tier adds a variant pill to Powersave mode; the mode glyph (leaf) is untouched.

`glyphFor` is now a fixed map from the **three modes** to three artworks, plus a labelled fallback:

| mode | glyph asset | source artwork |
|---|---|---|
| `Powersave` | `power-mode-powersave.svg` | `~/Downloads/power-modes/battery-empty-unplugged-default.svg` |
| `Balanced` | `power-mode-balanced.svg` | `~/Downloads/power-modes/balance-law-svgrepo-com 1.svg` |
| `Performance` | `power-mode-performance.svg` | `~/Downloads/power-modes/car-engine-1 1.svg` |
| *(unlisted)* | `power-mode-unknown.svg` | **hand-drawn fallback**, labelled |

The previous run's per-tier `power-mode-superpowersave.svg` and `power-mode-ultraperformance.svg` are
**retired as modes** — `Superpowersave` is a variant of Powersave's leaf, `Ultraperformance` is a
variant of Performance's engine. The run no longer presents five glyphs.

**A rename moves nothing.** `Performance++ → Showtime` keeps the engine: the tier
(`Ultraperformance`) still resolves to Performance mode. See `mockups/key-dynamic.html §dynamic-rename`.

**Two profiles on one tier become two sibling variants — and that is correct.** Both are selected
through the same mode; the name line says which is live.

## Icon plan

### Asset normalisation

The three sources have different viewBoxes (`1024`, `1024`, `1024` here; the retired `24` and `601.8`
sources are gone). Each is normalised by copying the source geometry **verbatim** into
`width="1024" height="1024" viewBox="0 0 1024 1024"`, wrapped in a `translate()/scale()` that maps
the measured content box into a common **860-unit content box** centred at `(512,512)`. **No path is
redrawn, re-wound or simplified.**

Outputs: `mockups/assets/power-mode-<mode>.svg` (ink `#c5c8ce`) and
`mockups/assets/power-mode-<mode>-active.svg` (accent `#dbab67`) — the same neutral/accent pairing the
sibling run stages for `settings-panel-bluetooth.svg` / `-off.svg`.

### The fallback, and its label

`power-mode-unknown.svg` is the **only** hand-drawn glyph in this run: a neutral ring-and-stem power
symbol with no tier meaning. It is drawn as a stroked `<circle>` plus a rounded `<rect>`, and every
surface that shows it also writes `unmapped tier` in text. A picture and a word, so the state never
rests on one channel.

### Manifest change (design intent, not implemented here)

The `power-mode` group in `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` keeps its
three existing mode templates (`powersave`, `balanced`, `performance`) and a
`unknown`/`fallback` variant. The retired `superpowersave`/`ultraperformance` templates are no longer
referenced by this panel. The group stays **out of `BAR_GROUPS`**: the rail sits on dark glass, so
`COLOR_FOREGROUND` resolves to the plain `foreground` and the glyph is never retargeted.

The `battery` header glyph resolves through the **existing** `battery` group exactly as the bar
indicator does. No new battery art.

## New CSS — the complete list

**Four classes are added:**

```css
/* The mode row: one 72×54 cell per declared mode. 3×72 + 2×8 = 232 ≤ 274. */
.battery-mode-rail {
  padding: 0 8px 2px 8px;
  /* flex, gap 8px, justify-content center, flex-wrap */
}
.battery-mode-cell {
  min-width: 72px;
  min-height: 54px;
  padding: 6px 2px 5px;
  border-radius: 7px;
  border-bottom: 2px solid transparent;
}
.battery-mode-cell:hover  { background-color: alpha(@color_foreground, 0.08); }
.battery-mode-cell.sel    { border-bottom-color: @color_10; }
.battery-mode-cell:disabled { opacity: 0.5; }
.battery-mode-label { font-size: 9.5px; font-weight: 600; letter-spacing: 0.05em;
                      text-transform: uppercase; color: alpha(@color_foreground, 0.62); }
.battery-mode-cell.sel .battery-mode-label { color: @color_foreground; }

/* The variant control: ONLY when the selected mode declares > 1 variant.
   Option geometry is the .settings-rowact pill; .sel is the @color_10 token. */
.battery-variant { padding: 2px 16px 8px 16px; /* flex, wrap, gap 6px */ }
.battery-variant-opt {
  font-size: 11px; font-weight: 600; line-height: 1.2;
  padding: 4px 10px; border-radius: 7px;
  border: 1px solid alpha(@color_foreground, 0.26);
  background: transparent;
}
.battery-variant-opt:hover { border-color: @color_10; }
.battery-variant-opt.sel   { border-color: @color_10; background-color: alpha(@color_10, 0.18); }
```

**And nothing else.** Every other element resolves to an existing class:

| Element | Existing class |
|---|---|
| panel body / window | `.settings-surface`, `window.settings-panel` |
| catcher | `.settings-catcher`, `.settings-catcher-fill` |
| nav header / title | `.settings-nav-header`, `.settings-nav-title` |
| header glyph / percentage | `.battery-header-icon`, `.battery-header-pct` |
| hero | `.battery-hero`, `.battery-hero-primary`, `.battery-hero-sub` |
| divider | `.settings-divider` |
| section label | `.settings-section-label` |
| mode glyph | `.battery-profile-icon` (18px in the shipped row; the rail sizes it 24px) |
| selected name / tier | `.settings-net-name`, `.settings-net-sub` |
| deep-link row | `.battery-deeplink` (the `button` form of `.settings-wifi-settings-row`) |

`POWER_PROFILE_ORDER` and `profileIconVariant()` in `presentation.ts` become **unused by this panel**
and are removed (or reduced to the tier-name normalisation the declaration lookup needs).

## Do's and Don'ts

| Do | Don't |
|---|---|
| Declare the tier→mode grouping (`mode → glyph → tiers`) | Infer it from a name suffix or the tier alone |
| Enumerate `profiles[]` from `GetProfilesInfo` | Render `POWER_PROFILE_ORDER` |
| Key the glyph off the **mode** the tier resolves to | Key it off `profile_name`, a filename, or the raw tier |
| Show the variant control only when a mode has >1 variant | Draw a one-option control for a mono-variant mode |
| State the selected profile **once**, under the selector | Repeat a name per mode cell |
| Write the resolution as text (`Performance mode · Ultraperformance tier`) | Imply it with a `++` suffix alone |
| Render a labelled neutral glyph for an unlisted tier | Drop the profile, or draw a blank cell |
| Carry `ON` in the rendered accent, `selected` in `@color_10` | Add a per-tier hue, or a CSS recolour layer |
| Reuse `.battery-hero*`, `.settings-rowact`, `.settings-net-*` | Invent a second settings vocabulary |
| Keep the header glyph the SAME state key as the bar | Let the header and the bar disagree |
| Keep `keymode NONE`; dismiss via catcher + `popup-close` | Grab the keyboard for a panel with no field |

---
name: AGS Battery Panel
description: Behavioral contract for the battery bar indicator's left-click panel — the two-level mode/variant power selector resolved through an explicit tier→mode declaration, the resolution rules (tier → mode; unknown tier → fallback; variant control only when >1), the selected-name-once pattern, and the mutual-exclusion rule that keeps the three full-screen catchers from stranding each other.
status: draft
updated: 2026-10-07
design: DESIGN.md
sources:
  - dotfiles/config/ags/components/battery/BatteryContent.tsx
  - dotfiles/config/ags/components/battery/BatteryPopup.tsx
  - dotfiles/config/ags/components/battery/presentation.ts
  - dotfiles/config/ags/components/battery/battery-icon.ts
  - dotfiles/config/ags/components/battery/state.ts
  - dotfiles/config/ags/services/power-service.ts
  - dotfiles/config/ags/bar/widgets/battery.tsx
  - dotfiles/config/ags/bar/widgets/network.tsx
  - dotfiles/config/ags/components/wifi/state.ts
  - dotfiles/config/ags/settings-panel/state.ts
  - dotfiles/config/ags/app.tsx
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-battery-panel-2026-10-07/mockups/
---

# AGS Battery Panel — Experience Spine

## Foundation

Desktop surface of the Hyprland dotfiles environment, rendered by AGS (GTK4) on Wayland. One bar
indicator and one panel behind its **left** click (its **right** click keeps launching
`power-options-gtk`). Power state comes exclusively from the daemon
`io.github.thealexdev23.power_daemon` over the system bus, through
`services/power-service.ts`; charge state comes from `AstalBattery` through `battery.tsx` /
`BatteryContent.tsx`. No polling: `/etc/power-options/config.toml` is monitored, because that file
is how every other frontend (including `power-options-gtk`) records a change.

The architectural rule this surface must not violate:

> **Services own state; the UI is a strictly thin reader that only forwards user intent.**

The selector is **two-level**: a **MODE** owns a glyph; a **VARIANT** is a selectable profile on a
tier the mode declares. Three glyphs, five selectable things.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Battery bar indicator | Always in the bar | Charge level + charging state; tooltip `82% — Performance++` / `2h 14m remaining`. Left-click opens the panel; right-click launches `power-options-gtk`. |
| Panel — header | Panel | The battery glyph at the **current** state key, the word `Battery`, and the percentage. |
| Panel — hero | Panel | The one number the panel exists to answer: time-to-empty / time-to-full, or the state word when there is no estimate. |
| Panel — Power Mode rail | Panel | **One cell per declared MODE** (leaf / scales / engine); the selected mode carries the accent + indicator. |
| Panel — Variant control | Panel | The selected mode's variants (profiles), shown **only when the mode has more than one**. |
| Panel — meta | Panel | The selected `profile_name` and its `<mode> mode · <tier> tier`, stated once. |
| Panel — deep link | Panel | `Power Options ›` launches `power-options-gtk`. |

**One panel, three regions, no subview.** The panel has no navigation stack and no collapsed
sections: it is short, fixed, and always fully visible. Anything that does not fit this shape belongs
in `power-options-gtk`, which the deep-link row reaches.

→ Composition reference: `mockups/index.html`, `mockups/panel.html`, `mockups/key-mode-rail.html`,
`mockups/key-declaration.html`, `mockups/key-dynamic.html`. **Spine wins on conflict.**

## Voice and Tone

Microcopy only. Brand voice lives in `DESIGN.md`.

| Do | Don't |
|---|---|
| `Battery` · `Power Mode` · `Variant` · `Power Options` | `Energy`, `Performance Mode`, `Advanced` |
| `remaining` · `full in` · `Charging` · `Discharging` | `left`, `until full`, `0m`, `calculating…` |
| `<profile_name>` **verbatim from the daemon** (`Powersave++`, `Performance++`) | Humanised guesses (`Power Saver Plus-plus`) |
| `<mode> mode` (`Performance mode`) | The mode alone, unmapped to its tiers |
| `<base_profile> tier` (`Ultraperformance tier`) | The tier alone (`Ultraperformance`), or a `++` with no word |
| `unmapped tier` for an undeclared `base_profile` | `Unknown`, `Error`, or a blank label |
| `opens power-options-gtk` | `opens the power settings app` |

Tone is terse and factual. The panel reports the daemon and the battery; it does not congratulate,
apologise, or explain what a governor is.

## The declaration and its resolution rules

**The daemon, quoted as the contract.** `GetProfilesInfo` returns:

```
{ "active_profile": <index>,
  "profiles": [ { "profile_name": <string>, "base_profile": <string> }, … ] }
```

- `base_profile` is the **stable semantic tier** — the daemon's own vocabulary:
  `Superpowersave`, `Powersave`, `Balanced`, `Performance`, `Ultraperformance`.
- `profile_name` is the user's **arbitrary instance label**, editable with `UpdateProfileName`.
- profiles are created and removed at runtime (`CreateProfile` / `RemoveProfile`); the list is the
  `profiles = [...]` array in `/etc/power-options/config.toml`.

**The declaration the panel consumes** groups those tiers under modes:

```
mode "Powersave"     glyph: leaf     tiers: [Powersave, Superpowersave]
mode "Balanced"      glyph: scales   tiers: [Balanced]
mode "Performance"  glyph: engine   tiers: [Performance, Ultraperformance]
```

### Resolution rules — the contract the view must implement

1. **tier → mode.** Resolve a profile to its mode by looking up its `base_profile` in the
   declaration: the mode whose `tiers` list contains that tier. The glyph is the **mode's** glyph, so
   every tier a mode declares shares it.
2. **The tier is the key; the declaration supplies the grouping.** Because the key is the stable
   `base_profile`, a rename (`UpdateProfileName`) changes only the variant label and the meta line —
   never the mode or the glyph. Because the grouping is declared, `Superpowersave` and
   `Performance++` resolve to leaf and engine respectively, not to a `++`-stripped guess.
3. **unknown / unlisted tier → fallback.** A `base_profile` no mode lists renders under the neutral
   **Unlisted** pseudo-mode with the labelled fallback glyph, and the meta line reads
   `unlisted mode · unmapped tier`. The profile is never dropped and never drawn blank.
4. **variant control renders ⇔ the selected mode has more than one variant.** A mono-variant mode
   (Balanced) renders **no control at all**; a multi-variant mode renders one `.settings-rowact`
   pill per variant profile, the active one marked. Variants are the profiles that resolve into the
   mode, in daemon order.
5. **Selection is by index, resolved to a profile.** Clicking a mode cell selects the variant the
   daemon currently offers for that mode (or the mode's sole variant); clicking a variant pill
   selects that `profile_name`. The write is the daemon's `profile_override` — a read-modify-write of
   the config document, exactly as `setPowerProfile` does today. `isActiveProfile`'s
   case-insensitive name comparison is replaced by `i === active_profile`; the index is unambiguous
   and rename-proof.

**Why this answers the owner's rejection.** The rejected flat rail drew five cells with five glyphs,
and `Powersave++` / `Powersave` read as a duplication while the real tier difference was invisible.
The two-level selector draws **three** mode glyphs and, for the selected mode, names its variants
once. There is no longer a place for a duplicate to appear, and the glyph spread matches the three
icons the owner supplied.

**No name munging.** There is no `++`-stripping. The old
`profileIconVariant(id).replace(/\+\+$/, "")` inferred a tier from a name and got
`Performance++ → performance` — wrong on this machine, where `Performance++` is
`Ultraperformance`. `POWER_PROFILE_ORDER` and `profileIconVariant()` become dead and are removed.

## Component Patterns

Behavioral rules. Visual specs live in `DESIGN.md.Components`.

| Component | Behavioral rules |
|---|---|
| Bar indicator | Unchanged: resolves `getBarMappings("battery").states[batteryStateKey(pct, charging)]`, 36px, records pointer x on hover. Left-click closes the settings panel and the Wi-Fi popup, then toggles this panel. Right-click runs `power-options-gtk`. |
| Panel window | `anchor TOP\|LEFT`, `exclusivity IGNORE`, `layer OVERLAY`, `marginTop 52`, `keymode NONE` (constant). `Esc` closes. Mirrors `BatteryPopup` verbatim. |
| Catcher | `BatteryPopupCatcher`, full-screen `.settings-catcher` / `-fill`, registered **before** the panel in `app.tsx` so the panel stacks above it. Click-outside closes. |
| Nav header | Battery glyph = `batteryStateKey(percentage, charging)` → the **bar** group. Percentage = `formatPercentage(pct)` (`—` when unknown), tabular figures. |
| Hero | `formatBatteryTime(seconds, charging)`: `primary` + `sub`. Discharging → `2h 14m` / `remaining`. Charging → `1h 05m` / `full in`. No estimate → the capitalised state word where the number was, **never `0m`**. |
| Mode rail | One `button` cell per **declared mode**, in declaration order, each with its glyph and a mode label. `sensitive = powerReady` (all cells). Click → select that mode's offered variant. Tooltip names the mode and its declared tiers. |
| Mode rail — Unlisted cell | A fourth, neutral cell appended **only** when an undeclared tier exists; its tooltip says `unmapped tier`. |
| Variant control | Rendered **only when the selected mode has >1 variant**. One pill per variant profile in daemon order, labelled `profile_name`; the active one carries `.sel`. Absent entirely for a mono-variant mode. |
| Selected mode cell | Accent glyph (`-active` asset) + 2px `@color_10` bottom border. The cell keeps its size and position; nothing reflows when the selection moves. |
| Selected variant | `.sel` pill: border + faint wash in `@color_10`. Two channels (indicator + label) so colour is never alone. |
| Rail meta | The selected entry's `profile_name` (12.5/600) and `<mode> mode · <base_profile> tier` (10.5/muted), printed **once**. Unlisted tier → `unlisted mode · unmapped tier`. With no active profile yet (`powerReady` false) the rail is dimmed and the meta line reads `—`. |
| Deep-link row | `button.battery-deeplink`, whole row is the hit target. Launches `power-options-gtk`; a launch failure logs to `console.error`, never a dialog. |
| Battery binding | `percentage` (0..1), `charging`, `is-present`, `time-to-full`, `time-to-empty` — read live; the panel is hidden when `!is-present`. |

## State Patterns

### Selector states

| State | Trigger | Treatment |
|---|---|---|
| **Default** | `GetProfilesInfo` returned | Three mode cells. The mode the active profile resolves into carries accent + indicator. Its variant control renders if >1 variant; the name/mode/tier sit under it. |
| **Mono-variant mode selected** | active profile's mode declares 1 variant (Balanced) | **No variant control at all.** The absence is the design; the panel is shorter. |
| **Multi-variant mode selected** | mode declares 2+ variants | Variant pills render; the active one is marked. |
| **Before the daemon answers** | `powerReady === false` | Every cell and pill insensitive (opacity 0.5); the meta line reads `—`. |
| **A profile is added** | `CreateProfile` → `config.toml` changes → monitor fires | If its tier is declared, a variant pill appears in that mode; if undeclared, the Unlisted mode cell appears. No restart. See `key-dynamic.html §dynamic-new-variant`. |
| **A profile is removed** | `RemoveProfile` → monitor fires | The variant pill (and the mode cell, if it now has zero variants) disappears; the correct cell takes the accent on the next read. No placeholder, no toast. |
| **A profile is renamed** | `UpdateProfileName` → monitor fires | Only the variant label, tooltips and the meta line change. **The mode and glyph do not move**, because the tier did not. See `§dynamic-rename`. |
| **Undeclared tier** | `base_profile` not in any mode's `tiers` | The profile renders under the neutral **Unlisted** pseudo-mode with the labelled fallback; meta `unmapped tier`. Stays selectable; never dropped. |
| **Two profiles, one tier** | e.g. two profiles on `Powersave` | Two sibling variant pills in the same mode; one glyph (leaf). **Correct, not a bug.** |
| **Selection click** | a mode cell or variant pill is clicked | `setPowerProfile(profile_name)` → `UpdateConfig(profile_override)` → on success the accent/`sel` moves and the meta line updates. The selector follows the daemon's `active_profile`, not an optimistic local move. |

### Panel states (the hero)

| State | Condition | Treatment |
|---|---|---|
| **Discharging, estimate** | `charging = false`, `time-to-empty > 0` | `primary` = `2h 14m`, `sub` = `remaining`. |
| **Charging, estimate** | `charging = true`, `time-to-full > 0` | `primary` = `1h 05m`, `sub` = `full in`. Header glyph carries the accent bolt. |
| **No estimate** | `seconds ≤ 0`, non-finite, or `> 24h` | `primary` = `Charging` / `Discharging`, no number. **Never `0m`.** *Flagged:* the shipped `formatBatteryTime` currently returns this word in `sub` with an empty `primary`; reconcile before build. |
| **Full** | `100%`, charging | `Charging` (no estimate at 100%). Header `battery-100-charging`. |
| **Low battery** | `< 25%` | Header `battery-0`. **No new colour.** |
| **No battery** | `is-present = false` | The whole indicator (and therefore the panel) is hidden. |
| **Unknown percentage** | `capacity` missing | Header reads `—`; the hero renders from the estimate or its state word. |

## Interaction Primitives

**Mouse-first, keyboard-supported.**

- Left-click the bar icon — open the panel under the icon (second left-click, same spot, closes it).
- Right-click the bar icon — launch `power-options-gtk`.
- Click a mode cell — select that mode's offered variant.
- Click a variant pill — select that profile.
- Hover a mode cell or variant pill — wash / border lift; tooltip names it.
- Click `Power Options ›` — launch `power-options-gtk`.
- Click outside, or `Esc`, or the global `ags request popup-close` — dismiss.

**Banned:** opening on hover; auto-hiding on a timer; hardcoding a profile order; keying a glyph off
`profile_name`; a one-option variant control; a per-tier colour; a CSS recolour/filter; a second
overlay live at the same time; running `power-options-gtk` from the view without a failure log;
keyboard grab (`keymode` stays `NONE`).

## Mutual exclusion — the defect the previous attempt shipped

**Three overlays each own a full-screen click-catcher:** the settings panel, the Wi-Fi popup, and
this battery panel. Each catcher is registered **before** its panel so the panel stacks above. If two
panels are visible at once, **both catchers are live**, the top one swallows every click outside
itself, and the panel underneath is **unreachable** — a click that looks like it dismissed one
overlay has silently dismissed neither. **Opening any one of the three MUST close the other two.**

The rule is coordinated by **callers**, never by the state module (`components/battery/state.ts`
imports nothing from `settings-panel/**`):

1. `settings-panel/state.open()` calls `closeBatteryPopup()`.
2. `bar/widgets/battery.tsx`'s left-click calls `close()` (settings) and `closeWifiPopup()` **before**
   `toggleBatteryPopup()`.
3. `BatteryPopup` stands down if `wifiPopupVisible()` becomes true while it is open — the reverse
   direction, without editing `network.tsx`.

This is already written in `BatteryPopup.tsx`; the design **keeps it verbatim** and makes it a hard
acceptance criterion of the selector's host. Any change that lets two of these overlays share the
screen is wrong by construction.

## Deep-link row

`Power Options · opens power-options-gtk · ›` is the panel's one escape hatch. The panel can set the
profiles the daemon offers, but the daemon's own GTK frontend exposes settings this panel does not
model (per-policy CPU scaling, thresholds). Rather than duplicate that surface, the last row hands
off to the real one. **The whole row is the hit target** (a `button.battery-deeplink`), because a
footer whose only clickable pixel is a 10px chevron is a miss most of the time. It mirrors the bar
icon's right-click so the behaviour is discoverable from either place, and a spawn failure lands in
`console.error`, never a modal.

## Accessibility Floor

- Every interactive element has a tooltip naming it and its target
  (`"Performance++ · Ultraperformance tier"`, `"Power Options — opens power-options-gtk"`).
- The selected mode is conveyed by **two** channels: the accent glyph **and** the 2px indicator.
- The selected variant is conveyed by **two** channels: the pill's border/wash **and** the name
  printed beneath — never colour alone.
- The unlisted tier is conveyed by **two** channels: the distinct neutral glyph **and** the words
  `unmapped tier`.
- The mode and variant controls are keyboard-reachable as ordinary buttons; `Esc` closes the panel.
  The panel traps no focus and holds no keyboard.
- The hero's missing-estimate case is legible without the number: the capitalised state word is the
  carrier, not a silent empty line.
- Long `profile_name`s ellipsize in the variant pill and the meta line with the full name in the
  tooltip; they never widen the surface. Variant pills wrap rather than overflow.

## Key Flows

### Flow 1 — Drop into a quieter mode for a meeting (juan david, 13:58, about to share screen)

1. He left-clicks the battery glyph. The panel drops under the icon. The hero reads `2h 14m /
   remaining`; the mode rail shows leaf / scales / engine with the accent on **Performance**, and the
   variant control offers `Performance` and `Performance++`.
2. He creates a `Meetings` profile in `power-options-gtk` on the `Powersave` tier.
3. **Climax:** the `Powersave` mode's variant control has already grown a `Meetings` pill — the mode
   glyph (leaf) is untouched, because the tier was already declared. He clicks it; the accent moves,
   and the meta line reads `Meetings` / `Powersave mode · Powersave tier`.
4. Failure: the daemon is not running (`powerReady = false`). The selector is dimmed, the meta line
   reads `—`, and no click silently does nothing.

### Flow 2 — The two levels (the owner's model)

1. He opens the panel and sees three mode glyphs, not five.
2. He selects **Powersave**.
3. **Climax:** the variant control appears below the rail with `Powersave` and `Powersave++` — one
   leaf, two choices — and the meta line spells out `Superpowersave tier`. The two profiles that used
   to read as duplicated text rows are now two labelled variants under a single glyph.

### Flow 3 — A rename that must not move the art

1. He renames `Performance++` to `Showtime` (tier unchanged: `Ultraperformance`).
2. The `config.toml` monitor fires; the service re-reads `GetProfilesInfo`.
3. **Climax:** Performance mode is still selected with the same engine glyph; only the variant pill
   and the meta line change to `Showtime`. The name is the user's; the tier is the daemon's; the art
   belongs to the mode.

### Flow 4 — A future tier (the fallback)

1. A daemon update reports a profile on a `base_profile` no mode declares.
2. **Climax:** a neutral **Unlisted** mode cell appears with the labelled fallback glyph, and if it is
   the active profile the meta line reads `unlisted mode · unmapped tier`. The profile is fully
   selectable; nothing is silently dropped.

### Flow 5 — The panel over the Wi-Fi popup (the defect)

1. He has the Wi-Fi popup open, clicks the battery glyph.
2. The left-click handler closes the Wi-Fi popup **first**, then opens the battery panel.
3. **Climax:** exactly one catcher is live. A click outside dismisses the battery panel rather than
   being swallowed by a Wi-Fi catcher that is still on top.
4. Failure (the reverse direction): if the Wi-Fi popup opens while the battery panel is up,
   `BatteryPopup`'s effect sees `wifiPopupVisible()` and closes itself.

## Inspirations & Anti-patterns

- **Lifted from the Wi-Fi popup / settings panel:** the 312px surface, the `settings-nav-header` as
  a sibling of the body, `marginTop 52`, `Exclusivity.IGNORE`, `Keymode.NONE`, the catcher-before-
  panel ordering, the whole-row deep-link, and the guard-exempt panel glyph discipline.
- **Lifted from the shipped battery block in `style.css`:** `.battery-hero*`, `.battery-header-*`,
  `.battery-profile*`, `.battery-deeplink`, and the `formatBatteryTime` contract.
- **Lifted from the sibling Bluetooth run:** the palette, the mock structure, and the neutral/accent
  asset pairing (`settings-panel-bluetooth.svg` / `-off.svg` → `power-mode-*.svg` / `-active.svg`).
- **Lifted from the daemon:** `base_profile` as the stable key, and `config.toml` as the change
  channel — the mechanism `watchPowerOptionsConfig` already implements.
- **Rejected — a flat one-glyph-per-profile rail.** It asked for five glyphs from three supplied
  icons and made `Powersave`/`Powersave++` read as duplicates. The owner's model groups tiers into
  modes.
- **Rejected — keying the glyph off `profile_name`, or stripping `++`.** `Performance++` is
  `Ultraperformance`, not `performance`; and a rename breaks any suffix rule.
- **Rejected — keying the glyph off `base_profile` alone.** `base_profile` is stable but yields five
  tiers, not three; the grouping is declared, not derived.
- **Rejected — a one-option variant control.** A picker with one choice is decoration; a mono-variant
  mode renders no control.
- **Rejected — dropping or blanking an undeclared tier.** A newer daemon tier must not silently
  remove a user's profile; the labelled fallback keeps it usable and makes the gap visible.
- **Rejected — a per-tier colour.** Hue carries exactly two meanings in this family (accent = ON,
  `@color_10` = where you are). Three modes spanning two roles is plenty.
- **Rejected — a modal / a confirm on profile select.** Selecting a governor is cheap and reversible.

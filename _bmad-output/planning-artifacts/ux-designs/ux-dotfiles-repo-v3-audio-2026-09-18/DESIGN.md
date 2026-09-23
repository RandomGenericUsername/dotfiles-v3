---
name: AGS Audio Control
description: PipeWire/WirePlumber audio control for the Hyprland dotfiles desktop — a bar output indicator, a bar mic indicator, and a follower-anchored audio popup (outputs, per-application streams with routing, inputs, recorders). Visual identity inherits the existing GUI-unification language and the AGS settings panel; the runtime wallpaper palette is the only ink.
status: final
updated: 2026-09-21
sources:
  - docs/linux-wayland-pipewire-ags-audio-control.md
  - _bmad-output/planning-artifacts/gui-unification-ux-spec.md
  - openspec/changes/add-ags-settings-panel/
colors:
  # Semantic roles map onto runtime palette slots 1:1 (values below are the
  # live palette of 2026-09-18; a wallpaper swap restyles every surface).
  surface-panel: '{color_00} @ 0.94 alpha'        # #0c131d — glass panel
  surface-panel-border: '{color_04}'               # #513f50 — 1.5px
  surface-card: '{color_01} @ 0.18 alpha'          # #293549 — cards
  surface-row-active: '{color_10}'                 # #c2463e — selected device / list row
  ink-primary: '{color_foreground}'                # #c2c4c6
  ink-muted: '{color_foreground} @ 0.55 alpha'
  hairline: '{color_foreground} @ 0.12 alpha'
  action-primary: '{color_06}'                     # #a41e24 — primary action / active toggle
  action-active: '{color_06} @ 0.18 alpha + {color_06} border'
  slider-track: '{color_foreground} @ 0.16 alpha'
  slider-fill: '{color_13}'                        # #d96451
  slider-thumb: '{color_15}'                       # #c2c4c6
  signal-live: '#2ecc71'                           # literal green — "a recorder is consuming the mic"
typography:
  # Inherited from the AGS settings panel; no new type scale.
  card-title:
    fontSize: 12.5px
    fontWeight: '650'
  row-title:
    fontSize: 13px
    fontWeight: '600'
  row-subtitle:
    fontSize: 11px
    fontWeight: '400'
    color: '{colors.ink-muted}'
  bar-percent:
    fontSize: 12.5px
    fontWeight: '600'
    fontVariantNumeric: tabular-nums
rounded:
  panel: 12px
  card: 9px
  row: 5px
  pill: 8px
spacing:
  panel-padding: 11px
  card-padding: 10px 11px
  row-gap: 8px
components:
  panel:
    background: '{colors.surface-panel}'
    border: '1.5px solid {colors.surface-panel-border}'
    radius: '{rounded.panel}'
  card:
    background: '{colors.surface-card}'
    border: '1px solid {colors.hairline}'
    radius: '{rounded.card}'
  level-slider:
    track: '{colors.slider-track}'
    fill: '{colors.slider-fill}'
    thumb: '{colors.slider-thumb}'
  list-row:
    background: transparent
    active-background: '{colors.surface-row-active}'
    active-foreground: '{colors.ink-primary}'
    radius: '{rounded.row}'
  routing-select:
    background: '{color_foreground} @ 0.06 alpha'
    border: '1px solid {color_foreground} @ 0.14 alpha'
    radius: '{rounded.pill}'
  bar-indicator:
    background: transparent
    glyph-size: 28px
  live-dot:
    background: '{colors.signal-live}'
    size: 8px
---

## Brand & Style

The dotfiles desktop is a personal, single-user Hyprland environment whose interface language was set by the GUI-unification effort and the AGS settings panel: translucent glass panels over the wallpaper, the generated wallpaper palette as the *only* ink, and two accents with two fixed meanings. Audio control is not a new product — it is a new room in a house that already has a style. It inherits that style completely and adds no third accent, no new type scale, and no new surface vocabulary.

The governing posture, inherited verbatim from the PipeWire control document, is:

> **AGS is a frontend to the audio system, never a second audio-management system.** PipeWire/WirePlumber own the graph; the UI is generated from the live graph rather than from a fixed list of applications.

Visually this means the popup must never look like a settings form the user maintains. It is a live mirror: sections appear because streams exist and vanish when they end. The interface is quiet when nothing is happening and dense when the graph is busy.

## Colors

The palette is the runtime wallpaper palette. No literal colours appear in any audio surface **except** `signal-live` — the green that means "a recording stream is active." That exception is deliberate and matches the existing recording dot and wallpaper `LIVE` badge: a semantic signal that must survive every wallpaper, not decoration.

- **`surface-panel` (`@color_00` at 0.94)** — the glass body of the popup. Translucency is for the panel only.
- **`surface-card` (`@color_01` at 0.18)** — each section (Output, Applications, Input, Recording) sits on a card above the panel.
- **`surface-row-active` (`@color_10`)** — the selected output device or the active list row, filled solid. This is the "where you are" accent. Text on it is `ink-primary` (foreground), never background: the live palette's `@color_10` is bright enough for foreground text and background-on-`@color_10` fails contrast.
- **`action-primary` (`@color_06`)** — the "what you can do" accent, used for active toggles and primary affordances. Kept distinct from selection on purpose.
- **Slider** — track is a foreground tint, fill is `@color_13`, thumb is `@color_15`. One slider look across the popup and the settings panel.
- **`signal-live` (`#2ecc71`)** — literal green, used only for the mic-live dot (bar and Recording card header).

Do not introduce a red "record" colour, a blue "output" colour, or any hue that carries meaning the palette did not assign. The two-accent discipline from the GUI-unification spec holds.

## Typography

The audio surfaces add no type scale. Card titles use the settings panel's 12.5px/650; row titles 13px/600; row subtitles 11px muted; the bar percentage 12.5px/600 with tabular numerals so the value does not jitter as it changes. Device and stream names are truncated with an ellipsis rather than wrapped — rows keep a fixed height so the popup does not reflow as names change.

## Layout & Spacing

The popup is a single 356px column, follower-anchored under the output bar indicator on the primary monitor. It grows downward; when it would exceed the monitor it scrolls, matching the settings panel's scroll behaviour. Section order is fixed: **Output · Applications · Input · Recording**.

Every row uses one layout rule: **the top line carries the leading control, the name/subtitle, and any trailing control (mute, routing); the slider line carries the track and the percentage.** The percentage never sits on the title line. This is the single rule that keeps output, application, and recording rows visually identical.

Sections with no content **collapse entirely** — no empty placeholder row and no "No apps playing" line. The popup height therefore follows the live audio graph.

## Elevation & Depth

Inherited from the settings panel: the panel casts a soft shadow (`0 18px 48px rgba(0,0,0,.5)`) and sits above a transparent catcher window; cards have no shadow and are separated by a hairline border only. Depth is not used as a hierarchy device beyond the single panel-over-desktop step.

## Shapes

Panels use a 12px radius, cards 9px, list rows 5px, routing pills 8px. The subview (device list) is the same panel with its content swapped — same dimensions, same radius, no shape change on navigation. The live dot is a full circle.

## Components

These are the audio surface components, built on the settings panel's existing primitives (`PanelCard`, `LevelSlider`, catcher window) rather than new ones.

Transport and master glyphs resolve through the `media-transport` icon group (`play`, `pause`, `previous`, `next`), ITR-rendered like every other system icon — never inline paths. The group maps `COLOR_FOREGROUND: foreground`, so the glyphs inherit the runtime wallpaper palette like the rest of the popup, and it is strictly popup-internal (not in `BAR_GROUPS`, so the bar-icon contrast guard never touches it).

- **Audio bar indicator** — bare glyph (no pill, no background), 28px, using the existing `volume` icon group (level-aware: muted/lowest/low/medium/max) plus the live percentage label. Transparent button; the glyph and text float directly over the wallpaper and are covered by the bar-icon contrast guard.
- **Microphone bar indicator** — bare glyph, 28px, using the `microphone` icon group (`mic-on` / `mic-off`). When any recording stream is active it carries the `live-dot`; otherwise no dot. Left-click opens the popup focused on the Input section.
- **Audio popup panel** — the glass panel described above, follower-anchored under the output indicator, dismissed on `Esc` and click-outside.
- **Section card** — `PanelCard` with a title and one or more rows. Cards: Output, Applications, Input, Recording.
- **Level row** — a device or stream: leading mute/level glyph, name + subtitle, optional trailing routing select, then a `LevelSlider` row with the percentage. Used by output, applications, input, and recording.
- **Routing select** — compact trailing control on each playback row; opens a menu of the live speakers collection. Selecting writes `stream.target-endpoint`; volume and mute are untouched.
- **Device subview** — tapping `Change ›` in the Output card swaps the panel to a device list (each row: icon, name, subtitle, check on the active device) with a `‹` back arrow. Same in-place navigation the settings panel uses for Wi-Fi/Bluetooth; panel dimensions stay stable. The **active-device checkmark** (`✓`) plus the active-row fill mark the current default sink; selecting any other row sets the default and returns. Default only governs new/unrouted streams — existing routed streams are untouched.
- **Transport line** — a fourth line on an Applications row, below the volume `LevelSlider`, rendered **only** when that stream has a matching MPRIS player: `⏮ ▶/⏸ ⏭ · seek slider · elapsed / duration` (`1:24 / 4:02`, elapsed-only when duration is unknown). Prev/next glyphs appear only when the player exposes `CanGoPrevious`/`CanGoNext`; the seek slider appears only when it exposes `CanSeek`. A paused player renders dimmed (fill and title at reduced opacity) with the time frozen. Glyphs come from the `media-transport` icon group.
- **Master play/pause** — a bordered `▶/⏸` button in the Output card's head row, between the name/meta block and `Change ›`. It reflects the most recently active player and is **hidden** when no player exists. Tooltip: `Play/Pause — <identity> (most recent)`.
- **Live dot** — the literal-green dot marking active recording, used at most in two places: the mic bar indicator and the Recording card header.

## Do's and Don'ts

| Do | Don't |
|---|---|
| Generate sections from the live AstalWp collections | Hard-code application names, or assume one app equals one stream |
| Keep one row layout rule across output/app/input/recording rows | Put the percentage on the title line or vary row structure per section |
| Collapse empty sections | Show "No apps playing" placeholder rows |
| Use `@color_10` for selection and `@color_06` for actions | Collapse the two accents into one or introduce a third |
| Use `signal-live` only for active recording | Use the green decoratively or for output state |
| Anchor the popup under its triggering icon | Anchor to a fixed screen edge |
| Reuse `PanelCard` / `LevelSlider` / catcher / subview patterns | Invent new visual primitives for audio |
| Render the transport line only when a stream has an MPRIS player | Give every row transport controls, or a disabled transport for no-player rows |
| Resolve transport/master glyphs through the `media-transport` group | Inline hand-drawn paths or a third icon group |
| Keep device list navigation in-panel with a back arrow | Open a second window or stack panels |

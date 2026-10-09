---
name: AGS Audio Panel Redesign
description: Compact, wallpaper-aware audio controls with a preferred output and independent app playback.
status: final
updated: 2026-10-09
sources:
  - EXPERIENCE.md
  - mockups/audio-panel-redesign-concept.html
  - openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md
  - _bmad-output/planning-artifacts/gui-unification-ux-spec.md
  - docs/linux-wayland-pipewire-ags-audio-control.md
colors:
  surface-panel: 'alpha(@color_00, 0.94)'
  surface-card: 'alpha(@color_01, 0.18)'
  ink-primary: '@color_foreground'
  ink-secondary: 'alpha(@color_foreground, 0.72)'
  ink-muted: 'alpha(@color_foreground, 0.64)'
  divider: 'alpha(@color_foreground, 0.12)'
  selection: '@color_10 fill; on-selection text follows GUI-unification contrast rule'
  action: '@color_06'
  slider-track: 'alpha(@color_foreground, 0.16)'
  slider-fill: '@color_13'
  slider-thumb: '@color_15'
  focus-ring: '@color_10, 2px'
  signal-live: '#2ecc71'
typography:
  panel-title:
    fontFamily: 'system-ui sans-serif'
    fontSize: 16px
    fontWeight: '650'
    lineHeight: '1.3'
  section-label:
    fontFamily: 'system-ui sans-serif'
    fontSize: 11px
    fontWeight: '700'
    letterSpacing: '0.075em'
  media-title:
    fontFamily: 'system-ui sans-serif'
    fontSize: 12px
    fontWeight: '650'
    lineHeight: '1.3'
  supporting-label:
    fontFamily: 'system-ui sans-serif'
    fontSize: 10px
    fontWeight: '400'
  numeric-value:
    fontFamily: 'system-ui sans-serif'
    fontSize: 11px
    fontWeight: '600'
    letterSpacing: '0'
rounded:
  sm: 8px
  md: 10px
  lg: 14px
  xl: 18px
  full: 9999px
spacing:
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  5: 20px
  panel-inset: 12px
components:
  audio-popup:
    background: '{colors.surface-panel}'
    radius: '{rounded.xl}'
    max-width: 408px
    focus: '{colors.focus-ring}'
  section-card:
    background: '{colors.surface-card}'
    border: '{colors.divider}'
    radius: '{rounded.lg}'
    padding: '{spacing.3}'
  preferred-output-selector:
    radius: '{rounded.md}'
    active: '{colors.selection}'
  app-media-row:
    artwork: '43px square, cropped, rounded {rounded.sm}'
    divider: '{colors.divider}'
  route-selector:
    radius: '{rounded.sm}'
    selected: '{colors.selection}'
  app-transport:
    primary-action: '{colors.action}'
  seek-slider:
    fill: '{colors.slider-fill}'
    thumb: '{colors.slider-thumb}'
  app-level-control:
    fill: '{colors.slider-fill}'
    thumb: '{colors.slider-thumb}'
  input-device-control:
    radius: '{rounded.md}'
  microphone-activity-row:
    live-signal: '{colors.signal-live}'
  bar-audio-indicators:
    background: 'transparent'
    glyph-size: 28px
  settings-sound-control:
    level-fill: '{colors.slider-fill}'
---

## Brand & Style

The audio panel is a compact desktop control surface, not a second audio-management system. It mirrors PipeWire/WirePlumber and MPRIS state, keeps app and device scopes visually distinct, and inherits the dotfiles' wallpaper-generated palette. It should feel quiet when few apps are active and remain legible when rows and device names are dense.

The approved hierarchy and row composition are shown in [the audio-panel redesign concept](mockups/audio-panel-redesign-concept.html). This mock illustrates layout and interaction. Its hand-built colors are placeholders; the generated runtime palette is authoritative.

## Colors

The audio UI inherits the wallpaper-generated runtime palette through AGS `colors.css`, the same source used by the status bar, Settings panel, and GTK surfaces. [`app.tsx`](../../../../dotfiles/config/ags/app.tsx) loads that generated file after AGS starts. New panel styles belong in the shared AGS stylesheet and use its `@color_*` tokens; components must not introduce their own fixed theme or inline hex colors. The palette contract is documented in [GUI unification](../../gui-unification-ux-spec.md), and existing [AGS audio/settings rules](../../../../dotfiles/config/ags/style.css) are the implementation precedent. The browser mock uses a fixed sample palette only to show hierarchy and interaction; it is not evidence of final theme rendering.

- `{colors.surface-panel}` is the glass popup surface; `{colors.surface-card}` distinguishes sections.
- `{colors.ink-primary}`, `{colors.ink-secondary}`, and `{colors.ink-muted}` provide readable information hierarchy. Small text uses at least 64% foreground opacity; lower-emphasis decoration must not carry required information.
- `{colors.selection}` uses the established AGS selected-row fill, `@color_10`. Its text color is resolved by the [GUI-unification on-selection rule](../../gui-unification-ux-spec.md#text-on-fill-contrast-rule): use `@color_background` when it reaches 4.5:1 against the fill, otherwise use `@color_foreground`. Validate both candidates across generated palettes; if neither passes, the shared palette generator must expose a computed on-selection token. The current Settings row's foreground choice is a precedent for the current wallpaper, not a universal fixed pairing.
- `{colors.action}` uses `@color_06`, the GUI-unification primary-action role. `{colors.slider-fill}` uses the existing AGS slider slot `@color_13`; `{colors.slider-track}` uses `alpha(@color_foreground, 0.16)`. Slider fill indicates level/position, never mute by itself. Match the shared Settings slider thumb token `{colors.slider-thumb}` (`@color_15`).
- `{colors.focus-ring}` uses a 2px visible ring in `@color_10`, consistent with existing AGS controls. Focus and control boundaries must reach 3:1 against adjacent colors; small text must reach 4.5:1.
- `{colors.signal-live}` is the single fixed semantic color for active microphone use. Mute, route intent, and selection are also expressed through icon, text, and selected state, never color alone.

## Typography

Use the platform sans-serif stack and the compact roles in the frontmatter. Media title and device labels remain readable above supporting metadata. Percentages and playback times use tabular numerals so changing values do not change the row geometry. Text may ellipsize in the row but its full value remains available through a tooltip and accessible description.

## Layout & Spacing

The panel is a single-column surface with a 408px maximum design width and `{spacing.panel-inset}` inset. It may narrow to the available monitor work area, with a 320px preferred minimum when available. Its content scrolls vertically; horizontal clipping is not allowed. At constrained widths or increased text scale, supporting labels can wrap and route controls may move below the media header while preserving their association and reachability.

Section order is Preferred output → Playing → Input → Microphone activity. The app row groups media identity and app identity above app-scoped transport/seek and app stream level. The preferred-output section selects the destination only: device output gain is deliberately **not** exposed by the panel (owner decision 2026-10-07) and stays reachable from the Settings panel through the shared output-level action, so there is one implementation of that use case rather than two.

Historical references are retained but superseded: [key-audio-popup](mockups/key-audio-popup.html), [key-audio-transport](mockups/key-audio-transport.html), [key-alternatives](mockups/key-alternatives.html), and [key-bar-indicators](mockups/key-bar-indicators.html). They are not implementation references for this redesign. [The new concept](mockups/audio-panel-redesign-concept.html) is the current UI reference. Spines win on conflict with any mock.

## Elevation & Depth

The panel uses the established settings-surface shadow and a subtle glass border. Cards use tonal separation and a hairline only; avoid adding nested shadows that make each app row look like a separate popup.

## Shapes

Use `{rounded.xl}` for the popup, `{rounded.lg}` for section cards, `{rounded.md}` for device controls, and `{rounded.sm}` for route chips/artwork. Pill shapes are limited to compact status indicators.

## Components

Visual anatomy is shared with the behavioral definitions in [EXPERIENCE.md Component Patterns](EXPERIENCE.md#component-patterns). The [approved concept](mockups/audio-panel-redesign-concept.html) illustrates these components together.

| Component | Visual rule |
|---|---|
| Audio popup | One narrow, anchored surface; scrolls vertically; never clips controls. |
| Section card | Tonal surface, hairline edge, compact inset, uppercase section label. |
| Preferred output selector | Full-width device row with output mark, selected device name, device description, and disclosure indicator. Destination only; it carries no level or mute control. |
| App media row | Artwork, visible app name, title/artist, route chip; app identity is text, not badge-only. |
| Route selector | Compact visible selected value; separates “Follow preferred · C” from “C · Override”. When intent cannot be confirmed, shows “Route unknown · C” so the observed endpoint remains visible without claiming a follow/override choice. |
| App transport | Compact previous/play/next controls when supported, kept with that app's media. The main play/pause button uses the panel's own round-filled transport art. |
| Seek slider | Flexible track with elapsed/total time; no displacement of adjacent row controls. |
| App level control | Level-aware speaker icon, slider, numeric percent; visibly distinct from the preferred-output selector by grouping and label. Reuse the same runtime slider tokens. |
| Input device control | Device selector, level-aware mic mute, input slider and percent. |
| Microphone activity row | Visible app identity and input-use signal; separate from screen-capture status. |
| Bar audio indicators | Bare speaker/mic glyphs following the current endpoint and actual activity/mute state. |
| Settings sound control | Owns the device output-level/mute use case through the shared action; never maintains a separate volume authority. |

## Do's and Don'ts

| Do | Don't |
|---|---|
| Use `{colors.selection}` with the established AGS foreground for active route/device. | Reuse the historical output-card aggregate player control. |
| Keep the preferred-output selector and each app's stream-level control visibly and semantically distinct. | Add a device-level level or mute control back into the panel (owner decision 2026-10-07); sink gain lives in Settings. |
| Keep app name visible beside media title/artist and artwork. | Rely on an app-icon tooltip for app identity. |
| Use the runtime `colors.css` palette and shared AGS slider/focus treatments. | Treat the mock's literal colors as the final theme or add fixed color literals to components. |

---

**Review note (2026-10-09):** The changes to this spine postdate Sally's focused review (see `validation/README.md`). They were reconciled with the implemented panel and the approved concept mock on 2026-10-09 during `finish-audio-panel-redesign`: the device-level output level/mute control is removed (owner decision 2026-10-07), the preferred-output selector and its follow-default routing remain, and the panel's main transport button now carries its own round-filled art. Re-checked against the design of record at that time.

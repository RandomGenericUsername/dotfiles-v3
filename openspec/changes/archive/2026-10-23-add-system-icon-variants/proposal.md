## Why

The icon-contrast guard (`add-icon-contrast-guard`) retargets group-level
`COLOR_FOREGROUND` / `COLOR_JOIN` of `BAR_GROUPS` at `wallpaper set` time via a
staging-only overlay. It was built on a single-consumer assumption
(transparent bar over wallpaper) but the rendered files serve every surface:
the AGS bar (transparent, over wallpaper) AND dark-glass system surfaces
(settings-panel Sound card, audio popup rows) read the same SVGs through
`IconRegistry`.

Concrete breakage (2026-09-21 investigation):
`_bmad-output/planning-artifacts/icon-pipeline-contrast-handoff-2026-09-21.md:114`
("One render serves bar + panels … THE architectural gap") and
`high-contrast-icon-architecture-investigation-2026-09-21.md:14`
("no model of who consumes what — the guard knows groups, not surfaces").
On light wallpapers the guard makes `volume-*` / `microphone-*` dark — correct
on the bar, washed out on dark glass. The same speaker icon is used in 3
places (status bar + settings panel + audio popup) but contrast must only ever
touch the status-bar version.

Owner need (locked): icons in the status bar use high contrast when auto
triggers or the user selects `on` (and stay authored when `off`); icons NOT in
the status bar just follow the current palette pipeline, never retargeted.
Future authors must be able to declare "these two outputs — one for bar, one
for system" from day one.

## What Changes

- 7 new `system-*` variants reusing the SAME templates (no new SVG assets):
  `volume`: `system-muted`, `system-lowest`, `system-low`, `system-medium`,
  `system-max` (outputs `volume-system-*.svg`); `microphone`: `system-mic-on`,
  `system-mic-off` (outputs `microphone-system-*.svg`). Each carries a
  variant-level `COLOR_FOREGROUND: foreground` pin, which the guard
  structurally cannot rewrite (same mechanism as shipped `ui/search` and
  `camera-accent` / `warning-caution`).
- Bar keeps resolving bare variants (guard-eligible, `auto/on/off` unchanged).
  System surfaces resolve `system-*`:
  `components/sliders/VolumeSlider.tsx:66`,
  `audio/AudioPopup.tsx:479,480,483,484,600,665,705,806,861,887,892`.
- `icons.json` regenerated (`yaml → json.dumps(sort_keys)`); `verify_icons_samples`
  gains `volume-system-low.svg` + `microphone-system-mic-on.svg`.
- Additive overlay-preservation test for `system-*` (mirror `camera-accent`).
- `docs/Adding an Icon §14` gains the `system` wording + standing rule.
- Provisioning carries the change; success gate is `make bootstrap` green
  (owner accept). No new asset entries (whole-dir `synchronize`), no runtime /
  guard / cache / registry logic change.

## Non-goals

- No `ui` / `email-client` / `wallpaper-selector` consumer classification in
  this pilot (scoped to `volume` + `microphone` only, the verified dual-use set).
- No guard v2, no per-consumer renders, no dual cache keys, no registry API
  change, no CSS tinting, no `BAR_GROUPS` change, no threshold change.
- No new SVG artwork; no `bar_mappings` changes; no palette/effects/cache-layout
  changes; no `panel-*` naming (rejected in favor of locked `system-` prefix).

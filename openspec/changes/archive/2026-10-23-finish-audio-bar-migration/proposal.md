# finish-audio-bar-migration

## Why

The audio panel redesign (`redesign-ags-audio-panel`, reconciled by
`finish-audio-panel-redesign`) introduced a hexagonal audio boundary —
`domain/` → `application/{ports,audio-actions,runtime}` → `adapters/{pipewire,mpris}`
→ `presentation/` → `composition.ts` — and its spec now carries the
requirement **"Audio application boundaries are hexagonal"**. That requirement
says GTK widgets "render presentation state and dispatch application actions
without owning graph parsing, cross-source identity policy, or audio routing
rules."

Only the panel adopted it. **The bar's audio indicators and `app.tsx` still
import `audio/state.ts`**, a 1648-line legacy module that binds `AstalWp`
directly, derives collections by media-class, and carries the
`useEndpointEpoch` staleness workaround the redesign set out to remove
("measured: node 0.85 while the accessor still said 0.75"). So the capability
is half-adopted: the panel is a thin view, the bar is not, and the two do not
observe the same source. This directly contradicts the redesign spec, which
already says the "popup, bar volume nudge, and Settings slider SHALL use the
same selected-output level/mute application actions and observe the same source
state."

A second coupling blocks a clean retirement: `AudioPopup.tsx` *also* imports
UI scaffolding from the same legacy module (`popupVisible`, `audioIconX`,
`close`, `levelVariant`). Those are UI-local concerns, not audio-graph state, so
they must be separated before the legacy module can go.

**The merged redesign also left `audio/state.ts` almost entirely dead.** Its
graph/rows/devices machinery (`applicationRows`, `outputDeviceList`,
`inputDeviceList`, `recordingList`, `graph`, `playersOnSink`,
`streamAppIconPath`, …) has no consumer outside the module itself — the panel
moved to the hexagon. The only *live* surface is the bar's 11 symbols plus
`app.tsx`'s `open`/`close`/`debugAudioState`, and `debugAudioState` is the sole
thing keeping the rows machinery transitively alive. Once the bar and `app.tsx`
migrate, the file is deleted wholesale. `services/mpris-service.ts` (884 lines)
is likewise dead after that: only `audio/state.ts` imports it, while the
hexagon's `mpris-adapter` already talks MPRIS through the pure `mpris-core`.

This change is the first step of the "one hexagon per UI domain" program. It
finishes the audio migration so the same pattern (and the eventual package
split) can be applied to Wi-Fi, Bluetooth, battery/power, recording and tray —
each as its own follow-up change. It is sequenced after
`finish-audio-panel-redesign`, which touches `AudioPopup.tsx` and the same
`ags-audio-panel` capability.

## What Changes

- **Split `audio/state.ts` into its two real responsibilities.** UI-local state
  (popup visibility, active section, view epoch, follower anchor x) moves to
  `audio/ui-state.ts`; the pure level vocabulary (`levelVariant`, `clampVolume`)
  moves to `audio/presentation/levels.ts`. The remaining ~1600 lines (the
  graph/rows machinery — most of it already unconsumed) are deleted. (The new
  files use distinct names because `audio/state.ts` cannot coexist with an
  `audio/state/` directory.)
- **Make the bar audio indicators consumers of the composition binding.** The
  `OutputIndicator` and `MicIndicator` (`bar/widgets/audio.tsx`) derive their
  glyph and live-dot state from the projected session model
  (`audio-panel-view-model`), and their click/scroll actions dispatch the same
  application actions the panel uses. The `useEndpointEpoch` workaround
  disappears from the bar path.
- **Repoint `AudioPopup.tsx` and `app.tsx`** to the new UI-state module; redirect
  (or drop) the legacy `audio-debug` dump now that `audio-panel-debug` exposes
  the same facts from the binding.
- **Retire the now-dead `services/mpris-service.ts`.** Only `audio/state.ts`
  imports it; the hexagon's `mpris-adapter` already talks MPRIS through the pure
  `mpris-core`, so no logic needs re-homing — the service is deleted once the
  legacy module goes.
- **Add a bar-indicator projection and its unit tests.** The projection is pure
  (`ags`-free), so it is registered by name in
  `dotfiles/config/ags/tests/tsconfig.tests.json`'s purity list and covered by
  `make ags-test`, alongside the existing audio gates (`make ags-typecheck`,
  `make audio-panel-gates`).
- **Amend the `ags-audio-panel` deltas** so the hexagon requirement names the
  bar indicators as consumers and forbids any surface binding `AstalWp` outside
  an adapter.

## Non-goals

- **No visual or behavioural change to the bar indicators.** Same `volume`
  (level-aware) and `microphone` (on/off) glyphs, same left-click-to-open,
  scroll-to-nudge, right-click-to-`pavucontrol`, and the same live-dot backdrop
  behaviour.
- **Not migrating the other bar domains.** Wi-Fi, Bluetooth, battery/power,
  recording and tray remain on their current service modules; each is a separate
  change under investigation.
- **Not the monorepo split.** Publishing `src/shared/*`, externalising
  csg/weg/itr, and extracting AGS packages are later, separately-scoped changes.
- **No changes to the provisioning pipeline, the runtime engine, the event
  contract, or the icon manifest.** This is a bar/runtime-consumer refactor only.

## Impact

- `dotfiles/config/ags/audio/state.ts` (split then retirement of the graph
  remainder)
- `dotfiles/config/ags/audio/ui-state.ts` and
  `dotfiles/config/ags/audio/presentation/levels.ts` (new UI-state module and
  pure level vocabulary)
- `dotfiles/config/ags/bar/widgets/audio.tsx` (consumer of the binding)
- `dotfiles/config/ags/bar/Bar.tsx` and `dotfiles/config/ags/app.tsx`
  (binding injection + UI-state imports + debug handler)
- `dotfiles/config/ags/audio/AudioPopup.tsx` (UI-state imports)
- `dotfiles/config/ags/audio/presentation/` (bar-indicator projection)
- `dotfiles/config/ags/services/mpris-service.ts` and
  `dotfiles/config/ags/audio/adapters/mpris/mpris-adapter.ts` (fold)
- `dotfiles/config/ags/tests/ts/` and `tests/tsconfig.tests.json` (the
  bar-indicator projection test and the purity-list registration)
- `dotfiles/config/ags/tsconfig.bar.json` (allow the audio hexagon's `.ts`
  imports — a pre-existing gap this change repairs so `bar-typecheck` runs)
- `scripts/ags-typecheck.py` (drop the now-dead `state.ts` exemption)
- `openspec/changes/redesign-ags-audio-panel/validation/audio-icons.test.mjs`
  (read `levelVariant` from its new home)
- `src/provisioning/ansible/roles/{compositor_configs,verify}/vars/main.yml`
  and their unit tests (track the added/removed AGS sources — deployment is
  per-file)
- `openspec/changes/*/specs/ags-audio-panel/spec.md` (this delta)

# Tasks

## 0. Anti-drift preamble (read before editing)

Added 2026-10-03 after the first implementation pass left the popup rendering
nothing. That pass wrote `domain/`, `adapters/`, `application/`, and
`presentation/`, rewrote `AudioPopup.tsx` against a `binding` prop, and never
wired it — no task in sections 1-7 named the composition root, so the omission
had no box to fail. This section exists so the next omission is forced to
surface.

- **Worktree:** `/home/inumaki/Development/dotfiles-v3-audio-panel` on branch
  `codex/audio-panel-redesign`. Never edit `/home/inumaki/Development/dotfiles-v3`
  (`master`) — that is the live host spine.
- **Files in scope** (only these; a step needing another one must STOP and
  report before touching it):
  - `dotfiles/config/ags/audio/domain/**`, `application/**`, `adapters/**`,
    `presentation/**` — new boundary
  - `dotfiles/config/ags/audio/AudioPopup.tsx`, `audio-panel.css`, `state.ts`
  - `dotfiles/config/ags/app.tsx` — **composition root; see task 6.0**
  - `dotfiles/config/ags/bar/widgets/audio.tsx`
  - `openspec/changes/redesign-ags-audio-panel/**`
- **Invariants that hold (I1-I9):** see `IMPLEMENTATION_HARNESS.md`. The two
  most load-bearing: I2 endpoint equality never proves route intent; I6 a
  transient unlink/relink must never transfer a command to another app.
- **`state.ts` is the validated baseline, not the target.** `design.md` forbids
  a second competing global audio model. We migrate consumers onto the new
  boundary and then delete `state.ts`; it is not to be extended in parallel.
  The last hands-on-validated panel is recoverable from `master` history.
- **A module existing is not a module being wired.** Every layer must be
  reachable from `app.tsx` before its section is checkable. `grep` for the
  module from `app.tsx` is part of every acceptance step below.

## 1. Establish the current boundary and migration plan

- [x] 1.1 Map every current consumer and side effect of `audio/state.ts`, including popup, bar speaker/mic indicators, Settings volume control, MPRIS service, popup lifecycle, graph snapshot, and icon resolution. (See `validation/current-boundary-review.md`.)
- [x] 1.2 Inspect the uncommitted audio edits before implementation; separate proven fixes from debug-only changes and speculative caches/holds. (Review only; working-tree implementation edits were left intact.)
- [x] 1.3 Write a migration map from current modules to pure core, use cases/ports, PipeWire/MPRIS adapters, presentation projection, and GTK consumers. (See target seam column in `validation/current-boundary-review.md`.)
- [x] 1.4a Verify ordinary default-follow behavior, the same-as-preferred WirePlumber edge, and same-stream explicit-route reassertion feasibility using silent temporary sinks. A follow-up test reasserted A on the same stream after WirePlumber moved it A → B; it stayed at A after the next default change. Firefox and Tidal routes and the original C-Media default were restored. This verifies the PipeWire/Pulse command path, not an AGS-owned intent adapter. See `validation/README.md`.
- [x] 1.4b Inspect the live PipeWire monitor surface before choosing an adapter: default metadata (`default.audio.sink`), stream `target.object`, and effective link node IDs were observed; the same-stream command-level reassertion check passed. This confirms useful event data and route-action feasibility, not AGS reconciliation. Adapter lifecycle/event behavior is acceptance work in 3.6.
- [ ] 1.5 Compare live MPRIS metadata and AGS row projection for Chrome, Tidal, and Firefox while Playing, Paused, after seek, and after popup reopen. Playing-state MPRIS/row mismatch is confirmed for all three. A corrected Firefox MPRIS-seek capture kept `rowListWrite`, `streamRow`, and `labelWrite` stable and showed no blink in sampled frames, but Firefox's reported position disagreed with the popup and the seek advanced its playlist; physical slider-drag reproduction and the pause/reopen transition remain open. See `validation/README.md`.

## 2. Extract domain and application boundaries

- [ ] 2.1 Define pure TypeScript route intent (`FollowPreferred`, explicit endpoint, or unknown), app identity, volume/mute, and player-capability values. `node openspec/changes/redesign-ags-audio-panel/validation/audio-core.test.mjs` → 7 pass.
- [ ] 2.2 Define named application actions for preferred output, app route, output/app/input levels and mute, and app-scoped player controls. `node …/validation/audio-core.test.mjs` → 7 pass (actions are asserted there, incl. per-app isolation and stale-seek rejection).
- [ ] 2.3 Define outbound PipeWire, MPRIS, and artwork ports without GJS/GTK imports. `grep -nE "from ['\"](gi://|ags/)" dotfiles/config/ags/audio/{domain,application}/**/*.ts` → no matches.
- [ ] 2.4 Add pure tests for route transitions including unknown intent, route labels, per-app isolation, identity joining, and capability projection. `node …/validation/audio-core.test.mjs` → 7 pass, 0 fail.

## 3. Implement and reconcile event-driven adapters

- [ ] 3.1 After the feasibility spike, move/adapt PipeWire node/device/default endpoint observation and stream commands behind the PipeWire port; use `wp.nodes` and the verified graph snapshot/event seam, not unavailable `wp.audio.*` collections.
- [ ] 3.2 Make preferred-output selection update the system default and route every follow-preferred live stream while preserving explicit routes.
- [ ] 3.3 Keep MPRIS hydration and D-Bus signal handling behind the player port; retain action-only use of `playerctl` and no authoritative polling.
- [ ] 3.4 Resolve MPRIS artwork URIs through an artwork adapter with a bounded cache and an unavailable result for safe app-icon fallback.
- [ ] 3.5 Keep adapter reconnect, stream relink, and action errors bounded and observable without exposing adapter details to UI components.
- [ ] 3.6 Implement event-driven route-intent reconciliation; verify external default and target changes, an externally targeted new stream, same-stream explicit-route reassertion, stream unlink/relink continuity, and AGS restart with unknown intent when history is unavailable. Use observed PipeWire events rather than periodic polling, and keep this state off the dotfiles domain event hub. `node …/validation/pipewire-adapter.test.mjs` → 2 pass, plus `…/live_same_stream_reassert.py` for the live reassertion edge (restores the physical default in `finally`). The event-driven reconciliation loop itself is live acceptance work for 7.1, not something the unit gate can prove.

## 4. Build stable presentation state

- [ ] 4.1 Project PipeWire streams and MPRIS players into stable per-app rows using canonical app identity, with no duplicate rows for spelling/framework aliases; retain a row while either source remains and gate stream-only actions on a current stream.
- [ ] 4.2 Project live MPRIS metadata while a player remains Playing for Chrome, Tidal, and Firefox; use honest app fallback when metadata is absent, and suppress generic PipeWire labels such as `Playback` and `AudioStream` when an MPRIS title is available.
- [ ] 4.3 Project current route intent distinctly from actual endpoint coincidence: “Follow preferred · C” versus explicit “C · Override”.
- [ ] 4.4 Preserve row identity and labels across seek/relink churn, including the Firefox blink reproduction; ensure transient state never permits commands against a stale node. `node …/validation/audio-presentation.test.mjs` → 7 pass. The Firefox blink is a live visual defect and stays open until 7.5 reproduces it; do not mark this checked on unit evidence alone.
- [ ] 4.5 Expose stream volume and mute separately so muting preserves the app's level and the icon follows actual source state.

## 5. Rebuild the user interface

- [ ] 5.1 Rebuild the popup to match the approved concept: preferred output, playing apps, input, and microphone activity in a compact scrollable panel. **Not checkable until 6.0 lands** — an unwired popup compiles and bundles while rendering nothing, which is exactly how the first pass produced a panel that displayed only `Audio controls are connecting`.
- [ ] 5.2 Implement the preferred output selector and clearly labelled selected-device Output level/mute control.
- [ ] 5.3 Implement app rows with artwork/app identity, title/artist, route menu, per-app level-aware mute/volume, and capability-gated player transport/seek.
- [ ] 5.4 Remove aggregate output transport and make each player action app-scoped.
- [ ] 5.5 Keep input-device state and microphone-consuming app rows clear; the bar mic indicator is visible only during actual input use, its glyph reflects default-mic mute state, and its live ornament reflects the active consumer; preserve screen-capture status as a separate feature.
- [ ] 5.6 Apply repository theme tokens, accessible labels/focus, stable slider/row geometry, and sensible long-name truncation.
- [ ] 5.7 Confirm new audio styles inherit regenerated `colors.css` and match shared AGS surface, selection, focus, and slider treatments; keep only the established live-mic semantic color exception. `python3 scripts/audio-mock-parity.py` → PASS, and `grep -rn "audio-panel.css" dotfiles/config/ags` → at least one real import (currently none, so all 345 lines are dead). `python3 …/validation/check_palette_contrast.py` → every role at or above target; token-level only, so 7.9 still has to render it.
- [ ] 5.8 Ensure visible app labels, route-menu selection semantics, focus return, semantic slider values, and input-device controls match the accessibility contract.

## 6. Wire the composition root, then integrate the surrounding surfaces

- [ ] 6.0 **Compose the panel.** Nothing renders until this task is done. The
  first implementation pass wrote the whole new boundary and left this step
  out, so `app.tsx:61` still called `AudioPopup(primary)` with no argument,
  `binding` was `undefined`, and the popup rendered only the
  `Audio controls are connecting` fallback at `AudioPopup.tsx:598` — a panel
  that looked "connecting" forever instead of failing. Do:
  - a. Construct the session runtime (`application/runtime/audio-session-runtime.ts`),
    the PipeWire/MPRIS adapters, and the actions from a single composition
    root, and construct the `AudioPanelViewModel` accessor from them.
  - b. Pass that binding at `app.tsx:61` (`AudioPopup(primary, binding)`), and
    have the popup shell render `AudioPanelContent` unconditionally.
  - c. Delete the `binding ? … : <label …/>` fallback at `AudioPopup.tsx:598`.
    Its only purpose was to hide an unwired panel; leaving it in place makes
    "unwired" indistinguishable from "starting" forever.
  - d. Make `binding` a required parameter, so the omission above becomes a
    typecheck error rather than a silent empty panel (see 6.5).
  - e. Import `audio-panel.css` from the AGS stylesheet. It is currently
    referenced by no file, so all 345 lines of the approved theme are dead.
  - f. Delete or reduce `state.ts` per §0 — at completion, no consumer outside
    the new boundary may import it.
  - Verify: `node openspec/changes/redesign-ags-audio-panel/validation/audio-panel-render.test.mjs`
  → passes; and `grep -rn "from \"./state\"" dotfiles/config/ags` → no matches
  outside the new boundary.
- [ ] 6.1 Adapt the status-bar output and mic indicators to the application boundary while preserving level-aware speaker state, left-click popup entry, right-click `pavucontrol`, scroll volume nudges, default-mic mute glyph, and actual mic-use visibility/ornament.
- [ ] 6.2 Adapt Settings-panel system volume to the same output-level use case so it cannot drift from the audio popup.
- [ ] 6.3 Keep screen-capture indicator state on the dotfiles domain event hub; do not bridge PipeWire or MPRIS through that hub.
- [ ] 6.4 Update provisioning/deployment manifests and verification file lists if runtime modules or assets are moved or added; regenerate generated icon output only through its source pipeline.
- [ ] 6.5 **Add a `tsc` gate over `dotfiles/config/ags`, and wire it into
  `.github/workflows/gates.yml`.** Root cause, not this instance: `binding?:
  AudioPanelBinding` was passed to components declaring `binding:
  AudioPanelBinding` — a hard `strictNullChecks` error — and nothing caught it,
  because `gates.yml` ran only `contracts-check` plus the three mock/parity
  gates and never compiled the AGS tree. Zero errors in our files is the bar
  (precedent: `1b24e840`). Record the baseline count if unrelated
  third-party errors exist; do not leave ours silent.
- [ ] 6.6 **Promote the panel's remaining gates into `gates.yml` and `make
  gates` once 6.0 lands.** `scripts/audio-mock-parity.py` and the audio unit
  suites are wired now; `audio-panel-render.test.mjs` and the 6.5 `tsc` gate
  are deliberately excluded while the panel is unwired, since both are red
  until 6.0 completes. Move them in the same commit that ticks 6.0, and fix the
  CI trigger at the same time: `gates.yml` fires on `push: branches: [main]`
  but the default branch is `master`, so gate results never gate a push today.

## 7. Verify the approved contract

The user has hands-on validated the current panel's controls and routing. Live comparison confirms that MPRIS supplies titles for Chrome, Firefox, and Tidal while Playing, but the current rows show blank Chrome/Tidal subtitles and Firefox `AudioStream`. The user reports a brief Firefox blink during seek. A corrected MPRIS-seek capture kept list, row-component, and label-write counters stable and did not visually capture a blink, but Firefox's seek position was inconsistent and the original pointer-drag case remains unverified. The checks below remain acceptance criteria for the redesigned implementation; the metadata projection failure is confirmed.

- [ ] 7.1 Verify preferred-output changes move follow-preferred apps and leave explicit routes unchanged; verify returning an app to Follow preferred opts it back in.
- [ ] 7.2 Verify selected-device output level affects all streams routed to that sink and does not overwrite per-app levels.
- [ ] 7.3 Verify app level/mute isolation, level-aware icon updates from external changes, and mute-level preservation.
- [ ] 7.4 Verify title/artist/artwork projection while streams are live for Chrome (`Cowboy Bebop | Lofi Hiphop & Jazzhop Mix`), Tidal (`Opus Pocus`), and Firefox (`Cowboy Bebop Study Music and Chillout`); also cover artwork fallback, metadata absence, MPRIS absence, and capability-gated seek.
- [ ] 7.5 Reproduce Chrome pause/reopen metadata delay and Firefox seek blink/relink churn; confirm metadata updates without pause/reopen and that no row blinks, resets, loses route, writes a stale node, or duplicates.
- [ ] 7.6 Verify input, mic activity, screen-capture state, bar indicators, Settings volume, popup dismissal/anchoring, and hotplug behavior.
- [ ] 7.7 Run the applicable pure-core tests, AGS bundle checks, provisioning/source-set checks, then the live AGS smoke and manual interaction matrix before calling the change complete. **Gate order, cheapest first:** `node …/validation/audio-core.test.mjs` → `node …/validation/audio-presentation.test.mjs` → `node …/validation/pipewire-adapter.test.mjs` → `node …/validation/audio-session-runtime.test.mjs` → `node …/validation/audio-panel-render.test.mjs` → the new `tsc` gate from 6.5 → `ags bundle app.tsx …` → `make gates` → live AGS smoke. Note that `ags bundle` passes against the broken panel — it compiles an unwired popup without complaint — so it is never sufficient on its own; the render gate and the live smoke are what would have caught it.
- [ ] 7.8 Verify route selectors, app grouping, slider values, focus order, constrained work-area layout, and generated-palette contrast with keyboard and assistive-technology review.
- [ ] 7.9 Render the panel under at least two generated wallpaper palettes and review actual GTK/compositor contrast for selected routes, focus, small text, and slider states. Token-level calculations are recorded in `validation/README.md` but do not replace this visual check.

# Tasks

## 1. Establish the current boundary and migration plan

- [x] 1.1 Map every current consumer and side effect of `audio/state.ts`, including popup, bar speaker/mic indicators, Settings volume control, MPRIS service, popup lifecycle, graph snapshot, and icon resolution. (See `validation/current-boundary-review.md`.)
- [x] 1.2 Inspect the uncommitted audio edits before implementation; separate proven fixes from debug-only changes and speculative caches/holds. (Review only; working-tree implementation edits were left intact.)
- [x] 1.3 Write a migration map from current modules to pure core, use cases/ports, PipeWire/MPRIS adapters, presentation projection, and GTK consumers. (See target seam column in `validation/current-boundary-review.md`.)
- [x] 1.4a Verify ordinary default-follow behavior, the same-as-preferred WirePlumber edge, and same-stream explicit-route reassertion feasibility using silent temporary sinks. A follow-up test reasserted A on the same stream after WirePlumber moved it A → B; it stayed at A after the next default change. Firefox and Tidal routes and the original C-Media default were restored. This verifies the PipeWire/Pulse command path, not an AGS-owned intent adapter. See `validation/README.md`.
- [x] 1.4b Inspect the live PipeWire monitor surface before choosing an adapter: default metadata (`default.audio.sink`), stream `target.object`, and effective link node IDs were observed; the same-stream command-level reassertion check passed. This confirms useful event data and route-action feasibility, not AGS reconciliation. Adapter lifecycle/event behavior is acceptance work in 3.6.
- [ ] 1.5 Compare live MPRIS metadata and AGS row projection for Chrome, Tidal, and Firefox while Playing, Paused, after seek, and after popup reopen. Playing-state MPRIS/row mismatch is confirmed for all three. A corrected Firefox MPRIS-seek capture kept `rowListWrite`, `streamRow`, and `labelWrite` stable and showed no blink in sampled frames, but Firefox's reported position disagreed with the popup and the seek advanced its playlist; physical slider-drag reproduction and the pause/reopen transition remain open. See `validation/README.md`.

## 2. Extract domain and application boundaries

- [ ] 2.1 Define pure TypeScript route intent (`FollowPreferred`, explicit endpoint, or unknown), app identity, volume/mute, and player-capability values.
- [ ] 2.2 Define named application actions for preferred output, app route, output/app/input levels and mute, and app-scoped player controls.
- [ ] 2.3 Define outbound PipeWire, MPRIS, and artwork ports without GJS/GTK imports.
- [ ] 2.4 Add pure tests for route transitions including unknown intent, route labels, per-app isolation, identity joining, and capability projection.

## 3. Implement and reconcile event-driven adapters

- [ ] 3.1 After the feasibility spike, move/adapt PipeWire node/device/default endpoint observation and stream commands behind the PipeWire port; use `wp.nodes` and the verified graph snapshot/event seam, not unavailable `wp.audio.*` collections.
- [ ] 3.2 Make preferred-output selection update the system default and route every follow-preferred live stream while preserving explicit routes.
- [ ] 3.3 Keep MPRIS hydration and D-Bus signal handling behind the player port; retain action-only use of `playerctl` and no authoritative polling.
- [ ] 3.4 Resolve MPRIS artwork URIs through an artwork adapter with a bounded cache and an unavailable result for safe app-icon fallback.
- [ ] 3.5 Keep adapter reconnect, stream relink, and action errors bounded and observable without exposing adapter details to UI components.
- [ ] 3.6 Implement event-driven route-intent reconciliation; verify external default and target changes, an externally targeted new stream, same-stream explicit-route reassertion, stream unlink/relink continuity, and AGS restart with unknown intent when history is unavailable. Use observed PipeWire events rather than periodic polling, and keep this state off the dotfiles domain event hub.

## 4. Build stable presentation state

- [ ] 4.1 Project PipeWire streams and MPRIS players into stable per-app rows using canonical app identity, with no duplicate rows for spelling/framework aliases; retain a row while either source remains and gate stream-only actions on a current stream.
- [ ] 4.2 Project live MPRIS metadata while a player remains Playing for Chrome, Tidal, and Firefox; use honest app fallback when metadata is absent, and suppress generic PipeWire labels such as `Playback` and `AudioStream` when an MPRIS title is available.
- [ ] 4.3 Project current route intent distinctly from actual endpoint coincidence: “Follow preferred · C” versus explicit “C · Override”.
- [ ] 4.4 Preserve row identity and labels across seek/relink churn, including the Firefox blink reproduction; ensure transient state never permits commands against a stale node.
- [ ] 4.5 Expose stream volume and mute separately so muting preserves the app's level and the icon follows actual source state.

## 5. Rebuild the user interface

- [ ] 5.1 Rebuild the popup to match the approved concept: preferred output, playing apps, input, and microphone activity in a compact scrollable panel.
- [ ] 5.2 Implement the preferred output selector and clearly labelled selected-device Output level/mute control.
- [ ] 5.3 Implement app rows with artwork/app identity, title/artist, route menu, per-app level-aware mute/volume, and capability-gated player transport/seek.
- [ ] 5.4 Remove aggregate output transport and make each player action app-scoped.
- [ ] 5.5 Keep input-device state and microphone-consuming app rows clear; the bar mic indicator is visible only during actual input use, its glyph reflects default-mic mute state, and its live ornament reflects the active consumer; preserve screen-capture status as a separate feature.
- [ ] 5.6 Apply repository theme tokens, accessible labels/focus, stable slider/row geometry, and sensible long-name truncation.
- [ ] 5.7 Confirm new audio styles inherit regenerated `colors.css` and match shared AGS surface, selection, focus, and slider treatments; keep only the established live-mic semantic color exception.
- [ ] 5.8 Ensure visible app labels, route-menu selection semantics, focus return, semantic slider values, and input-device controls match the accessibility contract.

## 6. Integrate the surrounding surfaces

- [ ] 6.1 Adapt the status-bar output and mic indicators to the application boundary while preserving level-aware speaker state, left-click popup entry, right-click `pavucontrol`, scroll volume nudges, default-mic mute glyph, and actual mic-use visibility/ornament.
- [ ] 6.2 Adapt Settings-panel system volume to the same output-level use case so it cannot drift from the audio popup.
- [ ] 6.3 Keep screen-capture indicator state on the dotfiles domain event hub; do not bridge PipeWire or MPRIS through that hub.
- [ ] 6.4 Update provisioning/deployment manifests and verification file lists if runtime modules or assets are moved or added; regenerate generated icon output only through its source pipeline.

## 7. Verify the approved contract

The user has hands-on validated the current panel's controls and routing. Live comparison confirms that MPRIS supplies titles for Chrome, Firefox, and Tidal while Playing, but the current rows show blank Chrome/Tidal subtitles and Firefox `AudioStream`. The user reports a brief Firefox blink during seek. A corrected MPRIS-seek capture kept list, row-component, and label-write counters stable and did not visually capture a blink, but Firefox's seek position was inconsistent and the original pointer-drag case remains unverified. The checks below remain acceptance criteria for the redesigned implementation; the metadata projection failure is confirmed.

- [ ] 7.1 Verify preferred-output changes move follow-preferred apps and leave explicit routes unchanged; verify returning an app to Follow preferred opts it back in.
- [ ] 7.2 Verify selected-device output level affects all streams routed to that sink and does not overwrite per-app levels.
- [ ] 7.3 Verify app level/mute isolation, level-aware icon updates from external changes, and mute-level preservation.
- [ ] 7.4 Verify title/artist/artwork projection while streams are live for Chrome (`Cowboy Bebop | Lofi Hiphop & Jazzhop Mix`), Tidal (`Opus Pocus`), and Firefox (`Cowboy Bebop Study Music and Chillout`); also cover artwork fallback, metadata absence, MPRIS absence, and capability-gated seek.
- [ ] 7.5 Reproduce Chrome pause/reopen metadata delay and Firefox seek blink/relink churn; confirm metadata updates without pause/reopen and that no row blinks, resets, loses route, writes a stale node, or duplicates.
- [ ] 7.6 Verify input, mic activity, screen-capture state, bar indicators, Settings volume, popup dismissal/anchoring, and hotplug behavior.
- [ ] 7.7 Run the applicable pure-core tests, AGS bundle checks, provisioning/source-set checks, then the live AGS smoke and manual interaction matrix before calling the change complete.
- [ ] 7.8 Verify route selectors, app grouping, slider values, focus order, constrained work-area layout, and generated-palette contrast with keyboard and assistive-technology review.
- [ ] 7.9 Render the panel under at least two generated wallpaper palettes and review actual GTK/compositor contrast for selected routes, focus, small text, and slider states. Token-level calculations are recorded in `validation/README.md` but do not replace this visual check.

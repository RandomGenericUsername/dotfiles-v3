## Why

The current sound panel combines PipeWire device/stream state, MPRIS player state, identity matching, graph snapshots, popup state, and UI workarounds in a large shared state module. Hands-on validation confirms the controls and routing work, but media presentation remains inconsistent: Chrome only reveals its media subtitle after pausing and reopening the popup, Tidal does not show its media title, and Firefox shows the generic `AudioStream` label. Seeking in Firefox also briefly blinks the row.

The owner approved a complete panel redesign around one clear routing model: a preferred output for apps that follow the system default, explicit per-app output overrides, device-level output gain, and independent per-app media/volume controls. The approved visual reference is `mockups/audio-panel-redesign-concept.html` in the linked UX workspace.

## What Changes

- Redesign the full audio popup: preferred output, playing apps, input, and microphone-consuming streams.
- Add an explicit preferred-output selector. Streams following the preference move with it; explicit app routes remain on their chosen device.
- Keep preferred-device output level separate from app stream volume. Device level affects every stream routed to that device; app level affects only that app's stream.
- Give each app row media artwork when available, title/artist metadata, visible app identity, route selection, independent level-aware mute/volume, and player transport/seek where supported.
- Remove aggregate play/pause/seek from the output-device section.
- Rework audio code toward hexagonal boundaries: pure domain/application rules, explicit PipeWire and MPRIS adapters, presentation projections, and a thin GTK view.
- Keep the bar speaker/microphone indicators and Settings-panel system-volume control coherent with the same application boundary.
- Keep the dotfiles event hub for dotfiles-owned domain events; do not route PipeWire or MPRIS state through it.

## Non-goals and scope boundaries

- Persist per-app output overrides across application or AGS restarts. If the panel cannot recover route intent for an existing stream, it reports the observed endpoint with `Unknown` intent.
- Add a device-level or aggregate media transport. Playback and seek remain in the matching app row.
- Replace the screen-capture job indicator or move audio/player events onto the dotfiles event hub.
- Copy the browser mock's sample colors into runtime GTK styles.

## Acceptance constraints

- Do not expose Follow/Explicit labels as confirmed until the audio adapter can distinguish intent from effective endpoint and reconcile the installed WirePlumber default-follow behavior.
- Keep player identity/metadata stable while the associated PipeWire stream pauses, unlinks, or relinks. Stream volume/mute/route writes require a currently valid stream.
- Use one selected-output level/mute application action from the popup, bar, and Settings surface.
- Treat the palette measurements in `validation/README.md` as token-level evidence. Final GTK/compositor contrast and keyboard review remain implementation acceptance work.

## Capabilities

### New Capabilities

- `ags-audio-panel`: approved popup interaction, output-follow/override routing semantics, independent device/app levels, per-app media presentation and transport, input and microphone activity.

### Modified Capabilities

None. Earlier audio changes are historical proposals with incomplete or superseded acceptance records; this change is the current functional contract.

## Impact

- AGS audio popup, audio state, status-bar audio indicators, shared Settings volume control, and audio CSS.
- MPRIS and PipeWire adapter boundaries and app identity/metadata projection.
- Potential AGS file deployment/verification manifests and icon artwork handling if module paths or UI assets change.
- UX source of truth: `_bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/{DESIGN.md,EXPERIENCE.md,mockups/audio-panel-redesign-concept.html}`.

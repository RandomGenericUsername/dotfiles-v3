# Audio panel validation evidence and handoff

Date: 2026-10-02

## User-reported functional baseline

The user has hands-on validated the running audio panel's controls and routing. Three metadata/rendering cases remain open:

- **Chrome:** while playing, the row shows no media title. After pausing, waiting a few seconds, and reopening the popup, a media subtitle appears (observed: `Cowboy Bebop | Loft Hiphop & Jazzhop Mix`).
- **Tidal:** the media title/subtitle does not appear.
- **Firefox:** the subtitle is the generic `AudioStream`; moving the seek bar briefly redraws/blinks the row.

These are separate user-reported observations. The idea that the Firefox blink is more noticeable when its subtitle changes is plausible, but its cause is unverified. Do not treat any of these as solved by the otherwise working controls/routing baseline.

## MPRIS-to-row source comparison (2026-10-02)

An initial read-only snapshot caught Chrome and Firefox Paused, with their MPRIS metadata still present; Tidal was not registered at that time. A later read-only snapshot, after the user resumed all three, showed all three players Playing. `playerctl` reported:

| App | MPRIS title | Artist | AGS row subtitle while Playing |
|---|---|---|---|
| Chrome | `Cowboy Bebop | Lofi Hiphop & Jazzhop Mix` | Ambition | empty |
| Firefox | `Cowboy Bebop Study Music and Chillout` | Musically Chill | `AudioStream` |
| Tidal | `Opus Pocus` | Jason Becker | empty |

The live MPRIS snapshot also supplied artwork URIs for all three. AGS's `audio-debug` independently showed each player as `Playing` with its title and linked each to a live PipeWire stream. PipeWire reported the media name `Playback` for Chrome and Tidal and `AudioStream` for Firefox.

Source inspection confirms the row-projection defect: `StreamRow.subtitle` in `AudioPopup.tsx` uses `streamSubtitle(...)` whenever a live stream exists and uses the MPRIS title only when no stream exists. `streamSubtitle(...)` prefers the PipeWire media name, filters the literal `Playback`, but does not filter `AudioStream` or consult MPRIS metadata. This explains all three observed Playing rows: Chrome/Tidal discard available MPRIS metadata after filtering `Playback`, while Firefox shows the generic PipeWire label instead of available MPRIS metadata. The provider is not missing the title in this capture; the row projection is.

### Firefox seek capture (2026-10-02)

An instrumented capture was performed with Firefox Playing and the audio popup open. The first capture attempt used stale popup geometry and captured the terminal; it is discarded. In the corrected capture, eight snapshots were taken around an MPRIS seek while capturing the visible popup. The diagnostic counters stayed at `rowListWrite=11`, `streamRow=4`, and `labelWrite=317` throughout the sampled seek interval. The screenshot samples showed no visible row blink. This rules out list replacement, row component reconstruction, and changed subtitle writes during those samples; it does not rule out a sub-frame GTK repaint or reproduce a physical pointer drag.

The seek/position behavior was inconsistent: Firefox's MPRIS position readout did not agree with the popup's elapsed/duration display, the MPRIS duration was absent from `playerctl metadata`, and a seek advanced the YouTube playlist. Restoring the position reported at capture start was not honored; Firefox remained Playing but reported position near zero. Treat this as a confirmed provider/seek-state discrepancy and an inconclusive reproduction of the reported blink. Do not claim the Firefox visual defect is fixed or disproven. The session's Firefox media changed during this probe, so no further seeks should be used to characterize that original track.

The capture script and representative screenshots are retained in `live_seek_capture.py` and `evidence/2026-10-02/`. The script sends a real MPRIS seek and can change the current media/position; treat it as a record of the probe, not as a harmless routine check. `live_same_stream_reassert.py` is also retained; it briefly routes live playback through silent test sinks and restores the original default in `finally`.

## What is validated

### Runtime theme tokens

`check_palette_contrast.py` measured the approved token recipe against two existing cached `colors.gtk.css` palettes: the active desktop palette (`28c9edc5…`) and a second generated cache palette (`b6c439dc…`). It applies the design's 94% panel and 18% card alpha over `color_00`, then computes WCAG contrast for small text, selection text, focus/action colors, and slider states.

| Role | Active palette | Second cached palette | Target |
|---|---:|---:|---:|
| Primary text on panel | 10.97:1 | 10.28:1 | 4.5:1 |
| Secondary text at 72%, panel | 6.05:1 | 5.88:1 | 4.5:1 |
| Muted text at 64%, panel | 4.98:1 | 4.91:1 | 4.5:1 |
| Muted text at 64%, card | 4.76:1 | 4.61:1 | 4.5:1 |
| Selection text using `color_background` | 6.59:1 | 8.86:1 | 4.5:1 |
| Focus `color_10` against card | 5.90:1 | 7.91:1 | 3:1 |
| Action `color_06` against panel | 4.07:1 | 4.30:1 | 3:1 |
| Slider thumb against track | 8.15:1 | 7.27:1 | 3:1 |
| Slider fill against track | 6.92:1 | 8.69:1 | 3:1 |

This surfaced and fixed two design-token issues: the former 55% muted text measured 3.95:1 on the active panel and 4.41:1 on the second card, so the small-text muted token is now 64%; and `color_foreground` on selected `color_10` measured 1.66:1 and 1.16:1, so the specified GUI-unification fallback selects `color_background` (which passes both). All checked roles pass with those decisions.

This is repeatable palette-token evidence, not a rendered GTK/compositor result. The card composite assumes its backdrop is the panel surface. It does not measure wallpaper behind the popup, focus rendering at actual stroke width, scaling, or state-specific real widgets. Sally's request for generated-theme render review remains open as task 7.9.

### Routing intent semantics

`route_intent_prototype.py` is a dependency-free application-model sketch. It demonstrates these expected transitions: startup hydration stays unknown without intent evidence; observed endpoint remains visible; a new app without an override follows the preferred output; an explicit target equal to preferred remains explicit; explicit-to-current-preferred selection; preferred changes; return to Follow preferred; external target changes; relink continuity; and safe `Unknown` after owner restart if intent cannot be restored. All twelve synthetic scenarios pass.

The original `live_route_gate.py` check confirmed ordinary first-launch behavior and the explicit-same-as-preferred WirePlumber edge. A default-follow stream moved A → C. An explicit target A chosen while A was preferred also followed the default to C. A separate stream started with target A while C was preferred stayed on A through another default change.

A follow-up same-stream check (2026-10-02) used two temporary silent sinks while Firefox and Tidal were playing through the physical output. The synthetic stream began on preferred A; changing the default to B moved that same stream to B. A PulseAudio-compatible move command reasserted A on that same stream, and it stayed on A after changing the default back to the original physical C-Media sink. This proves that same-stream explicit-route reassertion is feasible at the PipeWire/Pulse command layer. It does not validate an AGS-owned intent registry or its event-driven reconciliation, which are new implementation work. The test restored the physical default and confirmed Firefox and Tidal streams linked back to physical sink 53.

`live_controls_gate.py` verified silent app-stream level/mute operations, mute preserving level, app-stream isolation, selected-sink level isolation, temporary monitor-source level/mute, synthetic capture-stream visibility, and AGS observing the stream's gain/mute state. All temporary nodes/streams are cleaned up. This does not substitute for the user's end-to-end validation of popup interaction.

The installed settings are `linking.follow-default-target=true` and `linking.allow-moving-streams=true`. The live `pw-dump --monitor` capture included the default Metadata object and its `default.audio.sink` JSON value, the synthetic stream's `target.object`, and link objects carrying `link.output.node`/`link.input.node`. This establishes usable event data for default identity, requested target, and effective links. We have not audited externally initiated target changes through the proposed AGS adapter, new-stream initialization races, unlink/relink identity continuity, or AGS restart while streams remain alive. Those are implementation adapter checks; they do not reveal a gap in the user's routing concept.

The design contract now requires a row to survive while either its PipeWire stream or MPRIS player remains, real media metadata to take precedence over generic stream labels, and row identity to stay stable during seek/relink. User observations show the current panel violates this in Chrome, Tidal, and Firefox as detailed above. The source and cause of each discrepancy have not yet been isolated.

The UX `DESIGN.md` and `EXPERIENCE.md` now express the same unknown-route and independent player/stream lifetime behavior. These refinements postdate Sally's focused review and have not been reviewed by her yet.

The ordinary default-follow route, equal-to-default override edge, and same-stream reassertion feasibility are live-validated. The same stream can be moved back to its explicit endpoint and remain there across a later default change. The application-owned intent record and its event-driven reconciliation remain implementation responsibilities; do not claim that the current AGS panel already preserves this distinction. Detailed adapter payload handling remains open as task 1.4b.

## Next implementation step

The existing panel's controls and routing have been accepted by the user. Before treating the redesigned implementation as complete, reproduce and fix the Chrome, Tidal, and Firefox metadata/rendering cases above, then complete the remaining adapter/theme evidence. Token calculations and synthetic routing checks do not replace those checks.

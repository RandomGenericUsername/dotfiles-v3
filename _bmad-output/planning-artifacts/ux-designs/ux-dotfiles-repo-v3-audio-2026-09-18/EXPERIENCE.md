---
name: AGS Audio Panel Redesign
status: final
updated: 2026-10-02
sources:
  - DESIGN.md
  - mockups/audio-panel-redesign-concept.html
  - openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md
  - openspec/changes/redesign-ags-audio-panel/design.md
  - _bmad-output/planning-artifacts/ags-audio-mpris-transport-dispatch-contract-2026-09-21.md
  - docs/linux-wayland-pipewire-ags-audio-control.md
---

# AGS Audio Panel — Experience Spine

## Foundation

Desktop GTK4 surface in the Hyprland status bar, opened from the speaker indicator and anchored under the triggering icon. It serves a multi-output PipeWire desktop and multiple simultaneous media players. `DESIGN.md` is the visual identity reference; this spine defines behavior. PipeWire/WirePlumber own device, route, and stream level state; MPRIS owns player metadata and transport state.

The UX contract records the owner's approved interaction choices. Technical notes and older audio mocks are evidence only. The [approved concept](mockups/audio-panel-redesign-concept.html) shows the preferred output, app rows, device/app level distinction, route choices, and activity hierarchy. The earlier [popup mock](mockups/key-audio-popup.html), [transport mock](mockups/key-audio-transport.html), [alternatives](mockups/key-alternatives.html), and [bar-indicator mock](mockups/key-bar-indicators.html) are historical and superseded; they must not override this spine.

### Confirmed current media metadata/rendering defects

The owner has validated the current panel's controls and routing. A live comparison confirmed that Chrome, Tidal, and Firefox all report MPRIS titles while Playing, but the current rows show no Chrome/Tidal subtitle and Firefox `AudioStream`. The row projection currently chooses PipeWire text whenever the stream exists, even when MPRIS title/artist are available. The owner also reports that seeking in Firefox briefly blinks the row. This rendering defect is separate from the validated controls and routing; the specific redraw trigger still needs instrumented capture.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Bar speaker indicator | Always-visible status bar | Shows default output level/mute; opens the audio popup. |
| Bar microphone indicator | Visible while an input stream is active | Shows default mic mute and current mic use; opens the input/activity area. |
| Preferred output | Audio popup | Selects the default destination and adjusts that sink's master output level. |
| Playing apps | Audio popup | Shows app/media identity, route, app level/mute, and app-scoped playback/seek. |
| Input | Audio popup | Selects the preferred microphone and adjusts input level/mute. |
| Microphone activity | Audio popup | Shows which apps currently consume microphone input. |
| Screen-capture status | Existing Capture Tool surface/bar indicator | Shows dotfiles-owned capture state; does not represent generic microphone use. |
| Settings Sound control | Settings panel | Adjusts the same system output level through the shared audio application boundary. |

## Voice and Tone

Microcopy labels the scope and effect of a control. Use **Preferred output**, **Output level**, **Follow preferred · C**, **C · Override**, **Route unknown · C**, **App volume**, and **Input level**. `Route unknown · C` means C is the observed endpoint but the panel cannot confirm whether the stream follows the default or is an override. Use direct recovery messages such as “Output unavailable” or “Couldn’t change app output.” Avoid ambiguous **Master playback**, backend terms, generic track titles, and unexplained icons.

## Component Patterns

Behavioral rules for the visual components named in [DESIGN.md Components](DESIGN.md#components):

| Component | Behavioral contract |
|---|---|
| Audio popup | Opened from the bar speaker; stable single-column order; scrolls vertically; outside click and the existing global close action dismiss it. Focusable controls must not steal keyboard input on open. |
| Section card | Has a visible heading and a meaningful empty/loading/error state; its controls remain usable when another section fails. |
| Preferred output selector | Announces current endpoint; choosing a device sets the preferred destination and moves streams following it, leaving explicit app routes intact. |
| Output level control | Accessible name includes device and “output level”; slider changes that sink only; speaker icon toggles that sink's mute and reflects actual state. |
| App media row | A labelled group exposes a persistent visible app name plus media title/artist; artwork is supplementary and falls back to app icon. Row and focus identity survive graph churn. |
| Route selector | Announces app, observed endpoint, and confirmed intent; if intent is unknown it says so without hiding the endpoint. Offers keyboard-operable “Follow preferred · C” separately from explicit device routes. Selected option, expanded state, Escape, and focus return are exposed. |
| App transport | Controls only the corresponding app's player. Unsupported actions are omitted without disabling route or audio level controls. |
| Seek slider | Offered only with seek capability and a known duration; accessible value reports elapsed and total time; commit/reconciliation does not blink or move the row. |
| App level control | Accessible name includes app and “stream volume”; the slider changes only its stream. Speaker icon reports actual level and mute; activation toggles mute while preserving level. |
| Input device control | Announces selected microphone; provides device choice, input-level slider, and separate mute toggle. |
| Microphone activity row | Identifies the consuming app and actual microphone state. It does not imply screen-capture recording. |
| Bar audio indicators | Speaker follows default-output level/mute. Mic indicator follows actual input use and default-mic mute. Right-click/scroll behavior stays labelled and discoverable. |
| Settings sound control | Uses the same device output-level action/state as the audio popup; it is not a second volume authority. |

Route menus use native GTK selection semantics where possible. Keyboard users can open a selector, move among options, commit, cancel with Escape, and return focus to its trigger. Tab order follows visual order. Each interactive app row is labelled with app and media identity. When rows reorder or disappear, focus stays on the same logical control when it still exists, otherwise moves to the nearest surviving row/section heading.

## State Patterns

| State | Surface | Treatment |
|---|---|---|
| Initial discovery | Popup | Show a brief loading/connecting state; do not imply that an empty snapshot means no devices before discovery completes. |
| No output devices | Preferred output | Keep app metadata and input visible; show “No output devices available” and a recovery hint. Disable only output-dependent controls. |
| Preferred output unavailable | Preferred output | Name the unavailable endpoint and the active fallback if known; never show the missing device as selected and active. |
| Empty app list | Playing apps | Show a quiet “No apps playing” message; retain preferred output and input sections. |
| App stream without player | Playing apps | Show app name/icon and route/level/mute; omit media transport and seek. |
| Player without stream | Playing apps | Preserve the row, media, artwork, and player transport while the MPRIS player exists; disable stream-only volume/mute/route actions until a current stream returns. Never write to a stale node. |
| Existing stream with unknown route intent | App row | Show the observed endpoint with “Route unknown”; do not infer Follow preferred or Override from endpoint equality. Let the user choose either route intent. |
| Missing track metadata | App row | Show app name and a concise fallback; do not render `Playback` or another backend label as a song title. |
| Missing artwork | App row | Fall back to the app icon without hiding title/artist. |
| Seek unsupported or duration unknown | App row | Hide seek only; retain other supported player and stream controls. |
| Device/action error | Affected control | Keep current confirmed state, show a local “Couldn’t…” message, and allow retry; unrelated rows remain available. |
| No microphone consumers | Microphone activity | Show “No apps using the microphone”; do not show a live-use indicator. |
| Input permission denied | Input/activity | When the platform exposes denial, name the affected app/device and provide its available recovery route; do not infer denial solely from an absent stream. |
| Capture running | Screen-capture status | Keep Capture Tool state separate from app microphone consumers and the bar mic-use indicator. |
| Long names/constrained work area | All sections | Ellipsize with full accessible description; narrow the popup to available work area, allow labels to wrap, and preserve scroll/focus visibility. |

## Interaction Primitives

- **Open/close:** click the bar speaker; click outside or invoke the existing global popup-close action to close. Popup opening does not steal focus from the active application.
- **Keyboard open/close:** keyboard activation opens the popup with focus moved into it intentionally; closing restores focus to the bar trigger. Pointer opening does not steal keyboard focus from the active application. Click outside or invoke the existing global popup-close action to close.
- **Selectors:** buttons expose their current value and expanded state. Enter/Space opens; arrows move; Enter commits; Escape closes and restores focus.
- **Sliders:** pointer drag and keyboard arrows adjust in small steps; Home/End reach bounds. Device/app scope and current percentage are exposed as accessible name/value. Seek announces elapsed and total time.
- **Mute toggles:** icon and accessible pressed/mute state follow live PipeWire values. Toggling mute does not rewrite volume.
- **Player controls:** actions are explicitly targeted to that row's MPRIS player. Seek commits at release and reconciles with subsequent source events.
- **Updates:** source signals update only affected values. Unchanged projections retain row identity, label content, and focus.

## Accessibility Floor

Behavioral contract; palette and focus appearance live in [DESIGN.md Colors](DESIGN.md#colors).

- Small text contrast is at least 4.5:1; control boundaries and visible focus indicators are at least 3:1 against adjacent colors, consistent with the [GUI-unification contrast rules](../../gui-unification-ux-spec.md#text-on-fill-contrast-rule).
- All controls have descriptive names including scope (device/app/input), value, and mute/route state where applicable. App identity is visible text, not tooltip-only.
- Route selectors, sliders, toggles, and transport are keyboard operable. Focus order follows the visual structure; focus remains stable across reactive updates.
- Sliders expose meaningful values: percent for level, elapsed/total for seek. State is not conveyed by color alone.
- Truncated labels retain full text in an accessible description. Artwork is decorative when redundant with the title, and app identity remains available separately.
- Controls remain reachable at constrained monitor sizes and increased text scale. Scrolling does not strand keyboard focus outside the visible area.
- Honor GTK/system reduced-motion preferences if transitions are introduced; no motion is necessary to communicate a state change.

## Responsive & Platform

This is a desktop GTK popup, not a responsive web page. Width is capped by the reference in `{components.audio-popup.max-width}` and narrowed to the available monitor work area. At narrow widths or increased UI scale, controls wrap into a stable vertical stack, the content scrolls, and the app route remains associated with its row. Full title/device text remains available to assistive technology even when visually ellipsized. The primary monitor/anchor behavior follows the current bar topology; multi-monitor anchoring must use the triggering indicator's monitor and position.

## Key Flows

### Flow 1 — Set the preferred output (Juan David, changing from speakers to headphones)

1. Juan David clicks the bar speaker and sees the currently preferred output, its device-level output level, and active app rows.
2. He opens Preferred output and selects C · Studio headphones.
3. The system default changes; Chrome and Firefox, which follow preferred, move to C. Spotify's explicit route to A remains visible and unchanged.
4. **Climax:** Juan David sees C named as preferred, sees the following apps now report “Preferred · C,” and sees Spotify still marked “A · Override.” The scope of the change is legible without testing sound app by app.

Failure: If C disappears or rejects the change, show the confirmed active/fallback endpoint and a local error. Keep all app rows and allow another selection.

### Flow 2 — Route one app and restore follow-preferred (Juan David, sending a call to speakers)

1. Juan David opens the route selector on Discord's row.
2. The selector announces the observed endpoint and confirmed intent. If the panel cannot establish intent, it says “Route unknown · [endpoint]” and does not guess from the endpoint alone.
3. He chooses A · Desk speakers. Discord moves to A; other apps do not move.
4. Later, he chooses “Follow preferred · C.” Discord returns to C and tracks the preferred output again.
5. **Climax:** Discord is isolated on A when requested, then visibly re-joins the default when he asks it to follow preferred.

Failure: If the route command fails, the row continues to show the last confirmed route and says it could not change output. No selected state is fabricated.

### Flow 3 — Adjust and mute one app (Juan David, lowering a browser video)

1. Juan David finds Chrome by its visible app name and the media title/artwork in its row.
2. He lowers Chrome's app-volume slider. Spotify and the device output level stay unchanged.
3. He clicks Chrome's level-aware speaker icon to mute it; the icon shows mute and the 63% level is preserved.
4. **Climax:** Chrome is muted independently, and clicking the icon again restores its previous stream level.

Failure: If the stream disappears during the gesture, stop writing to the stale node, retain the row/player state where possible, and reconcile when the stream returns.

### Flow 4 — Seek a track without losing the row (Juan David, locating a section in a video)

1. Juan David reads the visible app name, title, and artist/artwork for the playing browser media.
2. He moves that row's seek slider to the desired time. The slider is present only if MPRIS supports seek and duration is known.
3. PipeWire may briefly unlink/relink the stream; the MPRIS player remains the action target.
4. **Climax:** the position changes in that same row; title, route, app level, and focus remain steady with no visible blink.

Failure: If the player rejects a seek, restore/report the last confirmed position and leave volume, mute, and routing usable.

### Flow 5 — Check microphone input (Juan David, before joining a call)

1. Juan David opens Audio from the speaker or mic bar indicator.
2. Input shows the selected microphone, level, and mute. Microphone activity identifies apps currently consuming it.
3. He changes input or toggles mic mute if needed; screen-capture state remains separate.
4. **Climax:** he can tell which endpoint is selected and whether Discord is consuming it, without mistaking capture-tool status for microphone use.

Failure: If no input device is available, show that locally and keep output/app controls active. If permission denial is known, show its recovery route; absence alone is not labelled a permission error.

## Requirement-to-flow coverage

The functional scenarios in the [OpenSpec capability](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md) map to the named flows as follows. The hexagonal boundary requirement is a technical invariant and is specified in the [architecture design](../../../../openspec/changes/redesign-ags-audio-panel/design.md), rather than represented as a user-facing journey.

| OpenSpec requirement | User flow |
|---|---|
| Preferred output and follow-preferred routing | Flows 1 and 2 |
| Device output level is separate from app stream level | Flows 1 and 3 |
| Per-app mute icon reflects live stream state | Flow 3 |
| App rows present media identity and artwork | Flows 3 and 4 |
| Playback and seek controls are app-scoped and capability-aware | Flow 4 |
| Audio controls expose accessible identity, state, and keyboard operation | Flows 1–5 |
| Input, microphone activity, and screen capture stay distinct | Flow 5 |
| Audio adapters preserve event-driven authority | Flows 1, 3, and 4 |
| Audio rows remain stable under graph churn | Flow 4 |

## Terminology and source traceability

| Term | Meaning |
|---|---|
| Preferred output | The system default sink chosen as the default destination for streams confirmed to follow the preference. |
| Follow preferred | Confirmed route intent that tracks changes to the preferred output. |
| Explicit override | A live app stream explicitly pinned to a selected output while that stream exists. Persistence across app restarts is not promised. |
| Unknown route | The current endpoint is observed, but available source state cannot prove Follow preferred or Explicit override. The app may choose either option to establish intent. |
| Output level | Master gain/mute on one sink; affects every stream actually routed there. |
| App volume | Gain/mute on one app's PipeWire stream; independent from sink output level. |
| Microphone activity | PipeWire app streams consuming input. Distinct from Capture Tool screen recording. |

The [OpenSpec capability](../../../../openspec/changes/redesign-ags-audio-panel/specs/ags-audio-panel/spec.md) defines testable functional scenarios. The [audio/MPRIS dispatch notes](../../ags-audio-mpris-transport-dispatch-contract-2026-09-21.md) and [PipeWire control notes](../../../../docs/linux-wayland-pipewire-ags-audio-control.md) are technical evidence, not binding UX. The old mockups listed under Foundation remain historical; this spine and DESIGN.md win on conflict.

**Review note (2026-10-02):** The route-unknown and independent player/stream-lifetime rules were added after Sally's focused review. Those additions are not covered by her earlier review and should be included in a future focused UX/accessibility pass.

# Current audio boundary review

Date: 2026-10-02. Source inspection only; no changes to runtime code made in this review.

## Current map

| Surface | Current owner and behavior | Target seam |
|---|---|---|
| Popup lifecycle | `ags/app.tsx` constructs `AudioCatcher` and `AudioPopup`; `AudioPopup.tsx` owns popup UI, event handlers, and presentation bindings. `state.ts` exports `close`. | GTK popup/catcher remains a UI adapter; dispatch view actions through use cases and render a stable projected view model. |
| Output/input endpoints | `audio/state.ts` wraps `AstalWp` `wp.nodes`, default speaker/mic, endpoint volume/mute, routing, stream identity and effective sink resolution. | PipeWire adapter implements endpoint/stream observation and commands; output/app/input gain and route use cases live in application layer. |
| Per-app rows | Popup combines PipeWire playback streams with MPRIS players through helpers in `audio/state.ts`, `services/mpris-core.ts`, and `services/mpris-service.ts`. | Pure domain projection joins canonical app identity, effective route/intent, stream controls, player capabilities, and media metadata. |
| Playback metadata/actions | `mpris-service.ts` owns session-bus discovery, hydration, property updates, cache and player actions. `mpris-core.ts` owns pure parsing, identity, and normalization. | Preserve/refine pure `mpris-core` rules in domain; put bus lifecycle/actions behind MPRIS port adapter. |
| Bar output/mic indicators | `bar/widgets/audio.tsx` consumes `audio/state.ts`; speaker glyph follows default-output level/mute, left click opens the popup, right click launches `pavucontrol`, and vertical scroll nudges output level by 5%. Mic indicator is visible during actual mic use, its glyph shows default-mic mute, and a dot/ring marks live input use. | Keep as lightweight consumers of application view state/use cases; preserve click/right-click/scroll behavior and derive microphone visibility/ornament from actual input activity. |
| Settings system volume | Settings `SoundCard` embeds `components/sliders/VolumeSlider.tsx`, which calls `AstalWp` directly for default-speaker volume/mute. | Replace parallel AstalWp binding with same selected-output level/mute use cases used by popup. |
| Recording/screen capture | `bar/widgets/recording.tsx` subscribes to `domainEvents` topic `capture.state` from `lib/event-bus-core.ts`. | Leave on event hub as the existing capture-job feature; do not move PipeWire/MPRIS state onto it. |
| Icon/artwork lookup | Popup uses the shared icon registry and app identity/icon resolver; player media artwork is not yet the authoritative row artwork contract. | Add artwork port/adapter with bounded cache; projected media artwork falls back to shared app icon. |

## Review of existing uncommitted audio edits

The user's working-tree audio edits are intact and were inspected, not modified.

- **Observed intent / diagnostic additions:** debug counters and expanded `audio-debug` projection are diagnostic instrumentation. They increase coupling in `state.ts` and should not be mistaken for the final architecture.
- **Rendering mitigation:** `stableText` and `setIconOnce` avoid writing identical labels/images on every reactive notification. This is directionally useful if same-value property writes were the flicker cause, but it is not a root-cause proof on its own.
- **Transient display caches:** 1.5-second held stream and media/app-name values preserve row shape through graph gaps. These can hide a legitimate stream stop or stale metadata, and the maps currently live in the large state module. Treat as a documented transition workaround until stable identity and source events are modeled.
- **Routing snapshot:** `pw-dump` is coalesced after graph changes to resolve stream-to-sink links. It reads effective graph topology; it does not encode user's FollowPreferred-versus-Explicit intent.
- **Endpoint epochs:** signal subscription reuse appears to address redundant connect/disconnect churn and stale bindings. The implementation still exposes counters from a presentation-oriented helper in the state facade.
- **Evidence gap:** comments report measurements/captured frames, but this source review did not independently reproduce the user's title blink, validate all changes on the live GTK panel, or prove the 1.5-second behavior under app stop/hotplug.

## Architecture conclusion

The main design risk is not that every workaround is inherently wrong; it is that one AGS state module currently owns too many reasons to change while Settings takes a parallel AstalWp path and MPRIS owns a separate but coupled state model. A clean hexagonal redo should first extract pure app/route/player projection rules and command ports, then place PipeWire graph/metadata observation, MPRIS D-Bus lifecycle, artwork, and UI rendering behind distinct adapters. The existing event hub remains a separate input only for capture-job state.

The route-intent model and runtime adapter feasibility remain gated as described in `README.md` and `../design.md`.

## Follow-up audit of the existing audio source diff (2026-10-02)

The current working-tree source edits are still a mitigation layer, not the requested architecture redo. A live comparison and source read agree that `StreamRow.subtitle` still takes the PipeWire-derived subtitle whenever a stream exists; it does not prefer the linked MPRIS player's title/artist. Therefore the Chrome/Tidal blank subtitles and Firefox `AudioStream` defect remain in the edited source.

The seek diagnostics are useful but do not yet prove the source comments' asserted root cause. In the corrected MPRIS-seek capture, `rowListWrite`, `streamRow`, and `labelWrite` stayed stable and sampled images showed no blink; the physical pointer-drag case was not reproduced, and Firefox's MPRIS position was inconsistent. Treat claims that node-ID churn or repeated image/label writes fully explain the blink as hypotheses until a valid drag capture confirms them.

The display-hold implementation also needs lifecycle cleanup before it is a safe foundation: `releaseHeldStream()` currently has no call site, while `lastSeenStream` and `lastNames` can retain per-app objects/strings after rows are removed; expiration is only checked on a later accessor read, not by a timer. `lastSeenSinkId` has no read or write sites and appears unused. Keep these as explicit review findings; this planning pass did not modify the source files.

The current graph snapshot is refreshed after this panel's own route/default writes, popup open, and a playback/recording/output node-ID signature change. The source does not consume `pw-dump --monitor` events. The live monitor experiment confirmed that the event stream carries default metadata, `target.object`, and effective link IDs; it does not establish that current AGS reacts to external route changes while the popup stays open. This is the concrete reason the redesigned PipeWire adapter needs its own event subscription and reconciliation tests.

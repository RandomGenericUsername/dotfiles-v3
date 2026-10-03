# Design: Hexagonal audio panel

## Approved behavior

The UI reference is `mockups/audio-panel-redesign-concept.html` in the UX workspace. Its arrangement is binding at the interaction level: preferred output and output level first, then app rows with media and per-app controls, followed by input and microphone activity. The final AGS styling uses repository palette tokens rather than the mock's illustrative literal colors.

The system default/preferred output is the route for ordinary streams. Choosing another preferred output moves streams with confirmed `FollowPreferred` intent. A stream with confirmed explicit app routing remains on that endpoint. An app route menu exposes a separate `Follow preferred` choice, labelled with the current preferred device, and explicit endpoint choices. The route model also has `Unknown`: effective endpoint equality alone cannot prove whether an existing stream follows or overrides the default. The row shows its observed endpoint while intent is unknown; the user can choose either intent to establish it. An explicit route applies to the active stream; saved routing across application or AGS restarts is outside this change.

Output-device level is the selected sink's master gain and affects every stream reaching that sink, including explicit routes to it. App stream volume/mute remains independent. There is no device-scoped or aggregate player transport. Every player action is app-scoped.

Track title/artist and artwork come from MPRIS metadata when available. The UI keeps the app mark visible as identity and uses it as the artwork fallback. A stream without an MPRIS player keeps its route/level/mute controls and has no transport. Seek appears only when advertised and duration is usable.

### Validated media defects to resolve

The owner validated the current controls and routing. A read-only live comparison confirmed MPRIS title/artist metadata while Chrome, Tidal, and Firefox were Playing. AGS's player projection had that metadata, but the rows showed no Chrome/Tidal subtitle and Firefox `AudioStream`. `StreamRow.subtitle` currently chooses a PipeWire-derived subtitle whenever the stream exists and consults MPRIS only after the stream disappears; this explains the observed metadata mismatch. Firefox's reported seek blink remains a visual defect whose redraw trigger needs an instrumented seek capture. Required behavior: use available MPRIS metadata while Playing, use an honest app fallback if it is absent, and keep the row stable through seek/relink.

## Target boundary

```text
 GTK AudioPopup / bar widgets / Settings volume control
                │ input actions + read-only view models
                ▼
       Audio presentation / application layer
         ├── use cases (preferred output, app route,
         │   device gain, app gain/mute, input, transport)
         ├── app identity + stream/player projection
         └── pure audio domain rules and value types
                │ outbound ports
          ┌─────┴─────────┐
          ▼               ▼
 PipeWire/WirePlumber   MPRIS session bus
 adapter                adapter
 (AstalWp + graph       (signals + hydration;
  snapshot where        playerctl for actions)
  required)
```

The core defines the concepts and port contracts; adapters translate the installed system APIs into those contracts. GTK components render projected state and dispatch use-case commands. UI modules do not own identity matching, graph parsing, timers for state polling, or device routing policy.

Suggested code seams (names are design guidance, not a forced directory layout):

- **Domain core:** endpoint identity, preferred-vs-explicit route intent, app identity, volume/mute state, player capabilities, deterministic row projection. Pure TypeScript with no GJS imports.
- **Application/use cases:** observe combined audio session state; set preferred output; route an app stream to an endpoint or back to preferred; set sink/app/input level; toggle relevant mute; play/pause/seek a specific player.
- **PipeWire port/adapter:** observe AstalWp `wp.nodes` and endpoint/device state, obtain graph/link metadata through the existing one-pass snapshot seam where necessary, and perform stream/default endpoint actions. `wp.audio.*` convenience collections are unavailable on the measured AstalWp build. `wpctl` is not a UI state reader.
- **MPRIS port/adapter:** discover players and hydrate/observe properties from session D-Bus signals; preserve subscribe-before-read; use `playerctl` only for explicit actions. No periodic authoritative-state polling.
- **Artwork port/adapter:** resolve a player's supplied artwork URI to an image and cache it with bounded lifetime; report unavailable cleanly so the view can use the app icon. Avoid making media URI fetching part of GTK row logic.
- **Presentation:** map normalized graph/player updates to stable app rows; retain stable row identity while stream nodes re-link; expose actions/capabilities as view data.

`audio/state.ts` should become a composition/facade during the migration, then shrink or disappear as consumers move to these seams. Avoid a second, competing global audio model. Avoid arbitrary timed holds in the presentation layer; any transitional reconciliation must have a named domain reason, owner, bounded lifetime, and signal-driven invalidation.

## Routing state and reconciliation

The selected system default is the preferred destination. A stream route is `FollowPreferred`, `Explicit(endpointId)`, or `Unknown`. The application layer owns intent for active streams; it must not collapse Follow and Explicit after the user selects an explicit route, even if it currently points at the preferred device. A newly appearing app stream starts in `FollowPreferred` by default, so an app with no per-app override uses the current preference and moves when that preference changes. A per-app route command establishes Explicit, including when the selected endpoint equals the preferred endpoint. An observed external target change establishes Explicit unless it is part of the preferred-output use case. A stream already present when the adapter starts, or whose intent history was lost, is Unknown unless the adapter can authoritatively restore intent. Do not infer route intent for such an existing stream from endpoint equality alone.

Changing preferred output performs both operations as one user-facing use case: update the system default and ensure `FollowPreferred` streams are routed to it. Explicit routes are preserved, including an explicit target equal to the old or new default. Unknown pre-existing streams are not silently reclassified; report their observed endpoint and leave their intent undecided. New app streams follow the preferred output unless the user or an observed external route action explicitly overrides them. Returning a stream to `FollowPreferred` moves it to the current preferred output and opts it into future changes.

### Feasibility finding (2026-10-02)

The repository's current implementation does **not** represent the required route intent. `audio/state.ts` assigns AstalWp `target_endpoint` for a move and takes a later `pw-dump` snapshot of actual stream-to-sink links; `GraphSnapshot` contains effective targets, not whether the user chose FollowPreferred or Explicit. The installed read-only `wpctl settings` query reports both `linking.follow-default-target` and `linking.allow-moving-streams` as `true`.

WirePlumber documents that `target.object` directs a stream to an endpoint, but with `linking.follow-default-target=true`, a stream whose explicit target equals the current default is treated as following the default and moves when that default changes. Therefore endpoint equality, and even a route write to the current preferred endpoint, cannot by themselves preserve or prove the panel's FollowPreferred-versus-Explicit intent. Do not globally disable WirePlumber's follow-default compatibility behavior as a shortcut; that would change routing semantics for other applications.

The architecture uses an application-owned route-intent record plus a PipeWire/WirePlumber adapter that observes default-target metadata and stream target/link changes. A preferred-output use case reconciles `FollowPreferred` streams to the new default and reasserts recorded `Explicit(endpointId)` streams that WirePlumber moved because they previously matched the old default. A user/external stream-target change updates that stream's intent to explicit. Stable stream/app identity and node relinks must not lose that record. If intent cannot be restored after an AGS restart while the app stream is still alive, the selector presents the observed route as unknown until confirmed; it must not invent “Follow preferred” from endpoint equality. Intent persistence beyond this process lifetime is out of scope.

### Controlled runtime check (2026-10-02)

Using two temporary silent null sinks and a synthetic `pw-cat` stream, with no other playback streams active, the live session confirmed:

- A new stream without a per-app target linked to preferred A, then followed the preferred change A → C.
- An explicit target A selected while A was preferred followed WirePlumber to C after the preferred output changed. This is the narrow same-as-preferred override edge, not a failure of ordinary default routing.
- A separate stream launched with target A while C was preferred linked to A and stayed there after another default change. This proves explicit-target placement and persistence for that synthetic stream; it does not test AGS reasserting the same already-running stream after WirePlumber moves it.
- A follow-up used one running silent stream: WirePlumber moved it from preferred A to B; a Pulse-compatible move command reasserted A on that same stream; after the default changed to the original physical sink, the stream remained at A. This validates same-stream reassertion feasibility at the command layer, but not an AGS-owned route-intent registry or reconciliation loop. Firefox and Tidal, which were active on the physical sink during the test, were restored to sink 53.
- `pw-dump --monitor` captured 23 lines mentioning the temporary sinks or stream. The original physical default (C-Media sink 53) was restored; the temporary sinks and test streams were removed.

This confirms the user's first-launch scenario, explicit target placement, and same-stream reassertion feasibility. The application-owned intent/reconciliation behavior remains to be implemented and verified. The monitor capture exposed the default metadata key/value, stream `target.object`, and effective link node ids. Payload handling for externally initiated target changes, new-stream initialization races, unlink/relink, and AGS restart remains an adapter verification item; none of these findings make the user's routing concept unsound.

PipeWire offers an event-driven monitor (`pw-dump --monitor`) and native registry/metadata listeners, so a clean event source exists in principle. The current `wp.nodes`/snapshot seam alone is not proven to observe every default metadata and target change. Implementation must choose and validate the monitor/metadata subscription in the adapter before UI work depends on it. The monitor is an event subscription, not a periodic state poll.

**Remaining implementation gate:** implement the route-intent adapter and verify event handling for externally initiated target changes, new streams with an externally supplied target, stream unlink/relink, and AGS restart while a stream remains alive. Confirm route intent stays accurate or displays Unknown for a pre-existing stream whose history cannot be restored. The same-stream command-level reassertion behavior is already live-validated; verify AGS performs it from observed events. Do not replace event observation with periodic state polling.

### Evidence

- Current implementation: [`state.ts`](../../../dotfiles/config/ags/audio/state.ts) (`routeStreamTo`, `refreshStreamTargets`, `effectiveSinkName`); it has effective target/link data but no route-intent model.
- Installed runtime settings were queried read-only on 2026-10-02: `linking.follow-default-target=true`; `linking.allow-moving-streams=true`.
- [WirePlumber settings](https://pipewire.pages.freedesktop.org/wireplumber/daemon/configuration/settings.html) documents movable streams and default-target-follow behavior.
- [WirePlumber linking policy](https://pipewire.pages.freedesktop.org/wireplumber/policies/linking.html) documents `target.object` and ordinary default routing.
- [PipeWire `pw-dump` manual](https://pipewire.pages.freedesktop.org/pipewire/page_man_pw-dump_1.html) documents `--monitor` as reporting state changes.
- [AstalWp Stream API](https://docs.astal.dev/wireplumber/class.stream) exposes get/set target endpoint, but does not define the product-level follow/override intent.

The adapter reports actual endpoint and stream state back through events. UI labels reflect confirmed/current state, not only an optimistic selection. Errors remain local to the affected action and do not clear unrelated app rows.

## Event and update flow

PipeWire graph changes and MPRIS signals arrive through their adapters. The PipeWire adapter must observe target/default metadata changes as well as graph membership; a graph snapshot may be coalesced after relevant events to resolve links and app metadata, but it is not a timer-driven poll. MPRIS state arrives through D-Bus signals plus initial hydration. Position display may interpolate locally while a player is playing, but authoritative position is refreshed only at defined MPRIS sync events.

The dotfiles event hub remains independent. It carries application-owned job state such as screen capture, not desktop audio graph or player state. The popup may show microphone-consuming PipeWire streams beside a clearly separate screen-capture state, without conflating them.

## Failure and edge behavior

- Unavailable artwork falls back to the app icon.
- Missing media metadata uses an honest app/media fallback, never a generic backend title.
- Unsupported/unknown seek hides only seek; stream level, mute, route, and any supported transport actions remain available.
- A PipeWire re-link does not remount the row or transfer writes to a stale node. A command is accepted only against a current stream target.
- Device hot-unplug updates the selected endpoint truthfully and lets existing fallback/default behavior recover; do not report an unavailable endpoint as active.
- Multiple MPRIS interfaces and different PipeWire/MPRIS names resolve to one app row where they represent the same app. Unknown apps remain distinct rather than being merged by a broad guess.

## Migration boundary

This is a full popup rework, not an additive-only change to the current 1,600-line state module. Keep the existing event-driven invariants and measured API constraints, but reassess caches/holds against the new explicit domain and projection model. The same output-level application use case should serve the bar/Settings panel consumers so the system control does not keep a second raw AstalWp implementation.

Provisioning owns AGS file deployment and generated assets. If the proposed seams add or move runtime files, update the compositor deployment manifest, verification file list, and relevant source-set checks together. Never hand-edit generated `icons.json`.

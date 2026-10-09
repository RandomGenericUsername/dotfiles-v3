# Design

## Context: the audio tree today

`dotfiles/config/ags/audio/` contains **two architectures at once**.

The hexagon (from `redesign-ags-audio-panel`):

```
audio/
  domain/audio-model.ts                       pure values (AudioSession, EndpointState, VolumeState, …)
  application/ports.ts                        port interfaces (AudioSessionReader, PipeWirePort, MprisPort, …)
  application/audio-actions.ts                use cases taking the port bag
  application/runtime/audio-session-runtime.ts  session state, route-intent history, event reconciliation
  adapters/pipewire/{observation,commands,…}  AstalWp / wpctl seam
  adapters/mpris/mpris-adapter.ts             MPRIS seam
  presentation/audio-panel-view-model.ts      pure projection → AudioPanelViewModel
  composition.ts                              the composition root → AudioPanelBinding { model, actions }
  AudioPopup.tsx                              thin view over the binding
```

The legacy module `audio/state.ts` (1648 lines) bundles three concerns:

1. **Graph binding** — `wp.nodes` derivation by media-class, `defaultSpeaker`/
   `defaultMicrophone`, `micInUse`, the `useEndpointEpoch` invalidation hack,
   `applicationRows`, graph snapshots, per-app routing helpers (lines ~40–1300).
2. **UI-local state** — `popupVisible`, `activeSection`, `viewEpoch`,
   `audioIconX`/`setAudioIconX`, `open`/`close`/`toggle`/`back` (lines ~1303–1396).
3. **Pure vocabulary** — `levelVariant`, `clampVolume`, `nodeLabel`
   (lines ~1398–1417).

**Consumers of the legacy module:**

| Consumer | Imports | Which concern it actually needs |
|---|---|---|
| `bar/widgets/audio.tsx` | `clampVolume, defaultMicrophone, defaultSpeaker, levelVariant, micInUse, nodeOf, nudgeDefaultOutputVolume, open, setAudioIconX, toggle, useEndpointEpoch` | graph data (should come from the binding) + UI state + vocabulary |
| `AudioPopup.tsx` | `close, popupVisible, audioIconX, levelVariant` | UI state + vocabulary only |
| `app.tsx` | `close, debugAudioState, open` | UI state + a debug dump |

### The legacy module is ~90% dead already

The redesign merge moved the panel to the hexagon but left the legacy module's
whole rows/devices/graph machinery behind with **no external consumer**. An
import scan (`grep` over `dotfiles/config/ags`) shows the only importers of
`audio/state.ts` are `bar/widgets/audio.tsx` and `app.tsx`; and of the module's
large exports —

`applicationRows`, `outputDeviceList`, `inputDeviceList`, `recordingList`,
`graph`, `snapshotStats`, `defaultSinkPlayers`, `sinkAggregatePlaying`,
`playersOnSink`, `streamAppIconPath`, `appRowKey`, `routeAppTo`,
`setDefaultSpeaker`, `heldStreamForApp`, `isStreamBoundForDisplay`,
`releaseHeldStream`, `mediaNameForApp`, `appNameForApp`, `stableText`

— every one has **zero** external consumers. Several of the newly-added hold
helpers have no *internal* consumer either. The only thing keeping the rows
machinery transitively alive is `debugAudioState`, and `debugAudioState` is used
only by `app.tsx`.

Consequence: the "retire 1600 lines" step is mostly **deletion of dead code**,
not a risky rewrite. The live surface to re-home is small and enumerable:

| Consumer | Live symbols |
|---|---|
| `bar/widgets/audio.tsx` | `clampVolume, defaultMicrophone, defaultSpeaker, levelVariant, micInUse, nodeOf, nudgeDefaultOutputVolume, open, setAudioIconX, toggle, useEndpointEpoch` |
| `app.tsx` | `close, debugAudioState, open` |

### `mpris-service.ts` is dead once the legacy module goes

`audio/adapters/mpris/mpris-adapter.ts` imports `../../../services/mpris-core`
(the **pure** core), not `mpris-service`. `services/mpris-service.ts` is
imported **only** by `audio/state.ts`. So there is no dual MPRIS source to
reconcile: `mpris-service.ts` simply becomes unreachable when `audio/state.ts`
is deleted, and is removed. `mpris-core.ts` stays — the adapter and
`tests/tsconfig.tests.json` both rely on it.

## Target shape

### 1. Split `audio/state.ts` by responsibility

```
audio/ui-state.ts           UI-local state: popupVisible, activeSection, viewEpoch,
                            audioIconX/setAudioIconX, open/close/toggle/show*/back,
                            AudioSection type.  Imports ONLY `ags` (createState).
audio/presentation/levels.ts  pure vocabulary: levelVariant(muted, level), clampVolume(v).
                            No GJS, no `ags` — node-testable.
```

(The new files carry distinct names because `audio/state.ts` cannot coexist with
an `audio/state/` directory.)

The graph-binding remainder of `audio/state.ts` is **deleted**, not moved. Its
data now comes from `audioPanelBinding().model` (the projected session).

`open()` currently also calls `invalidateDefaultEndpoint()` and
`refreshStreamTargets()` to re-read the default after an out-of-panel change
(pavucontrol/wpctl/hotplug). In the hexagon, that re-read is the runtime's job:
the session is event-fed (`pipewire-observation` subscribes
`default-sink`/`default-source` changes), so the projection is already current
and the manual re-read is dropped. If an evidence-based gap is found during
implementation (the runtime misses an event the legacy epoch covered), it is
recorded as a follow-up on the observation adapter — **not** reintroduced as a
bar-side epoch.

### 2. Bar indicators consume the binding

The bar gets a small **pure projection** so the widget holds no mapping logic:

```
audio/presentation/bar-indicators.ts
  projectBarIndicators(model: AudioPanelViewModel): {
    output: { variant: string; level: number; muted: boolean }
    mic:    { variant: string; live: boolean }
  }
```

- `output.variant = levelVariant(model.preferredOutput?.volume.muted ?? false,
  model.preferredOutput?.volume.level ?? 0)`
- `output.muted/level` read `model.preferredOutput?.volume` (live, event-fed)
- `mic.variant = (model.input?.volume.muted ?? false) ? "mic-off" : "mic-on"`
- `mic.live = model.inputConsumers.length > 0` (input-direction current streams —
  the hexagon equivalent of the legacy `micInUse`)

Being pure and `ags`-free, this is registered by name in
`tests/tsconfig.tests.json`'s purity list and covered by `make ags-test` exactly
like `components/battery/presentation.ts`.

### 3. Binding injection (matching `AudioPopup`)

`AudioPopup` already receives `binding: AudioPanelBinding` as a prop from
`app.tsx`. The bar follows the same rule rather than importing the composition
singleton inside a widget:

- `app.tsx` `main()` calls `audioPanelBinding()` once.
- It passes the binding to `Bar(monitor, audioBinding)`.
- `Bar` passes it to `OutputIndicator`/`MicIndicator`.

This keeps the widgets pure renderers and makes the composition root the single
place the boundary is assembled — the same "one place" property
`composition.ts` documents for the panel.

*Alternative considered and rejected:* importing `audioPanelBinding()` directly
from the widget. Rejected because it re-creates the module-scope singleton
pattern the legacy `audio/state.ts` used (the reason the bar bypassed the
hexagon in the first place); prop injection makes the dependency visible and
testable.

### 4. Bar actions

- **Left click** → `open("main")` from `audio/ui-state.ts` +
  `setAudioIconX(x)`. Unchanged behaviour, new import path.
- **Scroll** → replace `nudgeDefaultOutputVolume(delta)` with a dispatched
  application action. The bar reads the current preferred-output level from the
  projection, clamps `level ± 0.05`, and calls
  `actions.setOutputVolume(model.preferredOutputId, nextPercent)`. This is the
  spec's "bar volume nudge … SHALL use the same selected-output level/mute
  application actions".
- **Right click** → still `execAsync(["pavucontrol"])` (an external launcher, out
  of scope here; the app-launcher port is a separate future change).

### 5. Delete the dead `mpris-service.ts`

`services/mpris-service.ts` is reachable only through `audio/state.ts`, so it is
deleted with it. `services/mpris-core.ts` (pure) is retained: the hexagon's
`mpris-adapter` imports it, and `tests/tsconfig.tests.json` lists it as a pure
module. No MPRIS logic moves — the adapter is already the merged, tested
implementation.

## Migration sequence (safe, incremental, revertable)

1. **Extract UI state + vocabulary.** Create `audio/ui-state.ts` and
   `audio/presentation/levels.ts`; repoint `AudioPopup.tsx`, `app.tsx`. The legacy
   module still exists and still exports the old names, so the bar keeps working.
   Gate: `make ags-typecheck`, `make ags-test`.
2. **Add `projectBarIndicators` + tests.** Pure module, no consumers yet. Gate:
   `make ags-test`.
3. **Repoint the bar widgets** to the binding + projection + UI-state module.
   Gate: `make ags-typecheck`, `make bar-typecheck`, `make audio-panel-render-test`.
4. **Retire the graph remainder of `audio/state.ts`.** After step 3 nothing
   imports it; delete the file, and redirect `audio-debug` to the binding (or
   drop it). Gate: `make audio-panel-gates`.
5. **Delete the dead `mpris-service.ts`** (and the module's now-unreachable hold
   helpers) once `audio/state.ts` is gone. Gate: `make audio-core-test` /
   `make audio-panel-gates`.
6. **Reconcile the spec delta** and run the full `make audio-panel-gates`.

Each step leaves the tree green and is independently revertable; the bar is
never left without a data source.

## Sequencing and dependencies

- **Depends on `finish-audio-panel-redesign` merging first.** That change edits
  `audio/AudioPopup.tsx` (the `media-transport-panel` group) and the same
  `ags-audio-panel` capability delta this change also edits. Landing this change
  on top avoids a conflict in both.
- **`make gates-ci` should be green.** `finish-audio-panel-redesign` fixed the
  `ci-gates-parity` drift (the audio gates are now seven per-target CI jobs and
  `ags-typecheck` is a declared self-hosted gate), so task 6.4 no longer carries
  a pre-existing-failure caveat.
- **The redesign's bar touch does not migrate the bar.** The merge only added
  owner ids to the bar's `useEndpointEpoch(defaultSpeaker, "bar:spk")` /
  `useEndpointEpoch(defaultMicrophone, "bar:mic")` calls. Removing that epoch
  path entirely is exactly what this change does.

## Risks

| Risk | Mitigation |
|---|---|
| The event-fed runtime misses a default-device change the legacy epoch caught | Verify empirically with a live pavucontrol/wpctl swap; if a gap exists, fix it in the observation adapter (the port's job), and record it — do not reintroduce a bar-side epoch |
| Bar glyph lags during the binding's async hydration | The projection returns `muted:false/level:0` for a null `preferredOutput`; the glyph renders the `muted` variant until hydration, matching today's boot behaviour. A dedicated scenario pins this |
| `Bar(monitor)` signature change ripples to per-monitor construction | `app.tsx` is the only caller; the binding is created once before the monitor loop |
| A "dead" legacy export actually has a consumer the scan missed | The import scan is a task gate (task 4.1) re-run before deletion; `make ags-typecheck` fails on any dangling import |

## What this unlocks

Once the bar is a binding consumer, `audio/` is a self-contained hexagon with a
single composition root — the template for the Wi-Fi, Bluetooth, battery/power,
recording and tray migrations, and the unit of extraction for the eventual
package split.

`finish-audio-panel-redesign` also established a useful precedent for that
program: a **per-surface icon group** (`media-transport-panel`) so one surface
can restyle without touching another, with `media-transport` retained for the
bar and everywhere else. The same "one icon decision module per domain" shape
is what the later cross-cutting pass (`registry.statePath(group, stateKey)` and
per-domain state-key modules) will formalise. The bar's own audio icons are
unchanged here — `volume` and `microphone` remain theirs.

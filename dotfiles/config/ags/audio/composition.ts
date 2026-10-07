import { createComputed, createState } from "ags"
import { PipeWireObservationAdapter } from "./adapters/pipewire/pipewire-observation"
import { createPipeWireCommands } from "./adapters/pipewire/pipewire-commands"
import { MprisAdapter, MprisArtworkAdapter } from "./adapters/mpris/mpris-adapter"
import { AudioSessionRuntime } from "./application/runtime/audio-session-runtime"
import {
  playPausePlayer, nextPlayer, previousPlayer, seekPlayer, selectPreferredInput,
  selectPreferredOutput, setAppRoute, setAppVolume, setInputVolume, setPreferredOutputVolume,
  toggleAppMute, toggleInputMute, togglePreferredOutputMute,
} from "./application/audio-actions"
import type { ActionResult, AudioPorts } from "./application/ports"
import { projectAudioPanel } from "./presentation/audio-panel-view-model"
import type { AudioPanelActions, AudioPanelBinding, RouteChoice, TransportAction } from "./AudioPopup"
import type { EndpointId } from "./domain/audio-model"

/**
 * The audio composition root (tasks.md 6.0).
 *
 * This is the single place the new boundary is assembled. Before this existed,
 * nothing constructed the session runtime, so `AudioPopup` received no binding
 * and rendered only its "connecting" placeholder -- the panel and every layer
 * beneath it were present but unreachable from `app.tsx`.
 *
 * Division of labour it depends on:
 *   adapters   own AstalWp / D-Bus / wpctl and the measured API constraints
 *   runtime    owns session state, route-intent history, event reconciliation
 *   actions    own the use cases; they take a port bag and return ActionResult
 *   view model is a pure projection of the session
 *   AudioPopup owns no audio policy -- it renders and dispatches only
 *
 * Failures here are contained rather than fatal: hydration uses
 * allSettled internally, and an artwork miss degrades to the app icon. A panel
 * that cannot reach MPRIS must still show routes and levels.
 */

/**
 * The view speaks percent (0-100); the use cases take a gain level (0-1) and
 * clamp it. Converting here keeps both sides honest -- the actions can never be
 * handed 72 meaning 7200% gain.
 */
const percentToLevel = (percent: number): number => percent / 100

/** Reports a failed action once instead of spamming per keystroke while dragging a slider. */
function reportAction(label: string, result: ActionResult): void {
  if (result.ok) return
  console.error(`audio action ${label} failed:`, result.reason ?? `${result.failed} target(s)`)
}

// Wrapped in Promise.resolve because some use cases return synchronously, and
// `.catch` must exist on the chain whatever they return.
function run(label: string, action: () => ActionResult | Promise<ActionResult>): void {
  Promise.resolve(action()).then((result) => reportAction(label, result)).catch((error: unknown) => {
    console.error(`audio action ${label} threw:`, error)
  })
}

let binding: AudioPanelBinding | null = null

/**
 * Rolling per-row trace, debug-only. Exposed so `ags request audio-panel-debug`
 * can show what a row reported immediately before and after an action -- the
 * only way to see a one-frame transient like the Firefox seek flash.
 */
let audioPanelTrace: string[] = []
export function audioPanelTraceLines(): readonly string[] {
  return audioPanelTrace
}

export function audioPanelBinding(): AudioPanelBinding {
  if (binding) return binding

  const pipeWireObservation = new PipeWireObservationAdapter()
  const pipeWireCommands = createPipeWireCommands()
  const mprisAdapter = new MprisAdapter()
  const artwork = new MprisArtworkAdapter()

  const runtime = new AudioSessionRuntime(pipeWireObservation, mprisAdapter, pipeWireCommands)

  const ports: AudioPorts = {
    session: runtime,
    pipewireObservation: pipeWireObservation,
    mprisObservation: mprisAdapter,
    pipewire: pipeWireCommands,
    routeIntents: runtime,
    mpris: mprisAdapter,
    artwork,
  }

  const actions: AudioPanelActions = {
// The settle is what makes a default change appear after ONE selection.
    // WirePlumber applies the write in its own daemon ~20ms after wpctl exits,
    // so without this the panel re-reads the stale default and keeps showing the
    // previous device until some unrelated event arrives. See the measured note
    // on PipeWireObservationAdapter.settleDefault.
    selectPreferredOutput: (endpointId) => run("selectPreferredOutput", () =>
      selectPreferredOutput(ports, endpointId as EndpointId)
        .then((result) => {
          if (result.ok) pipeWireObservation.settleDefault("output", endpointId)
          return result
        })),
    setOutputVolume: (endpointId, percent) => run("setOutputVolume", () =>
      setPreferredOutputVolume(ports, endpointId as EndpointId, percentToLevel(percent))),
    toggleOutputMute: (endpointId) => run("toggleOutputMute", () =>
      togglePreferredOutputMute(ports, endpointId as EndpointId)),
    setAppRoute: (appId, route: RouteChoice) => run("setAppRoute", () =>
      setAppRoute(ports, appId, route.kind === "follow-preferred"
        ? { kind: "follow-preferred" }
        : { kind: "explicit", endpointId: route.endpointId as EndpointId })),
    setAppVolume: (appId, percent) => run("setAppVolume", () => setAppVolume(ports, appId, percentToLevel(percent))),
    toggleAppMute: (appId) => run("toggleAppMute", () => toggleAppMute(ports, appId)),
    playerAction: (playerId, action: TransportAction) => run("playerAction", () => {
      if (action === "play-pause") return playPausePlayer(ports, playerId)
      if (action === "next") return nextPlayer(ports, playerId)
      return previousPlayer(ports, playerId)
    }),
    seek: (playerId, positionUs) => run("seek", () => seekPlayer(ports, playerId, positionUs)),
selectInput: (endpointId) => run("selectInput", () =>
      selectPreferredInput(ports, endpointId as EndpointId)
        .then((result) => {
          if (result.ok) pipeWireObservation.settleDefault("input", endpointId)
          return result
        })),
    // The view passes an endpoint id for uniformity with the other level
    // controls, but the input use case acts on the session's own default input.
    setInputVolume: (_endpointId, percent) => run("setInputVolume", () => setInputVolume(ports, percentToLevel(percent))),
    toggleInputMute: () => run("toggleInputMute", () => toggleInputMute(ports)),
  }

  // Artwork resolution is async and per-URI, so it cannot live in the pure
  // projection: `projectAudioPanel` leaves `artworkPath` null by design
  // (see the field comment there). The resolved paths are held here and
  // overlaid onto the projection. A miss simply leaves the app icon.
  const resolvedArtwork = new Map<string, string>()

  // THE reactive edge.
  //
  // `runtime.current()` is a plain method returning a clone, so reading it
  // inside createComputed registers no reactive dependency: the computed would
  // evaluate exactly once, at first render -- before the async PipeWire/MPRIS
  // hydration had resolved -- and never re-run. That shipped a panel with the
  // correct structure and permanently empty data ("No output available",
  // "No apps playing") while every gate passed, because nothing observable had
  // changed on disk.
  //
  // So the runtime's publish() is bridged onto a reactive revision. Bumping it
  // is what makes the projection recompute. One signal for both session updates
  // and artwork arrivals, so the two can never disagree.
  const [revision, setRevision] = createState(0)
  const bump = () => setRevision((value) => value + 1)

  // Rolling trace of what each row actually reported, so a transient like
  // "Firefox's volume flashes to 0 during a seek" can be OBSERVED instead of
  // inferred. Reported 2026-10-07: moving the seek bar briefly shows the row's
  // volume as 0, then it returns. Every fix in this area written from a theory
  // rather than a trace produced a second bug, so the trace comes first.
  // Bounded, in-memory, debug-only, and it cannot affect the panel.
  const trace: string[] = []
  const sample = (): void => {
    try {
      const rows = projectAudioPanel(runtime.current()).rows.map((row) =>
        `${row.appId}:s${row.streamIds.length}:${row.volume.level.toFixed(3)}${row.volume.muted ? ":M" : ""}`)
      trace.push(`${Date.now() % 100000} ${rows.join(" ")}`)
      if (trace.length > 80) trace.shift()
    } catch { /* never let the debug trace affect the panel */ }
  }
  audioPanelTrace = trace
  void sample

  // Serialised so a burst of session events cannot launch overlapping resolve
  // passes; each pass only looks at URIs it has not seen yet.
  let artworkPass: Promise<void> = Promise.resolve()

  runtime.subscribe(() => {
    bump()
    sample()
    artworkPass = artworkPass.then(async () => {
      const pending = runtime.current().players
        .map((player) => player.media.artworkUri)
        .filter((uri): uri is string => !!uri && !resolvedArtwork.has(uri))
      if (pending.length === 0) return
      let changed = false
      for (const uri of pending) {
        try {
          const resolved = await artwork.resolve(uri)
          if (resolved) {
            resolvedArtwork.set(uri, resolved.localPath)
            changed = true
          }
        } catch (error) {
          console.error("audio artwork resolve failed:", error)
        }
      }
      if (changed) bump()
    }).catch(() => {})
  })

  // Declared before first use: the artwork pass is chained onto it from the
// subscribe callback above, which is registered before this assignment.
// Recomputed whenever `revision` moves. Reads the revision FIRST so the
  // reactive dependency is registered before any early return.
  const model = createComputed(() => {
    revision()
    const projected = projectAudioPanel(runtime.current())
    if (resolvedArtwork.size === 0) return projected
    return {
      ...projected,
      rows: projected.rows.map((row) => {
        const path = row.artworkUri ? resolvedArtwork.get(row.artworkUri) : undefined
        return path && path !== row.artworkPath ? { ...row, artworkPath: path } : row
      }),
    }
  })

  runtime.start().catch((error) => console.error("audio runtime start failed:", error))

  binding = { model, actions }
  return binding
}
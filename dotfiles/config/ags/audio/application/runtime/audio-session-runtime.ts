import {
  FollowPreferred,
  UnknownRoute,
  explicitRoute,
  type AudioPlayer,
  type AudioSession,
  type AppId,
  type AudioStream,
  type EndpointId,
  type RouteIntent,
  type StreamId,
} from "../../domain/audio-model.ts"
import type {
  AudioSessionReader,
  MprisObservation,
  MprisObservationPort,
  PipeWireObservation,
  PipeWireObservationPort,
  PipeWirePort,
  RouteIntentWriter,
  Unsubscribe,
} from "../ports.ts"

type SessionListener = (session: AudioSession) => void

const emptySession = (): AudioSession => ({
  preferredOutputId: null,
  preferredInputId: null,
  outputs: [],
  inputs: [],
  input: null,
  apps: [],
  streams: [],
  players: [],
  appIntents: {},
})

function cloneSession(session: AudioSession): AudioSession {
  return {
    ...session,
    outputs: [...session.outputs],
    inputs: [...session.inputs],
    apps: [...session.apps],
    streams: session.streams.map((stream) => ({ ...stream, routeIntent: { ...stream.routeIntent } })),
    players: [...session.players],
    appIntents: { ...session.appIntents },
  }
}

function expectedRequestedTarget(intent: RouteIntent): EndpointId | null | undefined {
  if (intent.kind === "follow-preferred") return null
  if (intent.kind === "explicit") return intent.endpointId
  return undefined
}

/**
 * Composes PipeWire and MPRIS event streams into one session read model.
 * Route history is process-local and keyed by PipeWire stream identity;
 * effective endpoint equality is never used to infer FollowPreferred.
 */
export class AudioSessionRuntime implements AudioSessionReader, RouteIntentWriter {
  private session = emptySession()
  private readonly listeners = new Set<SessionListener>()
  private readonly routeHistory = new Map<StreamId, RouteIntent>()
  private readonly appHistory = new Map<AppId, RouteIntent>()
  private readonly lastStreams = new Map<StreamId, AudioStream>()
  private readonly pendingPipeWire: PipeWireObservation[] = []
  private readonly pendingMpris: MprisObservation[] = []
  private pipeWireUnsubscribe: Unsubscribe | null = null
  private mprisUnsubscribe: Unsubscribe | null = null
  private startPromise: Promise<void> | null = null
  private ready = false
  private disposed = false
  private readonly pipeWireObservation: PipeWireObservationPort
  private readonly mprisObservation: MprisObservationPort
  private readonly pipeWire: PipeWirePort

  constructor(
    pipeWireObservation: PipeWireObservationPort,
    mprisObservation: MprisObservationPort,
    pipeWire: PipeWirePort,
  ) {
    this.pipeWireObservation = pipeWireObservation
    this.mprisObservation = mprisObservation
    this.pipeWire = pipeWire
  }

  current(): AudioSession {
    return cloneSession(this.session)
  }

  subscribe(listener: SessionListener): Unsubscribe {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  /** Subscribe before one-shot hydration, then apply events received meanwhile. */
  start(): Promise<void> {
    if (this.startPromise) return this.startPromise
    if (this.disposed) return Promise.reject(new Error("Audio session runtime is disposed"))

    this.pipeWireUnsubscribe = this.pipeWireObservation.subscribe((event) => {
      if (!this.ready) this.pendingPipeWire.push(event)
      else this.acceptPipeWire(event)
    })
    this.mprisUnsubscribe = this.mprisObservation.subscribe((event) => {
      if (!this.ready) this.pendingMpris.push(event)
      else this.acceptMpris(event)
    })

    this.startPromise = Promise.allSettled([
      this.pipeWireObservation.hydrate(),
      this.mprisObservation.hydrate(),
    ]).then((results) => {
      const [pipeWireResult, mprisResult] = results
      if (pipeWireResult.status === "fulfilled") this.acceptPipeWire(pipeWireResult.value, true)
      else console.error("audio PipeWire hydration failed:", pipeWireResult.reason)
      if (mprisResult.status === "fulfilled") this.acceptMpris(mprisResult.value)
      else console.error("audio MPRIS hydration failed:", mprisResult.reason)
      this.ready = true
      for (const event of this.pendingPipeWire.splice(0)) this.acceptPipeWire(event)
      for (const event of this.pendingMpris.splice(0)) this.acceptMpris(event)
    })
    return this.startPromise
  }

  /**
   * Record intent for an APP, with or without a live stream.
   *
   * This is the paused case: the user wants Tidal to follow the preferred
   * device before anything is connected, but Tidal has released its stream, so
   * there is nothing to write to yet. The intent is stored and applied when the
   * app produces its next stream (see the seeding in acceptPipeWire), which is
   * also the moment a write becomes possible at all.
   */
  recordApp(appId: AppId, intent: RouteIntent): void {
    this.appHistory.set(appId, { ...intent })
    const now = this.session.apps.some((app) => app.id === appId)
    this.session = { ...this.session, appIntents: this.appIntents() }
    if (now) this.publish()
  }

  private appIntents(): Record<AppId, RouteIntent> {
    return Object.fromEntries([...this.appHistory.entries()].map(([id, intent]) => [id, { ...intent }]))
  }

  /** Store intent before an application command; ignore IDs no longer current. */
  record(streamId: StreamId, intent: RouteIntent): void {
    if (!this.session.streams.some((stream) => stream.id === streamId && stream.current)) return
    this.routeHistory.set(streamId, { ...intent })
    const owner = this.session.streams.find((stream) => stream.id === streamId)?.appId
    if (owner) this.appHistory.set(owner, { ...intent })
    this.boundHistory()
    this.session = {
      ...this.session,
      streams: this.session.streams.map((stream) => stream.id === streamId
        ? { ...stream, routeIntent: { ...intent } }
        : stream),
      appIntents: this.appIntents(),
    }
    this.publish()
  }

  dispose(): void {
    this.disposed = true
    this.pipeWireUnsubscribe?.()
    this.mprisUnsubscribe?.()
    this.pipeWireUnsubscribe = null
    this.mprisUnsubscribe = null
    this.listeners.clear()
    this.pendingPipeWire.length = 0
    this.pendingMpris.length = 0
    this.routeHistory.clear()
    this.lastStreams.clear()
  }

  private acceptPipeWire(event: PipeWireObservation, startup = false): void {
    if (event.kind === "snapshot") {
      this.reconcilePipeWireSnapshot(event.session, startup)
      return
    }

    // Compatibility for adapters that still emit granular observations.
    const next = this.current()
    if (event.kind === "preferred-output-changed") {
      this.reconcilePipeWireSnapshot({ ...next, preferredOutputId: event.endpointId })
    } else if (event.kind === "endpoint-changed") {
      this.reconcilePipeWireSnapshot({
        ...next,
        outputs: next.outputs.map((item) => item.id === event.endpoint.id ? event.endpoint : item),
      })
    } else if (event.kind === "stream-changed") {
      const streams = next.streams.filter((item) => item.id !== event.stream.id)
      this.reconcilePipeWireSnapshot({ ...next, streams: [...streams, event.stream] })
    } else if (event.kind === "stream-removed") {
      this.reconcilePipeWireSnapshot({ ...next, streams: next.streams.filter((item) => item.id !== event.streamId) })
    }
  }

  private reconcilePipeWireSnapshot(incoming: AudioSession, startup = false): void {
    const previousSession = this.session
    const before = new Map(this.lastStreams)
    const preferredChanged = !startup && previousSession.preferredOutputId !== incoming.preferredOutputId
    const nextStreams = incoming.streams.map((raw): AudioStream => {
      const previous = before.get(raw.id)
      const stored = this.routeHistory.get(raw.id)
      let intent: RouteIntent

      if (startup) {
        // A non-null requested target is evidence of an explicit override.
        // A target-less stream already present at startup has unknown history.
        intent = raw.requestedEndpointId !== null
          ? explicitRoute(raw.requestedEndpointId)
          : UnknownRoute
      } else if (stored !== undefined) {
        intent = stored
        const expected = expectedRequestedTarget(stored)
        if (!(preferredChanged && stored.kind === "explicit") && previous &&
            raw.requestedEndpointId !== previous.requestedEndpointId &&
            expected !== undefined && raw.requestedEndpointId !== expected) {
          intent = raw.requestedEndpointId === null ? FollowPreferred : explicitRoute(raw.requestedEndpointId)
        }
      } else if (previous) {
        intent = previous.routeIntent
        const expected = expectedRequestedTarget(intent)
        if (!(preferredChanged && intent.kind === "explicit") &&
            raw.requestedEndpointId !== previous.requestedEndpointId &&
            (expected === undefined || raw.requestedEndpointId !== expected)) {
          intent = raw.requestedEndpointId === null ? FollowPreferred : explicitRoute(raw.requestedEndpointId)
        }
      } else {
        // Streams appearing after startup follow default unless PipeWire
        // supplies a requested target. This does not inspect effective links.
        intent = raw.requestedEndpointId === null
          ? FollowPreferred
          : explicitRoute(raw.requestedEndpointId)
      }

      // An app-scoped intent outranks inference for a stream that has no
      // recorded history of its own -- e.g. the stream Tidal recreated after
      // being paused, for an app the user already told us to follow or pin.
      // Without this the new stream would be graded FollowPreferred by default
      // and silently discard a deliberate "pin to A" choice.
      const appStored = this.appHistory.get(raw.appId)
      if (appStored !== undefined && (startup || stored === undefined)) {
        intent = appStored
      }

      this.routeHistory.set(raw.id, { ...intent })
      return { ...raw, routeIntent: { ...intent } }
    })

    const nextIds = new Set(nextStreams.map((stream) => stream.id))
    const explicitToReassert = preferredChanged
      ? nextStreams.filter((stream) => stream.current && stream.direction === "output" && stream.routeIntent.kind === "explicit")
      : []

    this.lastStreams.clear()
    for (const stream of nextStreams) this.lastStreams.set(stream.id, stream)
    this.session = { ...incoming, streams: nextStreams, players: previousSession.players, appIntents: this.appIntents() }
    this.boundHistory()
    this.publish()

    // WirePlumber can retarget an explicit stream during default changes.
    // Reassert its recorded endpoint against the current node identity.
    for (const stream of explicitToReassert) {
      if (!nextIds.has(stream.id) || stream.routeIntent.kind !== "explicit") continue
      void this.pipeWire.setStreamTarget(stream.id, stream.routeIntent.endpointId).catch((error) => {
        console.error(`audio explicit route reassertion failed for ${stream.id}:`, error)
      })
    }
  }

  private acceptMpris(event: MprisObservation): void {
    let players: AudioPlayer[]
    if (event.kind === "snapshot") players = [...event.players]
    else if (event.kind === "player-changed") {
      players = this.session.players.filter((player) => player.id !== event.player.id)
      players.push(event.player)
    } else {
      players = this.session.players.filter((player) => player.id !== event.playerId)
    }
    this.session = { ...this.session, players }
    this.publish()
  }

  private publish(): void {
    const snapshot = this.current()
    for (const listener of [...this.listeners]) {
      try { listener(snapshot) } catch (error) { console.error("audio session listener failed:", error) }
    }
  }

  private boundHistory(): void {
    // Retain recently unlinked IDs for a same-ID relink; never transfer an
    // intent to a different stream based only on app name. Bound process data.
    const maxEntries = 512
    while (this.routeHistory.size > maxEntries) {
      const oldest = this.routeHistory.keys().next().value as StreamId | undefined
      if (oldest === undefined) break
      this.routeHistory.delete(oldest)
    }
  }
}

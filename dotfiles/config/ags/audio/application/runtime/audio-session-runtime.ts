import {
  FollowPreferred,
  UnknownRoute,
  explicitRoute,
  type AudioPlayer,
  type AudioSession,
  type AppId,
  type AudioStream,
  type VolumeState,
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
  appVolumes: {},
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
    appVolumes: { ...session.appVolumes },
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
  /**
   * Last volume an app was known to have, per app.
   *
   * Measured 2026-10-07 (per-row trace): seeking in Firefox tears down and
   * recreates its PipeWire stream, and the replacement node is reported by
   * AstalWp as level 0 AND muted for ~100ms before its real properties load.
   * The row therefore flicked to 0/muted and back on every seek. An app's level
   * is a property of the app, not of one stream instance: a re-created stream
   * must not reset it.
   */
  private readonly lastVolume = new Map<AppId, VolumeState>()
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
    this.session = { ...this.session, appIntents: this.appIntents(), appVolumes: this.appVolumes() }
    // ALWAYS publish, including for an app that is not in `session.apps`.
    //
    // The first version published only when `session.apps` already contained
    // the app, on the theory that an unknown app had nothing to update. That is
    // exactly backwards for the case this method exists for: a paused app has
    // released its stream, so its identity is not in `apps` (that list is built
    // from live streams), so the intent was stored but never published and the
    // row kept showing its old label until some unrelated event republished the
    // session. Reported as "I select speakers and it won't change".
    this.publish()
  }

  private appVolumes(): Record<AppId, VolumeState> {
    return Object.fromEntries([...this.lastVolume.entries()].map(([id, volume]) => [id, { ...volume }]))
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

      // A target write that merely lands on the CURRENT preferred output is
      // WirePlumber following the default, not a user override. Measured
      // 2026-10-07: connecting headphones rewrote target.object on every
      // follow-default stream to the headphone node, and the old code recorded
      // that as explicit intent -- flipping every row to "Override" and leaving
      // pinned apps playing through the headphones. design.md:55 states the
      // rule: an external target change establishes Explicit UNLESS it is part
      // of the preferred-output use case. This is that exception.
      const followedTarget = incoming.preferredOutputId
      const establishesExplicit = (target: EndpointId | null): boolean =>
        target !== null && target !== followedTarget

      if (startup) {
        // A target that DIFFERS from the current preferred output is real
        // evidence of a pin; a target that EQUALS the preferred output is what
        // WirePlumber writes for streams merely following the default, so it
        // proves nothing and stays Unknown. App intents do not survive a
        // restart, so this is all that is knowable here.
        intent = establishesExplicit(raw.requestedEndpointId)
          ? explicitRoute(raw.requestedEndpointId as EndpointId)
          : UnknownRoute
      } else if (stored !== undefined) {
        intent = stored
        const expected = expectedRequestedTarget(stored)
        if (!(preferredChanged && stored.kind === "explicit") && previous &&
            raw.requestedEndpointId !== previous.requestedEndpointId &&
            expected !== undefined && raw.requestedEndpointId !== expected) {
          intent = establishesExplicit(raw.requestedEndpointId)
            ? explicitRoute(raw.requestedEndpointId as EndpointId)
            : FollowPreferred
        }
      } else if (previous) {
        intent = previous.routeIntent
        const expected = expectedRequestedTarget(intent)
        if (!(preferredChanged && intent.kind === "explicit") &&
            raw.requestedEndpointId !== previous.requestedEndpointId &&
            (expected === undefined || raw.requestedEndpointId !== expected)) {
          intent = establishesExplicit(raw.requestedEndpointId)
            ? explicitRoute(raw.requestedEndpointId as EndpointId)
            : FollowPreferred
        }
      } else {
        intent = establishesExplicit(raw.requestedEndpointId)
          ? explicitRoute(raw.requestedEndpointId as EndpointId)
          : FollowPreferred
      }

      // An app-scoped intent ALWAYS outranks inference, whether or not this
      // stream has history of its own. The user's recorded choice is the only
      // thing that distinguishes "I pinned this" from "the policy moved it",
      // and the target-change heuristic above cannot. This is what keeps a
      // pinned app pinned when the default changes.
      const appStored = this.appHistory.get(raw.appId)
      if (appStored !== undefined) {
        intent = appStored
      }

      this.routeHistory.set(raw.id, { ...intent })

      // Trust a stream's volume unless it is a stream we have not seen before
      // that reports the uninitialised default (0 and muted). AstalWp exposes a
      // fresh node that way briefly; inheriting the app's last known level is
      // what stops the seek flick. A real change is never affected: it arrives
      // on a stream that already exists, or reports a volume that is not the
      // untouched default.
      const appKey = raw.appId
      let volume = raw.volume
      if (previous === undefined && volume.level === 0 && volume.muted) {
        const known = this.lastVolume.get(appKey)
        if (known) volume = { ...known }
      }
      if (!(volume.level === 0 && volume.muted)) this.lastVolume.set(appKey, { ...volume })

      return { ...raw, routeIntent: { ...intent }, volume }
    })

    const nextIds = new Set(nextStreams.map((stream) => stream.id))
    // Reassert any explicit stream that is not actually on its recorded
    // endpoint -- not only on a preferred-output change.
    //
    // Restricting this to `preferredChanged` missed the common case: the
    // headphone connection and WirePlumber's follow-default move arrive as
    // separate events, and by the time the preferred output was observed the
    // stream had already been classified. Comparing effective endpoint against
    // recorded intent is self-correcting and covers a policy move, a relink, or
    // any other drift with one rule.
    const explicitToReassert = nextStreams.filter((stream) =>
      stream.current && stream.direction === "output" &&
      stream.routeIntent.kind === "explicit" &&
      stream.endpointId !== stream.routeIntent.endpointId)

    this.lastStreams.clear()
    for (const stream of nextStreams) this.lastStreams.set(stream.id, stream)
    this.session = { ...incoming, streams: nextStreams, players: previousSession.players, appIntents: this.appIntents(), appVolumes: this.appVolumes() }
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

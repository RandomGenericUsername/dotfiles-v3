/** Pure audio-panel values. Keep this module independent of desktop runtimes. */
export type AppId = string
export type StreamId = string
export type PlayerId = string
export type EndpointId = string

export type RouteIntent =
  | { kind: "follow-preferred" }
  | { kind: "explicit"; endpointId: EndpointId }
  | { kind: "unknown" }

export const FollowPreferred: RouteIntent = Object.freeze({ kind: "follow-preferred" })
export const UnknownRoute: RouteIntent = Object.freeze({ kind: "unknown" })

export interface AppIdentity {
  id: AppId
  displayName: string
  desktopId?: string
  processId?: number
  aliases?: readonly string[]
}

export interface VolumeState {
  /** Normalized linear gain; muting never destroys the stored gain. */
  level: number
  muted: boolean
}

export interface AudioStream {
  id: StreamId
  appId: AppId
  direction: "output" | "input"
  /** Effective linked endpoint, independent from a stream's requested target. */
  endpointId: EndpointId | null
  /** PipeWire's requested target (target.object); null means follow default. */
  requestedEndpointId: EndpointId | null
  routeIntent: RouteIntent
  volume: VolumeState
  current: boolean
}

export interface PlayerCapabilities {
  canPlay: boolean
  canPause: boolean
  canPlayPause: boolean
  canGoNext: boolean
  canGoPrevious: boolean
  canSeek: boolean
}

export interface PlayerMedia {
  title: string
  artist: string
  album: string
  artworkUri: string | null
  lengthUs: number | null
  positionUs: number | null
}

export type PlaybackState = "playing" | "paused" | "stopped" | "unknown"

/** Player identity remains distinct from app and stream identities. */
export interface AudioPlayer {
  id: PlayerId
  appId: AppId
  current: boolean
  playback: PlaybackState
  capabilities: PlayerCapabilities
  media: PlayerMedia
}

export interface EndpointState {
  id: EndpointId
  name: string
  available: boolean
  volume: VolumeState
}

export interface InputState extends EndpointState {}

export interface AudioSession {
  preferredOutputId: EndpointId | null
  preferredInputId: EndpointId | null
  outputs: readonly EndpointState[]
  inputs: readonly EndpointState[]
  input: InputState | null
  apps: readonly AppIdentity[]
  /** Multiple current streams can belong to one app; actions address all. */
  streams: readonly AudioStream[]
  players: readonly AudioPlayer[]
  /**
   * Route intent held per APP, independent of any stream's lifetime.
   *
   * Streams are not durable: Tidal releases its PipeWire stream when paused for
   * a while and creates a new one on resume (measured 2026-10-07: hasStream
   * true -> false after ~20s paused, streams []). Intent stored only per stream
   * therefore vanished with the stream, the row fell back to "No current route",
   * and the user could not say "follow the preferred device" while paused --
   * which is precisely when they want to, because that is when a headset gets
   * connected. App-scoped intent survives that gap and is re-applied to the
   * app's next stream.
   */
  appIntents: Readonly<Record<AppId, RouteIntent>>
  /**
   * Last known level per app, so a row can hold it while the app's stream is
   * momentarily absent or freshly re-created. Measured: Firefox's stream
   * disappears and returns with the uninitialised 0/muted default on every
   * seek, which made the row flick.
   */
  appVolumes: Readonly<Record<AppId, VolumeState>>
}

export function clampLevel(level: number): number {
  if (!Number.isFinite(level)) return 0
  return Math.min(1, Math.max(0, level))
}

export function volumeState(level: number, muted: boolean): VolumeState {
  return { level: clampLevel(level), muted }
}

export function explicitRoute(endpointId: EndpointId): RouteIntent {
  return { kind: "explicit", endpointId }
}

/** A persisted/adapter-owned intent wins; existing streams without history stay unknown. */
export function initialRouteIntent(input: {
  isNew: boolean
  authoritativeIntent?: RouteIntent | null
  externallyRequestedTarget?: EndpointId | null
}): RouteIntent {
  if (input.authoritativeIntent) return input.authoritativeIntent
  if (!input.isNew) return UnknownRoute
  if (input.externallyRequestedTarget) return explicitRoute(input.externallyRequestedTarget)
  return FollowPreferred
}

export function routeIntentAfterUserSelection(
  selection: { kind: "follow-preferred" } | { kind: "explicit"; endpointId: EndpointId },
): RouteIntent {
  return selection.kind === "follow-preferred" ? FollowPreferred : explicitRoute(selection.endpointId)
}

/** An independently observed target change is an explicit routing action. */
export function routeIntentAfterExternalTargetChange(endpointId: EndpointId): RouteIntent {
  return explicitRoute(endpointId)
}

/** Route labels report recorded intent and observed endpoint independently. */
export function routeLabel(
  intent: RouteIntent,
  preferredEndpointId: EndpointId | null,
  observedEndpointId: EndpointId | null,
  endpoints: readonly EndpointState[],
): string {
  const name = (id: EndpointId | null): string | null =>
    id === null ? null : endpoints.find((endpoint) => endpoint.id === id)?.name ?? id
  if (intent.kind === "follow-preferred")
    return `Follow preferred · ${name(preferredEndpointId) ?? "Unavailable"}`
  if (intent.kind === "explicit") return `${name(intent.endpointId) ?? intent.endpointId} · Override`
  const observed = name(observedEndpointId)
  return observed === null ? "Unknown route" : `${observed} · Route unknown`
}

const ALIASES: Readonly<Record<string, string>> = Object.freeze({
  chromium: "google-chrome", chrome: "google-chrome", "google-chrome": "google-chrome",
  "mozilla-firefox": "firefox", firefox: "firefox",
  tidal: "tidal-hifi", "tidal-hi-fi": "tidal-hifi", "tidal-hifi": "tidal-hifi",
})

export function canonicalAppKey(value: string): string {
  const slug = value.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")
  return ALIASES[slug] ?? slug
}

/** PID is authoritative when both sides have one; otherwise use conservative aliases. */
export function identitiesReferToSameApp(a: AppIdentity, b: AppIdentity): boolean {
  if (a.id === b.id) return true
  if (a.processId !== undefined && b.processId !== undefined) return a.processId === b.processId
  const keys = (identity: AppIdentity): string[] =>
    [identity.desktopId, identity.id, ...(identity.aliases ?? [])]
      .filter((value): value is string => Boolean(value)).map(canonicalAppKey)
  const left = keys(a)
  return keys(b).some((key) => left.includes(key))
}

export function currentStreamsForApp(session: AudioSession, appId: AppId): AudioStream[] {
  return session.streams.filter((stream) => stream.current && stream.direction === "output" && stream.appId === appId)
}

export function currentInputConsumers(session: AudioSession): AppIdentity[] {
  const ids = new Set(session.streams
    .filter((stream) => stream.current && stream.direction === "input")
    .map((stream) => stream.appId))
  return session.apps.filter((app) => ids.has(app.id))
}

export function playerSupportsSeek(player: AudioPlayer): boolean {
  return player.current && player.capabilities.canSeek && player.media.lengthUs !== null &&
    Number.isFinite(player.media.lengthUs) && player.media.lengthUs > 0
}

import type { AppId, AudioSession, EndpointId, PlayerId, RouteIntent, StreamId, VolumeState } from "../domain/audio-model.ts"

/** Event-fed read model. Implementations must not poll for authoritative state. */
export interface AudioSessionReader { current(): AudioSession }

export interface Unsubscribe { (): void }

export type PipeWireObservation =
  | { kind: "snapshot"; session: AudioSession }
  | { kind: "preferred-output-changed"; endpointId: EndpointId | null }
  | { kind: "endpoint-changed"; endpoint: AudioSession["outputs"][number] }
  | { kind: "stream-changed"; stream: AudioSession["streams"][number] }
  | { kind: "stream-removed"; streamId: StreamId }

export type MprisObservation =
  | { kind: "snapshot"; players: AudioSession["players"] }
  | { kind: "player-changed"; player: AudioSession["players"][number] }
  | { kind: "player-removed"; playerId: PlayerId }

/** Signal-driven observation contracts; snapshots hydrate startup, subscriptions carry changes. */
export interface PipeWireObservationPort {
  hydrate(): Promise<PipeWireObservation>
  subscribe(listener: (event: PipeWireObservation) => void): Unsubscribe
}

export interface MprisObservationPort {
  hydrate(): Promise<MprisObservation>
  subscribe(listener: (event: MprisObservation) => void): Unsubscribe
}

export interface PipeWirePort {
  setPreferredOutput(endpointId: EndpointId): Promise<void>
  /** A null target clears the explicit PipeWire target so the stream follows the preferred output. */
  setStreamTarget(streamId: StreamId, endpointId: EndpointId | null): Promise<void>
  setPreferredInput(endpointId: EndpointId): Promise<void>
  setStreamVolume(streamId: StreamId, volume: VolumeState): Promise<void>
  setOutputVolume(endpointId: EndpointId, volume: VolumeState): Promise<void>
  setInputVolume(endpointId: EndpointId, volume: VolumeState): Promise<void>
}

/** Process-lifetime intent registry; never derives intent from endpoint equality. */
export interface RouteIntentWriter {
  record(streamId: StreamId, intent: RouteIntent): void
  /**
   * App-scoped intent, valid with or without a live stream. Needed because an
   * app can legitimately have no stream when the user sets its route -- Tidal
   * releases its stream while paused -- and the intent must survive until the
   * app creates its next one.
   */
  recordApp(appId: AppId, intent: RouteIntent): void
}

export interface MprisPort {
  play(playerId: PlayerId): Promise<void>
  pause(playerId: PlayerId): Promise<void>
  playPause(playerId: PlayerId): Promise<void>
  next(playerId: PlayerId): Promise<void>
  previous(playerId: PlayerId): Promise<void>
  seek(playerId: PlayerId, positionUs: number): Promise<void>
}

export interface ArtworkPort {
  resolve(uri: string): Promise<{ localPath: string } | null>
}

export interface AudioPorts {
  session: AudioSessionReader
  pipewireObservation: PipeWireObservationPort
  mprisObservation: MprisObservationPort
  pipewire: PipeWirePort
  routeIntents: RouteIntentWriter
  mpris: MprisPort
  artwork: ArtworkPort
}

export interface ActionResult {
  ok: boolean
  applied: number
  failed: number
  reason?: "missing-endpoint" | "no-current-stream" | "missing-player" | "unsupported"
}

export type AppScopedAction = (appId: AppId) => Promise<ActionResult>

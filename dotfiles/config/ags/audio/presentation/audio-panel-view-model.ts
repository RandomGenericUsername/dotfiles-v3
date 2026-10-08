import {
  canonicalAppKey, playerSupportsSeek, routeLabel,
  type AppIdentity, type AudioPlayer, type AudioSession, type AudioStream,
  type EndpointState, type PlayerCapabilities, type RouteIntent, type VolumeState,
} from "../domain/audio-model.ts"

export interface AudioPanelStreamView {
  id: AudioStream["id"]
  endpointId: AudioStream["endpointId"]
  routeIntent: RouteIntent
  volume: VolumeState
}

export interface AudioAppRowView {
  /** Stable canonical app key, independent of metadata, position, and stream relinks. */
  id: string
  appId: string
  appName: string
  desktopId?: string
  iconName: string
  artworkUri: string | null
  /** Local bounded-cache path; populated by composition after async artwork resolution. */
  artworkPath: string | null
  title: string
  artist: string
  album: string
  playback: AudioPlayer["playback"] | null
  playerId: AudioPlayer["id"] | null
  playerIds: readonly AudioPlayer["id"][]
  positionUs: number | null
  durationUs: number | null
  capabilities: PlayerCapabilities
  canSeek: boolean
  hasCurrentPlayer: boolean
  hasCurrentStream: boolean
  /** Stream and player identifiers stay distinct; app actions affect all listed streams. */
  streamIds: readonly AudioStream["id"][]
  streams: readonly AudioPanelStreamView[]
  /** Mean gain; mixed flags indicate that fan-out streams don't share one value. */
  volume: VolumeState
  mixedLevel: boolean
  mixedMuted: boolean
  observedEndpointId: string | null
  routeIntent: RouteIntent | null
  routeLabel: string
}

export interface AudioInputConsumerView {
  id: string
  appId: string
  appName: string
  iconName: string
}

export interface AudioPanelViewModel {
  preferredOutputId: string | null
  preferredOutput: EndpointState | null
  outputs: readonly EndpointState[]
  preferredInputId: string | null
  input: AudioSession["input"]
  inputs: readonly EndpointState[]
  inputConsumers: readonly AudioInputConsumerView[]
  rows: readonly AudioAppRowView[]
  /** App-scoped route intent, keyed by app id. Exposed for inspection. */
  appIntents: Readonly<Record<string, RouteIntent>>
  appVolumes: Readonly<Record<string, VolumeState>>
}

const clean = (value: string | null | undefined): string => value?.trim() ?? ""

function sameIntent(a: RouteIntent, b: RouteIntent): boolean {
  return a.kind === b.kind && (a.kind !== "explicit" || (b.kind === "explicit" && a.endpointId === b.endpointId))
}

function choosePlayer(players: readonly AudioPlayer[]): AudioPlayer | null {
  const rank = (player: AudioPlayer): number => {
    const state = player.playback === "playing" ? 4 : player.playback === "paused" ? 3 :
      player.playback === "stopped" ? 2 : 1
    return state * 2 + (clean(player.media.title) ? 1 : 0)
  }
  return [...players].sort((a, b) => rank(b) - rank(a) || a.id.localeCompare(b.id))[0] ?? null
}

function volumeSummary(streams: readonly AudioStream[]): {
  volume: VolumeState; mixedLevel: boolean; mixedMuted: boolean
} {
  if (!streams.length) return { volume: { level: 0, muted: false }, mixedLevel: false, mixedMuted: false }
  const levels = streams.map((stream) => stream.volume.level)
  const mutes = streams.map((stream) => stream.volume.muted)
  return {
    // The MAX level, not the mean.
    //
    // Measured 2026-10-07 with a per-row trace: Firefox spawns short-lived
    // extra PipeWire streams while seeking, and the row briefly reported 2 and
    // then 3 streams with means of 0.500 and 0.333 -- (1.0+0)/2 and
    // (1.0+0+0)/3. Those spooks read 0, dragging the average down and making
    // the volume visibly flick to another value and back. The user described it
    // exactly: "it changes to another value and then to the normal".
    //
    // An app's level is its level, not the average of however many streams it
    // currently happens to have. setAppVolume writes the same level to every
    // stream of the app, so in steady state max === mean; they diverge only
    // when a transient stream appears with a default of 0, which is precisely
    // the case that must not be allowed to move the display.
    //
    // Mute stays "all muted": one unmuted stream means audio is audible, and
    // reporting muted while sound plays would be the same class of lie.
    volume: { level: Math.max(...levels), muted: mutes.every(Boolean) },
    mixedLevel: levels.some((level) => Math.abs(level - levels[0]) > 0.0001),
    mixedMuted: mutes.some((muted) => muted !== mutes[0]),
  }
}

/** Pure projection: one stable canonical row while either a current player or stream exists. */
export function projectAudioPanel(session: AudioSession): AudioPanelViewModel {
  const groups = new Map<string, { streams: AudioStream[]; players: AudioPlayer[] }>()
  const ensure = (appId: string) => {
    const key = canonicalAppKey(appId) || appId
    let group = groups.get(key)
    if (!group) { group = { streams: [], players: [] }; groups.set(key, group) }
    return { key, group }
  }
  for (const stream of session.streams) if (stream.current) ensure(stream.appId).group.streams.push(stream)
  for (const player of session.players) if (player.current) ensure(player.appId).group.players.push(player)

  const identityByKey = new Map<string, AppIdentity>()
  for (const app of session.apps) {
    const key = canonicalAppKey(app.id)
    if (key && !identityByKey.has(key)) identityByKey.set(key, app)
  }

  const rows = [...groups.entries()].map(([key, group]): AudioAppRowView => {
    const app = identityByKey.get(key)
    const streams = group.streams.filter((stream) => stream.direction === "output")
      .sort((a, b) => a.id.localeCompare(b.id))
    const players = [...group.players].sort((a, b) => a.id.localeCompare(b.id))
    const player = choosePlayer(players)
    const media = player?.media
    const appName = app?.displayName?.trim() || player?.appId || group.streams[0]?.appId || key
    const intents = streams.map((stream) => stream.routeIntent)
    // With no stream there is no stream intent to show, so fall back to the
    // app-scoped one the user set while the app was silent. This is what keeps
    // the route control meaningful for a paused app instead of collapsing to
    // "No current route" and losing the choice.
    const appIntent = session.appIntents?.[key] ?? null
    const routeIntent = intents.length && intents.every((intent) => sameIntent(intent, intents[0]))
      ? intents[0]
      : streams.length === 0 ? appIntent : null
    const endpoints = new Set(streams.map((stream) => stream.endpointId))
    const observedEndpointId = endpoints.size === 1 ? streams[0]?.endpointId ?? null : null
    // With no stream, hold the app's last known level instead of reporting 0.
    // A one-frame 0 is indistinguishable from "you turned it down", and it is
    // what made every Firefox seek flick the row.
    const volume = streams.length === 0 && session.appVolumes?.[key]
      ? { volume: { ...session.appVolumes[key] }, mixedLevel: false, mixedMuted: false }
      : volumeSummary(streams)
    const canSeek = player !== null && playerSupportsSeek(player)
    const routeText = routeIntent
      ? routeLabel(routeIntent, session.preferredOutputId, observedEndpointId, session.outputs)
      : streams.length > 1 ? "Multiple routes · Mixed intent" : "No current route"
    return {
      id: key,
      appId: key,
      appName,
      desktopId: app?.desktopId,
      iconName: app?.aliases?.[0] || app?.desktopId || key,
      artworkUri: media?.artworkUri ?? null,
      artworkPath: null,
      title: clean(media?.title) || appName,
      artist: clean(media?.artist),
      album: clean(media?.album),
      playback: player?.playback ?? null,
      playerId: player?.id ?? null,
      playerIds: players.map((item) => item.id),
      positionUs: canSeek ? media?.positionUs ?? null : null,
      durationUs: canSeek ? media?.lengthUs ?? null : null,
      capabilities: player ? { ...player.capabilities } : {
        canPlay: false, canPause: false, canPlayPause: false,
        canGoNext: false, canGoPrevious: false, canSeek: false,
      },
      canSeek,
      hasCurrentPlayer: player !== null,
      hasCurrentStream: streams.length > 0,
      streamIds: streams.map((stream) => stream.id),
      streams: streams.map((stream) => ({
        id: stream.id, endpointId: stream.endpointId, routeIntent: stream.routeIntent,
        volume: { ...stream.volume },
      })),
      volume: volume.volume,
      mixedLevel: volume.mixedLevel,
      mixedMuted: volume.mixedMuted,
      observedEndpointId,
      routeIntent,
      routeLabel: routeText,
    }
  }).sort((a, b) => a.appName.localeCompare(b.appName) || a.id.localeCompare(b.id))

  const consumers = session.streams.filter((stream) => stream.current && stream.direction === "input")
    .sort((a, b) => a.appId.localeCompare(b.appId) || a.id.localeCompare(b.id))
    .map((stream) => {
      const key = canonicalAppKey(stream.appId)
      const app = identityByKey.get(key)
      return { id: stream.id, appId: key, appName: app?.displayName || stream.appId, iconName: app?.aliases?.[0] || app?.desktopId || key }
    })

  return {
    preferredOutputId: session.preferredOutputId,
    preferredOutput: session.outputs.find((item) => item.id === session.preferredOutputId) ?? null,
    outputs: session.outputs,
    preferredInputId: session.preferredInputId,
    input: session.input,
    inputs: session.inputs,
    appIntents: session.appIntents ?? {},
    appVolumes: session.appVolumes ?? {},
    inputConsumers: consumers,
    rows,
  }
}

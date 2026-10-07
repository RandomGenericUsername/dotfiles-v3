import {
  clampLevel, currentStreamsForApp, playerSupportsSeek, volumeState,
  type AppId, type AudioPlayer, type AudioSession, type EndpointId, type PlayerId,
} from "../domain/audio-model.ts"
import type { ActionResult, AudioPorts } from "./ports.ts"

const rejected = (reason: NonNullable<ActionResult["reason"]>): ActionResult =>
  ({ ok: false, applied: 0, failed: 0, reason })
async function fanOut(actions: readonly (() => Promise<void>)[]): Promise<ActionResult> {
  const results = await Promise.allSettled(actions.map((action) => action()))
  const failed = results.filter((result) => result.status === "rejected").length
  return { ok: failed === 0, applied: results.length - failed, failed }
}

export async function selectPreferredOutput(ports: AudioPorts, endpointId: EndpointId): Promise<ActionResult> {
  const session = ports.session.current()
  if (!session.outputs.some((item) => item.id === endpointId && item.available)) return rejected("missing-endpoint")
  await ports.pipewire.setPreferredOutput(endpointId)
  // Target-less FollowPreferred streams follow WirePlumber's new default.
  // The event runtime reasserts explicit streams if the policy moves them.
  return { ok: true, applied: 1, failed: 0 }
}

export async function setAppRoute(
  ports: AudioPorts, appId: AppId,
  route: { kind: "follow-preferred" } | { kind: "explicit"; endpointId: EndpointId },
): Promise<ActionResult> {
  const session = ports.session.current()
  const streams = currentStreamsForApp(session, appId)
  const target = route.kind === "follow-preferred" ? null : route.endpointId
  if (target !== null && !session.outputs.some((item) => item.id === target && item.available))
    return rejected("missing-endpoint")
  if (target === null && (session.preferredOutputId === null || !session.outputs.some((item) => item.id === session.preferredOutputId && item.available)))
    return rejected("missing-endpoint")
  // Route intent is reducer/observation state; the explicit command remains explicit
  // even when its endpoint currently equals preferredOutputId.
  const intent = route.kind === "follow-preferred" ? { kind: "follow-preferred" as const } : route
  // Record at APP scope first, and unconditionally. An app with no current
  // stream (Tidal while paused) has nothing to write to, but the choice must
  // still be remembered so it applies to the stream the app creates next. With
  // a live stream this also makes the intent survive the stream being torn
  // down and recreated.
  ports.routeIntents.recordApp(appId, intent)
  if (!streams.length) return { ok: true, applied: 0, failed: 0 }
  return fanOut(streams.map((stream) => async () => {
    await ports.pipewire.setStreamTarget(stream.id, target)
    ports.routeIntents.record(stream.id, intent)
  }))
}

export async function selectPreferredInput(ports: AudioPorts, endpointId: EndpointId): Promise<ActionResult> {
  if (!ports.session.current().inputs.some((item) => item.id === endpointId && item.available))
    return rejected("missing-endpoint")
  await ports.pipewire.setPreferredInput(endpointId)
  return { ok: true, applied: 1, failed: 0 }
}

export async function setPreferredOutputVolume(
  ports: AudioPorts, endpointId: EndpointId, level: number,
): Promise<ActionResult> {
  const endpoint = ports.session.current().outputs.find((item) => item.id === endpointId && item.available)
  if (!endpoint) return rejected("missing-endpoint")
  await ports.pipewire.setOutputVolume(endpointId, volumeState(clampLevel(level), endpoint.volume.muted))
  return { ok: true, applied: 1, failed: 0 }
}

export async function togglePreferredOutputMute(ports: AudioPorts, endpointId: EndpointId): Promise<ActionResult> {
  const endpoint = ports.session.current().outputs.find((item) => item.id === endpointId && item.available)
  if (!endpoint) return rejected("missing-endpoint")
  await ports.pipewire.setOutputVolume(endpointId, volumeState(endpoint.volume.level, !endpoint.volume.muted))
  return { ok: true, applied: 1, failed: 0 }
}

export async function setAppVolume(ports: AudioPorts, appId: AppId, level: number): Promise<ActionResult> {
  const streams = currentStreamsForApp(ports.session.current(), appId)
  if (!streams.length) return rejected("no-current-stream")
  return fanOut(streams.map((stream) => () => ports.pipewire.setStreamVolume(
    stream.id, volumeState(clampLevel(level), stream.volume.muted),
  )))
}

export async function toggleAppMute(ports: AudioPorts, appId: AppId): Promise<ActionResult> {
  const streams = currentStreamsForApp(ports.session.current(), appId)
  if (!streams.length) return rejected("no-current-stream")
  const muted = !streams.every((stream) => stream.volume.muted)
  return fanOut(streams.map((stream) => () => ports.pipewire.setStreamVolume(
    stream.id, volumeState(stream.volume.level, muted),
  )))
}

export async function setInputVolume(ports: AudioPorts, level: number): Promise<ActionResult> {
  const input = ports.session.current().input
  if (!input?.available) return rejected("missing-endpoint")
  await ports.pipewire.setInputVolume(input.id, volumeState(clampLevel(level), input.volume.muted))
  return { ok: true, applied: 1, failed: 0 }
}

export async function toggleInputMute(ports: AudioPorts): Promise<ActionResult> {
  const input = ports.session.current().input
  if (!input?.available) return rejected("missing-endpoint")
  await ports.pipewire.setInputVolume(input.id, volumeState(input.volume.level, !input.volume.muted))
  return { ok: true, applied: 1, failed: 0 }
}

function currentPlayer(session: AudioSession, id: PlayerId): AudioPlayer | null {
  return session.players.find((player) => player.id === id && player.current) ?? null
}
function playerAction(
  ports: AudioPorts, id: PlayerId, can: (player: AudioPlayer) => boolean,
  action: (port: AudioPorts["mpris"], id: PlayerId) => Promise<void>,
): Promise<ActionResult> | ActionResult {
  const player = currentPlayer(ports.session.current(), id)
  if (!player) return rejected("missing-player")
  if (!can(player)) return rejected("unsupported")
  return action(ports.mpris, id).then(() => ({ ok: true, applied: 1, failed: 0 }))
}

export const playPlayer = (ports: AudioPorts, id: PlayerId) =>
  playerAction(ports, id, (player) => player.capabilities.canPlay, (port, key) => port.play(key))
export const pausePlayer = (ports: AudioPorts, id: PlayerId) =>
  playerAction(ports, id, (player) => player.capabilities.canPause, (port, key) => port.pause(key))
export const playPausePlayer = (ports: AudioPorts, id: PlayerId) =>
  playerAction(ports, id, (player) => player.capabilities.canPlayPause, (port, key) => port.playPause(key))
export const nextPlayer = (ports: AudioPorts, id: PlayerId) =>
  playerAction(ports, id, (player) => player.capabilities.canGoNext, (port, key) => port.next(key))
export const previousPlayer = (ports: AudioPorts, id: PlayerId) =>
  playerAction(ports, id, (player) => player.capabilities.canGoPrevious, (port, key) => port.previous(key))

export async function seekPlayer(ports: AudioPorts, id: PlayerId, positionUs: number): Promise<ActionResult> {
  const player = currentPlayer(ports.session.current(), id)
  if (!player) return rejected("missing-player")
  if (!playerSupportsSeek(player) || !Number.isFinite(positionUs) || positionUs < 0)
    return rejected("unsupported")
  await ports.mpris.seek(id, Math.min(positionUs, player.media.lengthUs as number))
  return { ok: true, applied: 1, failed: 0 }
}

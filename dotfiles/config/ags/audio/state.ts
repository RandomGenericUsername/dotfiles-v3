import Wp from "gi://AstalWp?version=0.1"
import { Accessor, createBinding, createComputed, createState } from "ags"
import { execAsync } from "ags/process"
import GLib from "gi://GLib?version=2.0"

/**
 * Shared audio state + data model for the AGS bar instance
 * (add-pipewire-audio-control).
 *
 * ── The binding we actually have ─────────────────────────────────────────
 * `Wp.get_default()` returns a session object whose collections live on the
 * `audio` sub-object: `wp.audio.speakers/microphones/streams/recorders/
 * devices/default-speaker/default-microphone`. (Probing `wp.speakers` etc.
 * directly yields `undefined` — an earlier iteration built a nodes-filter
 * model on that mistake; the doc's collection model was right all along.)
 * `AstalWp.Endpoint.id` equals the PipeWire node id (verified: default sink
 * id 104 == `wpctl` sink 104), which is what the link snapshot joins on.
 *
 * No polling, no `wpctl` loop (doc §19/§20): collections are GObject
 * properties with add/remove notifies; the one exception is the per-stream
 * effective-sink snapshot (see `refreshStreamTargets`), which runs on popup
 * open + graph-membership change + after our own routing writes — never on a
 * timer.
 */

const wp = Wp.get_default()
const audio = (wp as unknown as { audio?: unknown } | null)?.audio ?? null

export { wp, audio }

type WpNode = {
  id?: number
  name?: string | null
  description?: string | null
  icon?: string | null
  volume?: number
  mute?: boolean
  "media-class"?: number
  target_endpoint?: unknown
  is_default?: boolean
}

/** Output devices (sinks) — the device subview + routing menus. */
export const outputDevices: Accessor<WpNode[]> = audio
  ? (createBinding(audio, "speakers") as Accessor<WpNode[]>)
  : createComputed(() => [])
/** Input devices (microphones). */
export const inputDevices: Accessor<WpNode[]> = audio
  ? (createBinding(audio, "microphones") as Accessor<WpNode[]>)
  : createComputed(() => [])
/** Playback application streams (one row per app stream). */
export const playbackStreams: Accessor<WpNode[]> = audio
  ? (createBinding(audio, "streams") as Accessor<WpNode[]>)
  : createComputed(() => [])
/** Recording application streams. */
export const recordingStreams: Accessor<WpNode[]> = audio
  ? (createBinding(audio, "recorders") as Accessor<WpNode[]>)
  : createComputed(() => [])

/** The default output/input endpoints (proven pattern: 3-path bindings). */
export const defaultSpeaker: Accessor<unknown> = audio
  ? createBinding(audio, "default-speaker")
  : createComputed(() => null)
export const defaultMicrophone: Accessor<unknown> = audio
  ? createBinding(audio, "default-microphone")
  : createComputed(() => null)

export const defaultSpeakerVolume: Accessor<number> = audio
  ? createBinding(audio, "default-speaker", "volume")
  : createComputed(() => 0)
export const defaultSpeakerMute: Accessor<boolean> = audio
  ? createBinding(audio, "default-speaker", "mute")
  : createComputed(() => true)
export const defaultMicrophoneVolume: Accessor<number> = audio
  ? createBinding(audio, "default-microphone", "volume")
  : createComputed(() => 0)
export const defaultMicrophoneMute: Accessor<boolean> = audio
  ? createBinding(audio, "default-microphone", "mute")
  : createComputed(() => true)

/** Set the default output volume (fraction 0..1). */
export function setDefaultOutputVolume(fraction: number) {
  const speaker = nodeOf(defaultSpeaker())
  if (speaker) speaker.volume = Math.max(0, Math.min(1, fraction))
}

/** Adjust the default output volume by `delta` (fraction of full scale). */
export function nudgeDefaultOutputVolume(delta: number) {
  const speaker = nodeOf(defaultSpeaker())
  if (speaker) speaker.volume = Math.max(0, Math.min(1, (speaker.volume ?? 0) + delta))
}

/** Toggle the default output mute. */
export function toggleDefaultOutputMute() {
  const speaker = nodeOf(defaultSpeaker())
  if (speaker) speaker.mute = !speaker.mute
}

/** Switch the default sink (proven pattern: set `is_default` on the endpoint,
 *  same as the settings panel's Bluetooth audio routing). */
export function setDefaultSpeaker(device: unknown) {
  const node = nodeOf(device)
  if (node) (node as { is_default?: boolean }).is_default = true
}

/** True while any recorder is consuming the microphone (drives the live dot). */
export const micInUse: Accessor<boolean> = createComputed(
  () => (recordingStreams()?.length ?? 0) > 0,
)

export function nodeOf(value: unknown): WpNode | null {
  return (value as WpNode) ?? null
}

// ── Effective per-stream sink ─────────────────────────────────────────────
// AstalWp's `Stream.target_endpoint` is NULL for streams routed outside AstalWp
// (e.g. via pavucontrol — verified live), so the popup cannot rely on it alone.
// The ground truth lives in PipeWire Link objects (stream port → sink port).
// We snapshot links on popup open + membership change + after our own routing
// writes, and join sink node ids to AstalWp endpoints (ids match PipeWire ids).
// Display rule: explicit target → link-resolved sink → default sink NAME —
// never the word "Default".

const [streamTargets, setStreamTargets] = createState<Record<number, number>>({})

export { streamTargets }

export async function refreshStreamTargets(): Promise<void> {
  try {
    const out = (await execAsync(["pw-dump"])) as unknown as string
    const dump = JSON.parse(out) as Array<{
      id?: number
      type?: string
      info?: Record<string, unknown>
    }>
    const portToNode: Record<number, number> = {}
    for (const obj of dump) {
      if (obj.type === "PipeWire:Interface:Port") {
        const props = (obj.info?.props ?? {}) as Record<string, unknown>
        const nodeId = props["node.id"]
        if (typeof obj.id === "number" && typeof nodeId === "number") {
          portToNode[obj.id] = nodeId
        }
      }
    }
    const map: Record<number, number> = {}
    for (const obj of dump) {
      if (obj.type !== "PipeWire:Interface:Link") continue
      const info = (obj.info ?? {}) as Record<string, unknown>
      if (String(info["state"] ?? "").toLowerCase() !== "active") continue
      const fromNode = portToNode[info["output-port-id"] as number]
      const toNode = portToNode[info["input-port-id"] as number]
      if (fromNode !== undefined && toNode !== undefined) map[fromNode] = toNode
    }
    setStreamTargets(map)
  } catch (e) {
    console.error("audio: stream-target snapshot failed:", e)
  }
}

/** Human name of the sink a stream is effectively playing on. */
export function effectiveSinkName(stream: unknown): string {
  const node = nodeOf(stream)
  // 1. Explicit AstalWp target (set by us or main's BT routing).
  const explicit = nodeOf(node?.target_endpoint)
  if (explicit) return nodeLabel(explicit, "Unknown output")
  // 2. Link-resolved sink.
  const targets = streamTargets()
  const sinkId = node?.id !== undefined ? targets[node.id] : undefined
  if (sinkId !== undefined) {
    const endpoint = (outputDevices() ?? []).find((s) => nodeOf(s)?.id === sinkId)
    if (endpoint) return nodeLabel(endpoint, "Unknown output")
  }
  // 3. Default sink name — a stream with no explicit target follows it.
  return nodeLabel(nodeOf(defaultSpeaker()), "No output")
}

/** Move a stream to another output (proven pattern: assign target_endpoint). */
export function routeStreamTo(stream: unknown, device: unknown) {
  const node = nodeOf(stream)
  if (node) (node as { target_endpoint?: unknown }).target_endpoint = device
  // Re-snapshot once WirePlumber re-links (one-shot, not a poll).
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 600, () => {
    void refreshStreamTargets()
    return false
  })
}

// ── UI state ───────────────────────────────────────────────────────────────

export type AudioSection = "main" | "output-devices"

const [popupVisible, setPopupVisible] = createState(false)
const [activeSection, setActiveSection] = createState<AudioSection>("main")
const [viewEpoch, setViewEpoch] = createState(0)

// Follower anchor: surface x-centre of the bar indicator that opened the
// popup (recorded by a motion controller on the buttons, same pattern as the
// settings panel's iconCenterX).
const [audioIconX, setAudioIconX] = createState<number | null>(null)

export { popupVisible, activeSection, viewEpoch, audioIconX, setAudioIconX }

/** Open the popup (optionally jumping straight to a section). */
export function open(section: AudioSection = "main") {
  setActiveSection(section)
  setPopupVisible(true)
  setViewEpoch((n) => n + 1)
  void refreshStreamTargets()
}

export function close() {
  setPopupVisible(false)
  setActiveSection("main")
}

export function toggle(section: AudioSection = "main") {
  if (popupVisible()) close()
  else open(section)
}

/** Enter the Output device subview (settings-panel in-place navigation). */
export function showOutputDevices() {
  setActiveSection("output-devices")
  setViewEpoch((n) => n + 1)
}

/** Return to the main popup view. */
export function back() {
  setActiveSection("main")
  setViewEpoch((n) => n + 1)
}

// ── Level vocabulary (shared with the settings-panel Sound card) ───────────

export function levelVariant(muted: boolean, value: number): string {
  if (muted || value <= 0) return "muted"
  const percent = Math.min(100, value * 100)
  if (percent <= 25) return "lowest"
  if (percent <= 50) return "low"
  if (percent <= 75) return "medium"
  return "max"
}

/** Clamp an AstalWp volume to [0,1] (it can briefly report NaN during swaps). */
export function clampVolume(value: number | null | undefined): number {
  return Math.max(0, Math.min(1, Number(value ?? 0)))
}

/** A stable display label for a node (falls back sensibly on empty fields). */
export function nodeLabel(node: WpNode | null, fallback: string): string {
  return node?.description || node?.name || fallback
}

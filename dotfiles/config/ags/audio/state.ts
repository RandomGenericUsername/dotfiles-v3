import Wp from "gi://AstalWp?version=0.1"
import { Accessor, createBinding, createComputed, createState } from "ags"

/**
 * Shared audio state + data model for the AGS bar instance
 * (add-pipewire-audio-control).
 *
 * ── The binding we actually have ─────────────────────────────────────────
 * The provisioned `libastal-wireplumber-git` (r973) exposes the post-rewrite
 * AstalWp model: `wp.nodes` (all PipeWire nodes), `wp.devices`,
 * `wp.default-speaker`, `wp.default-microphone`. The convenience collections
 * the upstream docs describe (`speakers`/`microphones`/`streams`/`recorders`)
 * are NOT compiled into this build — `get_speakers()` etc. are `undefined` at
 * runtime even though the GIR lists them. So we derive every collection from
 * `wp.nodes` by `media-class`, which IS populated (verified live: a `pw-play`
 * stream shows up as a class-4 node and vanishes when playback ends).
 *
 * MediaClass enum (AstalWp.MediaClass):
 *   0 Unknown, 1 Audio_Source (mic), 2 Audio_Sink (output),
 *   3 Stream_Input_Audio  (recorder), 4 Stream_Output_Audio (playback app),
 *   5+ video.
 *
 * All collections are reactive: `nodes` is a GObject property, so
 * `createBinding` re-fires on every add/remove — no polling, no wpctl
 * (doc §19/§20).
 */

const wp = Wp.get_default()

export { wp }

export const MEDIA_CLASS = {
  UNKNOWN: 0,
  AUDIO_SOURCE: 1,
  AUDIO_SINK: 2,
  STREAM_INPUT: 3,
  STREAM_OUTPUT: 4,
} as const

type WpNode = {
  id?: number
  name?: string | null
  description?: string | null
  icon?: string | null
  volume?: number
  mute?: boolean
  "media-class"?: number
  target_endpoint?: unknown
}

const allNodes: Accessor<unknown[]> = wp
  ? createBinding(wp, "nodes")
  : createComputed(() => [])

function byClass(mediaClass: number): Accessor<WpNode[]> {
  return createComputed(() => {
    const list = allNodes() ?? []
    return list.filter((n) => (n as WpNode)["media-class"] === mediaClass) as WpNode[]
  })
}

/** Output devices (sinks) — the surfaces in the Output-devices subview. */
export const outputDevices = byClass(MEDIA_CLASS.AUDIO_SINK)
/** Input devices (microphones). */
export const inputDevices = byClass(MEDIA_CLASS.AUDIO_SOURCE)
/** Playback application streams (one row per app stream). */
export const playbackStreams = byClass(MEDIA_CLASS.STREAM_OUTPUT)
/** Recording application streams. */
export const recordingStreams = byClass(MEDIA_CLASS.STREAM_INPUT)

/**
 * The default output/input nodes.
 *
 * This build does not emit `notify::default-speaker` / `notify::default-microphone`
 * (their property ids are mis-registered — the same "invalid property id" bug
 * that hits `connected`). A `createBinding` created at module load therefore
 * latches onto the initial `null` — which is exactly why the bar first showed
 * "No output device" and a later attempt showed 0%/muted forever.
 *
 * `wp.nodes` DOES notify, so we resolve the default endpoints from it: read the
 * live `default_speaker`/`default_microphone` for its `.id`, then find the
 * matching node. The result re-evaluates whenever the graph changes, and the
 * node object carries the live `volume`/`mute`.
 */
type DefaultEndpoint = { id?: number }

function defaultNodeId(kind: "speaker" | "microphone"): number | undefined {
  if (!wp) return undefined
  const ep = (wp as unknown as Record<string, DefaultEndpoint | null>)[
    kind === "speaker" ? "default_speaker" : "default_microphone"
  ]
  return ep?.id
}

function defaultNodeFor(mediaClass: number): Accessor<WpNode | null> {
  return createComputed(() => {
    const id = defaultNodeId(mediaClass === MEDIA_CLASS.AUDIO_SINK ? "speaker" : "microphone")
    const list = allNodes() ?? []
    if (id !== undefined) {
      const match = list.find((n) => (n as WpNode).id === id) as WpNode | undefined
      if (match) return match
    }
    // Fallback: first node of the class (mirrors WirePlumber picking a default).
    return (list.find((n) => (n as WpNode)["media-class"] === mediaClass) as WpNode) ?? null
  })
}

/** The default output node (sink). */
export const defaultSpeaker: Accessor<WpNode | null> = defaultNodeFor(MEDIA_CLASS.AUDIO_SINK)
/** The default input node (source). */
export const defaultMicrophone: Accessor<WpNode | null> = defaultNodeFor(MEDIA_CLASS.AUDIO_SOURCE)

export const defaultSpeakerVolume: Accessor<number> = createComputed(
  () => defaultSpeaker()?.volume ?? 0,
)
export const defaultSpeakerMute: Accessor<boolean> = createComputed(
  () => defaultSpeaker()?.mute === true,
)
export const defaultMicrophoneVolume: Accessor<number> = createComputed(
  () => defaultMicrophone()?.volume ?? 0,
)
export const defaultMicrophoneMute: Accessor<boolean> = createComputed(
  () => defaultMicrophone()?.mute === true,
)

/** Set the default output volume (fraction 0..1) by mutating the default node. */
export function setDefaultOutputVolume(fraction: number) {
  const n = defaultSpeaker()
  if (n) n.volume = Math.max(0, Math.min(1, fraction))
}

/** Adjust the default output volume by `delta` (fraction of full scale). */
export function nudgeDefaultOutputVolume(delta: number) {
  const n = defaultSpeaker()
  if (n) n.volume = Math.max(0, Math.min(1, (n.volume ?? 0) + delta))
}

/** Toggle the default output mute. */
export function toggleDefaultOutputMute() {
  const n = defaultSpeaker()
  if (n) n.mute = !n.mute
}

/** True while any recorder is consuming the microphone (drives the live dot). */
export const micInUse: Accessor<boolean> = createComputed(
  () => (recordingStreams()?.length ?? 0) > 0,
)

// ── UI state ───────────────────────────────────────────────────────────────

export type AudioSection = "main" | "output-devices"

const [popupVisible, setPopupVisible] = createState(false)
const [activeSection, setActiveSection] = createState<AudioSection>("main")
const [viewEpoch, setViewEpoch] = createState(0)

export { popupVisible, activeSection, viewEpoch }

/** Open the popup (optionally jumping straight to a section). */
export function open(section: AudioSection = "main") {
  setActiveSection(section)
  setPopupVisible(true)
  setViewEpoch((n) => n + 1)
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

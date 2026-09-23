import Wp from "gi://AstalWp?version=0.1"
import { Accessor, createBinding, createComputed, createEffect, createState, onCleanup } from "ags"
import { execAsync } from "ags/process"
import GLib from "gi://GLib?version=2.0"
import { registry } from "../lib/icon-registry"
import { activePlayer, playersByApp, type MprisPlayer } from "../services/mpris-service"
import { ALIAS, canonicalIdentity } from "../services/mpris-core"

/**
 * Shared audio state + data model for the AGS bar instance
 * (add-pipewire-audio-control).
 *
 * ── The binding we actually have ─────────────────────────────────────────
 * The provisioned `libastal-wireplumber-git` (r973) exposes the post-rewrite
 * AstalWp model: `wp.nodes` (all PipeWire nodes), `wp.devices`,
 * `wp.default_speaker`/`wp.default_microphone`. The convenience collections
 * the upstream docs describe (`audio.speakers`/`microphones`/`streams`/
 * `recorders`) are NOT compiled into this build — `get_speakers()` etc. are
 * `undefined` at runtime even though the GIR lists them (verified live: a
 * fresh `wp.audio.streams` stayed at 0 while two streams were playing). So we
 * derive every collection from `wp.nodes` by `media-class`, which IS populated
 * and notifies — no polling, no wpctl (doc §19/§20).
 *
 * MediaClass enum (AstalWp.MediaClass):
 *   0 Unknown, 1 Audio_Source (mic), 2 Audio_Sink (output),
 *   3 Stream_Input_Audio  (recorder), 4 Stream_Output_Audio (playback app),
 *   5+ video.
 *
 * Per-stream volume/mute are the node objects' own GObject properties, so each
 * row controls its own channel.
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

export function nodeOf(value: unknown): WpNode | null {
  return (value as WpNode) ?? null
}

// ── Graph snapshot (links + per-node identity) ────────────────────────────
//
// AstalWp's `Stream.target_endpoint` is NULL for streams routed outside AstalWp
// (e.g. via pavucontrol — verified live), so the popup cannot rely on it alone.
// The ground truth lives in the PipeWire graph: active Link objects join a
// stream port to a sink port, and each node carries its own identity props
// (app name, icon name, description). We snapshot all of it in ONE `pw-dump`
// pass:
//
//   streamSink : stream node id  → sink node id   (from active links)
//   nodeName   : any node id     → human name     (node.description / name)
//   nodeApp    : stream node id  → application name
//   nodeBinary : stream node id  → application.process.binary
//   nodeIcon   : stream node id  → application icon-theme name
//   nodeMedia  : stream node id  → media/track name (node.description)
//
// IMPORTANT: `pw-dump` Node/Port/Link props are keyed by the LITERAL PipeWire
// property names — DOTTED (`media.class`, `node.id`, `application.name`,
// `application.process.binary`, `application.icon-name`, `media.name`), NOT
// hyphenated. Links also carry the
// node ids directly (`output-node-id` / `input-node-id`), so no port join is
// needed. The sink-name map is what lets a Bluetooth sink resolve even when it
// is not enumerated as an AstalWp sink (verified live: `bluez_output.*` was
// absent from the sink list yet was the real link target).
//
// The snapshot is triggered by graph-membership change only (popup open, a
// stream/sink appearing or vanishing, our own routing writes) — never a timer
// (doc §19/§20). When idle, the graph legitimately has no links and the maps
// are empty; the display falls back to the default-sink NAME, never "Default".

interface GraphSnapshot {
  streamSink: Record<number, number>
  nodeName: Record<number, string>
  nodeApp: Record<number, string>
  nodeBinary: Record<number, string>
  nodeIcon: Record<number, string>
  nodeMedia: Record<number, string>
}

const EMPTY_SNAPSHOT: GraphSnapshot = {
  streamSink: {},
  nodeName: {},
  nodeApp: {},
  nodeBinary: {},
  nodeIcon: {},
  nodeMedia: {},
}

const [graph, setGraph] = createState<GraphSnapshot>(EMPTY_SNAPSHOT)

export { graph }

function asString(value: unknown): string {
  return typeof value === "string" ? value : ""
}

export async function refreshStreamTargets(): Promise<void> {
  try {
    const out = (await execAsync(["pw-dump"])) as unknown as string
    const dump = JSON.parse(out) as Array<{
      id?: number
      type?: string
      info?: Record<string, unknown>
    }>

    const nodeName: Record<number, string> = {}
    const nodeApp: Record<number, string> = {}
    const nodeBinary: Record<number, string> = {}
    const nodeIcon: Record<number, string> = {}
    const nodeMedia: Record<number, string> = {}
    const sinkIds = new Set<number>()

    for (const obj of dump) {
      if (typeof obj.id !== "number") continue
      if (obj.type !== "PipeWire:Interface:Node") continue
      const props = (obj.info?.props ?? {}) as Record<string, unknown>
      const cls = asString(props["media.class"])
      const name = asString(props["node.description"]) || asString(props["node.name"])
      if (name) nodeName[obj.id] = name
      if (cls === "Audio/Sink") sinkIds.add(obj.id)
      if (cls.startsWith("Stream/")) {
        const app = asString(props["application.name"])
        const binary = asString(props["application.process.binary"])
        const icon = asString(props["application.icon-name"])
        if (app) nodeApp[obj.id] = app
        if (binary) nodeBinary[obj.id] = binary
        if (icon) nodeIcon[obj.id] = icon
        // `media.name` is the track/stream name ("Playback", a tab title, …);
        // only keep it when it adds context over the app name.
        const media = asString(props["media.name"])
        if (media && media !== app) nodeMedia[obj.id] = media
      }
    }

    const streamSink: Record<number, number> = {}
    for (const obj of dump) {
      if (obj.type !== "PipeWire:Interface:Link") continue
      const info = (obj.info ?? {}) as Record<string, unknown>
      if (String(info["state"] ?? "").toLowerCase() !== "active") continue
      const fromNode = info["output-node-id"]
      const toNode = info["input-node-id"]
      if (typeof fromNode !== "number" || typeof toNode !== "number") continue
      // Only a stream→sink link is a routing fact; skip monitor/other links.
      if (sinkIds.has(toNode)) streamSink[fromNode] = toNode
    }

    setGraph({ streamSink, nodeName, nodeApp, nodeBinary, nodeIcon, nodeMedia })
  } catch (e) {
    console.error("audio: graph snapshot failed:", e)
  }
}

/** The name a sink node id resolves to, spanning AstalWp sinks → the snapshot's
 *  own node names (covers sinks AstalWp does not enumerate, e.g. Bluetooth). */
function sinkNameById(sinkId: number): string | null {
  const fromEndpoints = (outputDevices() ?? []).find((s) => nodeOf(s)?.id === sinkId)
  if (fromEndpoints) return nodeLabel(nodeOf(fromEndpoints), "")
  const snap = graph()
  return snap.nodeName[sinkId] ?? null
}

/** Human name of the sink a stream is effectively playing on. */
export function effectiveSinkName(stream: unknown): string {
  const node = nodeOf(stream)
  // 1. Explicit AstalWp target (set by us or main's BT routing).
  const explicit = nodeOf(node?.target_endpoint)
  if (explicit) return nodeLabel(explicit, "Unknown output")
  // 2. Link-resolved sink — the ground truth for externally-routed streams.
  const snap = graph()
  const sinkId = node?.id !== undefined ? snap.streamSink[node.id] : undefined
  if (sinkId !== undefined) {
    const name = sinkNameById(sinkId)
    if (name) return name
  }
  // 3. Default sink name — a stream with no explicit target follows it.
  return nodeLabel(nodeOf(defaultSpeaker()), "No output")
}

/** The application name a stream reports (Chrome, tidal-hifi, …). */
export function streamAppName(stream: unknown): string {
  const node = nodeOf(stream)
  const snap = graph()
  if (node?.id !== undefined) {
    const app = snap.nodeApp[node.id]
    if (app) return app
  }
  return nodeLabel(nodeOf(stream), "")
}

/** The media name a stream reports (e.g. a browser tab title), or "" when the
 *  backend exposes none. AstalWp's `Stream` has no such property — it comes
 *  from the snapshot's `node.description`. */
export function streamMediaName(stream: unknown): string {
  const node = nodeOf(stream)
  const snap = graph()
  if (node?.id === undefined) return ""
  return snap.nodeMedia[node.id] ?? ""
}

/** Slug an application name to an icon-name candidate: lowercase, spaces and
 *  punctuation → `-` (e.g. "YouTube Music" → `youtube-music`). Lets an app with
 *  no `application.icon-name` still match a brand asset by its display name. */
function slugifyAppName(name: string): string | null {
  const slug = name
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
  return slug === "" ? null : slug
}

// ── App-keyed row model ──────────────────────────────────────────────────────
//
// Rows are keyed by CANONICAL APP (`google-chrome`, `tidal-hifi`), never by
// PipeWire node id or MPRIS bus name. Both of those churn: YouTube re-links
// tear a stream down and recreate it under a new id on every seek, and an
// Electron app publishes two MPRIS interfaces for one playback. Keying rows by
// id/bus produced the whole reported bug family — volume `—` with routing
// visible (tearing between two computeds as `playbackStreams()` flapped),
// tidal's display resetting when its row flipped interfaces, phantom duplicate
// rows. An app-keyed row survives all of it; the live node/player are resolved
// at read time inside the row.
//
// Identity candidates come from the SAME graph snapshot used for routing:
// `application.name` (slugged) and `application.process.binary`. The MPRIS
// identity is frequently the framework (`chromium`), while the stream carries
// either the brand name (`Google Chrome` → `google-chrome`) or the process
// binary (`chrome`); `identityMatches` canonicalises BOTH sides through the
// alias table, so either field links (contract §5, resolved in bffa66c4).

/** Canonical app keys for one stream node (Identity/ALIAS-folded). */
function appKeysOfNode(node: WpNode | null): Set<string> {
  const keys = new Set<string>()
  if (!node) return keys
  const snap = graph()
  const raws: string[] = []
  if (node.id !== undefined) {
    const app = snap.nodeApp[node.id]
    if (app) raws.push(app)
    const binary = snap.nodeBinary[node.id]
    if (binary) raws.push(binary)
  }
  // Fall back to the node's own props when the async graph snapshot has not
  // caught up with a stream that just appeared (its app/binary are not in it
  // yet). Uses `description` ONLY — never `name`: AstalWp reports the MEDIA
  // name in `node.name` (e.g. literally "Playback"), which produced a phantom
  // "playback" app row beside the real one (caught via `ags request
  // audio-debug`). `description` carries the application name.
  if (raws.length === 0) {
    const v = node.description
    if (typeof v === "string" && v !== "") raws.push(v)
  }
  for (const raw of raws) {
    const slug = slugifyAppName(raw)
    if (slug) keys.add(canonicalIdentity(slug))
  }
  return keys
}

/** The MPRIS player for one app (canonical key), or null when the app has no
 *  live player. Reads from `playersByApp()`, so an Electron app's two
 *  interfaces resolve to their single representative. */
export function playerForApp(app: string): MprisPlayer | null {
  return playersByApp().find((player) => player.canonical === app) ?? null
}

/** The Output-card master button target (D1): the most recently active player. */
export { activePlayer as masterPlayer }

/**
 * One Applications row per canonical app (`{ app }`), whether the app
 * currently has a PipeWire stream, an MPRIS player, or both.
 *
 * The EXPERIENCE contract is explicit that a row persists for an app that still
 * has a player: "Stream paused (has player) → transport dims" and "the player
 * quits or goes Stopped → the row stays volume-only" (lines 83/175). Keying by
 * APP (not node id / bus name) is what makes that robust: YouTube re-links
 * tear a stream down and recreate it under a new id on seek, and
 * `playbackStreams()` flaps through transient drops — an id-keyed row then
 * evaluated `stream() === null` while its sibling routing chip still showed,
 * i.e. the torn volume-`—` + visible-routing state from the bug video. An
 * app-keyed row survives node churn; the live node is resolved per read.
 */
export interface AppRow {
  app: string
}

/** The stable `For` id for an app row. Never changes while the app exists. */
export function appRowKey(row: AppRow): string {
  return `app:${row.app}`
}

/** The live playback-stream node for an app, or null when the app has no
 *  stream right now (paused player, transient re-link gap). Resolved at read
 *  time so a reused row never holds a stale node object. */
export function liveStreamForApp(app: string): WpNode | null {
  const node =
    (playbackStreams() ?? []).find((s) => appKeysOfNode(nodeOf(s)).has(app)) ??
    null
  if (node) {
    lastLevel.set(app, {
      volume: clampVolume(node.volume ?? 0),
      mute: node.mute === true,
    })
  }
  return node
}

/**
 * Last-known level per app. Updated whenever a live node is read; read when
 * the app momentarily has no stream (re-link gap) so the volume line holds its
 * value instead of flashing `—`. A row whose app never had a stream in this
 * session has no entry and correctly renders the disabled line.
 */
const lastLevel = new Map<string, { volume: number; mute: boolean }>()

/** Display volume for an app row: live, else last-known, else 0. */
export function displayVolumeForApp(app: string): number {
  return liveStreamForApp(app)?.volume ?? lastLevel.get(app)?.volume ?? 0
}

/** Display mute for an app row: live, else last-known, else false. */
export function displayMuteForApp(app: string): boolean {
  const live = liveStreamForApp(app)
  if (live) return live.mute === true
  return lastLevel.get(app)?.mute ?? false
}

/** True when the app has a live stream node to write volume/mute/routing to. */
export function hasLiveStreamForApp(app: string): boolean {
  return liveStreamForApp(app) !== null
}

/** Write volume to the app's live stream; a no-op when there is none (the row
 *  is disabled in that state, so this only fires on stale closures). */
export function setAppVolume(app: string, fraction: number): void {
  const node = liveStreamForApp(app)
  if (node) node.volume = Math.max(0, Math.min(1, fraction))
}

/** Toggle mute on the app's live stream; a no-op when there is none. */
export function toggleAppMute(app: string): void {
  const node = liveStreamForApp(app)
  if (node) node.mute = !node.mute
}

/** Human name of the sink an app's stream is effectively playing on (routing
 *  label). Falls back to the default sink name when the app has no live
 *  stream — never the word "Default". */
export function effectiveSinkNameForApp(app: string): string {
  const node = liveStreamForApp(app)
  if (!node) return nodeLabel(nodeOf(defaultSpeaker()), "No output")
  return effectiveSinkName(node)
}

/** Route the app's live stream to another output; a no-op when there is none. */
export function routeAppTo(app: string, device: unknown): void {
  const node = liveStreamForApp(app)
  if (node) routeStreamTo(node, device)
}

/** Applications rows: one per canonical app that has a live stream, a live
 *  player, or both. Membership is a pure function of app presence, so transient
 *  node-id churn (seek re-links) and interface flips never add or remove rows —
 *  the row persists and its content rebinds. */
export const applicationRows: Accessor<AppRow[]> = createComputed(() => {
  const apps = new Map<string, true>()
  for (const stream of playbackStreams() ?? []) {
    for (const key of appKeysOfNode(nodeOf(stream))) apps.set(key, true)
  }
  for (const player of playersByApp()) {
    // A Stopped player with no stream has nothing to control (its transport
    // is inert and its volume target is gone) — only live players get a row.
    if (player.status === "Stopped") continue
    apps.set(player.canonical, true)
  }
  return [...apps.keys()].map((app) => ({ app }))
})

/** Every icon-name candidate for a stream, most specific first: the PipeWire
 *  `application.icon-name`, then the slug of the app name. */
function appIconCandidates(stream: unknown): string[] {
  const node = nodeOf(stream)
  const snap = graph()
  const candidates: string[] = []
  if (node?.id !== undefined) {
    const iconName = snap.nodeIcon[node.id]
    if (iconName) candidates.push(iconName)
  }
  const appName = streamAppName(stream)
  const appSlug = appName ? slugifyAppName(appName) : null
  if (appSlug) candidates.push(appSlug)
  return candidates
}

/** Resolve the SVG path for a stream's application icon.
 *
 *  The colored brand assets live in the literal-color `app-icons` group (keyed
 *  by `application.icon-name`, or a slug of the app name). Resolve order:
 *
 *    1. brand asset for each icon-name candidate;
 *    2. the neutral `app-icons/generic` fallback;
 *    3. `null` — the caller degrades to its own device glyph (e.g. the volume
 *       icon), so a row is never left blank.
 *
 *  Brand icons deliberately bypass the palette (they are literal-color), which
 *  is why they are resolved through the registry's `app-icons` group rather
 *  than the GTK theme (whose `*-symbolic` variants would strip the brand color).
 */
export function streamAppIconPath(stream: unknown): string | null {
  for (const candidate of appIconCandidates(stream)) {
    const path = registry.resolve("app-icons", candidate)
    if (path) return path
  }
  return registry.resolve("app-icons", "generic")
}

/** The brand-icon path for a stream-less row, keyed by an MPRIS identity rather
 *  than a live stream's props. An MPRIS identity is the framework name
 *  (`chromium`, `tidal-hifi`), so it is canonicalised through the same `ALIAS`
 *  table the stream matching uses before the registry lookup — `chromium`
 *  resolves the `google-chrome` asset, `tidal-hifi` its own. */
export function streamAppIconPathForIdentity(identity: string): string | null {
  const slug = slugifyAppName(identity)
  if (slug) {
    const path = registry.resolve("app-icons", slug)
    if (path) return path
    // The identity may be the framework name; try its brand alias too
    // (`chromium` → `google-chrome`).
    const alias = ALIAS[slug]
    if (alias && alias !== slug) {
      const aliased = registry.resolve("app-icons", alias)
      if (aliased) return aliased
    }
  }
  return registry.resolve("app-icons", "generic")
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

/** Switch the default sink.
 *
 *  `WpNode.is_default` is READ-ONLY on this AstalWp build (the GIR marks
 *  `is-default` writable only on `Endpoint`, and this build's default-endpoint
 *  notifies are mis-registered anyway), so assigning it is a silent no-op — the
 *  reason the Output card appeared to do nothing. The working action path is
 *  WirePlumber's own: `wpctl set-default <id>`. This is a one-shot ACTION, not a
 *  poll (doc §19: wpctl is fine for actions/diagnostics; only reactive state
 *  must come from the bindings). The graph then re-notifies `wp.nodes`, so the
 *  UI updates through the existing bindings. */
export function setDefaultSpeaker(device: unknown) {
  const node = nodeOf(device)
  if (node?.id === undefined) return
  execAsync(["wpctl", "set-default", String(node.id)]).catch((e) =>
    console.error("audio: set-default failed:", e),
  )
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

// ── Bar-process introspection (debug IPC) ────────────────────────────────────

/**
 * Snapshot of the audio state AS THE BAR SEES IT, for `ags request
 * audio-debug`. Exists because the bar's AstalWp `wp.nodes` binding can go
 * stale in the long-running process while `pw-dump` shows live streams — when
 * the popup's volume lines disagree with `pw-dump`, this tells us which side
 * is blind. Read-only; no side effects.
 */
export function debugAudioState(): Record<string, unknown> {
  const streams = (playbackStreams() ?? []).map((s) => {
    const n = nodeOf(s)
    return {
      id: n?.id ?? null,
      name: n?.name ?? null,
      description: n?.description ?? null,
      appKeys: [...appKeysOfNode(n)],
      volume: n?.volume ?? null,
      mute: n?.mute ?? null,
    }
  })
  const rows = (applicationRows() ?? []).map((row) => ({
    app: row.app,
    liveStreamId: liveStreamForApp(row.app)?.id ?? null,
    displayVolume: displayVolumeForApp(row.app),
    player: playerForApp(row.app)?.busName ?? null,
  }))
  const spk = nodeOf(defaultSpeaker())
  const mic = nodeOf(defaultMicrophone())
  return {
    streams,
    rows,
    defaultSpeaker: {
      id: spk?.id ?? null,
      volume: spk?.volume ?? null,
      mute: spk?.mute ?? null,
      accessorVolume: defaultSpeakerVolume(),
      accessorMute: defaultSpeakerMute(),
    },
    defaultMicrophone: {
      id: mic?.id ?? null,
      mute: mic?.mute ?? null,
      accessorMute: defaultMicrophoneMute(),
    },
    endpointEpoch: { ...endpointEpochStats },
  }
}

// ── Endpoint live-epoch (shared hook) ────────────────────────────────────────

/**
 * Diagnostics for the epoch hook below. `runs` counts effect executions,
 * `subscribes` counts successful notify subscriptions, `bumps` counts signal
 * deliveries. When a glyph freezes, these three numbers say exactly which link
 * died: runs=0 means the effect never ran; subscribes<runs means connect
 * failed; bumps=0 with subscribes>0 means signals never arrive (dead proxy).
 */
export const endpointEpochStats: { runs: number; subscribes: number; bumps: number } = {
  runs: 0,
  subscribes: 0,
  bumps: 0,
}

/**
 * Live epoch for an endpoint node (`defaultSpeaker()` / `defaultMicrophone()` /
 * a row's live stream). The volume/mute accessors only depend on list
 * membership, so without this a glyph freezes at its first render. Subscribes
 * to the CURRENT node's own notify signals and bumps an epoch the computeds
 * read; re-subscribes when node identity changes.
 */
export function useEndpointEpoch(endpoint: Accessor<unknown>): Accessor<number> {
  const [epoch, setEpoch] = createState(0)
  createEffect(() => {
    endpointEpochStats.runs++
    const node = endpoint() as unknown as {
      connect: (signal: string, cb: () => void) => number
      disconnect: (id: number) => void
    } | null
    if (!node) return
    const bump = () => {
      endpointEpochStats.bumps++
      setEpoch((n) => n + 1)
    }
    let hVolume = 0
    let hMute = 0
    try {
      hVolume = node.connect("notify::volume", bump)
      hMute = node.connect("notify::mute", bump)
      endpointEpochStats.subscribes++
    } catch {
      return
    }
    onCleanup(() => {
      try {
        node.disconnect(hVolume)
      } catch {
        /* node gone */
      }
      try {
        node.disconnect(hMute)
      } catch {
        /* node gone */
      }
    })
  })
  return epoch
}

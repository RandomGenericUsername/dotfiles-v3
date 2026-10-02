import Wp from "gi://AstalWp?version=0.1"
import { Accessor, createBinding, createComputed, createEffect, createState, onCleanup } from "ags"
import { execAsync } from "ags/process"
import GLib from "gi://GLib?version=2.0"
import { registry } from "../lib/icon-registry"
import {
  heldPositionsSnapshot,
  playersByApp,
  setAppIdentitySource,
  setClaimedStreamKeys,
  setPlayerPlaying,
  type MprisPlayer,
} from "../services/mpris-service"
import { ALIAS, canonicalIdentity, identityMatches } from "../services/mpris-core"

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
 *
 * ── Why `defaultEndpointEpoch` exists (measured, not inferred) ──────────────
 * The sentence above is true but INSUFFICIENT, and the gap was the reported
 * "the main Output never changes — it is always the speakers" bug. Measured
 * live with a throwaway null sink (created, set as default, removed):
 *
 *   `wpctl set-default <other sink>`  →  `wp.default_speaker.id` updates
 *                                         IN-PROCESS and immediately, and
 *   `wp.nodes`                        →  UNCHANGED (both sinks stay enumerated)
 *   `notify::default-speaker`         →  NEVER FIRES
 *
 * So a computed that depends only on `wp.nodes` membership never re-evaluates
 * when the default changes, and the Output card stayed pinned to whichever sink
 * happened to be resolved first — forever. Per-app routing was unaffected
 * because it goes through `target_endpoint` + a fresh `pw-dump` snapshot.
 *
 * The fix is a locally-owned epoch, bumped by every signal that can move a
 * default: our own `wpctl set-default` writes, any `wp.nodes` notify (a sink
 * connecting/leaving re-resolves the default), and the popup opening (a
 * user-action read, which also picks up a default changed outside the panel —
 * pavucontrol, a keybind, a hotplug). No polling (I1): these are events and one
 * user action.
 *
 * ── …and why the write alone was not enough ──────────────────────────────
 * Bumping the epoch the moment `wpctl` exits re-reads `wp.default_speaker` too
 * early: WirePlumber applies the change in its own daemon, AFTER the client
 * process is gone. Measured on this machine, 7ms after the `wpctl` process
 * exited the property still named the OLD sink; the flip landed ~20ms later.
 * So the re-resolve ran, read the stale value, and the card stayed on the old
 * device until some LATER trigger arrived — which is exactly the reported
 * "I have to change it twice, or play something, before it updates (even
 * though the audio actually switched)". A write is therefore followed by a
 * BOUNDED settle: re-resolve until the default really is the target, or the
 * budget expires. Bounded, started by a user action, and it stops the moment
 * the graph agrees — the same one-shot-after-a-write shape `routeStreamTo`
 * already uses for its own snapshot.
 */
type DefaultEndpoint = { id?: number }

//: Settle budget for a default WE just wrote. 15 × 100ms = 1.5s, far above the
//: measured ~20ms, and it aborts the moment the target is seen.
const DEFAULT_SETTLE_MS = 100
const DEFAULT_SETTLE_ATTEMPTS = 15

//: Bumped whenever the default endpoint may have changed. Read by
//: `defaultNodeFor` so the resolution re-runs even though `wp.nodes` did not.
const [defaultEndpointEpoch, bumpDefaultEndpoint] = createState(0)

/** Invalidate the resolved default endpoint. Called by the actions that write a
 *  default, by the `wp.nodes` notifier, and on popup open. */
export function invalidateDefaultEndpoint(): void {
  bumpDefaultEndpoint((n) => n + 1)
}

/** Re-resolve until a default we just wrote is actually in force.
 *
 *  Bumps immediately (the daemon may already have applied it) and then retries
 *  on a short timer, aborting as soon as `default_speaker`/`default_microphone`
 *  names the requested node — or when the budget runs out, which leaves the
 *  panel no worse off than before. Purely a re-resolution: no state is read
 *  into the UI from here, and the timer never outlives the budget.
 *
 *  On completion it also re-snapshots the graph. Changing the default makes
 *  WirePlumber re-link every stream to the new sink, and the per-app routing
 *  labels are resolved from that `pw-dump` snapshot — so without this the cards
 *  would update while the rows still advertised the old device until the next
 *  popup open. Same one-shot-after-a-write shape as `routeStreamTo`. */
function settleDefault(kind: "speaker" | "microphone", targetId: number): void {
  let attempts = 0
  const recheck = (): boolean => {
    invalidateDefaultEndpoint()
    attempts += 1
    const settled = defaultNodeId(kind) === targetId
    if (settled) void refreshStreamTargets()
    if (settled) return false
    return attempts < DEFAULT_SETTLE_ATTEMPTS
  }
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, DEFAULT_SETTLE_MS, recheck)
}

//: A sink appearing or disappearing re-points WirePlumber's default (measured:
//: disconnecting the configured Bluetooth sink fell back to the analog one), so
//: the default must be re-resolved when the graph changes — but ONLY when the
//: default actually moved. Bumping on every notify was a regression of its own:
//: an app whose streams churn (Firefox re-links on every seek and ad transition,
//: measured) fires `wp.nodes` notifications constantly, and each one re-resolved
//: the Output card. AstalWp hands back a FRESH GObject wrapper per lookup, so the
//: card re-rendered against a new object identity on every notification — the
//: flicker recorded in the Output section of the user's screen recording.
//: Comparing the resolved id is what distinguishes "the default moved" from
//: "the graph is busy", and only the former needs the UI to change.
if (wp) {
  let lastSpk: number | undefined
  let lastMic: number | undefined
  createEffect(() => {
    allNodes()
    const spk = defaultNodeId("speaker")
    const mic = defaultNodeId("microphone")
    const moved = spk !== lastSpk || mic !== lastMic
    lastSpk = spk
    lastMic = mic
    if (moved) invalidateDefaultEndpoint()
  })
}

function defaultNodeId(kind: "speaker" | "microphone"): number | undefined {
  if (!wp) return undefined
  const ep = (wp as unknown as Record<string, DefaultEndpoint | null>)[
    kind === "speaker" ? "default_speaker" : "default_microphone"
  ]
  return ep?.id
}

function defaultNodeFor(mediaClass: number): Accessor<WpNode | null> {
  return createComputed(() => {
    //: The epoch is the ONLY dependency that moves when the default changes —
    //: `wp.nodes` membership demonstrably does not (see the note above).
    defaultEndpointEpoch()
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

//: In-flight/queued bookkeeping for the graph snapshot. Firefox re-links its
//: stream on every seek and every ad transition, so while the popup is open the
//: `wp.nodes` binding can fire many times a second. Spawning a `pw-dump` per
//: notification means dozens of concurrent processes whose results land in an
//: arbitrary order — and the LAST one to land wins, so a stale parse could
//: overwrite a fresher one. One in flight, at most one queued behind it.
let snapshotInFlight = false
let snapshotQueued = false

/** Snapshot diagnostics, exposed via `ags request audio-debug`: how many times a
 *  dump was actually started, how many published a change, and how many were
 *  skipped because an identical snapshot was already held. When a row's identity
 *  looks wrong, these say immediately whether the snapshot is stale, churning, or
 *  simply never taken. */
export const snapshotStats: { started: number; published: number; skipped: number; coalesced: number } = {
  started: 0,
  published: 0,
  skipped: 0,
  coalesced: 0,
}

/** Do the parsed maps say anything new? Compared BY VALUE: `setGraph` installs a
 *  new object and gnim notifies on identity, so publishing an identical snapshot
 *  re-renders every row that reads it for nothing. That churn was itself visible:
 *  the Applications card blinked whenever a busy graph produced a dump identical
 *  to the one already held. */
function sameSnapshot(a: GraphSnapshot, b: GraphSnapshot): boolean {
  const sameMap = (x: Record<number, string>, y: Record<number, string>): boolean => {
    const keys = Object.keys(x)
    if (keys.length !== Object.keys(y).length) return false
    return keys.every((key) => x[Number(key)] === y[Number(key)])
  }
  const sameNumMap = (x: Record<number, number>, y: Record<number, number>): boolean => {
    const keys = Object.keys(x)
    if (keys.length !== Object.keys(y).length) return false
    return keys.every((key) => x[Number(key)] === y[Number(key)])
  }
  return (
    sameNumMap(a.streamSink, b.streamSink) &&
    sameMap(a.nodeName, b.nodeName) &&
    sameMap(a.nodeApp, b.nodeApp) &&
    sameMap(a.nodeBinary, b.nodeBinary) &&
    sameMap(a.nodeIcon, b.nodeIcon) &&
    sameMap(a.nodeMedia, b.nodeMedia)
  )
}

export async function refreshStreamTargets(): Promise<void> {
  if (snapshotInFlight) {
    snapshotQueued = true
    snapshotStats.coalesced++
    return
  }
  snapshotInFlight = true
  snapshotStats.started++
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

    const next: GraphSnapshot = { streamSink, nodeName, nodeApp, nodeBinary, nodeIcon, nodeMedia }
    if (sameSnapshot(graph(), next)) {
      snapshotStats.skipped++
    } else {
      snapshotStats.published++
      setGraph(next)
    }
  } catch (e) {
    console.error("audio: graph snapshot failed:", e)
  } finally {
    snapshotInFlight = false
    if (snapshotQueued) {
      snapshotQueued = false
      void refreshStreamTargets()
    }
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

/** True once a graph snapshot has actually been parsed.
 *
 *  A stream's app identity lives ONLY in the `pw-dump` snapshot (AstalWp exposes
 *  no `application.name`, and `node.description` is null for Firefox), so a panel
 *  that has never snapshotted cannot name any stream. Without this, the snapshot
 *  was taken solely while the popup was open, which left the rest of the surface
 *  — and `ags request audio-debug` — reporting an active stream with no identity
 *  at all, and the first popup open paying for a snapshot it then had to catch
 *  up with. Refreshing until the first snapshot exists keeps identity available
 *  everywhere; afterwards the popup's own gate is enough. */
export function hasGraphSnapshot(): boolean {
  const snapshot = graph()
  return Object.keys(snapshot.nodeApp).length > 0
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

/** Canonical keys last resolved for each stream node id.
 *
 *  The keys come from the `pw-dump` snapshot, which is refreshed ASYNCHRONOUSLY
 *  and therefore lags the graph by one round-trip. Measured across a seek: the
 *  Firefox stream's node id stayed 76 the whole time, yet for ~120ms the row had
 *  no keys at all — the snapshot momentarily carried no `application.name` for
 *  that id — so the row unbound from its stream, fell back to the player's
 *  identity for its title, and showed a dead `—` volume line. That is the reset
 *  in the screen recording, and it lasted exactly one dump.
 *
 *  Because the node id is STABLE across a re-link (the links change, the node
 *  does not — measured), the resolved identity is cached per id and reused when
 *  a snapshot comes back incomplete. The cache only fills a gap: a genuinely new
 *  node still has to be named by a snapshot, and a key is never invented. */
const streamKeysByNodeId = new Map<number, string[]>()

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
  //: Last resort, and the one that matters in practice: a snapshot taken while
  //: the node was mid-re-link. The id is unchanged across that window, so the
  //: identity we already resolved for it is still true — using it keeps the row
  //: bound instead of dropping to the player-only rendering for a frame.
  if (keys.size === 0 && node.id !== undefined) {
    const cached = streamKeysByNodeId.get(node.id)
    if (cached !== undefined) for (const key of cached) keys.add(key)
  }
  if (keys.size > 0 && node.id !== undefined) {
    streamKeysByNodeId.set(node.id, [...keys])
  }
  return keys
}

/**
 * Close the identity loop between the two naming sources.
 *
 * A stream claims an app under its OWN canonical keys; this answers the mirror
 * question — "which app keys do the live streams claim for THIS identity?" — by
 * matching the identity against every stream's raw identity candidates through
 * the same `ALIAS` fold `identityMatches` uses. Installed at module load so the
 * MPRIS service can resolve an unclaimed player onto the stream's key, which is
 * what collapses a Firefox-style double row into one.
 */
setAppIdentitySource((identity) => {
  const keys: string[] = []
  for (const stream of playbackStreams() ?? []) {
    const node = nodeOf(stream)
    if (node === null || node.id === undefined) continue
    const snap = graph()
    const candidates = [snap.nodeApp[node.id], snap.nodeBinary[node.id]]
      .filter((value): value is string => typeof value === "string" && value !== "")
    if (candidates.length === 0) continue
    if (!identityMatches(identity, candidates)) continue
    for (const key of appKeysOfNode(node)) {
      if (!keys.includes(key)) keys.push(key)
    }
  }
  return keys
})

/** The MPRIS player for one app (resolved key), or null when the app has no
 *  live player. Reads from `playersByApp()`, so an Electron app's two
 *  interfaces resolve to their single representative. */
export function playerForApp(app: string): MprisPlayer | null {
  //: Match on the player's resolved `appKeys`, not its `canonical`: when a
  //: stream spells the app differently from MPRIS (`Firefox` vs
  //: `Identity "Mozilla firefox"`), the player is listed under the STREAM's key
  //: and this row must still find it — otherwise the one unified row loses its
  //: transport line and the phantom row comes back.
  return playersByApp().find((player) => player.appKeys.includes(app)) ?? null
}

/** True when any live stream claims this app key. Diagnostic seam for the
 *  `audio-debug` dump; the row model reaches the same answer through
 *  `liveStreamForApp`. */
export function isStreamClaimed(app: string): boolean {
  return (playbackStreams() ?? []).some((s) => appKeysOfNode(nodeOf(s)).has(app))
}

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
  //: Deliberately does NOT record the level: `displayVolumeForApp` /
  //: `displayMuteForApp` own level bookkeeping (the momentary-zero hold), and
  //: this resolver is also used by pure lookups (routing, icons) that must not
  //: move the display state as a side effect.
  return streamNodeForApp(app)
}

/**
 * Last-known level per app. Updated whenever a live node is read; read when
 * the app momentarily has no stream (re-link gap) so the volume line holds its
 * value instead of flashing `—`. A row whose app never had a stream in this
 * session has no entry and correctly renders the disabled line.
 */
const lastLevel = new Map<string, { volume: number; mute: boolean }>()

//: A live node's OWN `volume` can read 0 for a frame or two while the graph
//: re-links. Measured on the same seek that unbound the row: the level line
//: blinked to 0% and back within ~120ms, with the node id unchanged throughout.
//: A real drop to zero PERSISTS — a user dragging to zero, or a mute elsewhere,
//: keeps reporting 0 on every later read — so a short hold on an implausible
//: fall to zero is invisible in use, and costs one re-read of latency in the
//: rare case a genuine zero arrives that fast.
//: Our own writes bypass the hold (see `setAppVolume`/`toggleAppMute`), so
//: dragging the slider to zero is never second-guessed.
const LEVEL_HOLD_MS = 500
const lastLevelAt = new Map<string, number>()

/** Record the level we are showing for an app. */
function recordLevel(app: string, volume: number, mute: boolean, holdable: boolean): void {
  lastLevel.set(app, { volume, mute })
  lastLevelAt.set(app, holdable ? GLib.get_monotonic_time() / 1000 : 0)
}

/** The level to show, holding an implausible momentary zero. */
function displayLevelFor(app: string, node: WpNode | null): { volume: number; mute: boolean } {
  if (node === null) return lastLevel.get(app) ?? { volume: 0, mute: false }
  const volume = clampVolume(node.volume ?? 0)
  const mute = node.mute === true
  const previous = lastLevel.get(app)
  const since = lastLevelAt.get(app) ?? 0
  const withinHold = since > 0 && GLib.get_monotonic_time() / 1000 - since < LEVEL_HOLD_MS
  if (
    volume <= 0 &&
    previous !== undefined &&
    previous.volume > 0 &&
    withinHold
  ) {
    //: Implausible dip: keep showing what we had, and do NOT refresh the
    //: timestamp — the hold must expire on its own even if more zeros arrive.
    return previous
  }
  recordLevel(app, volume, mute, true)
  return lastLevel.get(app) as { volume: number; mute: boolean }
}

/** Display volume for an app row: live (with the momentary-zero hold), else
 *  last-known, else 0. */
export function displayVolumeForApp(app: string): number {
  return displayLevelFor(app, liveStreamForApp(app)).volume
}

/** Display mute for an app row: live (with the same hold), else last-known. */
export function displayMuteForApp(app: string): boolean {
  return displayLevelFor(app, liveStreamForApp(app)).mute
}

/** True when the app has a live stream node to write volume/mute/routing to. */
export function hasLiveStreamForApp(app: string): boolean {
  return liveStreamForApp(app) !== null
}

/** Write volume to the app's live stream; a no-op when there is none (the row
 *  is disabled in that state, so this only fires on stale closures). */
export function setAppVolume(app: string, fraction: number): void {
  const node = liveStreamForApp(app)
  if (!node) return
  const value = Math.max(0, Math.min(1, fraction))
  node.volume = value
  //: The user chose this value; record it as non-holdable so dragging to zero is
  //: shown immediately instead of being masked by the momentary-zero hold.
  recordLevel(app, clampVolume(value), node.mute === true, false)
}

/** Toggle mute on the app's live stream; a no-op when there is none. */
export function toggleAppMute(app: string): void {
  const node = liveStreamForApp(app)
  if (!node) return
  node.mute = !node.mute
  recordLevel(app, clampVolume(node.volume ?? 0), node.mute === true, false)
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

// ── Selected-output aggregate transport (device-scoped) ────────────────────
//
// The Output card's transport is a control of the SELECTED DEVICE, not of any
// one application: with headphones selected, pausing it pauses everything routed
// through them — whether the other apps sit on other interfaces or on the same
// one. That makes it the mirror image of the per-app rows: same action, opposite
// scope (one app / one device).
//
// Attribution comes from the graph snapshot, which is the only place a
// stream→sink link exists (`target_endpoint` is NULL for streams routed outside
// AstalWp). A player with no live stream cannot be attributed and is therefore
// NOT touched: it is not demonstrably playing through that device, and guessing
// would be exactly the "invisible target" this control exists to avoid.

/** The live playback-stream node for an app, WITHOUT the `lastLevel` write of
 *  `liveStreamForApp` — for callers that only need the graph identity. */
function streamNodeForApp(app: string): WpNode | null {
  return (
    (playbackStreams() ?? []).find((s) => appKeysOfNode(nodeOf(s)).has(app)) ?? null
  )
}

/** The sink node id a stream is EFFECTIVELY playing on — the id behind
 *  `effectiveSinkName`, and deliberately kept in lockstep with it.
 *
 *  Same three steps, same order: explicit AstalWp target → the link-resolved
 *  sink from the graph snapshot → the default sink. The fallback is what makes
 *  the Output card's transport consistent with the UI: a PAUSED stream has only
 *  `init` links (measured — Firefox's links to the speakers are `init`, not
 *  `active`, while it is paused), so an active-link-only rule would exclude it
 *  and the button's blast radius would disagree with the routing chip on its own
 *  row, which shows the default device for exactly that case. One resolution,
 *  two consumers: the chip and the button can never name different devices. */
export function effectiveSinkIdForApp(app: string): number | null {
  const node = streamNodeForApp(app)
  if (!node) return null
  const explicit = nodeOf(node.target_endpoint)
  if (explicit?.id !== undefined) return explicit.id
  const snap = graph()
  const linked = node.id !== undefined ? snap.streamSink[node.id] : undefined
  if (linked !== undefined) return linked
  return nodeOf(defaultSpeaker())?.id ?? null
}

/** Every live MPRIS player whose effective sink is `sinkId` — i.e. exactly the
 *  rows whose routing chip names that device. */
export function playersOnSink(sinkId: number): MprisPlayer[] {
  return playersByApp().filter(
    (player) =>
      player.status !== "Stopped" &&
      player.appKeys.some((key) => effectiveSinkIdForApp(key) === sinkId),
  )
}

/** The players the Output card's transport acts on: everything routed to the
 *  SELECTED output right now. Empty when nothing plays through it. */
export const defaultSinkPlayers: Accessor<MprisPlayer[]> = createComputed(() => {
  const id = nodeOf(defaultSpeaker())?.id
  if (id === undefined) return []
  return playersOnSink(id)
})

/** True while at least one app routed to the selected output is playing — the
 *  aggregate state the button's glyph reflects (pause wins when mixed, so one
 *  press silences the device rather than starting the apps already paused). */
export const sinkAggregatePlaying: Accessor<boolean> = createComputed(() =>
  defaultSinkPlayers().some((player) => player.status === "Playing"),
)

/** Pause every app routed to the selected output, or resume them all.
 *
 *  Explicit per-app state, NOT a toggle: a naive `playPausePlayer` loop would
 *  START the apps that were already paused while pausing the ones that were
 *  playing. */
export function toggleSelectedOutputPlayback(): void {
  const players = defaultSinkPlayers()
  if (players.length === 0) return
  const playing = players.some((player) => player.status === "Playing")
  for (const player of players) setPlayerPlaying(player, !playing)
}

/** Applications rows: one per canonical app that has a live stream, a live
 *  player, or both. Membership is a pure function of app presence, so transient
 *  node-id churn (seek re-links) and interface flips never add or remove rows —
 *  the row persists and its content rebinds. */
// ── Stable presentation order ──────────────────────────────────────────────
//
// Rows are keyed by app (so a row survives node and bus-name churn), but the
// ORDER they came out in was an accident of WHICH source contributed the key:
// the union adds stream-derived keys first and player-derived keys second, so an
// app whose stream momentarily vanishes (Firefox re-links on every seek —
// measured) is re-contributed by its player and lands at a different index.
//
// Measured across one Firefox seek: `[[firefox], [chrome], [tidal]]` became
// `[[chrome], [tidal], [firefox]]`. `For` reorders its widgets on a list change,
// so every row below the moved one physically shifted — a whole-panel flicker
// reported as "moving Firefox makes everything flicker", while Chrome and Tidal
// were innocent bystanders being displaced.
//
// The order is therefore pinned per app for as long as the app exists: first
// appearance claims a slot, and nothing can move it. An app that leaves gives its
// slot back, so a returning app does not accumulate stale positions forever.
const rowOrder = new Map<string, number>()
let nextRowSlot = 0

// ── Stable reactive lists (for `For`) ──────────────────────────────────────
//
// gnim's `createComputed` re-notifies EVERY subscriber whenever ANY dependency
// notifies — it never compares its value — and `For` responds to a notification
// by unparenting and re-appending every child, unconditionally:
//
//     for (const [key, value] of map.entries()) fragment.remove(value.child)
//     … fragment.append(child)
//
// In GTK4, unparenting and re-appending a widget destroys and recreates its
// surface, so every row flashes. The trigger is ordinary: a seek, a metadata
// change, a status change, a new player appearing — anything touching
// `mprisPlayers` or the node list. Firefox emits a burst of those per seek, which
// is why it was the visible offender; Chrome and Tidal flickered too, just less
// often. The DATA was never wrong, which is exactly why polling the panel showed
// a clean 200/200 while the screen flickered: the widgets were being rebuilt, not
// the values changing.
//
// `createState` compares with `Object.is` before notifying, so a list held in
// state and written ONLY when its ordered keys actually differ never notifies
// `For` for a no-op. The effect still runs on every notification — it is a key
// computation and a string compare — but no widget is touched.
function stableList<T>(
  computeKeys: () => T[],
  keyOf: (item: T) => string,
): Accessor<T[]> {
  //: Rebound to a local because the repo's symbol checker only harvests params of
  //: `function f(a, b)` and `(a, b) =>` shapes — a parameter invoked from inside a
  //: zero-argument arrow reads as an undefined free identifier to it.
  const compute = computeKeys
  const [items, setItems] = createState<T[]>([])
  let shape: string | null = null
  createEffect(
    () => {
      const next = compute()
      const nextShape = next.map(keyOf).join("\u0000")
      if (nextShape === shape) return
      shape = nextShape
      setItems(next)
    },
    { immediate: true },
  )
  return items
}

export const applicationRows: Accessor<AppRow[]> = stableList<AppRow>(
  () => {
  const apps = new Set<string>()
  for (const stream of playbackStreams() ?? []) {
    for (const key of appKeysOfNode(nodeOf(stream))) apps.add(key)
  }
  // Publish what the streams claim BEFORE deriving the players, so a player
  // whose own canonical spelling differs is resolved onto the stream's key and
  // merges into the row above instead of adding a second one.
  setClaimedStreamKeys(new Set(apps))
  for (const player of playersByApp()) {
    // A Stopped player with no stream has nothing to control (its transport
    // is inert and its volume target is gone) — only live players get a row.
    if (player.status === "Stopped") continue
    for (const key of player.appKeys) apps.add(key)
  }
  // Release the slots of apps that are gone BEFORE new ones claim them, so a
  // returning app is ordered by its arrival rather than by an abandoned index.
  for (const key of [...rowOrder.keys()]) {
    if (!apps.has(key)) rowOrder.delete(key)
  }
  return [...apps]
    .map((app) => {
      let slot = rowOrder.get(app)
      if (slot === undefined) {
        slot = nextRowSlot++
        rowOrder.set(app, slot)
      }
      return { app, slot }
    })
    .sort((a, b) => a.slot - b.slot)
    .map(({ app }) => ({ app }))
  },
  appRowKey,
)

/** Device/recording lists for `For`, stabilised the same way. The device subviews
 *  re-parented every row on every node-list notification — which is most of
 *  them — so the Output/Input cards flickered on a churning graph too. */
export const outputDeviceList = stableList(
  () => outputDevices() ?? [],
  (device) => `sink:${nodeOf(device)?.id ?? "?"}`,
)
export const inputDeviceList = stableList(
  () => inputDevices() ?? [],
  (device) => `src:${nodeOf(device)?.id ?? "?"}`,
)
export const recordingList = stableList(
  () => recordingStreams() ?? [],
  (stream) => `rec:${nodeOf(stream)?.id ?? "?"}`,
)

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
  //: Captured in a const: property narrowing does not survive into the
  //: callback, and the settle needs the id the write ASKED for, not whatever
  //: the node object reports later.
  const targetId = node.id
  execAsync(["wpctl", "set-default", String(targetId)])
    .then(() => {
      //: Re-resolve on OUR write (see `defaultEndpointEpoch`): the write is the
      //: one moment we know a default moved and no signal will tell us — but the
      //: daemon applies it AFTER this process exits, so the re-resolve has to
      //: settle rather than fire once.
      settleDefault("speaker", targetId)
    })
    .catch((e) => console.error("audio: set-default failed:", e))
}

/** Switch the default microphone.
 *
 *  Same action path as outputs (`wpctl set-default <id>` — a one-shot ACTION,
 *  never a poll; `WpNode.is_default` is read-only on this build). Verified
 *  end-to-end for sinks; for sources the path is WirePlumber's identical
 *  default-device machinery (`Default Configured Devices` slot 1 is
 *  `Audio/Source`). Note: virtual/V4L2 sources are not eligible defaults —
 *  WirePlumber silently keeps the current one — so only real input devices
 *  effectively switch. */
export function setDefaultMicrophone(device: unknown) {
  const node = nodeOf(device)
  if (node?.id === undefined) return
  //: Captured in a const: property narrowing does not survive into the
  //: callback, and the settle needs the id the write ASKED for, not whatever
  //: the node object reports later.
  const targetId = node.id
  execAsync(["wpctl", "set-default", String(targetId)])
    .then(() => settleDefault("microphone", targetId))
    .catch((e) => console.error("audio: set-default failed:", e))
}

// ── UI state ───────────────────────────────────────────────────────────────

export type AudioSection = "main" | "output-devices" | "input-devices"

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
  //: A default changed OUTSIDE the panel (pavucontrol, a keybind, `wpctl`,
  //: a hotplug) reaches us only here — this is a user-action read, not a poll
  //: (I1), and it is what makes the Output/Input cards truthful on open.
  invalidateDefaultEndpoint()
  void refreshStreamTargets()
}

export function close() {
  setPopupVisible(false)
  setActiveSection("main")
}

// ── Graph snapshot scheduling ───────────────────────────────────────────────
//
// WHEN to take a `pw-dump` belongs to the state module, not to a view. This
// effect used to live inside the `AudioPopup` component, and that was a real
// defect rather than a style choice: gnim warns "effects created outside a
// `createRoot` will never be disposed", and measured behaviour matched — the
// effect ran ONCE at bar start and never again, so the snapshot was whatever the
// graph looked like before the first app had played, and stayed that way until
// the popup happened to open (which is why `open()` calling `refreshStreamTargets`
// had been carrying this feature on its back). Symptom: a live stream reported
// with NO app identity (`appKeys: []`), so its row could not bind to it.
//
// The trigger is the node ID SET, not the counts. Counts were strictly worse: an
// app that re-links its stream (Firefox does this on every seek and every ad
// transition, measured) keeps the count identical while replacing the node, so a
// count-gated effect missed the change that mattered, and a count that flapped
// instead re-snapshotted for nothing.
//
// Refreshing while the popup is CLOSED is deliberate only until the first
// snapshot exists: a stream's app identity lives nowhere else (AstalWp exposes no
// `application.name`, and `node.description` is null for Firefox), so without it
// the rest of the surface — and `ags request audio-debug` — cannot name any
// stream. After that, the popup's visibility is the gate, as before.
let lastGraphSignature: string | null = null

createEffect(() => {
  const signature = [
    ...(playbackStreams() ?? []).map((s) => `p${nodeOf(s)?.id ?? "?"}`),
    ...(recordingStreams() ?? []).map((s) => `r${nodeOf(s)?.id ?? "?"}`),
    ...(outputDevices() ?? []).map((s) => `o${nodeOf(s)?.id ?? "?"}`),
    `d${nodeOf(defaultSpeaker())?.id ?? "?"}`,
  ].join(",")
  if (!popupVisible() && hasGraphSnapshot()) return
  if (signature === lastGraphSignature) return
  lastGraphSignature = signature
  void refreshStreamTargets()
})

/** Toggle the popup (or jump straight to a section). */
export function toggle(section: AudioSection = "main") {
  if (popupVisible()) close()
  else open(section)
}

/** Enter the Output device subview (settings-panel in-place navigation). */
export function showOutputDevices() {
  setActiveSection("output-devices")
  setViewEpoch((n) => n + 1)
}

/** Enter the Input device subview — symmetric to outputs (decision 1B
 *  extended to inputs): list live sources, check the default microphone. */
export function showInputDevices() {
  setActiveSection("input-devices")
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
  //: The players the Output card's transport acts on, plus the service's own
  //: recency stamp — which ranks the REPRESENTATIVE interface when two of one
  //: app's interfaces share a PID (an Electron app publishes both a named
  //: interface and a framework mirror). `lastPlayingAt: 0` on a Playing player
  //: is the honest "we never saw it start" marker, and is what stops a
  //: re-registered bus name from claiming to be the newest playback of all.
  const players = playersByApp().map((p) => ({
    busName: p.busName,
    identity: p.identity,
    appKeys: p.appKeys,
    pid: p.pid,
    status: p.status,
    lastPlayingAt: Math.round(p.lastPlayingAt),
    title: p.metadata.title,
  }))
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
  const inputs = (inputDevices() ?? []).map((d) => {
    const n = nodeOf(d)
    return {
      id: n?.id ?? null,
      name: n?.description || n?.name || null,
      active: mic !== null && n?.id !== undefined && mic.id === n.id,
    }
  })
  return {
    players,
    //: The Output card's transport blast radius, as the bar sees it: the apps
    //: whose routing chip names the SELECTED output.
    defaultSinkPlayers: defaultSinkPlayers().map((p) => ({
      identity: p.identity,
      appKeys: p.appKeys,
      status: p.status,
    })),
    streams,
    rows,
    inputs,
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
    //: Called, not referenced: the bare accessor is a function and would be
    //: dropped by the JSON this dump is serialised into.
    defaultEndpointEpoch: defaultEndpointEpoch(),
    //: A position the panel is holding because the app has not reported a
    //: plausible one — the diagnostic for "the thumb jumped back to the start".
    heldPositions: heldPositionsSnapshot(),
    snapshot: { ...snapshotStats },
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

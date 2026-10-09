import {
  canonicalAppKey,
  UnknownRoute,
  volumeState,
  type AppIdentity,
  type AudioSession,
  type AudioStream,
  type EndpointId,
} from "../../domain/audio-model.ts"

type RawNode = {
  id?: number
  name?: string | null
  description?: string | null
  icon?: string | null
  volume?: number
  mute?: boolean
  "media-class"?: number
  target_endpoint?: RawNode | null
}

type DumpObject = {
  id?: number
  type?: string
  info?: {
    props?: Record<string, unknown>
    state?: string
    [key: string]: unknown
  }
}

export interface PipeWireGraph {
  /** Effective stream-node → connected endpoint-node links, as observed in the graph. */
  streamEndpoint: ReadonlyMap<number, number>
  /** PipeWire node IDs → labels, including sinks not represented by AstalWp. */
  nodeName: ReadonlyMap<number, string>
  /** PipeWire stream-node IDs → app/media identity properties. */
  streamProperties: ReadonlyMap<number, Readonly<Record<string, unknown>>>
  /** Stable PipeWire object serial, which distinguishes node-id reuse after unlink. */
  streamSerial: ReadonlyMap<number, string>
  /** PipeWire stream-node IDs → authoritative requested `target.object`, if set. */
  requestedTarget: ReadonlyMap<number, string>
  /**
   * WirePlumber's own `default.audio.sink` / `default.audio.source`, as node
   * NAMES. This is the authoritative default.
   *
   * AstalWp's `default_speaker` is NOT reliable for it: it returns null when
   * the default is a Bluetooth sink, because AstalWp does not enumerate
   * `bluez_output.*` nodes (measured 2026-10-07: WirePlumber reported
   * `default.audio.sink = bluez_output.94_4B_F8_4B_5B_16.1` while
   * `wp.default_speaker` was null). Reading only AstalWp therefore made
   * `preferredOutputId` null, so the panel could never display the headset as
   * the preferred output no matter how many times it was selected -- the
   * "I have to select it multiple times" report.
   */
  defaultSinkName: string | null
  defaultSourceName: string | null
  /**
   * PipeWire node id -> `node.name`, for every Node in the dump.
   *
   * Needed because WirePlumber's default metadata names the node by its
   * PipeWire `node.name` (e.g. `bluez_output.94_4B_F8_4B_5B_16.1`), while
   * AstalWp's wrapper exposes a different or absent `name` (its description is
   * the human label, "TOZO NC9"). Matching the metadata against AstalWp's name
   * therefore failed for Bluetooth sinks, the default fell back to AstalWp's
   * stale `default_speaker`, and the panel showed the previous device while
   * audio played through the new one.
   */
  pipewireNodeName: ReadonlyMap<number, string>
}

/**
 * Stream nodes that are not applications playing or capturing audio.
 *
 * `pavucontrol` opens one Stream/Input/Audio node per output device purely to
 * render its own level meters, all named "PulseAudio Volume Control". They are
 * genuine capture requests, so they exist in PipeWire, and projecting every
 * Stream/* node put them in the panel as mic consumers and as an app row --
 * including inside the pavucontrol window the user opened to check the panel,
 * which then listed itself.
 *
 * Monitor nodes (Stream/Input/Audio/Internal, e.g. a Bluetooth headset's
 * internal capture) are not consumers either: they are the device echoing
 * playback back. Screen-capture status stays on the dotfiles event hub and is
 * deliberately not inferred here.
 */
const NON_APPLICATION_BINARIES = new Set(["pavucontrol", "wpctl", "pw-cat"])

function isApplicationStream(props: Readonly<Record<string, unknown>>): boolean {
  const binary = text(props["application.process.binary"])
  return !(binary && NON_APPLICATION_BINARIES.has(binary))
}

const text = (value: unknown): string => typeof value === "string" ? value : ""
const number = (value: unknown): number | null => {
  const n = typeof value === "number" ? value : Number(value)
  return Number.isFinite(n) ? n : null
}
const id = (value: number | null | undefined): EndpointId | null =>
  value === null || value === undefined ? null : String(value)

/** Parse a point-in-time `pw-dump` JSON graph. This is deliberately pure. */
export function parsePipeWireGraph(json: string): PipeWireGraph {
  const dump = JSON.parse(json) as DumpObject[]
  const nodeName = new Map<number, string>()
  const pipewireNodeName = new Map<number, string>()
  const streamProperties = new Map<number, Readonly<Record<string, unknown>>>()
  const streamSerial = new Map<number, string>()
  const sinks = new Set<number>()
  const sources = new Set<number>()

  for (const object of dump) {
    if (typeof object.id !== "number" || object.type !== "PipeWire:Interface:Node") continue
    const props = object.info?.props ?? {}
    const name = text(props["node.description"]) || text(props["node.name"])
    if (name) nodeName.set(object.id, name)
    const wireName = text(props["node.name"])
    if (wireName) pipewireNodeName.set(object.id, wireName)
    const mediaClass = text(props["media.class"])
    if (mediaClass === "Audio/Sink") sinks.add(object.id)
    if (mediaClass === "Audio/Source") sources.add(object.id)
    if (mediaClass.startsWith("Stream/")) {
      streamProperties.set(object.id, props)
      const serial = props["object.serial"]
      if (typeof serial === "string" || typeof serial === "number") streamSerial.set(object.id, String(serial))
    }
  }

  // WirePlumber's default endpoints live in a Metadata object, not on a Node.
  // `value` is `{ name: "node.name" }` for both sink and source.
  let defaultSinkName: string | null = null
  let defaultSourceName: string | null = null
  for (const object of dump) {
    if (object.type !== "PipeWire:Interface:Metadata") continue
    const entries = (object as { metadata?: { key?: string; value?: unknown }[] }).metadata ?? []
    for (const entry of entries) {
      const value = entry.value as { name?: unknown } | undefined
      const name = value && typeof value.name === "string" ? value.name : null
      if (!name) continue
      if (entry.key === "default.audio.sink") defaultSinkName = name
      if (entry.key === "default.audio.source") defaultSourceName = name
    }
  }

  const streamEndpoint = new Map<number, number>()
  const requestedTarget = new Map<number, string>()
  for (const [streamId, props] of streamProperties) {
    const target = props["target.object"]
    if (typeof target === "string" && target.length > 0) requestedTarget.set(streamId, target)
    else if (typeof target === "number" && Number.isFinite(target)) requestedTarget.set(streamId, String(target))
  }
  for (const object of dump) {
    if (object.type !== "PipeWire:Interface:Link") continue
    const info = object.info ?? {}
    if (String(info.state ?? "").toLowerCase() !== "active") continue
    const props = info.props ?? {}
    // The live graph exposes dotted link properties. The older pw-dump shape
    // exposes these as info fields; accept both without guessing endpoint intent.
    const output = number(props["link.output.node"] ?? info["output-node-id"])
    const input = number(props["link.input.node"] ?? info["input-node-id"])
    if (output === null || input === null) continue
    if (sinks.has(input) && streamProperties.has(output)) streamEndpoint.set(output, input)
    else if (sources.has(output) && streamProperties.has(input)) streamEndpoint.set(input, output)
  }

  return { streamEndpoint, nodeName, pipewireNodeName, streamProperties, streamSerial, requestedTarget, defaultSinkName, defaultSourceName }
}

function endpoint(node: RawNode, available = true) {
  const nodeId = id(node.id)
  if (nodeId === null) return null
  return {
    id: nodeId,
    name: node.description || node.name || `Audio device ${nodeId}`,
    available,
    volume: volumeState(node.volume ?? 0, node.mute === true),
  }
}

/** Project AstalWp node wrappers and one graph snapshot into core values. */
export function projectPipeWireSession(input: {
  nodes: readonly RawNode[]
  defaultSpeakerId: number | null
  defaultMicrophoneId: number | null
  graph: PipeWireGraph
}): AudioSession {
  const outputs = input.nodes
    .filter((node) => node["media-class"] === 2)
    .map((node) => endpoint(node))
    .filter((item): item is NonNullable<typeof item> => item !== null)
  const inputs = input.nodes
    .filter((node) => node["media-class"] === 1)
    .map((node) => endpoint(node))
    .filter((item): item is NonNullable<typeof item> => item !== null)
  // Resolve WirePlumber's default node NAME to a node id, matching either the
  // PipeWire `node.name` or AstalWp's human description. Fall back to AstalWp's
  // `default_speaker` only when the metadata names nothing we can find -- which
  // is the case AstalWp handles, not the case it misses.
  const resolveDefault = (name: string | null, mediaClass: number): string | null => {
    if (!name) return null
    // Prefer PipeWire's own node.name: that is the identifier WirePlumber's
    // default metadata actually uses, and it is reliable for Bluetooth sinks
    // where AstalWp's name/description do not match it.
    const allowed = new Set(input.nodes
      .filter((node) => node["media-class"] === mediaClass && typeof node.id === "number")
      .map((node) => node.id as number))
    for (const [nodeId, wireName] of input.graph.pipewireNodeName) {
      if (wireName === name && allowed.has(nodeId)) return id(nodeId)
    }
    const match = input.nodes.find((node) =>
      node["media-class"] === mediaClass && (node.name === name || node.description === name))
    return match ? id(match.id) : null
  }

  const preferredOutputId =
    resolveDefault(input.graph.defaultSinkName, 2) ?? id(input.defaultSpeakerId)
  const microphoneId =
    resolveDefault(input.graph.defaultSourceName, 1) ?? id(input.defaultMicrophoneId)
  const inputEndpoint = inputs.find((item) => item.id === microphoneId) ?? null
  const appsById = new Map<string, AppIdentity>()
  const streams: AudioStream[] = []

  for (const node of input.nodes) {
    const direction = node["media-class"] === 4 ? "output" : node["media-class"] === 3 ? "input" : null
    if (direction === null || typeof node.id !== "number") continue
    const props = input.graph.streamProperties.get(node.id) ?? {}
    // Skip level-meter and monitor streams: not applications using audio.
    if (!isApplicationStream(props)) continue
    const processId = number(props["application.process.id"])
    const rawName = text(props["application.name"]) || text(props["application.process.binary"]) ||
      node.description || node.name || `Application ${node.id}`
    const appId = canonicalAppKey(rawName) || `pipewire-${node.id}`
    if (!appsById.has(appId)) {
      appsById.set(appId, {
        id: appId,
        displayName: text(props["application.name"]) || rawName,
        desktopId: text(props["application.desktop"]) || undefined,
        processId: processId ?? undefined,
        // Canonicalised, because `aliases[0]` is what the row uses to pick an
        // app icon and the icon registry keys apps by canonical name. Chrome's
        // process binary is the literal "chrome", while the registry ships
        // "google-chrome" -- so the row asked for an icon that does not exist,
        // fell through to the artwork, found none, and rendered the initial
        // letter "G" instead of the Chrome mark. Firefox was unaffected only
        // because its binary and its canonical name are the same string.
        aliases: [
          canonicalAppKey(text(props["application.process.binary"])),
          canonicalAppKey(text(props["application.icon-name"])),
        ].filter(Boolean),
      })
    }
    const target = node.target_endpoint?.id
    const requestedRaw = input.graph.requestedTarget.get(node.id)
    const requestedNumericId = requestedRaw && /^\d+$/.test(requestedRaw) ? Number(requestedRaw) : null
    const requestedByName = requestedRaw
      ? input.nodes.find((candidate) => candidate.name === requestedRaw || candidate.description === requestedRaw)?.id ?? null
      : null
    const requestedEndpointId = id(requestedNumericId ?? requestedByName ?? target ?? null)
    const endpointId = id(input.graph.streamEndpoint.get(node.id) ?? target ?? null)
    streams.push({
      id: `pipewire:${node.id}:${input.graph.streamSerial.get(node.id) ?? node.id}`,
      appId,
      direction,
      endpointId,
      requestedEndpointId,
      // The adapter observes effective links and requested targets; neither can
      // reconstruct whether an already-live stream followed a previous default.
      // Route-intent reconciliation owns that history and will refine this value.
      routeIntent: UnknownRoute,
      volume: volumeState(node.volume ?? 0, node.mute === true),
      current: true,
    })
  }

  return {
    preferredOutputId,
    preferredInputId: microphoneId,
    outputs,
    inputs,
    input: inputEndpoint,
    apps: [...appsById.values()],
    streams,
    // MPRIS owns players and joins them by app identity in presentation.
    players: [],
    // App-scoped route intent is runtime state, not something the graph can
    // observe. The runtime fills this in; the adapter reports it empty.
    appIntents: {},
    appVolumes: {},
    appLastIntents: {},
    appEndpoints: {},
  }
}

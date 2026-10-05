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
  const streamProperties = new Map<number, Readonly<Record<string, unknown>>>()
  const streamSerial = new Map<number, string>()
  const sinks = new Set<number>()
  const sources = new Set<number>()

  for (const object of dump) {
    if (typeof object.id !== "number" || object.type !== "PipeWire:Interface:Node") continue
    const props = object.info?.props ?? {}
    const name = text(props["node.description"]) || text(props["node.name"])
    if (name) nodeName.set(object.id, name)
    const mediaClass = text(props["media.class"])
    if (mediaClass === "Audio/Sink") sinks.add(object.id)
    if (mediaClass === "Audio/Source") sources.add(object.id)
    if (mediaClass.startsWith("Stream/")) {
      streamProperties.set(object.id, props)
      const serial = props["object.serial"]
      if (typeof serial === "string" || typeof serial === "number") streamSerial.set(object.id, String(serial))
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

  return { streamEndpoint, nodeName, streamProperties, streamSerial, requestedTarget }
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
  const preferredOutputId = id(input.defaultSpeakerId)
  const microphoneId = id(input.defaultMicrophoneId)
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
        aliases: [text(props["application.process.binary"]), text(props["application.icon-name"])].filter(Boolean),
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
  }
}

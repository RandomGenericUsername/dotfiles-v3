import Wp from "gi://AstalWp?version=0.1"
import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import { execAsync } from "ags/process"
import type { AudioSession } from "../../domain/audio-model.ts"
import type {
  PipeWireObservation,
  PipeWireObservationPort,
  Unsubscribe,
} from "../../application/ports.ts"
import { parsePipeWireGraph, projectPipeWireSession } from "./project-pipewire-session.ts"

type WpNode = {
  id?: number
  name?: string | null
  description?: string | null
  volume?: number
  mute?: boolean
  "media-class"?: number
  target_endpoint?: WpNode | null
}
type WpEndpoint = { id?: number }
type WpService = {
  nodes?: WpNode[]
  default_speaker?: WpEndpoint | null
  default_microphone?: WpEndpoint | null
  connect(signal: string, callback: () => void): number
  disconnect(handler: number): void
}

async function readSession(wp: WpService | null): Promise<AudioSession> {
  const dump = await execAsync(["pw-dump"])
  const graph = parsePipeWireGraph(dump as unknown as string)
  const nodes = wp?.nodes ?? []
  return projectPipeWireSession({
    nodes,
    defaultSpeakerId: wp?.default_speaker?.id ?? null,
    defaultMicrophoneId: wp?.default_microphone?.id ?? null,
    graph,
  })
}

/**
 * Event-fed AstalWp + PipeWire graph observation.
 *
 * AstalWp's supported `wp.nodes` collection supplies endpoint/stream controls;
 * a `pw-dump --monitor` process supplies graph and default-metadata change
 * events. Each event triggers a fresh, one-shot `pw-dump` hydration so links,
 * target properties, and node identity are interpreted from one coherent graph.
 */
export class PipeWireObservationAdapter implements PipeWireObservationPort {
  private readonly listeners = new Set<(event: PipeWireObservation) => void>()
  private nodeHandler: number | null = null
  private monitor: Gio.Subprocess | null = null
  private monitorReader: Gio.DataInputStream | null = null
  private refreshInFlight = false
  private refreshQueued = false
  private refreshSource = 0
  private lastSnapshot: AudioSession | null = null

  constructor(private readonly wp: WpService | null = Wp.get_default() as unknown as WpService | null) {}

  async hydrate(): Promise<PipeWireObservation> {
    const session = await readSession(this.wp)
    this.lastSnapshot = session
    return { kind: "snapshot", session }
  }

  subscribe(listener: (event: PipeWireObservation) => void): Unsubscribe {
    this.listeners.add(listener)
    if (this.listeners.size === 1) this.start()
    return () => {
      this.listeners.delete(listener)
      if (!this.listeners.size) this.stop()
    }
  }

  private start(): void {
    if (this.wp) this.nodeHandler = this.wp.connect("notify::nodes", () => this.scheduleRefresh())
    try {
      this.monitor = Gio.Subprocess.new(
        ["pw-dump", "--monitor"],
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE,
      )
      const stdout = this.monitor.get_stdout_pipe()
      if (!stdout) throw new Error("pw-dump --monitor exposed no stdout pipe")
      this.monitorReader = Gio.DataInputStream.new(stdout)
      this.readMonitorLine()
    } catch (error) {
      console.error("audio PipeWire monitor could not start:", error)
    }
  }

  private readMonitorLine(): void {
    const reader = this.monitorReader
    if (!reader || !this.listeners.size) return
    // Gio.PRIORITY_DEFAULT does not exist; the io_priority constants live on
    // GLib. Reading it off Gio yields undefined at the call site.
    reader.read_line_async(GLib.PRIORITY_DEFAULT, null, (source, result) => {
      try {
        if (!source) throw new Error("read_line_async delivered no source object")
        const [line] = source.read_line_finish_utf8(result)
        if (line === null) {
          this.monitorReader = null
          return
        }
        // The monitor stream is the event trigger only. Hydration parses one
        // complete snapshot rather than trying to merge partial JSON deltas.
        if (line.trim()) this.scheduleRefresh()
        this.readMonitorLine()
      } catch (error) {
        this.monitorReader = null
        if (this.listeners.size) console.error("audio PipeWire monitor read failed:", error)
      }
    })
  }

  private scheduleRefresh(): void {
    // A monitor event can describe one PipeWire object across several lines,
    // and `wp.nodes` can notify for a burst of related graph changes. This is
    // an event-triggered debounce, not a repeating state poll.
    if (this.refreshSource) return
    this.refreshSource = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 40, () => {
      this.refreshSource = 0
      this.refreshSnapshot()
      return GLib.SOURCE_REMOVE
    })
  }

  private refreshSnapshot(): void {
    if (this.refreshInFlight) {
      this.refreshQueued = true
      return
    }
    this.refreshInFlight = true
    void readSession(this.wp).then((session) => {
      // PipeWire notifications can be chatty. Suppress identical snapshots so
      // consumers keep stable row identity during unrelated graph changes.
      if (!sameSession(this.lastSnapshot, session)) {
        this.lastSnapshot = session
        this.listeners.forEach((listener) => listener({ kind: "snapshot", session }))
      }
    }).catch((error) => {
      console.error("audio PipeWire snapshot failed:", error)
    }).finally(() => {
      this.refreshInFlight = false
      if (this.refreshQueued) {
        this.refreshQueued = false
        this.refreshSnapshot()
      }
    })
  }

  private stop(): void {
    if (this.nodeHandler !== null && this.wp) this.wp.disconnect(this.nodeHandler)
    this.nodeHandler = null
    this.monitorReader?.close(null)
    this.monitorReader = null
    this.monitor?.force_exit()
    this.monitor = null
    if (this.refreshSource) GLib.source_remove(this.refreshSource)
    this.refreshSource = 0
    this.refreshQueued = false
  }
}

function sameSession(a: AudioSession | null, b: AudioSession): boolean {
  if (!a) return false
  // Compare value projections, not AstalWp wrapper identity. Players are owned
  // by MPRIS and intentionally absent from this adapter's snapshot.
  return JSON.stringify({ ...a, players: [] }) === JSON.stringify({ ...b, players: [] })
}

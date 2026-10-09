import Wp from "gi://AstalWp?version=0.1"
import { execAsync } from "ags/process"
import type { EndpointId, VolumeState } from "../../domain/audio-model.ts"
import type { PipeWirePort } from "../../application/ports.ts"

type WpNode = {
  id?: number
  volume?: number
  mute?: boolean
  "media-class"?: number
  target_endpoint?: WpNode | null
}
type WpService = { nodes?: WpNode[] }
type Run = (argv: string[]) => Promise<unknown>

function numericId(id: EndpointId): number {
  const value = Number(id)
  if (!Number.isSafeInteger(value) || value < 0) throw new Error(`Invalid PipeWire node id: ${id}`)
  return value
}

function streamNodeId(streamId: string): string {
  const raw = streamId.startsWith("pipewire:") ? streamId.slice("pipewire:".length).split(":", 1)[0] : streamId
  return raw
}

function findNode(wp: WpService, id: EndpointId, mediaClass?: number): WpNode {
  const nodeId = numericId(id)
  const node = (wp.nodes ?? []).find((candidate) => candidate.id === nodeId)
  if (!node || (mediaClass !== undefined && node["media-class"] !== mediaClass))
    throw new Error(`PipeWire node ${nodeId} is no longer available`)
  return node
}

function applyVolume(node: WpNode, volume: VolumeState): void {
  // AstalWp's gain and mute are independent writable properties. Keep the
  // requested normalized gain when muted so unmute restores the prior level.
  node.volume = Math.max(0, Math.min(1, volume.level))
  node.mute = volume.muted
}

/** Concrete PipeWire write port; it performs no UI projection or policy. */
export function createPipeWireCommands(
  wp: WpService | null = Wp.get_default() as unknown as WpService | null,
  run: Run = (argv) => execAsync(argv),
): PipeWirePort {
  const requiredWp = (): WpService => {
    if (!wp) throw new Error("AstalWp is unavailable")
    return wp
  }
  return {
    async setPreferredOutput(endpointId) {
      const nodeId = numericId(endpointId)
      findNode(requiredWp(), endpointId, 2)
      await run(["wpctl", "set-default", String(nodeId)])
    },
    async setStreamTarget(streamId, endpointId) {
      const rawStreamId = streamNodeId(streamId)
      const streamNode = findNode(requiredWp(), rawStreamId, 4)
      if (endpointId === null) {
        streamNode.target_endpoint = null
        return
      }
      const output = findNode(requiredWp(), endpointId, 2)
      streamNode.target_endpoint = output
    },
    async setPreferredInput(endpointId) {
      const nodeId = numericId(endpointId)
      findNode(requiredWp(), endpointId, 1)
      await run(["wpctl", "set-default", String(nodeId)])
    },
    async setStreamVolume(streamId, volume) {
      const rawStreamId = streamNodeId(streamId)
      applyVolume(findNode(requiredWp(), rawStreamId, 4), volume)
    },
    async setOutputVolume(endpointId, volume) {
      applyVolume(findNode(requiredWp(), endpointId, 2), volume)
    },
    async setInputVolume(endpointId, volume) {
      applyVolume(findNode(requiredWp(), endpointId, 1), volume)
    },
  }
}

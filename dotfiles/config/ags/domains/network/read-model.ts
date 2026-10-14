import type { ReadAccessor, ReactiveRuntime } from "../reactive"
import type { NetworkReading, WifiReading, WiredReading } from "../../lib/network-icon.ts"

/**
 * The network domain's read model: an AstalNetwork-shaped service → a reactive
 * `NetworkReading`. PURE — no `ags`, no `gi://*` (spine AD-2/AD-3).
 *
 * WHY THIS EXISTS (bar re-architecture §5.3). The descriptor prototype read the
 * device through `createBinding(network, "wifi")`, which fires when the *device
 * object* changes — a hotplug, or the radio toggling — but NOT when the device's
 * own `strength`/`state`/`enabled` properties change. So the bar icon froze at
 * its first reading. Subscribing to the system is the DOMAIN ADAPTER's job (the
 * analogue of `audio/adapters/pipewire/pipewire-observation.ts`); the widget's
 * read model is only as reactive as the adapter behind it.
 *
 * This factory owns exactly that subscription. It rebuilds the device-level
 * handlers whenever the service hands it a different Wi-Fi device, and
 * republishes a plain, inert reading. The widget never touches Astal.
 *
 * The types are structural (no GJS type import) and BOTH the service and the
 * reactive primitive are parameters, so the read model is a seam, not a hard
 * singleton — the Astal binding lives in `./astal.ts` and the tests drive this
 * file with a fake device and a fake runtime.
 */

/** The AstalNetwork properties this adapter reads, as a structural shape. */
export interface NetworkService {
  wifi: WifiDevice | null
  wired: WiredDevice | null
  connectivity: number
  connect(signal: string, callback: () => void): number
  disconnect(handler: number): void
}

export interface WifiDevice {
  enabled?: boolean
  state?: number
  strength: number
  connect(signal: string, callback: () => void): number
  disconnect(handler: number): void
}

export interface WiredDevice {
  state?: number
  connect(signal: string, callback: () => void): number
  disconnect(handler: number): void
}

/** The device properties whose changes move the network glyph. */
const WIFI_NOTIFY_PROPERTIES = ["strength", "state", "enabled"] as const

function snapshot(network: NetworkService): NetworkReading {
  const wifi = network.wifi
  const wired = network.wired
  const wifiReading: WifiReading | null = wifi
    ? { enabled: wifi.enabled, state: wifi.state, strength: wifi.strength }
    : null
  const wiredReading: WiredReading | null = wired ? { state: wired.state } : null
  return {
    wifi: wifiReading,
    wired: wiredReading,
    connectivity: network.connectivity,
  }
}

/**
 * Observe a network service as a reactive `NetworkReading`.
 *
 * Returns an accessor, so a `createComputed` that calls it re-runs whenever any
 * watched property moves — the reactivity the descriptor relies on.
 */
export function createNetworkReadModel(
  network: NetworkService,
  runtime: ReactiveRuntime,
): ReadAccessor<NetworkReading> {
  const [reading, setReading] = runtime.createState<NetworkReading>(snapshot(network))

  // The Wi-Fi device is replaced on hotplug/radio toggle; the handlers bound to
  // the old object would go silent, so they are torn down and re-bound.
  let boundWifi: WifiDevice | null = null
  let wifiHandlers: number[] = []

  const refresh = (): void => setReading(snapshot(network))

  const bindWifi = (): void => {
    const wifi = network.wifi
    if (wifi === boundWifi) return
    for (const id of wifiHandlers) boundWifi?.disconnect(id)
    wifiHandlers = []
    boundWifi = wifi
    if (wifi) {
      for (const prop of WIFI_NOTIFY_PROPERTIES) {
        wifiHandlers.push(wifi.connect(`notify::${prop}`, refresh))
      }
    }
    refresh()
  }

  network.connect("notify::wifi", bindWifi)
  network.connect("notify::wired", refresh)
  network.connect("notify::connectivity", refresh)
  bindWifi()

  return reading
}

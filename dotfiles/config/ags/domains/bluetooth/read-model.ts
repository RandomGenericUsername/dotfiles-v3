import type { ReadAccessor, ReactiveRuntime } from "ags-platform/ports/reactive"

/**
 * The Bluetooth domain's read model: the BlueZ-backed service's public
 * accessors → a reactive `BluetoothReading`. PURE — no `ags`, no `gi://*`
 * (spine AD-2/AD-3).
 *
 * WHY THIS EXISTS. `services/bluetooth-service.ts` already owns the D-Bus
 * source of truth and publishes reactive accessors, but a widget reaches into
 * those accessors one by one, so "what the Bluetooth domain currently is" is
 * never a single value. This read model gathers them into one inert reading and
 * republishes on any change, giving every Bluetooth surface one thing to
 * consume — the same shape the network read model established.
 *
 * The service's BlueZ logic is deliberately NOT touched: this wraps its public
 * accessors, it does not re-implement pairing, discovery, or RSSI ageing.
 */

/**
 * One device, structurally matching `services/bluetooth-service.ts`'s
 * `BluetoothDevice`. Declared here so the pure core imports no runtime module.
 */
export interface BluetoothDeviceReading {
  path: string
  address: string
  alias: string
  name: string
  connected: boolean
  paired: boolean
  trusted: boolean
  rssi: number
  /** Monotonic ms of the last time BlueZ said something about this device. */
  lastHeardAt: number
  icon: string
  adapter: string
  /** BlueZ Battery1 percentage, or 0 when the device exposes none. */
  battery: number
}

/** The action currently in flight, if any. */
export interface BluetoothBusyReading {
  address: string | null
  action: string | null
}

/** The inert Bluetooth reading a surface consumes. */
export interface BluetoothReading {
  powered: boolean
  discovering: boolean
  /** True once an `Adapter1` object exists on the bus. */
  ready: boolean
  /** The local controller's hardware address, or "" before it is read. */
  adapterAddress: string
  devices: readonly BluetoothDeviceReading[]
  busy: BluetoothBusyReading
  /** Where audio was last proven routed, or null. */
  audioTarget: string | null
}

/**
 * The read-model source: the service's public accessors plus one subscription
 * that fires when any of them changes.
 */
export interface BluetoothSource {
  powered(): boolean
  discovering(): boolean
  ready(): boolean
  adapterAddress(): string
  devices(): readonly BluetoothDeviceReading[]
  busy(): BluetoothBusyReading
  audioTarget(): string | null
  subscribe(listener: () => void): () => void
}

/** A plain snapshot of the source, so the reading is inert (AD-3). */
export function snapshot(source: BluetoothSource): BluetoothReading {
  return {
    powered: source.powered(),
    discovering: source.discovering(),
    ready: source.ready(),
    adapterAddress: source.adapterAddress(),
    devices: source.devices(),
    busy: source.busy(),
    audioTarget: source.audioTarget(),
  }
}

/**
 * Observe a Bluetooth source as a reactive `BluetoothReading`.
 *
 * A source change republishes a fresh snapshot, so a `createComputed` that
 * calls the accessor re-runs on any Bluetooth change.
 */
export function createBluetoothReadModel(
  source: BluetoothSource,
  runtime: ReactiveRuntime,
): ReadAccessor<BluetoothReading> {
  const [reading, setReading] = runtime.createState<BluetoothReading>(snapshot(source))
  source.subscribe(() => setReading(snapshot(source)))
  return reading
}

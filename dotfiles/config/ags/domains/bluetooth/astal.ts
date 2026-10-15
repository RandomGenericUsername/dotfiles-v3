import { agsRuntime } from "../../platform/adapters/astal"
import type { ReadAccessor } from "../../platform/ports/reactive"
import {
  bluetoothAdapterAddress,
  bluetoothAudioTarget,
  bluetoothBusy,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothPowered,
  bluetoothReady,
} from "../../services/bluetooth-service"
import {
  createBluetoothReadModel as createReadModel,
  type BluetoothReading,
  type BluetoothSource,
} from "./read-model"

/**
 * The Bluetooth read model's binding to `services/bluetooth-service.ts`
 * (spine AD-2).
 *
 * The service is the BlueZ source of truth and owns the D-Bus logic; this
 * adapter only gathers its public accessors into the read model's source and
 * subscribes to all of them as one change signal. Closing over the service here
 * keeps it out of `BarContext`.
 */
export function createBluetoothReadModel(): ReadAccessor<BluetoothReading> {
  // The heterogeneous accessors share only the subscription shape; naming it
  // here keeps the `.map` below well-typed without reaching for `any`.
  const accessors: ReadonlyArray<{ subscribe(callback: () => void): () => void }> = [
    bluetoothPowered,
    bluetoothDiscovering,
    bluetoothReady,
    bluetoothAdapterAddress,
    bluetoothDevices,
    bluetoothBusy,
    bluetoothAudioTarget,
  ]

  const source: BluetoothSource = {
    powered: () => bluetoothPowered(),
    discovering: () => bluetoothDiscovering(),
    ready: () => bluetoothReady(),
    adapterAddress: () => bluetoothAdapterAddress(),
    devices: () => bluetoothDevices(),
    busy: () => bluetoothBusy(),
    audioTarget: () => bluetoothAudioTarget(),
    subscribe: (listener) => {
      const offs = accessors.map((accessor) => accessor.subscribe(listener))
      return () => {
        for (const off of offs) off()
      }
    },
  }

  return createReadModel(source, agsRuntime)
}

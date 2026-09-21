import { createComputed, For } from "ags"
import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { CapabilityTile, IconToggle } from "../primitives"
import {
  bluetoothBusy,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothFailure,
  bluetoothPowered,
  connectDevice,
  disconnectDevice,
  pairDevice,
  routeAudioToDevice,
  startBluetoothDiscovery,
  stopBluetoothDiscovery,
  toggleBluetooth,
  unpairDevice,
  type BluetoothDevice,
} from "../services/bluetooth-service"
import { show } from "../state"

/**
 * Bluetooth control (thin view over `services/bluetooth-service`).
 *
 * State is owned by BlueZ D-Bus and exposed through the service's accessors;
 * this file only reads them and forwards user intent (`pairDevice`,
 * `connectDevice`, `disconnectDevice`, `unpairDevice`, `toggleBluetooth`).
 * There is no subprocess, no bus call, no agent plumbing and no timer here.
 */

export {
  bluetoothBusy,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothFailure,
  bluetoothPowered,
  routeAudioToDevice,
  startBluetoothDiscovery,
  stopBluetoothDiscovery,
  toggleBluetooth,
}
export type { BluetoothDevice }

export function bluetoothIconOn(): string | null {
  return registry.resolve("settings-panel", "bluetooth")
}

export function bluetoothIconOff(): string | null {
  return registry.resolve("settings-panel", "bluetooth-off")
}

/** Header/standalone power toggle for the Bluetooth subview. */
export function BluetoothToggle() {
  return (
    <IconToggle
      iconOn={bluetoothIconOn()}
      iconOff={bluetoothIconOff()}
      active={bluetoothPowered}
      onClicked={toggleBluetooth}
      tooltip="Toggle Bluetooth"
      size={22}
    />
  )
}

export function BluetoothTile() {
  return (
    <CapabilityTile
      iconOn={bluetoothIconOn()}
      iconOff={bluetoothIconOff()}
      title="Bluetooth"
      subtitle={createComputed(() => {
        if (!bluetoothPowered()) return "Off"
        const connected = bluetoothDevices().find((device) => device.connected)
        return connected?.name || connected?.alias || "Not connected"
      })}
      active={bluetoothPowered}
      onToggle={toggleBluetooth}
      onOpen={() => show("bluetooth")}
      toggleTooltip="Toggle Bluetooth"
    />
  )
}

function BluetoothRow({ device: item }: { device: BluetoothDevice }) {
  // The service re-emits the list and a row widget may be reused for the same
  // address; read the live entry so status/battery stay correct.
  const live = createComputed(
    () =>
      bluetoothDevices().find((device) => device.address === item.address) ??
      item,
  )

  const name = createComputed(
    () => live().alias || live().name || "Unknown device",
  )
  const connected = createComputed(() => live().connected)
  const paired = createComputed(() => live().paired)
  const rssi = createComputed(() => live().rssi)
  const battery = createComputed(() => live().battery)

  const busy = createComputed(() => {
    const pending = bluetoothBusy()
    return pending.address === item.address && pending.action !== null
  })
  const anyBusy = createComputed(() => bluetoothBusy().address !== null)

  // BlueZ reports RSSI 0 when the device has not been seen (asleep / out of
  // range); a negative value means it is currently present. A paired device
  // that is not present is shown dimmed with Connect disabled.
  const inRange = createComputed(() => connected() || rssi() < 0)
  const absent = createComputed(() => paired() && !connected() && !inRange())
  const rowClass = createComputed(() =>
    absent() ? "settings-net out-of-range" : "settings-net",
  )

  function act() {
    if (busy() || !inRange()) return
    if (connected()) disconnectDevice(item.address)
    else if (paired()) connectDevice(item.address)
    else pairDevice(item.address)
  }

  function unpair() {
    if (anyBusy()) return
    unpairDevice(item.address)
  }

  return (
    <box class={rowClass} spacing={10}>
      <box orientation={1} hexpand>
        <label class="settings-net-name" xalign={0} label={name} />
        <label
          class="settings-net-sub"
          xalign={0}
          label={createComputed(() => {
            if (absent()) return "Not in range"
            const status = connected()
              ? "Connected"
              : paired()
                ? "Paired"
                : "Available"
            const level = battery()
            return connected() && level > 0 ? `${status} · ${level}%` : status
          })}
        />
      </box>
      <label class="settings-badge conn" label="Connected" visible={connected} />
      <Gtk.Spinner class="settings-spinner" visible={busy} spinning={busy} />
      <button
        class="settings-rowact"
        onClicked={act}
        canFocus={false}
        visible={createComputed(() => !busy())}
        sensitive={createComputed(() => inRange() && !anyBusy())}
      >
        <label
          label={createComputed(() =>
            connected() ? "Disconnect" : paired() ? "Connect" : "Pair",
          )}
        />
      </button>
      <button
        class="settings-rowact subtle"
        onClicked={unpair}
        canFocus={false}
        visible={createComputed(() => paired() && !anyBusy())}
      >
        <label label="Unpair" />
      </button>
    </box>
  )
}

export function BluetoothDeviceList() {
  return (
    <box orientation={1} spacing={4}>
      <For
        each={bluetoothDevices}
        id={(device: BluetoothDevice) => device.address}
      >
        {(device: BluetoothDevice) => <BluetoothRow device={device} />}
      </For>
    </box>
  )
}

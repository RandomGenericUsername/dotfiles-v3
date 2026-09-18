import Bluetooth from "gi://AstalBluetooth?version=0.1"
import { Accessor, createBinding, createComputed, For } from "ags"
import { registry } from "../../lib/icon-registry"
import { CapabilityTile, IconToggle } from "../primitives"
import { show } from "../state"

/**
 * Bluetooth control.
 *
 * AstalBluetooth (require 0.1) exposes a writable power toggle on the adapter
 * (`adapter.powered`); there is no `Bluetooth.powered`. Device connect /
 * disconnect / pair use the AstalBluetooth device methods.
 *
 * Version pinning uses the ESM equivalent `gi://AstalBluetooth?version=0.1`:
 * gjs ESM has no global `require_version`.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
type AnyDevice = any

const bluetooth = Bluetooth.get_default()
const devices: Accessor<AnyDevice[]> = bluetooth
  ? createBinding(bluetooth, "devices")
  : createComputed(() => [])
const adapterPowered: Accessor<boolean | null> = bluetooth
  ? createBinding(bluetooth, "adapter", "powered")
  : createComputed(() => false)

const powered = createComputed(() => adapterPowered() === true)

const sortedDevices = createComputed<AnyDevice[]>(() => {
  const score = (d: AnyDevice) => (d.connected ? 3 : d.paired ? 2 : 1)
  return [...(devices() ?? [])].sort(
    (a: AnyDevice, b: AnyDevice) => score(b) - score(a),
  )
})

export { sortedDevices as bluetoothDevices, powered as bluetoothPowered }

export function bluetoothIconOn(): string | null {
  return registry.resolve("settings-panel", "bluetooth")
}

export function bluetoothIconOff(): string | null {
  return registry.resolve("settings-panel", "bluetooth-off")
}

export function toggleBluetooth() {
  if (!bluetooth) return
  const adapter = bluetooth.adapter
  if (adapter) adapter.powered = !adapter.powered
}

function deviceConnect(device: AnyDevice) {
  try {
    device.connect_device((_src: unknown, res: unknown) => {
      try {
        device.connect_device_finish(res)
      } catch {
        /* short-lived; state is reflected reactively by AstalBluetooth */
      }
    })
  } catch {
    /* device may be mid-transition */
  }
}

function deviceDisconnect(device: AnyDevice) {
  try {
    device.disconnect_device((_src: unknown, res: unknown) => {
      try {
        device.disconnect_device_finish(res)
      } catch {
        /* ignore */
      }
    })
  } catch {
    /* ignore */
  }
}

function devicePair(device: AnyDevice) {
  try {
    device.pair()
  } catch {
    /* ignore */
  }
}

/** Header/standalone power toggle for the Bluetooth subview. */
export function BluetoothToggle() {
  return (
    <IconToggle
      iconOn={bluetoothIconOn()}
      iconOff={bluetoothIconOff()}
      active={powered}
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
        if (!bluetooth) return "Unavailable"
        if (!powered()) return "Off"
        const connected = (devices() ?? []).find((d: AnyDevice) => d.connected)
        return connected?.name || connected?.alias || "Not connected"
      })}
      active={powered}
      onToggle={toggleBluetooth}
      onOpen={() => show("bluetooth")}
      toggleTooltip="Toggle Bluetooth"
    />
  )
}

function BluetoothRow({ device }: { device: AnyDevice }) {
  const name = createBinding(device, "name")
  const alias = createBinding(device, "alias")
  const connected = createBinding(device, "connected")
  const paired = createBinding(device, "paired")
  const battery = createBinding(device, "battery-percentage")

  function act() {
    if (connected()) deviceDisconnect(device)
    else if (paired()) deviceConnect(device)
    else devicePair(device)
  }

  return (
    <box class="settings-net" spacing={10}>
      <box orientation={1} hexpand>
        <label
          class="settings-net-name"
          xalign={0}
          label={createComputed(() => alias() || name() || "Unknown device")}
        />
        <label
          class="settings-net-sub"
          xalign={0}
          label={createComputed(() => {
            const status = connected()
              ? "Connected"
              : paired()
                ? "Paired"
                : "Available"
            const level = Number(battery() ?? 0)
            return connected() && level > 0 ? `${status} · ${level}%` : status
          })}
        />
      </box>
      <label class="settings-badge conn" label="Connected" visible={connected} />
      <button class="settings-rowact" onClicked={act} canFocus={false}>
        <label
          label={createComputed(() =>
            connected() ? "Disconnect" : paired() ? "Connect" : "Pair",
          )}
        />
      </button>
    </box>
  )
}

export function BluetoothDeviceList() {
  return (
    <box orientation={1} spacing={4}>
      <For each={sortedDevices} id={(device: AnyDevice) => device.address ?? device.name}>
        {(device: AnyDevice) => <BluetoothRow device={device} />}
      </For>
    </box>
  )
}

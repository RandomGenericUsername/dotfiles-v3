import { Accessor, createComputed, createEffect, For } from "ags"
import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { IconToggle } from "../primitives/IconToggle"
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
} from "../../services/bluetooth-service"

/**
 * Bluetooth capability body (design §4).
 *
 * State is owned by BlueZ D-Bus and exposed through the service's accessors;
 * this component only reads them and forwards user intent (`pairDevice`,
 * `connectDevice`, `disconnectDevice`, `unpairDevice`, `toggleBluetooth`).
 * There is no subprocess, no bus call, no agent plumbing and no timer here.
 */

export {
  bluetoothBusy,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothFailure,
  bluetoothPowered,
  toggleBluetooth,
}
export type { BluetoothDevice }

function bluetoothIconOn(): string | null {
  return registry.resolve("settings-panel", "bluetooth")
}

function bluetoothIconOff(): string | null {
  return registry.resolve("settings-panel", "bluetooth-off")
}

/** Header/standalone power toggle for the Bluetooth capability. */
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

export function BluetoothRow({ device: item }: { device: BluetoothDevice }) {
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

/** The embeddable body: off/failure/scanning states + the device list. */
export function BluetoothContent({ visible }: { visible: Accessor<boolean> }) {
  const hasDevices = createComputed(() => bluetoothDevices().length > 0)
  const showList = createComputed(() => bluetoothPowered() && hasDevices())

  // Discovery runs while this content is visible and the adapter is powered;
  // hiding it (or powering off) stops it so BlueZ does not scan forever.
  createEffect(() => {
    if (!visible()) return
    if (!bluetoothPowered()) return
    startBluetoothDiscovery()
    return () => stopBluetoothDiscovery()
  })

  // Devices that connected outside the panel (auto-connect) still need the
  // audio sink defaulted; routing is idempotent.
  createEffect(() => {
    if (!visible()) return
    if (!bluetoothPowered()) return
    for (const device of bluetoothDevices()) {
      if (device.connected) {
        void routeAudioToDevice(device.alias || device.name)
      }
    }
  })

  // Failure is derived from the service state — no manual message timer.
  const failure = createComputed(() => bluetoothFailure())

  return (
    <box orientation={1} spacing={8}>
      <label
        class="settings-empty"
        xalign={0}
        label="Bluetooth is off"
        visible={createComputed(() => !bluetoothPowered())}
      />

      <label
        class="settings-message"
        xalign={0}
        wrap
        maxWidthChars={34}
        label={failure}
        visible={createComputed(() => failure() !== "")}
      />

      <label
        class="settings-empty"
        xalign={0}
        label="Scanning…"
        visible={createComputed(
          () => bluetoothPowered() && bluetoothDiscovering() && !hasDevices(),
        )}
      />

      <label
        class="settings-empty"
        xalign={0}
        label="No devices found"
        visible={createComputed(
          () => bluetoothPowered() && !bluetoothDiscovering() && !hasDevices(),
        )}
      />

      <box orientation={1} spacing={4} visible={showList}>
        <BluetoothDeviceList />
      </box>
    </box>
  )
}

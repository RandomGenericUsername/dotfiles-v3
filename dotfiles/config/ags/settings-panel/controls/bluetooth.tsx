import Bluetooth from "gi://AstalBluetooth?version=0.1"
import Wp from "gi://AstalWp?version=0.1"
import GLib from "gi://GLib?version=2.0"
import { Gtk } from "ags/gtk4"
import { Accessor, createBinding, createComputed, createState, For } from "ags"
import { execAsync } from "ags/process"
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

const adapterDiscovering: Accessor<boolean | null> = bluetooth
  ? createBinding(bluetooth, "adapter", "discovering")
  : createComputed(() => false)
const discovering = createComputed(() => adapterDiscovering() === true)

// The device whose connect/pair/disconnect action is in flight (drives the row
// spinner so a press is visibly acknowledged — no repeated clicking).
const [pendingAddr, setPendingAddr] = createState<string | null>(null)

const wp = Wp.get_default()

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
      resolve()
      return false
    })
  })
}

/**
 * Route audio to a freshly connected Bluetooth device.
 *
 * BlueZ connecting alone does not make the headset the default PipeWire sink,
 * and active streams keep playing on the previous sink — so the headphones
 * look "Connected" but sound stays on the speakers. Poll for the device's
 * speaker endpoint (the audio profile lags the BlueZ connect by a few seconds),
 * make it the default, and move active streams onto it.
 */
export async function routeAudioToDevice(label: string) {
  if (!wp || !label) return
  for (let attempt = 0; attempt < 16; attempt++) {
    const endpoint = (wp.audio?.speakers ?? []).find((s: AnyDevice) => {
      const n = s.name ?? ""
      const d = s.description ?? ""
      return n === label || d === label || n.includes(label) || d.includes(label)
    })
    if (endpoint) {
      try {
        endpoint.is_default = true
      } catch {
        /* endpoint vanished */
      }
      for (const stream of wp.audio?.streams ?? []) {
        try {
          stream.target_endpoint = endpoint
        } catch {
          /* stream may be gone */
        }
      }
      return
    }
    await sleep(500)
  }
}

const sortedDevices = createComputed<AnyDevice[]>(() => {
  const score = (d: AnyDevice) => (d.connected ? 3 : d.paired ? 2 : 1)
  return [...(devices() ?? [])].sort(
    (a: AnyDevice, b: AnyDevice) => score(b) - score(a),
  )
})

export { sortedDevices as bluetoothDevices, powered as bluetoothPowered, discovering as bluetoothDiscovering }

/**
 * BlueZ only reports devices it already knows (paired/bonded, or previously
 * seen and cached). Nearby-but-unseen devices require an explicit
 * `StartDiscovery`; without it the list stays empty even when devices are in
 * range. The view starts discovery while open and powered, and stops it on
 * leave so we do not scan forever.
 */
export function startBluetoothDiscovery() {
  const adapter = bluetooth?.adapter
  if (!adapter || !adapter.powered) return
  try {
    adapter.start_discovery()
  } catch {
    /* already discovering, or a transient adapter state */
  }
}

export function stopBluetoothDiscovery() {
  const adapter = bluetooth?.adapter
  if (!adapter) return
  try {
    adapter.stop_discovery()
  } catch {
    /* not discovering */
  }
}

export function bluetoothIconOn(): string | null {
  return registry.resolve("settings-panel", "bluetooth")
}

export function bluetoothIconOff(): string | null {
  return registry.resolve("settings-panel", "bluetooth-off")
}

/**
 * Toggle adapter power.
 *
 * BlueZ cannot power the adapter ON while rfkill soft-blocks it (the HCI shows
 * `PowerState: off-blocked`) and the `powered` setter fails silently, so the
 * icon press looks like a no-op. When enabling, clear a soft block first (the
 * Fn-key / airplane-mode state) — `rfkill unblock` is a control action against
 * the provisioned stack, not setup.
 */
export function toggleBluetooth() {
  if (!bluetooth) return
  const adapter = bluetooth.adapter
  if (!adapter) return

  if (adapter.powered) {
    adapter.powered = false
    return
  }

  // Off → on: clear any soft block, then power on (BlueZ AutoEnable also
  // powers on once the block lifts).
  execAsync(["rfkill", "unblock", "bluetooth"])
    .catch(() => "")
    .finally(() => {
      adapter.powered = true
    })
}

function deviceKey(device: AnyDevice): string | null {
  return device.address ?? device.name ?? null
}

function deviceConnect(device: AnyDevice) {
  const key = deviceKey(device)
  const label = device.alias || device.name
  if (key) setPendingAddr(key)
  try {
    device.connect_device((_src: unknown, res: unknown) => {
      try {
        device.connect_device_finish(res)
      } catch {
        /* short-lived; state is reflected reactively by AstalBluetooth */
      }
      if (key && pendingAddr() === key) setPendingAddr(null)
      if (label) void routeAudioToDevice(label)
    })
  } catch {
    if (key && pendingAddr() === key) setPendingAddr(null)
  }
}

function deviceDisconnect(device: AnyDevice) {
  const key = deviceKey(device)
  if (key) setPendingAddr(key)
  try {
    device.disconnect_device((_src: unknown, res: unknown) => {
      try {
        device.disconnect_device_finish(res)
      } catch {
        /* ignore */
      }
      if (key && pendingAddr() === key) setPendingAddr(null)
    })
  } catch {
    if (key && pendingAddr() === key) setPendingAddr(null)
  }
}

function deviceUnpair(device: AnyDevice) {
  try {
    const adapter = bluetooth?.adapter
    if (adapter?.remove_device) adapter.remove_device(device)
  } catch {
    /* device may already be gone */
  }
}

/**
 * Pair, then trust + connect once BlueZ reports the device paired.
 *
 * Pairing needs an authentication agent on the bus; the session's headless
 * NoInputNoOutput agent (settings-panel/bluetooth-agent) supplies it. Without
 * an agent `pair()` fails and the row briefly flips then reverts to "Pair".
 */
function devicePair(device: AnyDevice) {
  const key = deviceKey(device)
  let pairedId = 0
  let timeoutId = 0

  if (key) setPendingAddr(key)

  const clearPending = () => {
    if (key && pendingAddr() === key) setPendingAddr(null)
  }

  const cleanup = () => {
    clearPending()
    try {
      if (pairedId && device.disconnect) device.disconnect(pairedId)
    } catch {
      /* ignore */
    }
    if (timeoutId) {
      try {
        GLib.source_remove(timeoutId)
      } catch {
        /* ignore */
      }
      timeoutId = 0
    }
  }

  const onPaired = () => {
    if (!device.paired) return
    try {
      if (pairedId && device.disconnect) device.disconnect(pairedId)
    } catch {
      /* ignore */
    }
    pairedId = 0
    try {
      device.trusted = true
    } catch {
      /* some devices refuse trust; connect still works */
    }
    // deviceConnect takes over the pending flag and routes audio on success.
    deviceConnect(device)
  }

  try {
    if (device.connect) pairedId = device.connect("notify::paired", onPaired)
    timeoutId = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 20000, () => {
      timeoutId = 0
      clearPending()
      try {
        if (pairedId && device.disconnect) device.disconnect(pairedId)
      } catch {
        /* ignore */
      }
      return false
    })
    device.pair()
  } catch {
    cleanup()
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
  const connecting = createBinding(device, "connecting")
  const battery = createBinding(device, "battery-percentage")
  const rssi = createBinding(device, "rssi")

  const key = deviceKey(device)
  const busy = createComputed(
    () => connecting() || (key != null && pendingAddr() === key),
  )
  const idle = createComputed(() => !busy())
  // BlueZ reports RSSI 0 when the device has not been seen (asleep / out of
  // range); a negative value means it is currently present. A paired device
  // that is not present is shown dimmed with Connect disabled.
  const inRange = createComputed(() => connected() || Number(rssi() ?? 0) < 0)
  const absent = createComputed(
    () => paired() && !connected() && !inRange(),
  )
  const rowClass = createComputed(() =>
    absent() ? "settings-net out-of-range" : "settings-net",
  )

  function act() {
    if (busy() || !inRange()) return
    if (connected()) deviceDisconnect(device)
    else if (paired()) deviceConnect(device)
    else devicePair(device)
  }

  function unpair() {
    if (busy()) return
    deviceUnpair(device)
  }

  return (
    <box class={rowClass} spacing={10}>
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
            if (absent()) return "Not in range"
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
      <Gtk.Spinner
        class="settings-spinner"
        visible={busy}
        spinning={busy}
      />
      <button
        class="settings-rowact"
        onClicked={act}
        canFocus={false}
        visible={idle}
        sensitive={inRange}
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
        visible={createComputed(() => paired() && idle())}
      >
        <label label="Unpair" />
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

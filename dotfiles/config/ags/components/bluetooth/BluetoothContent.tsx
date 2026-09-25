import { Accessor, createComputed, createEffect, For } from "ags"
import { Gtk } from "ags/gtk4"
import Pango from "gi://Pango?version=1.0"
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

/**
 * Battery level (BlueZ integer 0-100) → the panel's guard-exempt glyph
 * variant. Bucket boundaries mirror the bar's `getBatteryStateKey`
 * (`<25 / <50 / <75 / <100`, which takes a 0-1 fraction): one threshold
 * set serves both surfaces. The panel must never resolve bare `battery-*`
 * — those are guard-subject (status bar only).
 */
function batteryVariant(level: number): string {
  if (level < 25) return "system-battery-0"
  if (level < 50) return "system-battery-25"
  if (level < 75) return "system-battery-50"
  if (level < 100) return "system-battery-75"
  return "system-battery-100"
}

/**
 * RSSI (dBm, negative = present) → `settings-panel` signal level.
 * Fixed contract thresholds (design D5): ≥−60 high, ≥−70 good,
 * ≥−80 medium, else low. The row only renders this line when `rssi < 0`.
 */
function signalVariant(rssi: number): string {
  if (rssi >= -60) return "high"
  if (rssi >= -70) return "good"
  if (rssi >= -80) return "medium"
  return "low"
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
    <box class={rowClass} orientation={1} spacing={3}>
      <box spacing={8}>
        <label
          class="settings-net-name"
          xalign={0}
          label={name}
          hexpand
          maxWidthChars={26}
          ellipsize={Pango.EllipsizeMode.END}
          tooltipText={name}
        />
        <label
          class="settings-badge conn"
          label="Connected"
          valign={Gtk.Align.CENTER}
          visible={connected}
        />
      </box>
      <box class="settings-row-meta" spacing={8}>
        <box orientation={1} spacing={2} hexpand>
          <label
            class="settings-meta-stat"
            xalign={0}
            label="Not in range"
            visible={absent}
          />
          <box
            class="settings-meta-stat"
            spacing={6}
            visible={createComputed(() => connected() && battery() > 0)}
          >
            <image
              class="settings-meta-icon"
              pixel_size={14}
              $={(self) => {
                createEffect(() => {
                  self.set_from_file(
                    registry.resolve("battery", batteryVariant(battery())) ??
                      "",
                  )
                })
              }}
            />
            <label label={createComputed(() => `${battery()}%`)} />
          </box>
          <box
            class="settings-meta-stat"
            spacing={6}
            visible={createComputed(() => rssi() < 0)}
          >
            <image
              class="settings-meta-icon"
              pixel_size={14}
              $={(self) => {
                createEffect(() => {
                  self.set_from_file(
                    registry.resolve(
                      "settings-panel",
                      "signal-" + signalVariant(rssi()),
                    ) ?? "",
                  )
                })
              }}
            />
            <label label={createComputed(() => `−${Math.abs(rssi())} dBm`)} />
          </box>
        </box>
        <box spacing={8} valign={Gtk.Align.CENTER}>
          <Gtk.Spinner class="settings-spinner" visible={busy} spinning={busy} />
          <button
            class="settings-rowact"
            onClicked={act}
            canFocus={false}
            valign={Gtk.Align.CENTER}
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
            valign={Gtk.Align.CENTER}
            visible={createComputed(() => paired() && !anyBusy())}
          >
            <label label="Unpair" />
          </button>
        </box>
      </box>
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

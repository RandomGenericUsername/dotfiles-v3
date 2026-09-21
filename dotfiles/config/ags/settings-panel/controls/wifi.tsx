import { Accessor, createComputed, createEffect, createState } from "ags"
import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { CapabilityTile, IconToggle } from "../primitives"
import {
  activate,
  cancel,
  connectState,
  startScanning,
  stopScanning,
  submitPassword,
  toggleWifi,
  wifiEnabled,
  wifiLog,
  wifiNetworks,
  type WifiNetwork,
} from "../services/wifi-service"
import { show } from "../state"

/**
 * Wi-Fi control (thin view over `services/wifi-service`).
 *
 * State is owned by NetworkManager D-Bus and exposed through the service's
 * accessors; this file only reads them and forwards user intent (`activate`,
 * `submitPassword`, `cancel`, `toggleWifi`). There is no subprocess, no bus
 * call, no saved-profile lookup and no timer here.
 */

export {
  connectState,
  startScanning,
  stopScanning,
  wifiEnabled,
  wifiNetworks,
}
export type { WifiNetwork }

/**
 * SSID the user explicitly selected (a secured network with no saved profile).
 * The prompt must appear on the press, before NetworkManager reports `needAuth`.
 */
const [selectedSsid, setSelectedSsid] = createState<string | null>(null)

/**
 * Target shown by the password prompt: NetworkManager's `needAuth` target, or
 * the explicit local selection. `idle` means nothing is pending, so a stale
 * selection is inert; `failed` keeps the prompt up so the user can retry.
 */
export const wifiPromptSsid: Accessor<string | null> = createComputed(() => {
  const conn = connectState()
  if (conn.phase === "needAuth") return conn.ssid
  if (conn.phase === "idle") return null
  return selectedSsid()
})

/** Whether the password prompt is on screen — drives SettingsPanel keymode. */
export const wifiPromptVisible: Accessor<boolean> = createComputed(
  () => wifiPromptSsid() !== null,
)

/** Dismiss the prompt: drop the explicit selection and cancel any attempt. */
export function cancelWifiPrompt(): void {
  setSelectedSsid(null)
  cancel()
}

export function wifiIconOn(): string | null {
  return registry.resolve("settings-panel", "wifi")
}

export function wifiIconOff(): string | null {
  return registry.resolve("settings-panel", "wifi-off")
}

/** Header/standalone power toggle for the Wi-Fi subview. */
export function WifiToggle() {
  return (
    <IconToggle
      iconOn={wifiIconOn()}
      iconOff={wifiIconOff()}
      active={wifiEnabled}
      onClicked={toggleWifi}
      tooltip="Toggle Wi-Fi"
      size={22}
    />
  )
}

export function WifiTile() {
  return (
    <CapabilityTile
      iconOn={wifiIconOn()}
      iconOff={wifiIconOff()}
      title="Wi-Fi"
      subtitle={createComputed(() => {
        if (!wifiEnabled()) return "Off"
        const conn = connectState()
        if (conn.phase === "preparing" || conn.phase === "activating") {
          return "Connecting…"
        }
        const active = wifiNetworks().find((network) => network.connected)
        if (active) {
          return active.strength > 0
            ? `${active.ssid} · ${active.strength}%`
            : active.ssid
        }
        return "Not connected"
      })}
      active={wifiEnabled}
      onToggle={toggleWifi}
      onOpen={() => show("wifi")}
      toggleTooltip="Toggle Wi-Fi"
    />
  )
}

function SignalBars({ strength }: { strength: number }) {
  const level = strength >= 75 ? 4 : strength >= 50 ? 3 : strength >= 25 ? 2 : 1
  return (
    <box class="settings-signal" valign={Gtk.Align.END} spacing={2}>
      {[1, 2, 3, 4].map((i) => (
        <box
          class={i <= level ? "settings-signal-bar on" : "settings-signal-bar"}
          valign={Gtk.Align.END}
        />
      ))}
    </box>
  )
}

export function WifiRow({ network: item }: { network: WifiNetwork }) {
  // The service re-emits the list, and a row widget may be reused for the same
  // SSID; read the live entry so the connected/saved badges stay correct.
  const live = createComputed(
    () => wifiNetworks().find((network) => network.ssid === item.ssid) ?? item,
  )
  const connected = createComputed(() => live().connected)
  const saved = createComputed(() => live().saved)
  const cls = createComputed(() =>
    connected() ? "settings-net sel" : "settings-net",
  )

  // Derived from the single connect attempt: the target row of a
  // preparing/activating attempt spins, so the spinner is present on the very
  // frame the press lands.
  const busy = createComputed(() => {
    const conn = connectState()
    return (
      conn.ssid === item.ssid &&
      (conn.phase === "preparing" || conn.phase === "activating")
    )
  })

  // Only the target of a pending attempt is disabled; every other row stays
  // sensitive so a press re-targets the in-flight attempt (never mass-disable).
  const sensitive = createComputed(() => {
    const conn = connectState()
    const pending =
      conn.phase === "preparing" ||
      conn.phase === "activating" ||
      conn.phase === "needAuth"
    return !pending || conn.ssid !== item.ssid
  })

  function act() {
    const isConnected = connected()
    wifiLog(
      `row click "${item.ssid}" connected=${isConnected} sensitive=${sensitive()} saved=${saved()}`,
    )
    if (isConnected || !sensitive()) return
    const wantsPassword = item.secured && !saved()
    activate(item.ssid)
    setSelectedSsid(wantsPassword ? item.ssid : null)
  }

  return (
    <box
      class={cls}
      spacing={10}
      $={(self) => {
        // Whole-row action (mirrors CapabilityTile): a small explicit button is
        // an unreliable hit target — presses on the name/signal area did
        // nothing, which read as "Connect is dead". The row itself is the
        // control; the trailing "button" is a non-interactive affordance.
        const click = new Gtk.GestureClick({ button: 1 })
        click.connect("released", () => act())
        self.add_controller(click)
      }}
    >
      <box orientation={1} hexpand>
        <label class="settings-net-name" xalign={0} label={item.ssid} />
        <label
          class="settings-net-sub"
          xalign={0}
          label={createComputed(() => {
            if (saved()) return "Saved"
            return live().secured ? "Secured" : "Open network"
          })}
        />
      </box>
      <label
        class="settings-badge conn"
        label="Connected"
        valign={Gtk.Align.CENTER}
        visible={connected}
      />
      <box visible={createComputed(() => !connected())} valign={Gtk.Align.END}>
        <SignalBars strength={item.strength} />
      </box>
      <box
        class={createComputed(() =>
          sensitive() ? "settings-rowact" : "settings-rowact disabled",
        )}
        valign={Gtk.Align.CENTER}
        visible={createComputed(() => !connected())}
      >
        <box spacing={6}>
          <Gtk.Spinner
            class="settings-spinner"
            visible={busy}
            spinning={busy}
          />
          <label label="Connecting…" visible={busy} />
          <label label="Connect" visible={createComputed(() => !busy())} />
        </box>
      </box>
    </box>
  )
}

export function WifiPasswordPrompt() {
  const [password, setPassword] = createState("")
  let entry: Gtk.Entry | null = null

  // The prompt is mounted permanently and only visibility-toggled, so reset and
  // focus the field whenever the target (not the mount) changes.
  createEffect(() => {
    if (wifiPromptSsid() === null) return
    setPassword("")
    entry?.grab_focus()
  })

  // The service moves to preparing/activating after a submit; the prompt stays
  // up with the busy affordance until the attempt reaches a terminal state.
  const joining = createComputed(() => {
    const conn = connectState()
    return conn.phase === "preparing" || conn.phase === "activating"
  })

  // Failure is state-derived: it appears when the attempt failed and clears the
  // moment the phase leaves `failed` (i.e. a new attempt starts).
  const promptError = createComputed(() => {
    const conn = connectState()
    if (conn.phase !== "failed") return ""
    return conn.reason ?? "Connection failed"
  })

  function join() {
    if (joining()) return
    const ssid = wifiPromptSsid()
    if (ssid === null) return
    // `needAuth` is the normal submit; a failed attempt is re-run as a fresh
    // activation with the newly typed secret.
    if (connectState().phase === "needAuth") submitPassword(password())
    else activate(ssid, password())
  }

  return (
    <box class="settings-password" orientation={1} spacing={8}>
      <label class="settings-field-label" xalign={0} label="Password" />
      <box class="settings-field-input">
        <entry
          class="settings-field-entry"
          hexpand
          visibility={false}
          placeholderText="Network password"
          onActivate={join}
          onNotifyText={(self: { text: string }) => setPassword(self.text)}
          $={(self) => {
            entry = self
          }}
        />
      </box>
      <label
        class="settings-field-error"
        xalign={0}
        label={promptError}
        visible={createComputed(() => promptError() !== "")}
      />
      <box class="settings-btnrow" spacing={8} homogeneous>
        <button
          class="settings-btn cancel"
          onClicked={cancelWifiPrompt}
          canFocus={false}
        >
          <label label="Cancel" />
        </button>
        <button
          class="settings-btn join"
          onClicked={join}
          canFocus={false}
          sensitive={createComputed(() => !joining())}
        >
          <label label={createComputed(() => (joining() ? "Joining…" : "Join"))} />
        </button>
      </box>
    </box>
  )
}

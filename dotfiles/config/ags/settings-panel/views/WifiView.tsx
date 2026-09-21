import { createComputed, createEffect, For } from "ags"
import { NavHeader } from "../primitives"
import { activeView, back } from "../state"
import {
  WifiRow,
  WifiPasswordPrompt,
  WifiToggle,
  cancelWifiPrompt,
  connectState,
  startScanning,
  stopScanning,
  wifiEnabled,
  wifiNetworks,
  wifiPromptSsid,
  wifiPromptVisible,
} from "../controls/wifi"

export function WifiView() {
  const showList = createComputed(
    () => wifiEnabled() && !wifiPromptVisible(),
  )

  // Scan while the view is open; the service owns the cadence and pauses while a
  // connect is in flight. Leaving the view stops the timer.
  createEffect(() => {
    if (activeView() !== "wifi") return
    startScanning()
    return () => stopScanning()
  })

  // Back from the password prompt returns to the network list, not the panel.
  function onBack() {
    if (wifiPromptVisible()) cancelWifiPrompt()
    else back()
  }

  // Failure is derived from the connect state — no manual message timer. It
  // clears as soon as the phase leaves `failed`.
  const failure = createComputed(() => {
    const conn = connectState()
    if (conn.phase !== "failed") return ""
    return conn.reason ?? "Connection failed"
  })

  return (
    <box orientation={1} spacing={8}>
      <NavHeader
        title={createComputed(() => wifiPromptSsid() ?? "Wi-Fi")}
        onBack={onBack}
        trailing={<WifiToggle />}
      />

      <label
        class="settings-empty"
        xalign={0}
        label="Wi-Fi is off"
        visible={createComputed(() => !wifiEnabled())}
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
        label="No networks found"
        visible={createComputed(() => showList() && wifiNetworks().length === 0)}
      />

      <box orientation={1} spacing={4} visible={showList}>
        <For each={wifiNetworks} id={(network) => network.ssid}>
          {(network) => <WifiRow network={network} />}
        </For>
      </box>

      {/* Mounted always (visibility-toggled) rather than conditionally via
          <With>: <With> did not render the prompt, so choosing a network left an
          empty body. The prompt reads the target itself. */}
      <box orientation={1} spacing={8} visible={wifiPromptVisible}>
        <WifiPasswordPrompt />
      </box>
    </box>
  )
}

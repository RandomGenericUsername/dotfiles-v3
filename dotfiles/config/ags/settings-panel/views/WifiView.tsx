import { createComputed, createEffect, For } from "ags"
import { interval } from "ags/time"
import { NavHeader } from "../primitives"
import { activeView, back } from "../state"
import {
  WifiRow,
  WifiPasswordPrompt,
  WifiToggle,
  clearWifiMessage,
  closeWifiPasswordPrompt,
  scanWifi,
  wifiEnabled,
  wifiMessage,
  wifiNetworks,
  wifiPasswordTarget,
} from "../controls/wifi"

export function WifiView() {
  const target = wifiPasswordTarget
  const showList = createComputed(() => wifiEnabled() && target() === null)

  // Force an authoritative scan on open and keep it fresh while the list is
  // shown (`iw scan` returns only what is on the air now, so vanished networks
  // drop promptly instead of lingering in NM's cache).
  createEffect(() => {
    if (activeView() !== "wifi") return
    clearWifiMessage()
    scanWifi()
    const timer = interval(8000, scanWifi)
    return () => timer.cancel()
  })

  // Back from the password prompt returns to the network list, not the panel.
  function onBack() {
    if (target() !== null) closeWifiPasswordPrompt()
    else back()
  }

  return (
    <box orientation={1} spacing={8}>
      <NavHeader
        title={createComputed(() => target() ?? "Wi-Fi")}
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
        label={wifiMessage}
        visible={createComputed(() => wifiMessage() !== "")}
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
      <box
        orientation={1}
        spacing={8}
        visible={createComputed(() => target() !== null)}
      >
        <WifiPasswordPrompt />
      </box>
    </box>
  )
}

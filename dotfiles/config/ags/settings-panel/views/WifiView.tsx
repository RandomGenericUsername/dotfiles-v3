import { createComputed, For, With } from "ags"
import { NavHeader } from "../primitives"
import { back } from "../state"
import {
  WifiRow,
  WifiPasswordPrompt,
  WifiToggle,
  wifiEnabled,
  wifiMessage,
  wifiNetworks,
  wifiPasswordTarget,
} from "../controls/wifi"

export function WifiView() {
  const target = wifiPasswordTarget
  const showList = createComputed(() => wifiEnabled() && target() === null)

  return (
    <box orientation={1} spacing={8}>
      <NavHeader
        title={createComputed(() => target() ?? "Wi-Fi")}
        onBack={back}
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

      <With value={target}>
        {(ssid) => (ssid ? <WifiPasswordPrompt /> : null)}
      </With>
    </box>
  )
}

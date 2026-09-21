import { createComputed } from "ags"
import { NavHeader } from "../primitives"
import { activeView, back, panelVisible } from "../state"
import {
  WifiContent,
  WifiToggle,
  cancelWifiPrompt,
  wifiPromptSsid,
  wifiPromptVisible,
} from "../../components/wifi/WifiContent"

export function WifiView() {
  // Back from the password prompt returns to the network list, not the panel.
  function onBack() {
    if (wifiPromptVisible()) cancelWifiPrompt()
    else back()
  }

  return (
    <box orientation={1} spacing={8}>
      <NavHeader
        title={createComputed(() => wifiPromptSsid() ?? "Wi-Fi")}
        onBack={onBack}
        trailing={<WifiToggle />}
      />

      <WifiContent
        visible={createComputed(
          () => panelVisible() && activeView() === "wifi",
        )}
      />
    </box>
  )
}

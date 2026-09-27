import { createComputed } from "ags"
import { NavHeader } from "../primitives"
import { activeView, back, panelVisible } from "../state"
import {
  WifiContent,
  cancelWifiPrompt,
  wifiPromptSsid,
  wifiPromptVisible,
} from "../../components/wifi/WifiContent"
import { WifiSwitch } from "../../components/primitives/WifiSwitch"
import { setWifiEnabled, wifiEnabled, wifiReady } from "../../services/wifi-service"

export function WifiView() {
  function onBack() {
    if (wifiPromptVisible()) cancelWifiPrompt()
    else back()
  }

  return (
    <box orientation={1} spacing={8}>
      <NavHeader
        title={createComputed(() => wifiPromptSsid() ?? "Wi-Fi")}
        onBack={onBack}
        trailing={<WifiSwitch active={wifiEnabled} sensitive={wifiReady} onToggled={(v) => { void setWifiEnabled(v) }} />}
      />
      <WifiContent
        visible={createComputed(
          () => panelVisible() && activeView() === "wifi",
        )}
      />
    </box>
  )
}

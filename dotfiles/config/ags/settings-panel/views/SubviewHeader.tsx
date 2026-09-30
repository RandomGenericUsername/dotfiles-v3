import { createComputed } from "ags"
import { NavHeader } from "../primitives"
import { activeView, back } from "../state"
import {
  cancelWifiPrompt,
  wifiPromptSsid,
  wifiPromptVisible,
} from "../../components/wifi/WifiContent"
import { BluetoothToggle } from "../../components/bluetooth/BluetoothContent"
import { WifiSwitch } from "../../components/primitives/WifiSwitch"
import { setWifiEnabled, wifiEnabled, wifiReady } from "../../services/wifi-service"

/**
 * The pinned subview header for the settings panel.
 *
 * This lives OUTSIDE the panel's scrolled window, as a sibling of it — which is
 * how the tray popup has always done it (WifiPopup.tsx renders the header as a
 * sibling of its scrolledwindow). It used to be rendered by WifiView and
 * BluetoothView, i.e. INSIDE the scrolled window, so the header scrolled away
 * with the content and the two surfaces behaved differently despite sharing the
 * same NavHeader component. Same components, two different containers; the
 * container is what decides whether the header stays put.
 *
 * Only the subviews have headers — MainView is a bare card stack — so the whole
 * slot is hidden on "main" rather than rendering an empty bar.
 */
export function SubviewHeader() {
  function onWifiBack() {
    // The Wi-Fi password prompt takes over the title with the target SSID, so
    // back must dismiss the prompt first and only then leave the subview.
    if (wifiPromptVisible()) cancelWifiPrompt()
    else back()
  }

  return (
    <box
      orientation={1}
      visible={createComputed(() => activeView() !== "main")}
    >
      <box visible={createComputed(() => activeView() === "wifi")}>
        <NavHeader
          title={createComputed(() => wifiPromptSsid() ?? "Wi-Fi")}
          onBack={onWifiBack}
          trailing={
            <WifiSwitch
              active={wifiEnabled}
              sensitive={wifiReady}
              onToggled={(v) => {
                void setWifiEnabled(v)
              }}
            />
          }
        />
      </box>
      <box visible={createComputed(() => activeView() === "bluetooth")}>
        <NavHeader title="Bluetooth" onBack={back} trailing={<BluetoothToggle />} />
      </box>
    </box>
  )
}

import { overlays } from "./kit/overlay"
import {
  closeWifiPopup,
  openWifiPopup,
  setWifiIconX,
  wifiPopupVisible,
} from "./components/wifi/state"
import {
  bluetoothPopupVisible,
  closeBluetoothPopup,
  openBluetoothPopup,
  setBluetoothIconX,
} from "./components/bluetooth/state"
import {
  batteryPopupVisible,
  closeBatteryPopup,
  openBatteryPopup,
  setBatteryIconX,
} from "./components/battery/state"
import {
  close as closeSettings,
  open as openSettings,
  panelVisible,
  setIconCenterX,
} from "./settings-panel/state"
import {
  close as closeAudio,
  open as openAudio,
  popupVisible as audioPopupVisible,
  setAudioIconX,
} from "./audio/ui-state"

/**
 * Register every bar overlay with the coordinator, once.
 *
 * This is the ONLY place the full overlay set is named — the obligation the
 * `app.tsx` `popup-close` comment used to carry ("EVERY overlay must be closed
 * here, or Esc strands it") is now `overlays.closeAll()` and this list. A new
 * surface adds one line here and Nothing else.
 *
 * Side-effect module: `app.tsx` imports it during composition. Registration is
 * inert until a widget actually calls `overlays.open/toggle`.
 */

overlays.register({
  id: "wifi",
  isOpen: () => wifiPopupVisible(),
  open: (anchorX) => {
    if (anchorX !== null) setWifiIconX(anchorX)
    openWifiPopup()
  },
  close: closeWifiPopup,
})

overlays.register({
  id: "bluetooth",
  isOpen: () => bluetoothPopupVisible(),
  open: (anchorX) => {
    if (anchorX !== null) setBluetoothIconX(anchorX)
    openBluetoothPopup()
  },
  close: closeBluetoothPopup,
})

overlays.register({
  id: "battery",
  isOpen: () => batteryPopupVisible(),
  open: (anchorX) => {
    if (anchorX !== null) setBatteryIconX(anchorX)
    openBatteryPopup()
  },
  close: closeBatteryPopup,
})

overlays.register({
  id: "settings",
  isOpen: () => panelVisible(),
  open: (anchorX) => {
    if (anchorX !== null) setIconCenterX(anchorX)
    openSettings()
  },
  close: closeSettings,
})

overlays.register({
  id: "audio",
  isOpen: () => audioPopupVisible(),
  open: (anchorX) => {
    if (anchorX !== null) setAudioIconX(anchorX)
    openAudio()
  },
  close: closeAudio,
})

import Network from "gi://AstalNetwork"
import { execAsync } from "ags/process"
import { createBinding } from "ags"
import type { BarWidgetSpec } from "../../kit/widget"
import { iconByStateKey } from "../../kit/icon"
import { overlays } from "../../kit/overlay"
import {
  networkIconState,
  networkLabel,
  type NetworkReading,
} from "../../lib/network-icon"

/**
 * The status-bar network indicator, reproduced as a widget DESCRIPTOR — the
 * stateful case the launchers did not cover.
 *
 * Compare with `network.tsx` (kept beside it in the bar, unchanged): that file
 * owns the Astal binding, the state→variant table, the label rule, the pointer
 * tracking, the gestures and the close-settings-first exclusion. Here the read
 * model lives in `reading()`, the mapping is the pure `lib/network-icon.ts`, and
 * the behaviour is three fields. The overlay is opened through the coordinator
 * (`overlays.toggle("wifi", anchorX)`), which closes the other overlays for us.
 *
 * Not yet carried over (deliberately, prototype scope): the `speedtesting` CSS
 * class the kit does not model. Everything else is at parity.
 */

const network = Network.get_default()
const wifi = createBinding(network, "wifi")
const wired = createBinding(network, "wired")
const connectivity = createBinding(network, "connectivity")

function reading(): NetworkReading {
  return {
    wifi: wifi() as unknown as NetworkReading["wifi"],
    wired: wired() as unknown as NetworkReading["wired"],
    connectivity: connectivity(),
  }
}

export const networkWidget: BarWidgetSpec<NetworkReading> = {
  id: "network",
  read: reading,
  class: "network-widget",
  icon: iconByStateKey("network", networkIconState),
  label: networkLabel,
  primary: (_reading, anchorX) => overlays.toggle("wifi", anchorX),
  secondary: () => {
    execAsync(["kitty", "--", "wifitui", "tui"]).catch(console.error)
  },
}

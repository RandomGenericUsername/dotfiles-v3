import { Astal, Gdk } from "ags/gtk4"
import { Workspaces } from "./widgets/workspaces"
import { Clock } from "./widgets/clock"
import { BatteryIndicator } from "./widgets/battery"
// Bluetooth sits immediately left of the network widget: the two connectivity
// glyphs read as one group, matching the mock's bar pair.
import { BluetoothStatus } from "./widgets/bluetooth"
import { NetworkStatus } from "./widgets/network"
import { networkWidget } from "./widgets/network-descriptor"
import { Tray } from "./widgets/tray"
import { MicIndicator, OutputIndicator } from "./widgets/audio"
import { BarWidgetButton } from "../kit/widget"
import { btopWidget } from "./widgets/btop"
import { thunderbirdWidget } from "./widgets/thunderbird"
import { settingsWidget } from "./widgets/settings"
import { powerMenuWidget } from "./widgets/power-menu"
import { readBarBackdrop } from "../lib/bar-backdrop"
import type { AudioPanelBinding } from "../audio/AudioPopup"

export default function Bar(gdkmonitor: Gdk.Monitor, audio: AudioPanelBinding) {
  const { TOP, LEFT, RIGHT } = Astal.WindowAnchor
  const backdrop = readBarBackdrop(gdkmonitor.get_connector())

  return (
    <window
      visible
      name="bar"
      class="bar"
      gdkmonitor={gdkmonitor}
      exclusivity={Astal.Exclusivity.EXCLUSIVE}
      anchor={TOP | LEFT | RIGHT}
    >
      <centerbox cssName="centerbox">
        <box $type="start">
          <Workspaces />
        </box>
        <box $type="center">
          <Clock />
        </box>
        <box $type="end" spacing={8}>
          <Tray />
          <OutputIndicator binding={audio} />
          <MicIndicator binding={audio} showLiveDotRing={backdrop !== "dark"} />
          <BatteryIndicator />
          <BluetoothStatus />
          <NetworkStatus />
          <BarWidgetButton spec={networkWidget} />
          <BarWidgetButton spec={btopWidget} />
          <BarWidgetButton spec={thunderbirdWidget} />
          <BarWidgetButton spec={settingsWidget} />
          <BarWidgetButton spec={powerMenuWidget} />
        </box>
      </centerbox>
    </window>
  )
}

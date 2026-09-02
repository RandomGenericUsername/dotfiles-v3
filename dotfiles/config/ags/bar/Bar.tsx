import { Astal, Gdk } from "ags/gtk4"
import { Workspaces } from "./widgets/workspaces"
import { Clock } from "./widgets/clock"
import { BatteryIndicator } from "./widgets/battery"
import { NetworkStatus } from "./widgets/network"
import { PowerMenu } from "./widgets/power-menu"
import { Btop } from "./widgets/btop"
import { Thunderbird } from "./widgets/thunderbird"
import { Tray } from "./widgets/tray"

export default function Bar(gdkmonitor: Gdk.Monitor) {
  const { TOP, LEFT, RIGHT } = Astal.WindowAnchor

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
          <BatteryIndicator />
          <NetworkStatus />
          <Btop />
          <Thunderbird />
          <PowerMenu />
        </box>
      </centerbox>
    </window>
  )
}

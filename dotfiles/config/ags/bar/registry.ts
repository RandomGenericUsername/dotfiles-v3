import type { AnyWidgetSpec, BarContext } from "../kit/widget"
import type { AudioPanelBinding } from "../audio/AudioPopup"
import type { BarBackdrop } from "../lib/bar-backdrop"
import { domainEvents } from "../lib/event-bus"
import { workspacesWidget } from "./widgets/workspaces"
import { clockWidget } from "./widgets/clock"
import { createTrayWidget } from "./widgets/tray"
import { createRecordingWidget } from "./widgets/recording"
import {
  createAudioMicWidget,
  createAudioOutputWidget,
} from "./widgets/audio"
import { createBatteryWidget } from "./widgets/battery"
import { createBluetoothWidget } from "./widgets/bluetooth"
import { networkWidget } from "./widgets/network-descriptor"
import { btopWidget } from "./widgets/btop"
import { thunderbirdWidget } from "./widgets/thunderbird"
import { settingsWidget } from "./widgets/settings"
import { powerMenuWidget } from "./widgets/power-menu"

/**
 * The bar's widget registry: a layout entry id → the spec that renders it.
 *
 * The layout (`bar/layout.default.ts`) is pure placement (AD-9); this is the
 * other half of the seam — the id vocabulary that placement addresses. A small
 * hand-written map today; AD-14/AD-15's pure-data `bar-manifest` + validators
 * replace it in a later step. The four launchers (btop, thunderbird, settings,
 * power-menu) were already descriptors and are registered unchanged.
 *
 * Built per bar, because the tray and recording specs hold per-bar state and the
 * audio specs close over the composition binding.
 */
export interface BarDeps {
  readonly audio: AudioPanelBinding
  readonly backdrop: BarBackdrop
}

export function createWidgetRegistry(
  deps: BarDeps,
): ReadonlyMap<string, AnyWidgetSpec> {
  const widgets = new Map<string, AnyWidgetSpec>()
  widgets.set("workspaces", workspacesWidget)
  widgets.set("clock", clockWidget)
  widgets.set("tray", createTrayWidget())
  widgets.set("recording", createRecordingWidget())
  widgets.set("audio-output", createAudioOutputWidget(deps.audio))
  widgets.set("audio-mic", createAudioMicWidget(deps.audio, deps.backdrop !== "dark"))
  widgets.set("battery", createBatteryWidget())
  widgets.set("bluetooth", createBluetoothWidget())
  widgets.set("network", networkWidget)
  widgets.set("btop", btopWidget)
  widgets.set("thunderbird", thunderbirdWidget)
  widgets.set("settings", settingsWidget)
  widgets.set("power-menu", powerMenuWidget)
  return widgets
}

/**
 * The injected `BarContext` the shapes call (AD-8). `hub.control` is the real
 * one event client; `popup` is the capability seam the platform extraction
 * fills — today every migrated widget opens its surface by id through the
 * overlay coordinator (`kit/overlay`), so nothing calls it yet.
 */
export function createBarContext(): BarContext {
  return {
    popup: () => {
      // Surfaces are opened by id via `overlays.toggle(id, anchorX)` today; the
      // generic content-popup arrives with the platform extraction (AD-20 step
      // 8). No migrated widget calls this.
    },
    hub: {
      control: (jobId, action) => domainEvents.control(jobId, action),
    },
  }
}

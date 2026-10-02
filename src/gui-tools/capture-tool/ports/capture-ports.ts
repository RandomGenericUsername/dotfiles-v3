// ---------------------------------------------------------------------------
// PORT: the aggregate `CaptureWindow` is constructed with (design.md §2,
// task 5.9).
//
// `oci-strict-hexagonal-layering` allows "ABCs or typed aggregates" in the
// ports layer; this is the aggregate. It exists so the view takes ONE
// parameter instead of four, and so the composition root (`app.tsx`, A8) has a
// single type to satisfy when it builds the adapters.
//
// Every member is an interface declared in this same layer, so this file adds
// no new vocabulary — it only names the set. Interface only: no
// implementation, no `ags/*`, no `gi://*` (gate check 1).
// ---------------------------------------------------------------------------

import type { BackendProbe } from "./backend-probe"
import type { CaptureLauncher } from "./capture-launcher"
import type { SettingsStore } from "./settings-store"
import type { UiStateStore } from "./ui-state-store"

export interface CapturePorts {
  /** `$XDG_CONFIG_HOME/capture-tool/config.json`. */
  settingsStore: SettingsStore
  /** `$XDG_STATE_HOME/capture-tool/capture-ui.json`. */
  uiStateStore: UiStateStore
  /** Spawns the capture backend after the window is hidden. */
  launcher: CaptureLauncher
  /** Reports the auto-selected recorder backend. */
  backendProbe: BackendProbe
}
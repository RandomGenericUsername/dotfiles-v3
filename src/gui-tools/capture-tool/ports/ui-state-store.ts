// ---------------------------------------------------------------------------
// PORT: persistence for the GUI-local `$XDG_STATE_HOME/capture-tool/capture-ui.json`
// last-used selections (design.md §2, task 5.2).
//
// Same split as `ports/settings-store.ts`: the state shape, the first-run
// constants and the merge are pure and live in `domain/ui-state.ts`; the read,
// the write and the missing-is-silent / corrupt-is-loud degradation live in
// `adapters/glib-ui-state-store.ts`. This file is only the contract.
//
// Interface only — no concrete implementation, no `ags/*`, no `gi://*`
// (gate check 1, and the spec requirement "Ports SHALL declare no concrete
// implementation").
// ---------------------------------------------------------------------------

import type {
  RecordingUiState,
  ScreenshotUiState,
  UiState,
} from "../domain/ui-state"

/** Read/persist the last-used mode-view selections. */
export interface UiStateStore {
  /**
   * Overlay the last-used values on the settings-derived defaults, falling
   * back per field. A missing state file is first run and is silent; an
   * unparseable one logs loudly and still yields the defaults. Never throws.
   */
  load(base: UiState): UiState

  /** Persist both mode views. Failures are logged, never propagated. */
  save(screenshot: ScreenshotUiState, recording: RecordingUiState): void
}
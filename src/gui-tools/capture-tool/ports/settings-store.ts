// ---------------------------------------------------------------------------
// PORT: persistence for `$XDG_CONFIG_HOME/capture-tool/config.json`
// (design.md §2 "ports/ — interfaces only", task 5.1).
//
// This file declares the SEAM, not the behaviour. The vocabulary, the merge
// and the validation live in `domain/settings.ts`; the GLib file reads/writes
// and the recursive directory creation live in
// `adapters/glib-settings-store.ts`. What is left for `ui/` is this contract,
// so the view can be constructed with any store — including an in-memory one —
// and so a future layout inherits persistence for free.
//
// NOTHING CONCRETE HERE. Gate check 1 forbids `ags/*` and `gi://*` imports in
// `ports/`, and the spec requirement "Ports SHALL declare no concrete
// implementation" forbids a class with a body: a port that could reach the
// filesystem would not be a port.
// ---------------------------------------------------------------------------

import type { CaptureSettings } from "../domain/settings"

/** Read/persist the capture settings config. */
export interface SettingsStore {
  /**
   * Read the config; missing/corrupt degrade to defaults (corrupt logs
   * loudly). Never throws.
   */
  load(): CaptureSettings

  /**
   * Persist settings (validated), creating the config dir and both output
   * directories with parents. Returns an error string, or null on success.
   */
  save(settings: CaptureSettings): string | null
}
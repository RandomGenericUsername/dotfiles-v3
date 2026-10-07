// ---------------------------------------------------------------------------
// ADAPTER: GLib-backed persistence for the GUI-local
// `$XDG_STATE_HOME/capture-tool/capture-ui.json` (design.md §3.4, task 5.6).
//
// The only place in the capture tool that touches `GLib.file_*` or
// `GLib.mkdir_with_parents` for UI state.
//
// THE NULL SUBSTITUTION (the sharp edge A4 flagged). `mergeUiState` is pure
// and dereferences `persisted.screenshot` directly, so passing it `null`
// THROWS — deliberately: whole-object null tolerance belongs to the layer that
// owns "the file was missing or unreadable", which is this one. So `null` is
// never handed across; `{}` (empty persisted state) is substituted instead,
// and the merge's per-field fallbacks then produce the base defaults.
//
// All three degraded paths, exactly as observed pre-A5:
//
//   * missing file               -> base defaults, SILENTLY (first run).
//   * unreadable bytes           -> base defaults, SILENTLY (`!ok`).
//   * JSON that parses to `null` -> base defaults, LOUDLY. This one DID throw
//                                   inside the merge before, so the log is
//                                   emitted here explicitly; dropping it would
//                                   be a silent behaviour change.
//   * unparseable JSON, any
//     other throw                -> base defaults, LOUDLY (the catch).
//
// `fallback` is a shallow copy of `base`, byte-identical to what
// `mergeUiState(base, {})` computes field for field.
// ---------------------------------------------------------------------------

import GLib from "gi://GLib?version=2.0"
import type { UiStateStore } from "../ports/ui-state-store"
import type {
  PersistedUiState,
  RecordingUiState,
  ScreenshotUiState,
  UiState,
} from "../domain/ui-state"
import { mergeUiState } from "../domain/ui-state"

const UI_STATE_DIR = `${
  GLib.getenv("XDG_STATE_HOME") || `${GLib.get_home_dir()}/.local/state`
}/capture-tool`
const UI_STATE_PATH = `${UI_STATE_DIR}/capture-ui.json`

function loadUiState(base: UiState): UiState {
  const fallback = {
    screenshot: { ...base.screenshot },
    recording: { ...base.recording },
  }
  try {
    // First run has no state file yet — fall back silently, not loudly.
    if (!GLib.file_test(UI_STATE_PATH, GLib.FileTest.EXISTS)) return fallback
    const [ok, bytes] = GLib.file_get_contents(UI_STATE_PATH)
    if (!ok || bytes === null) return fallback
    const parsed = JSON.parse(new TextDecoder().decode(bytes)) as PersistedUiState | null
    // Substitute, do not forward: `mergeUiState` would throw on `null`. The
    // log preserves what that throw used to produce for this input.
    if (parsed === null) {
      console.error(`capture-tool: cannot read UI state: ${UI_STATE_PATH} is null`)
      return mergeUiState(base, {})
    }
    return mergeUiState(base, parsed)
  } catch (error) {
    console.error(`capture-tool: cannot read UI state: ${error}`)
    return fallback
  }
}

function saveUiState(screenshot: ScreenshotUiState, recording: RecordingUiState): void {
  try {
    GLib.mkdir_with_parents(UI_STATE_DIR, 0o755)
    GLib.file_set_contents(UI_STATE_PATH, JSON.stringify({ screenshot, recording }))
  } catch (error) {
    console.error(`capture-tool: cannot write UI state: ${error}`)
  }
}

/** The composition root's `UiStateStore`. */
export function glibUiStateStore(): UiStateStore {
  return { load: loadUiState, save: saveUiState }
}
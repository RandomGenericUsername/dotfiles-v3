// ---------------------------------------------------------------------------
// ADAPTER: GLib-backed persistence for `$XDG_CONFIG_HOME/capture-tool/config.json`
// (design.md §3.4, task 5.5).
//
// This is the only place in the capture tool that touches `GLib.file_*` or
// `GLib.mkdir_with_parents` for settings, and it also owns the injected
// `Environment` for domain's pure `expandDir` (design.md §7.2 — A3 left the
// construction here, deliberately, because `domain/` may not import `gi://`).
//
// The two degradation rules are load-bearing and are reproduced verbatim from
// the pre-A5 inline implementation:
//   * missing  -> silent defaults (first run, not an error)
//   * corrupt  -> loud log, then the same defaults
// The reads are ALWAYS safe: the GUI owns writes, but `bin/capture-tool`
// reads this same file on every invocation, so a bad write must never be able
// to take the backend down.
// ---------------------------------------------------------------------------

import GLib from "gi://GLib?version=2.0"
import type { SettingsStore } from "../ports/settings-store"
import {
  type CaptureSettings,
  type Environment,
  defaultSettings,
  expandDir,
  mergeSettings,
  validateSettings,
} from "../domain/settings"

const CONFIG_DIR = `${
  GLib.getenv("XDG_CONFIG_HOME") || `${GLib.get_home_dir()}/.config`
}/capture-tool`
const CONFIG_PATH = `${CONFIG_DIR}/config.json`

// Environment seam for domain's pure `expandDir` (design.md §7.2, task 3.3):
// `getenv`/`home` mirror GLib exactly and are resolved at call time, so the
// expansion results are unchanged. This is the object A3's comment in
// `domain/settings.ts` pointed at: the adapter is the only layer allowed to
// touch GLib's environment, so it constructs the seam and passes it in.
const ENVIRONMENT: Environment = {
  getenv: (name) => GLib.getenv(name),
  home: () => GLib.get_home_dir(),
}

/** Read the config; missing/corrupt degrade to defaults (corrupt logs loudly). */
function loadSettings(): CaptureSettings {
  try {
    if (!GLib.file_test(CONFIG_PATH, GLib.FileTest.EXISTS)) return defaultSettings()
    const [ok, bytes] = GLib.file_get_contents(CONFIG_PATH)
    if (!ok || bytes === null) return defaultSettings()
    return mergeSettings(JSON.parse(new TextDecoder().decode(bytes)))
  } catch (error) {
    console.error(`capture-tool: cannot read settings config: ${error}`)
    return defaultSettings()
  }
}

/**
 * Persist settings (validated), creating the config dir and both output
 * directories with parents. Returns an error string, or null on success.
 */
function saveSettings(settings: CaptureSettings): string | null {
  const error = validateSettings(settings)
  if (error !== null) return error
  try {
    GLib.mkdir_with_parents(CONFIG_DIR, 0o755)
    for (const dir of [settings.screenshot_dir, settings.recording_dir]) {
      const expanded = expandDir(dir, ENVIRONMENT).trim()
      if (expanded !== "") GLib.mkdir_with_parents(expanded, 0o755)
    }
    GLib.file_set_contents(CONFIG_PATH, `${JSON.stringify(settings, null, 2)}\n`)
    return null
  } catch (cause) {
    console.error(`capture-tool: cannot write settings config: ${cause}`)
    return `Could not save settings: ${cause}`
  }
}

/** The composition root's `SettingsStore`. */
export function glibSettingsStore(): SettingsStore {
  return { load: loadSettings, save: saveSettings }
}
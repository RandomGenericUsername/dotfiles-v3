// ---------------------------------------------------------------------------
// CLASSIC LAYOUT — the settings view (design.md §2, task 8.4).
//
// Split out of the pre-split `ui/CaptureWindow.tsx` with NO behavioural
// change: the JSX below is a byte-for-byte move of that file's lines 1529-1572,
// leading indentation included, so the rendered widget tree is unchanged and
// `git diff -M` shows a move rather than an edit. Do not re-indent it.
//
// The page owns the settings draft (`settingsConfig`), the three groups
// (`renderSettings`), the inline path editor the window's key controller has to
// defer to, and the backend readout. It is REBUILT from disk each time it
// opens so it always reflects the current config; edits mutate the draft and
// are persisted on leave and immediately after every change.
//
// The row builders come from `ui/shared/rows.ts` (A7) — they were extracted
// from this very code and are shared with every future layout. `RowContext` is
// how they see this page's `persistSettings` and its active path editor; the
// builders never close over view state.
// ---------------------------------------------------------------------------

import { Gtk } from "ags/gtk4"
import { clearChildren } from "../shared/groups"
import {
  pathRow,
  pillRow,
  settingsGroup,
  settingsItem,
  toggleRow,
  type PathEditor,
  type RowContext,
} from "../shared/rows"
import type { BackendProbe } from "../../ports/backend-probe"
import type { SettingsStore } from "../../ports/settings-store"
import type {
  CaptureSettings,
  ConfigRecordingAudio,
  ConfigRecordingFps,
  ConfigRecordingQuality,
  ConfigScreenshotFormat,
  ConfigScreenshotOutput,
} from "../../domain/settings"

/**
 * What the window needs back from this page.
 *
 * The view container, the rebuild target, the error label, the backend
 * readout, the draft and the inline path editor are all page-local `let`s (the
 * JSX below assigns them in the `$` handlers, unchanged), so the window
 * reaches them through this handle rather than through shared mutable cells.
 */
export interface SettingsPageHandle {
  setVisible: (visible: boolean) => void
  /** Rebuild the three groups from the config on disk. */
  render: () => void
  /** Persist the draft; `false` means the save failed and the view stays open. */
  close: () => boolean
  /** Commit the open inline path editor, if any. `true` if one was open. */
  commitPathEditor: () => boolean
  /** Cancel the open inline path editor, if any. `true` if one was open. */
  cancelPathEditor: () => boolean
}

export interface SettingsPageProps {
  settingsStore: SettingsStore
  backendProbe: BackendProbe
  /** Return to a mode view; called once the draft has been persisted. */
  selectMode: (mode: "screenshot" | "recording") => void
  /** The mode to return to. */
  mode: "screenshot" | "recording"
  setHandle: (handle: SettingsPageHandle) => void
}

export function SettingsPage(props: SettingsPageProps) {
  const { settingsStore, backendProbe, selectMode, mode, setHandle } = props

  let settingsView: Gtk.Box | null = null
  let settingsBody: Gtk.Box | null = null
  let settingsError: Gtk.Label | null = null
  let backendReadout: Gtk.Label | null = null
  // Draft settings edited in the view; persisted on Back/Escape/Enter.
  let settingsConfig: CaptureSettings = settingsStore.load()
  // Active inline path editor, so Enter/Escape commit/cancel it instead of
  // being swallowed by the window's capture-phase key controller.
  let pathEditor: PathEditor | null = null

  const rowContext: RowContext = {
    persistSettings: () => persistSettings(),
    setPathEditor: (editor: PathEditor | null) => {
      pathEditor = editor
    },
  }

  /** Persist settings immediately after every change.
   *
   * They used to save only through closeSettings (the Back button / Enter), so
   * toggling something and then dismissing the window — pressing the keybind
   * again, switching apps — silently discarded the change. That read as "the
   * cursor toggle does nothing": the screenshot kept using the old value.
   */
  function persistSettings(): void {
    const error = settingsStore.save(settingsConfig)
    if (settingsError) {
      settingsError.set_label(error ?? "")
      settingsError.visible = error !== null
    }
  }

  function refreshBackendReadout() {
    const readout = backendReadout
    // The probe, the spawn and the `?? "none"` fallback are the adapter's
    // (A5). All that is left here is rendering. Note the `readout ===` re-check:
    // settings can be rebuilt while the probe is in flight, and a stale label
    // would outlive its view.
    backendProbe
      .backend()
      .then((name) => {
        if (readout !== null && readout === backendReadout) {
          readout.set_label(name === "none" ? "Automatic (unavailable)" : `Automatic (${name})`)
        }
      })
      .catch(() => {
        if (readout !== null && readout === backendReadout) readout.set_label("Automatic")
      })
  }

  function renderSettings() {
    if (settingsBody === null) return
    settingsConfig = settingsStore.load()
    clearChildren(settingsBody)
    if (settingsError) {
      settingsError.set_label("")
      settingsError.visible = false
    }

    const general = settingsGroup("General", [
      pathRow(
        "Screenshot folder",
        "Where saved screenshots go",
        () => settingsConfig.screenshot_dir,
        (value) => {
          settingsConfig.screenshot_dir = value
        },
        rowContext,
      ),
      pathRow(
        "Recording folder",
        "Where finished recordings go",
        () => settingsConfig.recording_dir,
        (value) => {
          settingsConfig.recording_dir = value
        },
        rowContext,
      ),
      pathRow(
        "Filename pattern",
        "Timestamp tokens are expanded at capture time",
        () => settingsConfig.filename_pattern,
        (value) => {
          settingsConfig.filename_pattern = value
        },
        rowContext,
      ),
      toggleRow(
        "Show notifications",
        null,
        () => settingsConfig.notifications,
        (value) => {
          settingsConfig.notifications = value
        },
        rowContext,
      ),
      toggleRow(
        "Compact bar indicator",
        "Bar shows only the timer; pause/stop appear in the popup. Off: the bar shows the buttons and opens no popup.",
        () => settingsConfig.bar_compact_controls,
        (value) => {
          settingsConfig.bar_compact_controls = value
        },
        rowContext,
      ),
    ])

    const screenshotGroup = settingsGroup("Screenshot", [
      pillRow<ConfigScreenshotFormat>(
        "Default format",
        [
          { label: "PNG", value: "png" },
          { label: "JPEG", value: "jpeg" },
        ],
        () => settingsConfig.screenshot.format,
        (value) => {
          settingsConfig.screenshot.format = value
        },
        rowContext,
      ),
      pillRow<ConfigScreenshotOutput>(
        "Default output",
        [
          { label: "Clipboard", value: "clipboard" },
          { label: "Save", value: "save" },
        ],
        () => settingsConfig.screenshot.output,
        (value) => {
          settingsConfig.screenshot.output = value
        },
        rowContext,
      ),
      toggleRow(
        "Include cursor",
        "Draw the pointer into the shot",
        () => settingsConfig.screenshot.cursor,
        (value) => {
          settingsConfig.screenshot.cursor = value
        },
        rowContext,
      ),
    ])

    backendReadout = new Gtk.Label({ label: "Automatic", halign: Gtk.Align.END })
    backendReadout.add_css_class("settings-readout")
    const recordingGroup = settingsGroup("Recording", [
      pillRow<ConfigRecordingFps>(
        "Default frame rate",
        [
          { label: "24", value: 24 },
          { label: "30", value: 30 },
          { label: "60", value: 60 },
        ],
        () => settingsConfig.recording.fps,
        (value) => {
          settingsConfig.recording.fps = value
        },
        rowContext,
      ),
      pillRow<ConfigRecordingQuality>(
        "Default quality",
        [
          { label: "Low", value: "low" },
          { label: "Medium", value: "medium" },
          { label: "High", value: "high" },
        ],
        () => settingsConfig.recording.quality,
        (value) => {
          settingsConfig.recording.quality = value
        },
        rowContext,
      ),
      pillRow<ConfigRecordingAudio>(
        "Default audio",
        [
          { label: "None", value: "none" },
          { label: "System", value: "system" },
          { label: "Mic", value: "mic" },
        ],
        () => settingsConfig.recording.audio,
        (value) => {
          settingsConfig.recording.audio = value
        },
        rowContext,
      ),
      toggleRow(
        "Include cursor",
        "Draw the pointer into the recording",
        () => settingsConfig.recording.cursor,
        (value) => {
          settingsConfig.recording.cursor = value
        },
        rowContext,
      ),
      settingsItem(
        "Recorder backend",
        "Chosen automatically after detection",
        backendReadout,
      ),
    ])

    settingsBody.append(general)
    settingsBody.append(screenshotGroup)
    settingsBody.append(recordingGroup)
    refreshBackendReadout()
  }

  // Named `closeSettings` (not `close`) because the moved JSX below wires this
  // straight to the Back button; renaming the binding would have meant editing
  // a JSX line, and no JSX line may change.
  function closeSettings(): boolean {
    const error = settingsStore.save(settingsConfig)
    if (error !== null) {
      if (settingsError) {
        settingsError.set_label(error)
        settingsError.visible = true
      }
      return false
    }
    // Save applies forward: mode selections stay exactly as they were.
    selectMode(mode)
    return true
  }

  function commitPathEditor(): boolean {
    if (pathEditor === null) return false
    pathEditor.commit()
    pathEditor = null
    return true
  }

  function cancelPathEditor(): boolean {
    if (pathEditor === null) return false
    pathEditor.cancel()
    pathEditor = null
    return true
  }

  setHandle({
    setVisible: (visible: boolean) => {
      if (settingsView) settingsView.visible = visible
    },
    render: () => renderSettings(),
    close: closeSettings,
    commitPathEditor,
    cancelPathEditor,
  })

  return (
        <box
          visible={false}
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
          $={(self) => {
            settingsView = self
          }}
        >
          <box class="settings-page" orientation={Gtk.Orientation.VERTICAL} spacing={12}>
            <label
              class="settings-title"
              label="Capture settings"
              halign={Gtk.Align.START}
            />
            <box
              orientation={Gtk.Orientation.VERTICAL}
              spacing={0}
              $={(self) => {
                settingsBody = self
              }}
            ></box>
            <label
              visible={false}
              class="settings-error"
              wrap
              halign={Gtk.Align.START}
              $={(self) => {
                settingsError = self
              }}
            />
          </box>
          <box class="panel-footer" spacing={8}>
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="back  ·" />
              <label class="kbd" label="Enter" />
              <label class="footer-note" label="save" />
            </box>
            <box hexpand halign={Gtk.Align.END}>
              <button class="ghost" label="Back" onClicked={closeSettings} />
            </box>
          </box>
        </box>
)
}
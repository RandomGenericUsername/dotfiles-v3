// ---------------------------------------------------------------------------
// CLASSIC LAYOUT — the window shell (design.md §2, task 8.1).
//
// Split out of the pre-split `ui/CaptureWindow.tsx` with NO behavioural
// change. What stayed here is what the three pages cannot own: the window
// itself, the `centerbox` + `capture-panel` wrapper, the mode switch, the
// capture-phase key controller, the `map` handler, `syncWindowSize()`, the
// capture actions and the view switch.
//
// The JSX that stayed is a byte-for-byte move of that file's lines 712-804 and
// 1573-1584; the three page subtrees are rendered by `./ScreenshotPage.tsx`,
// `./RecordingPage.tsx` and `./SettingsPage.tsx`, which were moved out of it
// unchanged. Do not re-indent what is left.
//
// ---------------------------------------------------------------------------
// Settings config (add-capture-settings): the app-owned
// `$XDG_CONFIG_HOME/capture-tool/config.json` contract (design.md §1/§3).
//
// The GUI owns writes; the backend reads on every invocation. Reads are always
// safe: missing is first-run (silent defaults), corrupt degrades to defaults
// with a loud log.
//
// Split three ways as of A5. The vocabulary, defaults, merge and validation
// are pure and live in `domain/settings.ts` (A3). The `GLib.file_*` /
// `mkdir_with_parents` persistence and the `expandDir` Environment live in
// `adapters/glib-settings-store.ts` (A5). What remains HERE is the port type
// in `ports/settings-store.ts` and, below, the calls into the injected store.
// The view no longer knows the config lives in a file at all. (The settings
// DRAFT moved to `./SettingsPage.tsx` with the three groups in A8; this file
// still reads the config, for the settings→defaults precedence rule.)
// ---------------------------------------------------------------------------

import { Astal, Gdk, Gtk } from "ags/gtk4"
import { recordingArgs, screenshotArgs } from "../../domain/cli-args"
import type { RecordingRequest, ScreenshotRequest } from "../../domain/capture-request"
import {
  configDefaults,
  durationSelection,
  type UiState,
} from "../../domain/ui-state"
import type { CapturePorts } from "../../ports/capture-ports"
import type {
  AudioSource,
  CaptureTarget,
  GifScale,
  RecordingFormat,
  RecordingQuality,
  ScreenshotFormat,
} from "../../types"
import { applyGroup } from "../shared/groups"
import { withIcon } from "../shared/icons"
import {
  RecordingPage,
  type RecordingPageHandle,
} from "./RecordingPage"
import {
  ScreenshotPage,
  type ScreenshotPageHandle,
} from "./ScreenshotPage"
import {
  SettingsPage,
  type SettingsPageHandle,
} from "./SettingsPage"

type Mode = "screenshot" | "recording"
type View = Mode | "settings"

// ---------------------------------------------------------------------------
// Persisted UI state (GUI-local JSON; no provisioning surface).
//
// The state shape, first-run constants, option vocabularies, the
// settings→defaults precedence rule and the merge all live in
// `domain/ui-state.ts` (A3). The read, the write and the
// missing-is-silent / corrupt-is-loud degradation live in
// `adapters/glib-ui-state-store.ts` (A5), behind `ports/ui-state-store.ts`.
// The calls are the only trace of persistence left in this file.
// ---------------------------------------------------------------------------

// The name is the window's PUBLIC identity, and it is deliberately NOT unique:
// `style.css` selects the surface with `window#capture-window` (a GTK id
// selector, which matches the widget NAME, not the class) and the provisioned
// launcher `capture-ui.j2` runs `ags toggle capture-window -i capture`. Both
// hard-code this string, so a per-monitor rename is not a local edit: it needs a
// stylesheet change AND a provisioning run. See
// openspec/changes/fix-capture-window-identity/design.md for the full blast
// radius and for why nothing in this file is allowed to depend on it.
//
// What this file used to do instead: resolve "my own window" through
// `app.get_window(WINDOW_NAME)`. `app.tsx` builds one window per monitor and
// every one of them carries this name, and AGS resolves the name with
// `windows.find(...)` over GTK's own window list — so the answer was whichever
// duplicate GTK happened to list first, a value that CHANGES as windows are
// mapped and unmapped (measured live: `B,A` before any map, `A,B` after window
// A had mapped and unmapped). Hiding "the window called capture-window" is
// therefore not the same thing as hiding THIS window, and with two windows it is
// demonstrably the wrong one.
const WINDOW_NAME = "capture-window"

// The return type is annotated because the JSX runtime's inferred element type
// widens to `Object`, which `app.add_window` rejects. `<window>` maps to
// Astal.Window (see ags/gtk4/jsx-runtime), so the annotation names the real
// type; see the cast on the return below for why TS cannot infer it.
//
// `ports` (design.md §2, task 5.9) is the injected hexagon: settings
// persistence, UI-state persistence, capture launching and the backend probe.
// `state` is the ONE live UI state, also injected by the composition root and
// SHARED by every window it builds — the state belongs to the app, not to a
// window, and a window that allocated its own would be a second writer to the
// same `capture-ui.json`. Both are required parameters on purpose: a window
// cannot be constructed without being told which state it mutates.
// The composition root builds the adapters and passes them in, so this file
// contains no filesystem access and no process spawning — only calls into
// interfaces it was handed.
export function ClassicWindow(
  gdkmonitor: Gdk.Monitor,
  ports: CapturePorts,
  state: UiState,
): Astal.Window {
  const { settingsStore, uiStateStore, launcher } = ports

  let mode: Mode = "screenshot"

  // THIS window, captured from its own `<window>` `$` handler rather than
  // looked up by name. It is per-CALL, not per-module: `app.tsx` builds one
  // window per monitor and they must not share it, or the second construction
  // would overwrite the first window's self-reference and the defect this
  // replaces would come straight back (measured: that exact mistake — a
  // module-level `let` — was made and caught, see
  // openspec/changes/fix-capture-window-identity/design.md §"The bug I wrote
  // first").
  //
  // Null until gnim runs that handler, and gnim runs it AFTER the children are
  // appended (jsx.ts evaluates the child array before constructing the parent,
  // then calls `$` last). So `syncWindowSize()` invoked from a child's own `$`
  // handler still no-ops — exactly as it did when the name lookup returned
  // `undefined` because the window had not been added to the app yet. Same
  // early-return, same reason, no behaviour change on the one-window path.
  let captureWindow: Astal.Window | null = null

  function hideCaptureWindow() {
    // The window whose button was pressed is the only window that may be
    // hidden; every other window is left exactly as it was found.
    if (captureWindow) captureWindow.visible = false
  }

  /**
   * Re-assert the layer surface size after a view switch.
   *
   * GTK does not shrink a layer-shell surface when its content gets shorter:
   * measured live, the surface stayed 718px tall after returning to the 590px
   * screenshot view, so the panel ended up glued to the top of a too-tall
   * transparent window.
   *
   * Deliberately SYNCHRONOUS (no idle callback): deferring the size change made
   * GTK paint an intermediate frame with the new, shorter content still inside
   * the OLD surface, and the panel's clipped shadow in that leftover area read
   * as a rectangle trailing the window. Measuring and resizing in the same turn
   * lets GTK resize and repaint atomically. GTK's measure() recomputes on
   * demand, so the visibility changes made just before this are already
   * reflected.
   */
  function syncWindowSize() {
    // Scoped to THIS window for the same reason as `hideCaptureWindow()`: a
    // name lookup resized whichever duplicate GTK listed first, so a view
    // switch on one monitor left that window at the old height and silently grew
    // another one.
    const window = captureWindow
    const panel = window?.get_child()
    if (!window || !panel) return
    const [, width] = panel.measure(Gtk.Orientation.HORIZONTAL, -1)
    const [, height] = panel.measure(Gtk.Orientation.VERTICAL, width)
    window.set_default_size(width, height)
  }

  let screenshotTab: Gtk.Button | null = null
  let recordingTab: Gtk.Button | null = null

  // The mode switch, and the three top-level views. A third top-level view
  // (settings) replaces the mode switch + mode views while open; the pages
  // hold their own containers and publish them through these handles, because
  // the `$` handlers that assign them moved with the JSX.
  let modeSwitch: Gtk.Box | null = null
  let screenshotPage: ScreenshotPageHandle | null = null
  let recordingPage: RecordingPageHandle | null = null
  let settingsPage: SettingsPageHandle | null = null
  let view: View = "screenshot"

  // Live UI state, INJECTED (fix-capture-per-monitor-state). The composition
  // root builds one state and passes the SAME object to every window it
  // creates, because the state is per-application: one `capture-ui.json`, one
  // precedence chain, one set of last-used selections. A window that allocated
  // its own copy would be a second owner of that value, and the two copies
  // would diverge the moment either was mutated — with the last `save()` to
  // run silently discarding the other's selection.
  //
  // Still MUTATED IN PLACE, never rebound — the three pages were handed these
  // exact objects when they were constructed, so a rebind would leave every
  // page mutating an object the window had already replaced. The store's merge
  // always returns every field, so `Object.assign` below lands the same key
  // set, and the same values, a rebind would have.
  const { screenshot, recording } = state

  // Button groups carry their value so persisted state can re-select them.
  const screenshotTargetGroup: Array<{ value: CaptureTarget; button: Gtk.Button }> = []
  const screenshotDelayGroup: Array<{ value: number; button: Gtk.Button }> = []
  const screenshotFormatGroup: Array<{ value: ScreenshotFormat; button: Gtk.Button }> = []
  const screenshotOutputGroup: Array<{ value: boolean; button: Gtk.Button }> = []
  const recordingTargetGroup: Array<{ value: CaptureTarget; button: Gtk.Button }> = []
  const recordingFpsGroup: Array<{ value: number; button: Gtk.Button }> = []
  const recordingGifFpsGroup: Array<{ value: number; button: Gtk.Button }> = []
  const recordingFormatGroup: Array<{ value: RecordingFormat; button: Gtk.Button }> = []
  const recordingAudioGroup: Array<{ value: AudioSource; button: Gtk.Button }> = []
  const recordingQualityGroup: Array<{ value: RecordingQuality; button: Gtk.Button }> = []
  // Duration: 0/10/30/60 seconds, -1 = custom (editor value in `recording`).
  const recordingDurationGroup: Array<{ value: number; button: Gtk.Button }> = []
  const recordingSizeGroup: Array<{ value: GifScale; button: Gtk.Button }> = []

  function selectMode(next: Mode) {
    mode = next
    view = next
    // Leaving settings must restore the mode switch: openSettings() hides it,
    // and without this the whole tab row (Screenshot + Recording) stayed
    // hidden for the rest of the session after one visit to settings.
    if (modeSwitch) modeSwitch.visible = true
    if (settingsPage) settingsPage.setVisible(false)
    const screenshotSelected = next === "screenshot"
    if (screenshotPage) screenshotPage.setVisible(screenshotSelected)
    if (recordingPage) recordingPage.setVisible(!screenshotSelected)
    if (screenshotTab) {
      screenshotTab.remove_css_class("active")
      if (screenshotSelected) screenshotTab.add_css_class("active")
    }
    if (recordingTab) {
      recordingTab.remove_css_class("active")
      recordingTab.remove_css_class("record")
      if (!screenshotSelected) {
        recordingTab.add_css_class("active")
        recordingTab.add_css_class("record")
      }
    }
    // Views differ in height; the surface must shrink as well as grow.
    syncWindowSize()
  }

  function takeScreenshot() {
    uiStateStore.save(screenshot, recording)
    const config = settingsStore.load()
    // Build the request, then TRANSLATE it. The argv vocabulary -- including
    // the `--size 75` (not `75%`) and `--audio mic` (not `microphone`) traps --
    // belongs to `domain/cli-args.ts` (A6), the one module that owns it, so the
    // next layout shares it instead of re-deriving it here.
    const request: ScreenshotRequest = {
      target: screenshot.target,
      delay: screenshot.delay,
      format: screenshot.format,
      // The backend owns the default save path (config dir + pattern); the
      // clipboard default is preserved unless Save was chosen.
      save: screenshot.save,
      cursor: config.screenshot.cursor,
    }
    hideCaptureWindow()
    // The 150ms hide-then-spawn delay lives in the launcher (A5), not here:
    // it is a compositor fact, so a second layout inherits it for free.
    launcher.launch(screenshotArgs(request))
  }

  function startRecording() {
    uiStateStore.save(screenshot, recording)
    const config = settingsStore.load()
    // Same seam as takeScreenshot: the GIF fps branch, the `--size` scale
    // mapping and the `microphone`→`mic` conversion are the translator's, not
    // the view's.
    const request: RecordingRequest = {
      target: recording.target,
      fps: recording.fps,
      gifFps: recording.gifFps,
      format: recording.format,
      audio: recording.audio,
      quality: recording.quality,
      duration: recording.duration,
      size: recording.size,
      cursor: config.recording.cursor,
    }
    hideCaptureWindow()
    launcher.launch(recordingArgs(request))
  }

  function onKey(keyval: number): boolean {
    if (keyval === Gdk.KEY_Escape) {
      // An open inline path editor owns Escape (cancel the edit).
      if (view === "settings" && settingsPage !== null && settingsPage.cancelPathEditor()) {
        return true
      }
      // Hierarchy: settings → mode view → hide window.
      if (view === "settings") closeSettings()
      else hideCaptureWindow()
      return true
    }
    if (keyval === Gdk.KEY_Return || keyval === Gdk.KEY_KP_Enter) {
      // An open inline path editor owns Enter (commit the edit).
      if (view === "settings" && settingsPage !== null && settingsPage.commitPathEditor()) {
        return true
      }
      if (view === "settings") closeSettings()
      else if (mode === "screenshot") takeScreenshot()
      else startRecording()
      return true
    }
    return false
  }

  function applyStateToUi() {
    // Last-used UI state > settings defaults > hardcoded constants.
    const state = uiStateStore.load(configDefaults(settingsStore.load()))
    Object.assign(screenshot, state.screenshot)
    Object.assign(recording, state.recording)
    applyGroup(screenshotTargetGroup, screenshot.target)
    applyGroup(screenshotDelayGroup, screenshot.delay)
    applyGroup(screenshotFormatGroup, screenshot.format)
    applyGroup(screenshotOutputGroup, screenshot.save)
    applyGroup(recordingTargetGroup, recording.target)
    applyGroup(recordingFpsGroup, recording.fps)
    applyGroup(recordingGifFpsGroup, recording.gifFps)
    applyGroup(recordingFormatGroup, recording.format)
    applyGroup(recordingAudioGroup, recording.audio)
    applyGroup(recordingQualityGroup, recording.quality)
    applyGroup(recordingDurationGroup, durationSelection(recording))
    applyGroup(recordingSizeGroup, recording.size)
    // The custom-duration spin write and the GIF/duration conditional rows
    // belong to the recording page (task 8.3), and it applies them here so the
    // order — groups, then spin, then conditional rows — is unchanged.
    if (recordingPage) recordingPage.applyState()
  }

  function openSettings() {
    view = "settings"
    if (modeSwitch) modeSwitch.visible = false
    if (screenshotPage) screenshotPage.setVisible(false)
    if (recordingPage) recordingPage.setVisible(false)
    if (settingsPage) {
      settingsPage.setVisible(true)
      settingsPage.render()
    }
    // Settings is the tallest view; the surface must grow to fit it.
    syncWindowSize()
  }

  function closeSettings() {
    // The draft, the error label and the save live in the settings page (task
    // 8.4); it reports whether the draft made it to disk. On success it has
    // already returned to the mode view.
    if (settingsPage !== null && !settingsPage.close()) return
    // Save applies forward: mode selections stay exactly as they were.
    selectMode(mode)
  }

  return (
    <window
      visible={false}
      name="capture-window"
      class="capture-window"
      namespace="capture"
      gdkmonitor={gdkmonitor}
      // NONE, not 0. `Astal.WindowAnchor` is a bitfield with no zero member
      // (NONE=1, TOP=2, RIGHT=4, LEFT=8, BOTTOM=16), so the bare literal was
      // never a valid value. It anchored to no edge, and so does NONE:
      // astal_window_set_anchor() reads only bits 1/2/3/4 and never tests bit 0,
      // so 0 and NONE both hand gtk_layer_shell four anchored=false edges.
      // Behaviour is identical; only the type is now honest.
      anchor={Astal.WindowAnchor.NONE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      halign={Gtk.Align.CENTER}
      valign={Gtk.Align.CENTER}
      $={(self) => {
        // gnim calls this with the constructed Astal.Window, AFTER the children
        // are appended — which is exactly when a name lookup would have started
        // working too (the window is added to the app by the caller). Capturing
        // it here is what makes `hideCaptureWindow()` / `syncWindowSize()` mean
        // "this window" instead of "a window with my name".
        captureWindow = self
        // Capture phase so Enter/Escape fire even when a pill has focus.
        const keys = new Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", (_controller, keyval, _keycode, _state) => onKey(keyval))
        self.add_controller(keys)
        // Re-read persisted choices on every show so the window reflects
        // captures that happened while it was hidden.
        self.connect("map", () => {
          applyStateToUi()
          // ON_DEMAND (like hypr-pano) never steals the keyboard from other
          // AGS windows; present() asks the compositor to focus on show.
          self.present()
        })
      }}
    >
      {/* CenterBox, not a Box. The window allocates its whole area to its
          direct child, and a GtkBox ignores a child's main-axis alignment
          (verified live: panel allocated 950 while its own content was 590), so
          the panel still stretched to the stale surface size and painted its
          background as a rectangle below the content during a view switch.
          CenterBox centres its centre widget by construction, so the panel
          keeps its natural size and the leftover area stays transparent. */}
      <centerbox class="capture-root">
        <box
          $type="center"
          class="capture-panel"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
        >
        <box
          class="mode-switch"
          homogeneous
          spacing={0}
          $={(self) => {
            modeSwitch = self
          }}
        >
          <button
            class="active"
            $={(self) => {
              screenshotTab = self
              selectMode("screenshot")
            }}
            onClicked={() => selectMode("screenshot")}
          >
            <box
              orientation={Gtk.Orientation.HORIZONTAL}
              spacing={9}
              halign={Gtk.Align.CENTER}
              valign={Gtk.Align.CENTER}
              $={withIcon("camera", 18)}
            >
              <label label="Screenshot" />
            </box>
          </button>
          <button
            $={(self) => {
              recordingTab = self
            }}
            onClicked={() => selectMode("recording")}
          >
            <box
              orientation={Gtk.Orientation.HORIZONTAL}
              spacing={9}
              halign={Gtk.Align.CENTER}
              valign={Gtk.Align.CENTER}
              $={withIcon("video", 18)}
            >
              <label label="Recording" />
            </box>
          </button>
        </box>

        {/* ------------------------------------------------ Screenshot view */}
        <ScreenshotPage
          screenshot={screenshot}
          screenshotTargetGroup={screenshotTargetGroup}
          screenshotDelayGroup={screenshotDelayGroup}
          screenshotFormatGroup={screenshotFormatGroup}
          screenshotOutputGroup={screenshotOutputGroup}
          takeScreenshot={takeScreenshot}
          openSettings={openSettings}
          setHandle={(handle) => {
            screenshotPage = handle
          }}
        />

        {/* ------------------------------------------------ Recording view */}
        <RecordingPage
          recording={recording}
          recordingTargetGroup={recordingTargetGroup}
          recordingFpsGroup={recordingFpsGroup}
          recordingGifFpsGroup={recordingGifFpsGroup}
          recordingFormatGroup={recordingFormatGroup}
          recordingAudioGroup={recordingAudioGroup}
          recordingQualityGroup={recordingQualityGroup}
          recordingDurationGroup={recordingDurationGroup}
          recordingSizeGroup={recordingSizeGroup}
          startRecording={startRecording}
          openSettings={openSettings}
          syncWindowSize={syncWindowSize}
          setHandle={(handle) => {
            recordingPage = handle
          }}
        />

        {/* ------------------------------------------------ Settings view */}
        <SettingsPage
          settingsStore={settingsStore}
          backendProbe={ports.backendProbe}
          selectMode={selectMode}
          mode={mode}
          setHandle={(handle) => {
            settingsPage = handle
          }}
        />
        </box>
      </centerbox>
    </window>
    // Type-level only. gnim types every intrinsic element as `CC | FC`, i.e.
    // a constructor yielding `GObject.Object`, so the JSX expression widens to
    // `GObject.Object` no matter which tag is used — gnim's own source says
    // "intrinsicElements always resolve as FC / so we can't narrow it down".
    // `<window>` really is an Astal.Window (ags/gtk4/jsx-runtime maps it), so
    // this cast records a fact rather than hiding a bug. Nothing at runtime
    // changes: `jsx()` already called `new Astal.Window(props)`.
  ) as unknown as Astal.Window
}

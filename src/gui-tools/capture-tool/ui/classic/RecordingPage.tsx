// ---------------------------------------------------------------------------
// CLASSIC LAYOUT — the recording view (design.md §2, task 8.3).
//
// Split out of the pre-split `ui/CaptureWindow.tsx` with NO behavioural
// change: the JSX below is a byte-for-byte move of that file's lines 1033-1526,
// leading indentation included, so the rendered widget tree is unchanged and
// `git diff -M` shows a move rather than an edit. Do not re-indent it.
//
// This page also owns what only the recording view has: the GIF-conditional
// rows (audio / frame rate / size) and both footers, `applyGifMode()`, and the
// custom-duration spin editor. `syncWindowSize()` is injected rather than
// imported so this page has no edge back to the window module.
// ---------------------------------------------------------------------------

import { Gtk } from "ags/gtk4"
import { select } from "../shared/groups"
import { withIcon } from "../shared/icons"
import { durationSelection, isGif, type RecordingUiState } from "../../domain/ui-state"
import type { AudioSource, CaptureTarget, GifScale, RecordingFormat, RecordingQuality } from "../../types"

/**
 * What the window needs back from this page.
 *
 * The view container and the conditional rows are page-local `let`s (the JSX
 * below assigns them in the `$` handlers, unchanged), so the window reaches
 * them through this handle rather than through shared mutable cells.
 */
export interface RecordingPageHandle {
  setVisible: (visible: boolean) => void
  /**
   * Re-assert the recording view's derived state after the window loaded the
   * persisted UI state. Scoped to the spin write on purpose: it is the only
   * statement that can emit `value-changed`, and `applyingState` existed to
   * suppress exactly that feedback loop.
   */
  applyState: () => void
}

export interface RecordingPageProps {
  /** Live selection state. Mutated in place by the page's own handlers. */
  recording: RecordingUiState
  /** Groups carry their value so persisted state can re-select them. */
  recordingTargetGroup: Array<{ value: CaptureTarget; button: Gtk.Button }>
  recordingFpsGroup: Array<{ value: number; button: Gtk.Button }>
  recordingGifFpsGroup: Array<{ value: number; button: Gtk.Button }>
  recordingFormatGroup: Array<{ value: RecordingFormat; button: Gtk.Button }>
  recordingAudioGroup: Array<{ value: AudioSource; button: Gtk.Button }>
  recordingQualityGroup: Array<{ value: RecordingQuality; button: Gtk.Button }>
  /** 0/10/30/60 seconds, -1 = custom (editor value in `recording`). */
  recordingDurationGroup: Array<{ value: number; button: Gtk.Button }>
  recordingSizeGroup: Array<{ value: GifScale; button: Gtk.Button }>
  startRecording: () => void
  openSettings: () => void
  /** Re-assert the layer surface size (the window owns the window handle). */
  syncWindowSize: () => void
  setHandle: (handle: RecordingPageHandle) => void
}

export function RecordingPage(props: RecordingPageProps) {
  const {
    recording,
    recordingTargetGroup,
    recordingFpsGroup,
    recordingGifFpsGroup,
    recordingFormatGroup,
    recordingAudioGroup,
    recordingQualityGroup,
    recordingDurationGroup,
    recordingSizeGroup,
    startRecording,
    openSettings,
    syncWindowSize,
    setHandle,
  } = props

  let recordingView: Gtk.Box | null = null

  // GIF-mode conditional rows.
  let audioRow: Gtk.Box | null = null
  let stdFpsRow: Gtk.Box | null = null
  let gifFpsRow: Gtk.Box | null = null
  let sizeRow: Gtk.Box | null = null
  let recFooterStd: Gtk.Box | null = null
  let recFooterGif: Gtk.Box | null = null

  // Custom-duration inline editor.
  let customBox: Gtk.Box | null = null
  let customSpin: Gtk.SpinButton | null = null
  let applyingState = false

  function applyGifMode() {
    const gif = isGif(recording)
    if (audioRow) audioRow.visible = !gif
    if (stdFpsRow) stdFpsRow.visible = !gif
    if (gifFpsRow) gifFpsRow.visible = gif
    if (sizeRow) sizeRow.visible = gif
    if (recFooterStd) recFooterStd.visible = !gif
    if (recFooterGif) recFooterGif.visible = gif
    // Swapping audio for size changes the height, so the surface must follow.
    syncWindowSize()
  }

  function refreshCustomBox() {
    if (customBox) customBox.visible = durationSelection(recording) === -1
  }

  function setRecordingFormat(format: RecordingFormat, button: Gtk.Button) {
    recording.format = format
    select(button, recordingFormatGroup.map((entry) => entry.button))
    applyGifMode()
  }

  function applyState() {
    applyingState = true
    try {
      if (customSpin) customSpin.set_value(recording.customDuration)
      applyGifMode()
      refreshCustomBox()
    } finally {
      applyingState = false
    }
  }

  setHandle({
    setVisible: (visible: boolean) => {
      if (recordingView) recordingView.visible = visible
    },
    applyState,
  })

  return (
        <box
          visible={false}
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
          $={(self) => {
            recordingView = self
          }}
        >
          <box class="settings" orientation={Gtk.Orientation.VERTICAL} spacing={15}>
            <box class="setting-block" orientation={Gtk.Orientation.VERTICAL} spacing={0}>
              <label class="setting-label" label="CAPTURE TARGET" halign={Gtk.Align.START} />
              <box class="targets" homogeneous spacing={9}>
                <button
                  class="target selected"
                  $={(self) => recordingTargetGroup.push({ value: "region", button: self })}
                  onClicked={(self) => {
                    recording.target = "region"
                    select(self, recordingTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("region", 24)}
                  >
                    <label label="Region" />
                  </box>
                </button>
                <button
                  class="target"
                  $={(self) => recordingTargetGroup.push({ value: "screen", button: self })}
                  onClicked={(self) => {
                    recording.target = "screen"
                    select(self, recordingTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("monitor", 24)}
                  >
                    <label label="Screen" />
                  </box>
                </button>
                <button
                  class="target"
                  $={(self) => recordingTargetGroup.push({ value: "window", button: self })}
                  onClicked={(self) => {
                    recording.target = "window"
                    select(self, recordingTargetGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.VERTICAL}
                    spacing={8}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("window", 24)}
                  >
                    <label label="Window" />
                  </box>
                </button>
              </box>
            </box>

            <box
              class="setting-row"
              spacing={14}
              $={(self) => {
                stdFpsRow = self
              }}
            >
              <label
                class="setting-label"
                label="FRAME RATE"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment"
                  label="24"
                  $={(self) => recordingFpsGroup.push({ value: 24, button: self })}
                  onClicked={(self) => {
                    recording.fps = 24
                    select(self, recordingFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="30"
                  $={(self) => recordingFpsGroup.push({ value: 30, button: self })}
                  onClicked={(self) => {
                    recording.fps = 30
                    select(self, recordingFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment selected"
                  label="60"
                  $={(self) => recordingFpsGroup.push({ value: 60, button: self })}
                  onClicked={(self) => {
                    recording.fps = 60
                    select(self, recordingFpsGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>
            <box
              visible={false}
              class="setting-row"
              spacing={14}
              $={(self) => {
                gifFpsRow = self
              }}
            >
              <label
                class="setting-label"
                label="FRAME RATE"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment"
                  label="10"
                  $={(self) => recordingGifFpsGroup.push({ value: 10, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 10
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment selected"
                  label="15"
                  $={(self) => recordingGifFpsGroup.push({ value: 15, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 15
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="20"
                  $={(self) => recordingGifFpsGroup.push({ value: 20, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 20
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="30"
                  $={(self) => recordingGifFpsGroup.push({ value: 30, button: self })}
                  onClicked={(self) => {
                    recording.gifFps = 30
                    select(self, recordingGifFpsGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>


            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="FORMAT"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="MP4"
                  $={(self) => recordingFormatGroup.push({ value: "mp4", button: self })}
                  onClicked={(self) => setRecordingFormat("mp4", self)}
                />
                <button
                  class="segment"
                  label="WebM"
                  $={(self) => recordingFormatGroup.push({ value: "webm", button: self })}
                  onClicked={(self) => setRecordingFormat("webm", self)}
                />
                <button
                  class="segment"
                  label="GIF"
                  $={(self) => recordingFormatGroup.push({ value: "gif", button: self })}
                  onClicked={(self) => setRecordingFormat("gif", self)}
                />
              </box>
            </box>

            <box
              class="setting-row"
              spacing={14}
              $={(self) => {
                audioRow = self
              }}
            >
              <label
                class="setting-label"
                label="AUDIO"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  $={(self) => recordingAudioGroup.push({ value: "system", button: self })}
                  onClicked={(self) => {
                    recording.audio = "system"
                    select(self, recordingAudioGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("speaker", 15)}
                  >
                    <label label="System" />
                  </box>
                </button>
                <button
                  class="segment"
                  $={(self) => recordingAudioGroup.push({ value: "microphone", button: self })}
                  onClicked={(self) => {
                    recording.audio = "microphone"
                    select(self, recordingAudioGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("mic", 15)}
                  >
                    <label label="Mic" />
                  </box>
                </button>
                <button
                  class="segment"
                  label="None"
                  $={(self) => recordingAudioGroup.push({ value: "none", button: self })}
                  onClicked={(self) => {
                    recording.audio = "none"
                    select(self, recordingAudioGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box
              visible={false}
              class="setting-row"
              spacing={14}
              $={(self) => {
                sizeRow = self
              }}
            >
              <label
                class="setting-label"
                label="SIZE"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="Original"
                  $={(self) => recordingSizeGroup.push({ value: "original", button: self })}
                  onClicked={(self) => {
                    recording.size = "original"
                    select(self, recordingSizeGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="75%"
                  $={(self) => recordingSizeGroup.push({ value: "75%", button: self })}
                  onClicked={(self) => {
                    recording.size = "75%"
                    select(self, recordingSizeGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="50%"
                  $={(self) => recordingSizeGroup.push({ value: "50%", button: self })}
                  onClicked={(self) => {
                    recording.size = "50%"
                    select(self, recordingSizeGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="QUALITY"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment"
                  label="Low"
                  $={(self) => recordingQualityGroup.push({ value: "low", button: self })}
                  onClicked={(self) => {
                    recording.quality = "low"
                    select(self, recordingQualityGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="Medium"
                  $={(self) => recordingQualityGroup.push({ value: "medium", button: self })}
                  onClicked={(self) => {
                    recording.quality = "medium"
                    select(self, recordingQualityGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment selected"
                  label="High"
                  $={(self) => recordingQualityGroup.push({ value: "high", button: self })}
                  onClicked={(self) => {
                    recording.quality = "high"
                    select(self, recordingQualityGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="DURATION"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="∞"
                  $={(self) => recordingDurationGroup.push({ value: 0, button: self })}
                  onClicked={(self) => {
                    recording.duration = 0
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="10s"
                  $={(self) => recordingDurationGroup.push({ value: 10, button: self })}
                  onClicked={(self) => {
                    recording.duration = 10
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="30s"
                  $={(self) => recordingDurationGroup.push({ value: 30, button: self })}
                  onClicked={(self) => {
                    recording.duration = 30
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="60s"
                  $={(self) => recordingDurationGroup.push({ value: 60, button: self })}
                  onClicked={(self) => {
                    recording.duration = 60
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <button
                  class="segment"
                  label="Custom"
                  $={(self) => recordingDurationGroup.push({ value: -1, button: self })}
                  onClicked={(self) => {
                    recording.duration = recording.customDuration
                    select(self, recordingDurationGroup.map((entry) => entry.button))
                    refreshCustomBox()
                  }}
                />
                <box
                  visible={false}
                  class="custom-duration"
                  spacing={6}
                  orientation={Gtk.Orientation.HORIZONTAL}
                  valign={Gtk.Align.CENTER}
                  $={(self) => {
                    customBox = self
                    const adjustment = new Gtk.Adjustment({
                      lower: 5,
                      upper: 3600,
                      step_increment: 5,
                      page_increment: 30,
                      value: recording.customDuration,
                    })
                    customSpin = new Gtk.SpinButton({ adjustment, digits: 0 })
                    customSpin.set_halign(Gtk.Align.START)
                    customSpin.set_valign(Gtk.Align.CENTER)
                    customSpin.connect("value-changed", () => {
                      if (applyingState || customSpin === null) return
                      recording.customDuration = customSpin.get_value_as_int()
                      recording.duration = recording.customDuration
                    })
                    self.append(customSpin)
                    const unit = new Gtk.Label({ label: "sec" })
                    unit.add_css_class("footer-note")
                    self.append(unit)
                  }}
                />
              </box>
            </box>

            <button class="primary record" onClicked={startRecording}>
              <box
                orientation={Gtk.Orientation.HORIZONTAL}
                spacing={10}
                halign={Gtk.Align.CENTER}
                valign={Gtk.Align.CENTER}
              >
                <box class="record-dot" valign={Gtk.Align.CENTER} />
                <label label="Start Recording" />
              </box>
            </button>
          </box>

          <box
            class="panel-footer"
            spacing={8}
            $={(self) => {
              recFooterStd = self
            }}
          >
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="cancel" />
            </box>
            <box hexpand halign={Gtk.Align.END} spacing={10}>
              <label
                class="footer-note"
                label="Runs in the background — controls move to the bar"
                valign={Gtk.Align.CENTER}
              />
              <button class="ghost" label="Settings" onClicked={openSettings} />
            </box>
          </box>
          <box
            visible={false}
            class="panel-footer"
            spacing={8}
            $={(self) => {
              recFooterGif = self
            }}
          >
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="cancel" />
            </box>
            <box hexpand halign={Gtk.Align.END} spacing={10}>
              <label
                class="footer-note"
                label="GIF mode — audio hardware is never opened"
                valign={Gtk.Align.CENTER}
              />
              <button class="ghost" label="Settings" onClicked={openSettings} />
            </box>
          </box>
        </box>
)
}
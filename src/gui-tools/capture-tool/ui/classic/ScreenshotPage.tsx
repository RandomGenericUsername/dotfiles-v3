// ---------------------------------------------------------------------------
// CLASSIC LAYOUT — the screenshot view (design.md §2, task 8.2).
//
// Split out of the pre-split `ui/CaptureWindow.tsx` with NO behavioural
// change: the JSX below is a byte-for-byte move of that file's lines 805-1030,
// leading indentation included, so the rendered widget tree is unchanged and
// `git diff -M` shows a move rather than an edit. Do not re-indent it.
//
// Everything window-level -- the mode switch, the capture actions, the
// view-switch bookkeeping and the key controller -- stays in
// `./ClassicWindow.tsx` and arrives here as props. The segment/selection
// helper and the icon resolver come from `ui/shared/`, which every future
// layout shares (A7).
// ---------------------------------------------------------------------------

import { Gtk } from "ags/gtk4"
import { select } from "../shared/groups"
import { withIcon } from "../shared/icons"
import type { ScreenshotUiState } from "../../domain/ui-state"
import type { CaptureTarget, ScreenshotFormat } from "../../types"

/**
 * What the window needs back from this page.
 *
 * The view container is a page-local `let` (the JSX below assigns it in the
 * `$` handler, unchanged), so the window reaches it through this handle rather
 * than through a shared mutable cell. `setVisible` is exactly the
 * `if (screenshotView) screenshotView.visible = <bool>` the window used to do
 * inline.
 */
export interface ScreenshotPageHandle {
  setVisible: (visible: boolean) => void
}

export interface ScreenshotPageProps {
  /** Live selection state. Mutated in place by the page's own handlers. */
  screenshot: ScreenshotUiState
  /** Groups carry their value so persisted state can re-select them. */
  screenshotTargetGroup: Array<{ value: CaptureTarget; button: Gtk.Button }>
  screenshotDelayGroup: Array<{ value: number; button: Gtk.Button }>
  screenshotFormatGroup: Array<{ value: ScreenshotFormat; button: Gtk.Button }>
  screenshotOutputGroup: Array<{ value: boolean; button: Gtk.Button }>
  takeScreenshot: () => void
  openSettings: () => void
  setHandle: (handle: ScreenshotPageHandle) => void
}

export function ScreenshotPage(props: ScreenshotPageProps) {
  const {
    screenshot,
    screenshotTargetGroup,
    screenshotDelayGroup,
    screenshotFormatGroup,
    screenshotOutputGroup,
    takeScreenshot,
    openSettings,
    setHandle,
  } = props

  let screenshotView: Gtk.Box | null = null

  setHandle({
    setVisible: (visible: boolean) => {
      if (screenshotView) screenshotView.visible = visible
    },
  })

  return (
        <box
          visible
          class="capture-view"
          orientation={Gtk.Orientation.VERTICAL}
          spacing={0}
          $={(self) => {
            screenshotView = self
          }}
        >
          <box class="settings" orientation={Gtk.Orientation.VERTICAL} spacing={15}>
            <box class="setting-block" orientation={Gtk.Orientation.VERTICAL} spacing={0}>
              <label class="setting-label" label="CAPTURE TARGET" halign={Gtk.Align.START} />
              <box class="targets" homogeneous spacing={9}>
                <button
                  class="target selected"
                  $={(self) => screenshotTargetGroup.push({ value: "region", button: self })}
                  onClicked={(self) => {
                    screenshot.target = "region"
                    select(self, screenshotTargetGroup.map((entry) => entry.button))
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
                  $={(self) => screenshotTargetGroup.push({ value: "screen", button: self })}
                  onClicked={(self) => {
                    screenshot.target = "screen"
                    select(self, screenshotTargetGroup.map((entry) => entry.button))
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
                  $={(self) => screenshotTargetGroup.push({ value: "window", button: self })}
                  onClicked={(self) => {
                    screenshot.target = "window"
                    select(self, screenshotTargetGroup.map((entry) => entry.button))
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

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="DELAY"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  label="None"
                  $={(self) => screenshotDelayGroup.push({ value: 0, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 0
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="3s"
                  $={(self) => screenshotDelayGroup.push({ value: 3, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 3
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="5s"
                  $={(self) => screenshotDelayGroup.push({ value: 5, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 5
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="10s"
                  $={(self) => screenshotDelayGroup.push({ value: 10, button: self })}
                  onClicked={(self) => {
                    screenshot.delay = 10
                    select(self, screenshotDelayGroup.map((entry) => entry.button))
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
                  label="PNG"
                  $={(self) => screenshotFormatGroup.push({ value: "png", button: self })}
                  onClicked={(self) => {
                    screenshot.format = "png"
                    select(self, screenshotFormatGroup.map((entry) => entry.button))
                  }}
                />
                <button
                  class="segment"
                  label="JPEG"
                  $={(self) => screenshotFormatGroup.push({ value: "jpeg", button: self })}
                  onClicked={(self) => {
                    screenshot.format = "jpeg"
                    select(self, screenshotFormatGroup.map((entry) => entry.button))
                  }}
                />
              </box>
            </box>

            <box class="setting-row" spacing={14}>
              <label
                class="setting-label"
                label="OUTPUT"
                halign={Gtk.Align.START}
                valign={Gtk.Align.CENTER}
                width_request={86}
              />
              <box class="segments" homogeneous hexpand spacing={6}>
                <button
                  class="segment selected"
                  $={(self) => screenshotOutputGroup.push({ value: false, button: self })}
                  onClicked={(self) => {
                    screenshot.save = false
                    select(self, screenshotOutputGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("clipboard", 15)}
                  >
                    <label label="Clipboard" />
                  </box>
                </button>
                <button
                  class="segment"
                  $={(self) => screenshotOutputGroup.push({ value: true, button: self })}
                  onClicked={(self) => {
                    screenshot.save = true
                    select(self, screenshotOutputGroup.map((entry) => entry.button))
                  }}
                >
                  <box
                    orientation={Gtk.Orientation.HORIZONTAL}
                    spacing={7}
                    halign={Gtk.Align.CENTER}
                    valign={Gtk.Align.CENTER}
                    $={withIcon("save", 15)}
                  >
                    <label label="Save" />
                  </box>
                </button>
              </box>
            </box>

            <button class="primary" onClicked={takeScreenshot}>
              <box
                orientation={Gtk.Orientation.HORIZONTAL}
                spacing={10}
                halign={Gtk.Align.CENTER}
                valign={Gtk.Align.CENTER}
                $={withIcon("camera", 18)}
              >
                <label label="Take Screenshot" />
              </box>
            </button>
          </box>

          <box class="panel-footer" spacing={8}>
            <box spacing={4} orientation={Gtk.Orientation.HORIZONTAL}>
              <label class="kbd" label="Esc" />
              <label class="footer-note" label="cancel  ·" />
              <label class="kbd" label="Enter" />
              <label class="footer-note" label="capture" />
            </box>
            <box hexpand halign={Gtk.Align.END} spacing={10}>
              <label
                class="footer-note"
                label="Remembers your last choices"
                valign={Gtk.Align.CENTER}
              />
              <button class="ghost" label="Settings" onClicked={openSettings} />
            </box>
          </box>
        </box>
)
}
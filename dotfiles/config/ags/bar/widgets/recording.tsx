import GLib from "gi://GLib?version=2.0"
import Gio from "gi://Gio?version=2.0"
import { createEffect, createState } from "ags"
import { Gtk } from "ags/gtk4"
import { registry } from "../../lib/icon-registry"
import { domainEvents } from "../../lib/event-bus"

type RecordingState = "idle" | "recording" | "paused"

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0")
  const remainder = (seconds % 60).toString().padStart(2, "0")
  return `${minutes}:${remainder}`
}

function iconPath(variant: "pause" | "play" | "stop"): string {
  return registry.resolve("capture-tool", variant) ?? ""
}

//: The capture tool's config (app-owned; the settings view writes it).
const CAPTURE_CONFIG = `${GLib.get_user_config_dir()}/capture-tool/config.json`

/**
 * Bar feedback mode, from the capture tool's `bar_compact_controls` setting.
 *
 * compact (`true`) — the bar shows only the dot + elapsed time and the popup
 * carries pause/resume/stop (no timer there: the bar already shows it).
 * full (`false`, default) — the bar carries the buttons itself and no popup
 * opens, so nothing is duplicated.
 *
 * Read straight from the config file because the bar is a separate AGS
 * instance from the capture tool; a missing/corrupt file means "full".
 */
function loadCompactControls(): boolean {
  try {
    const [ok, bytes] = GLib.file_get_contents(CAPTURE_CONFIG)
    if (!ok || bytes === null) return false
    const raw = JSON.parse(new TextDecoder().decode(bytes)) as Record<string, unknown>
    return raw.bar_compact_controls === true
  } catch {
    return false
  }
}

// The monitor MUST be held here, at module scope. Kept as a local inside the
// widget it is collectable as soon as the component function returns, and a
// collected FileMonitor stops emitting — the bar then silently ignored later
// settings changes (verified: flipping the setting left the old mode rendered).
let captureConfigMonitor: Gio.FileMonitor | null = null

// Recording indicator driven by the hub's `capture.state` DOMAIN event
// (Phase 5, AD-37/AD-40): no `capture-tool status` polling. Between pushes
// the elapsed value is interpolated locally from the recorded sync time —
// a rendered continuous value, not a state read. `domainEvents.subscribe`
// hydrates subscribe-before-read, so a bar that starts mid-recording renders
// immediately; a hub restart resets the indicator before re-hydration. Control
// actions go through the hub's `Control` method using the additive `job_id`
// on the event; when the hub is absent nothing is published (reduced
// functionality).
export function RecordingIndicator() {
  const [state, setState] = createState<RecordingState>("idle")
  const [elapsed, setElapsed] = createState("00:00")
  const [compact, setCompact] = createState(loadCompactControls())
  let jobId: string | null = null
  let baseElapsed = 0
  let syncedAtMs = Date.now()
  // Gtk.Popover dismissal (Escape / outside-click) is native; Stop and hub
  // restarts pop it down explicitly below.
  let popup: Gtk.Popover | null = null

  // The settings view writes the capture config, so watch it: switching mode
  // must take effect without restarting the bar. The monitor is assigned to a
  // module-scope slot so it stays alive (see captureConfigMonitor).
  try {
    captureConfigMonitor = Gio.File.new_for_path(CAPTURE_CONFIG).monitor_file(
      Gio.FileMonitorFlags.NONE,
      null,
    )
    captureConfigMonitor.connect("changed", () => {
      const next = loadCompactControls()
      setCompact(next)
      // Leaving compact mode removes the click affordance, so close any popup.
      if (!next) popup?.popdown()
    })
  } catch (error) {
    console.error(`capture-tool: cannot watch ${CAPTURE_CONFIG}: ${error}`)
  }

  function reset(): void {
    jobId = null
    baseElapsed = 0
    syncedAtMs = Date.now()
    setState("idle")
    setElapsed("00:00")
    popup?.popdown()
  }

  domainEvents.subscribe("capture.state", (_topic, payload) => {
    const next = payload.state
    const validState: RecordingState =
      next === "recording" || next === "paused" ? next : "idle"
    baseElapsed = Number(payload.elapsed_seconds) || 0
    syncedAtMs = Date.now()
    jobId = typeof payload.job_id === "string" ? payload.job_id : null
    setState(validState)
    setElapsed(formatElapsed(baseElapsed))
  })

  // A hub restart (new epoch) invalidates the old capture job: clear the
  // stale indicator, then the bus re-hydrates `capture.state` and re-renders
  // it if a capture is still live.
  domainEvents.onRestart(reset)

  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
    if (state() === "recording") {
      const interpolated = baseElapsed + Math.floor((Date.now() - syncedAtMs) / 1000)
      setElapsed(formatElapsed(interpolated))
    }
    return true
  })

  function send(action: "pause" | "resume" | "stop"): void {
    if (jobId !== null) domainEvents.control(jobId, action)
    if (action === "stop") popup?.popdown()
  }

  function toggle(): void {
    send(state() === "recording" ? "pause" : "resume")
  }

  // Derived bindings off the single `state` signal — the popup mirrors the
  // cluster with no second subscription and no new timer.
  const clusterClass = state((value) => (value === "paused" ? "rec-cluster paused" : "rec-cluster"))
  const dotClass = state((value) => (value === "paused" ? "rec-dot paused" : "rec-dot"))
  const popupClass = state((value) => (value === "paused" ? "rec-popup paused" : "rec-popup"))
  const statusText = state((value) => (value === "paused" ? "Recording paused" : "Recording"))
  const toggleLabel = state((value) => (value === "recording" ? "Pause" : "Resume"))
  const toggleTip = state((value) =>
    value === "recording" ? "Pause recording" : "Resume recording",
  )

  return (
    <box visible={state((value) => value !== "idle")} class={clusterClass}>
      <button
        class="rec-status"
        tooltipText={compact((value) => (value ? "Recording controls" : null))}
        onClicked={() => {
          // Only the compact mode has a popup: in full mode the controls are
          // already in the bar, so opening one would just duplicate them.
          if (compact()) popup?.popup()
        }}
      >
        <box spacing={6}>
          <box class={dotClass} valign={Gtk.Align.CENTER} />
          <label class="rec-timer" label={elapsed} />
        </box>
      </button>
      <button
        visible={compact((value) => !value)}
        class="rec-btn"
        tooltipText={toggleTip}
        onClicked={toggle}
      >
        <image
          pixel_size={16}
          $={(self) => {
            createEffect(() => {
              self.set_from_file(iconPath(state() === "recording" ? "pause" : "play"))
            })
          }}
        />
      </button>
      <button
        visible={compact((value) => !value)}
        class="rec-btn stop"
        tooltipText="Stop recording"
        onClicked={() => send("stop")}
      >
        <image pixel_size={16} $={(self) => self.set_from_file(iconPath("stop"))} />
      </button>
      <popover $={(self) => (popup = self)}>
        <box orientation={1} class={popupClass}>
          <box class="rec-popup-row" spacing={8}>
            <box class={dotClass} valign={Gtk.Align.CENTER} />
            <label label={statusText} />
          </box>
          {/* No big timer: the bar already shows the elapsed time in compact
              mode, which is the only mode that opens this popup. */}
          <box class="rec-popup-actions" homogeneous spacing={8}>
            <button class="rec-popup-action" tooltipText={toggleTip} onClicked={toggle}>
              <box spacing={7}>
                <image
                  pixel_size={16}
                  $={(self) => {
                    createEffect(() => {
                      self.set_from_file(iconPath(state() === "recording" ? "pause" : "play"))
                    })
                  }}
                />
                <label label={toggleLabel} />
              </box>
            </button>
            <button
              class="rec-popup-action danger"
              tooltipText="Stop recording"
              onClicked={() => send("stop")}
            >
              <box spacing={7}>
                <image pixel_size={16} $={(self) => self.set_from_file(iconPath("stop"))} />
                <label label="Stop" />
              </box>
            </button>
          </box>
        </box>
      </popover>
    </box>
  )
}

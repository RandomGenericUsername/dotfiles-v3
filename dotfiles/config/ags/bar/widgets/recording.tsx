import GLib from "gi://GLib?version=2.0"
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
  return registry.resolve("screen-recorder", variant) ?? ""
}

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
  let jobId: string | null = null
  let baseElapsed = 0
  let syncedAtMs = Date.now()

  function reset(): void {
    jobId = null
    baseElapsed = 0
    syncedAtMs = Date.now()
    setState("idle")
    setElapsed("00:00")
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
  }

  return (
    <box visible={state((value) => value !== "idle")} class="recording-controls" spacing={4}>
      <label class="recording-timer" label={elapsed} />
      <button
        class="widget recording-widget"
        tooltipText={state((value) => value === "recording" ? "Pause recording" : "Resume recording")}
        onClicked={() => send(state() === "recording" ? "pause" : "resume")}
      >
        <image
          pixel_size={28}
          class="recording-icon"
          halign={Gtk.Align.CENTER}
          valign={Gtk.Align.CENTER}
          $={(self) => {
            createEffect(() => {
              self.set_from_file(iconPath(state() === "recording" ? "pause" : "play"))
            })
          }}
        />
      </button>
      <button
        class="widget recording-widget stop"
        tooltipText="Stop recording"
        onClicked={() => send("stop")}
      >
        <image
          pixel_size={28}
          class="recording-icon"
          halign={Gtk.Align.CENTER}
          valign={Gtk.Align.CENTER}
          $={(self) => self.set_from_file(iconPath("stop"))}
        />
      </button>
    </box>
  )
}

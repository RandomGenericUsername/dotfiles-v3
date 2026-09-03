import GLib from "gi://GLib?version=2.0"
import { createEffect, createState } from "ags"
import { Gtk } from "ags/gtk4"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"

type RecordingState = "idle" | "recording" | "paused"

type RecordingStatus = { state: RecordingState; elapsed_seconds: number }

function readStatus(): RecordingStatus {
  try {
    const [ok, stdout] = GLib.spawn_command_line_sync("capture-tool status")
    if (!ok || !stdout) return { state: "idle", elapsed_seconds: 0 }
    const text = new TextDecoder().decode(stdout)
    const parsed = JSON.parse(text)
    return {
      state: parsed.state === "recording" || parsed.state === "paused" ? parsed.state : "idle",
      elapsed_seconds: Number(parsed.elapsed_seconds) || 0,
    }
  } catch {
    return { state: "idle", elapsed_seconds: 0 }
  }
}

function formatElapsed(seconds: number): string {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0")
  const remainder = (seconds % 60).toString().padStart(2, "0")
  return `${minutes}:${remainder}`
}

function iconPath(variant: "pause" | "play" | "stop"): string {
  return registry.resolve("screen-recorder", variant) ?? ""
}

export function RecordingIndicator() {
  let current = readStatus()
  const [state, setState] = createState<RecordingState>(current.state)
  const [elapsed, setElapsed] = createState(formatElapsed(current.elapsed_seconds))
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 500, () => {
    current = readStatus()
    setState(current.state)
    setElapsed(formatElapsed(current.elapsed_seconds))
    return true
  })

  return (
    <box visible={state((value) => value !== "idle")} class="recording-controls" spacing={4}>
      <label class="recording-timer" label={elapsed} />
      <button
        class="widget recording-widget"
        tooltipText={state((value) => value === "recording" ? "Pause recording" : "Resume recording")}
        onClicked={() => execAsync(["capture-tool", current.state === "recording" ? "pause" : "resume"]).catch(console.error)}
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
        onClicked={() => execAsync(["capture-tool", "stop"]).catch(console.error)}
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

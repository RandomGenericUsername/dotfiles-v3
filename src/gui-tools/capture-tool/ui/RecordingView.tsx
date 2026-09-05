import { Gtk } from "ags/gtk4"
import type { CaptureTarget } from "./CaptureWindow"

export type RecordingFormat = "mp4" | "webm" | "gif"
export type AudioSource = "none" | "system" | "microphone"

export interface RecordingConfig {
  target: CaptureTarget
  fps: number
  format: RecordingFormat
  audio: AudioSource
  quality: "low" | "medium" | "high"
  durationSeconds?: number
}

export function RecordingView() {
  return (
    <box orientation={Gtk.Orientation.VERTICAL} spacing={8}>
      <label label="Recording" />
      <label label="Target: region / screen / window" />
      <label label="FPS: 24 / 30 / 60" />
      <label label="Format: MP4 / WebM / GIF" />
      <label label="Audio: none / system / mic" />
    </box>
  )
}

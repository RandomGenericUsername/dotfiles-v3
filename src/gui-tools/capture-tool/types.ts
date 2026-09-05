export type CaptureTarget = "region" | "screen" | "window"
export type ScreenshotFormat = "png" | "jpeg"
export type RecordingFormat = "mp4" | "webm" | "gif"
export type AudioSource = "none" | "system" | "microphone"
export type RecordingQuality = "low" | "medium" | "high"

export interface ScreenshotConfig {
  target: CaptureTarget
  delaySeconds: number
  format: ScreenshotFormat
  saveToFile: boolean
}

export interface RecordingConfig {
  target: CaptureTarget
  fps: number
  format: RecordingFormat
  audio: AudioSource
  quality: RecordingQuality
  durationSeconds?: number
}

export type CaptureTarget = "region" | "screen" | "window"
export type ScreenshotFormat = "png" | "jpeg"
export type RecordingFormat = "mp4" | "webm" | "gif"
export type AudioSource = "none" | "system" | "microphone"
export type RecordingQuality = "low" | "medium" | "high"
export type GifScale = "original" | "75%" | "50%"

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
  /** GIF-only output scale (the GIF special pipeline never opens audio). */
  gifScale?: GifScale
}

import type { CaptureTarget } from "./CaptureWindow"

export type ScreenshotFormat = "png" | "jpeg"

export interface ScreenshotConfig {
  target: CaptureTarget
  delaySeconds: number
  format: ScreenshotFormat
  saveToFile: boolean
}

export function ScreenshotView() {
  return (
    <box vertical spacing={8}>
      <label label="Screenshot" />
      <label label="Target: region / screen / window" />
      <label label="Delay: none / 3s / 5s / 10s" />
      <label label="Format: PNG / JPEG" />
    </box>
  )
}

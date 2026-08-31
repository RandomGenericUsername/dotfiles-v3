export type CaptureTarget = "region" | "screen" | "window"

export function CaptureWindow() {
  return (
    <window class="capture-window" visible>
      <box vertical spacing={8}>
        <label label="Capture" />
        <label label="Screenshot / Recording" />
      </box>
    </window>
  )
}

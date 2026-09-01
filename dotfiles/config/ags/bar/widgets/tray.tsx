import { RecordingIndicator } from "./recording"

export function Tray() {
  return (
    <box class="bar-tray" spacing={8}>
      <RecordingIndicator />
    </box>
  )
}

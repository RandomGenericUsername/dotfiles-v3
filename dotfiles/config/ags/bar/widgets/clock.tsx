import GLib from "gi://GLib?version=2.0"
import { createState } from "ags"

function formatTime(): string {
  const now = GLib.DateTime.new_now_local()
  return now.format("%H:%M") ?? ""
}

function formatDate(): string {
  const now = GLib.DateTime.new_now_local()
  return now.format("%Y-%m-%d") ?? ""
}

export function Clock() {
  const [time, setTime] = createState(formatTime())
  const [date, setDate] = createState(formatDate())

  GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
    setTime(formatTime())
    setDate(formatDate())
    return true
  })

  return (
    <box class="clock" spacing={8}>
      <label label={date} />
      <label label={time} />
    </box>
  )
}

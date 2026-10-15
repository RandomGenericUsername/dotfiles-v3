import GLib from "gi://GLib?version=2.0"
import { createState } from "ags"
import type { RichWidgetSpec } from "../../kit/widget"

function formatTime(): string {
  const now = GLib.DateTime.new_now_local()
  return now.format("%H:%M") ?? ""
}

function formatDate(): string {
  const now = GLib.DateTime.new_now_local()
  return now.format("%Y-%m-%d") ?? ""
}

export interface ClockState {
  readonly date: string
  readonly time: string
}

const [time, setTime] = createState(formatTime())
const [date, setDate] = createState(formatDate())

GLib.timeout_add(GLib.PRIORITY_DEFAULT, 1000, () => {
  setTime(formatTime())
  setDate(formatDate())
  return true
})

/**
 * The clock, as a `RichWidgetSpec` (spine AD-8; doc 101 §5): two labels, so it
 * is the rich shape rather than a descriptor. The shared shell owns the root
 * box, its class and its visibility; the content is the two labels, kept
 * reactive by binding them straight to the state accessors (the widget tree is
 * static, so only the label properties re-evaluate).
 */
export const clockWidget: RichWidgetSpec<ClockState> = {
  id: "clock",
  read: () => ({ date: date(), time: time() }),
  class: "clock",
  content: () => (
    <box spacing={8}>
      <label label={date} />
      <label label={time} />
    </box>
  ),
}

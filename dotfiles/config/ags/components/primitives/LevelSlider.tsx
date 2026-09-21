import { Accessor } from "ags"

type MaybeAccessor<T> = T | Accessor<T>

/** Leading glyph + track. `--p`-style fill comes from the Gtk.Scale highlight. */
export function LevelSlider({
  leading,
  value,
  min = 0,
  max = 100,
  step = 1,
  onChange,
}: {
  leading: unknown
  value: MaybeAccessor<number>
  min?: number
  max?: number
  step?: number
  onChange: (value: number) => void
}) {
  return (
    <box class="settings-slider" spacing={9}>
      {leading as never}
      <slider
        class="settings-level-slider"
        hexpand
        min={min}
        max={max}
        step={step}
        value={value}
        drawValue={false}
        onNotifyValue={(self: { get_value: () => number }) =>
          onChange(self.get_value())
        }
      />
    </box>
  )
}

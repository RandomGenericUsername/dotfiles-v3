import { Gtk } from "ags/gtk4"
import { Accessor, createComputed, createEffect } from "ags"

/**
 * The bare power glyph — for Wi-Fi/Bluetooth this IS the power toggle.
 *
 * There is deliberately no background/border box: the on/off tint is baked
 * into two rendered ITR variants (`iconOn` accent, `iconOff` muted) and the
 * image swaps between them reactively. The initial assignment lives inside the
 * `createEffect` so the first paint is already correct (the recorder lesson).
 */
export function IconToggle({
  iconOn,
  iconOff,
  active,
  onClicked,
  tooltip,
  size = 28,
}: {
  iconOn: string | null
  iconOff: string | null
  active: Accessor<boolean>
  onClicked: () => void
  tooltip?: string
  size?: number
}) {
  const cls = createComputed(() =>
    active() ? "settings-icon-toggle on" : "settings-icon-toggle off",
  )

  return (
    <button
      class={cls}
      tooltipText={tooltip}
      onClicked={onClicked}
      canFocus={false}
    >
      <image
        pixel_size={size}
        class="settings-toggle-glyph"
        $={(self) => {
          createEffect(() => {
            self.set_from_file((active() ? iconOn : iconOff) ?? "")
          })
        }}
      />
    </button>
  )
}

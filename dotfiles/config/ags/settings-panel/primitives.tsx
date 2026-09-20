import { Gtk } from "ags/gtk4"
import { Accessor, createComputed, createEffect } from "ags"

/**
 * Reusable settings-panel building blocks.
 *
 * Add a new section by adding an entry to `SECTION_ORDER` (views/MainView.tsx)
 * and composing these primitives — no existing section needs surgery.
 */

type MaybeAccessor<T> = T | Accessor<T>

/** A titled section card (Display, Sound, future cards). */
export function PanelCard({
  title,
  children,
}: {
  title?: string
  children?: unknown
}) {
  return (
    <box class="settings-card" orientation={1} spacing={8}>
      {title !== undefined ? (
        <label class="settings-card-title" xalign={0} label={title} />
      ) : null}
      {children as never}
    </box>
  )
}

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

/**
 * A capability row: the icon is the power toggle, the label/chevron opens the
 * list. No explicit switch.
 */
export function CapabilityTile({
  iconOn,
  iconOff,
  title,
  subtitle,
  active,
  onToggle,
  onOpen,
  toggleTooltip,
}: {
  iconOn: string | null
  iconOff: string | null
  title: string
  subtitle: MaybeAccessor<string>
  active: Accessor<boolean>
  onToggle: () => void
  onOpen: () => void
  toggleTooltip?: string
}) {
  return (
    <box
      class="settings-tile"
      spacing={10}
      $={(self) => {
        // The whole card opens the list (except the icon toggle, whose own
        // button claims its click first). A nested button left the card padding
        // and the chevron hard to hit precisely.
        const click = new Gtk.GestureClick({ button: 1 })
        click.connect("released", () => onOpen())
        self.add_controller(click)
      }}
    >
      <IconToggle
        iconOn={iconOn}
        iconOff={iconOff}
        active={active}
        onClicked={onToggle}
        tooltip={toggleTooltip}
      />
      <box spacing={6} hexpand>
        <box orientation={1} valign={Gtk.Align.CENTER} hexpand>
          <label class="settings-tile-title" xalign={0} label={title} />
          <label class="settings-tile-sub" xalign={0} label={subtitle} />
        </box>
        <label
          class="settings-chevron"
          valign={Gtk.Align.CENTER}
          label={"\u203A"}
        />
      </box>
    </box>
  )
}

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

/** Back arrow + title + optional trailing control (the subview header). */
export function NavHeader({
  title,
  onBack,
  trailing,
}: {
  title: MaybeAccessor<string>
  onBack: () => void
  trailing?: unknown
}) {
  return (
    <box class="settings-nav-header" spacing={9}>
      <button class="settings-back" onClicked={onBack} canFocus={false}>
        <label class="settings-back-glyph" label={"\u2039"} />
      </button>
      <label
        class="settings-nav-title"
        xalign={0}
        hexpand
        label={title as never}
      />
      {trailing as never}
    </box>
  )
}

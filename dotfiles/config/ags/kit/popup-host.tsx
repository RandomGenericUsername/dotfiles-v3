import { Astal, Gtk, Gdk } from "ags/gtk4"
import { With, createComputed, createEffect } from "ags"
import type { Accessor } from "ags"
import { createSurfaceMount, type SurfaceSpec } from "./surface"

/**
 * The app-facing surface declaration: `kit/surface.ts` is pure and leaves the
 * accessor type structural, while the bar specializes it to gnim's concrete
 * `Accessor` so a body factory can pass `host.visible` to content components.
 */
export type PopupSurfaceSpec = SurfaceSpec<JSX.Element, Accessor<boolean>>

/**
 * `PopupHost` — the shipped popup primitive (spine AD-10; doc 101 §4.4).
 *
 * Five bar popups used to repeat the same chrome: a full-screen click-catcher
 * window, a glass surface box, the identical `marginLeft` anchor clamp, a
 * `marginTop`, and a `$` setup that pinned `Astal.Keymode` and installed the
 * Escape controller. This module owns that chrome ONCE. A popup keeps only its
 * own body and delegates the window/catcher/anchor/keymode to these two
 * components.
 *
 * MOUNT POLICY (AD-10). The body is a FACTORY on the `SurfaceSpec`. `PopupHost`
 * mounts it through gnim `With`, which builds the body only while the surface is
 * visible and disposes the body's reactive scope when it hides; the pure
 * `createSurfaceMount` decides build/drop and is unit-tested without GTK. Durable
 * state therefore lives in the popups' own `state.ts` modules, never in the body.
 *
 * TWO WINDOWS, deliberately. The panel is `OVERLAY` + `IGNORE` (it neither dims
 * nor blocks the desktop), so a second full-screen window on the same layer
 * absorbs the click that lands outside the panel. Registration order in `app.tsx`
 * is load-bearing: the catcher is added FIRST so the panel stacks ABOVE it, and a
 * click on the panel reaches the panel rather than the catcher underneath.
 */

export interface PopupCatcherProps {
  /** Window name; the panel's name + `-catcher` by convention. */
  readonly name: string
  readonly gdkmonitor: Gdk.Monitor
  readonly visible: Accessor<boolean>
  /** Run when the primary button is released outside the panel. */
  readonly onClose: () => void
}

/**
 * The click-outside catcher: a full-screen, 1%-opacity layer surface (a fully
 * transparent one is not hit-testable — see `.settings-catcher-fill` in
 * `style.css`). Shown only while its surface is visible.
 */
export function PopupCatcher({ name, gdkmonitor, visible, onClose }: PopupCatcherProps) {
  const { TOP, BOTTOM, LEFT, RIGHT } = Astal.WindowAnchor
  return (
    <window
      name={name}
      class="settings-catcher"
      gdkmonitor={gdkmonitor}
      anchor={TOP | BOTTOM | LEFT | RIGHT}
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      visible={visible}
    >
      <box class="settings-catcher-fill" hexpand vexpand $={(self) => {
        const click = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        click.connect("released", () => onClose())
        self.add_controller(click)
      }} />
    </window>
  )
}

export interface PopupHostProps {
  /** The surface declaration; its `body` factory is mounted while visible. */
  readonly spec: PopupSurfaceSpec
  /** Panel window name (e.g. `wifi-popup`). */
  readonly name: string
  readonly gdkmonitor: Gdk.Monitor
  readonly visible: Accessor<boolean>
  /** Bar-icon x-centre to anchor beneath, or null (falls back to right-most). */
  readonly anchorX: Accessor<number | null>
  /** Close the surface: the catcher click and the Escape key both call this. */
  readonly onClose: () => void
  /** Panel window CSS class; default `settings-panel`. */
  readonly windowClass?: string
  /** Surface box CSS class; default `settings-surface`. */
  readonly surfaceClass?: string
  /** Top margin under the bar; default 52. */
  readonly marginTop?: number
  /** Overrides `spec.width` (the audio drawer derives its width from the monitor). */
  readonly width?: number
}

/**
 * The anchored panel window. It computes the clamped left margin from the
 * surface width and the follower anchor, wraps the spec's factory output in the
 * surface box, and mounts that box lazily via gnim `With`.
 */
export function PopupHost({
  spec,
  name,
  gdkmonitor,
  visible,
  anchorX,
  onClose,
  windowClass = "settings-panel",
  surfaceClass = "settings-surface",
  marginTop = 52,
  width: widthOverride,
}: PopupHostProps) {
  const { TOP, LEFT } = Astal.WindowAnchor
  const width = widthOverride ?? spec.width ?? 312
  const monitorWidth = gdkmonitor.get_geometry().width

  // Anchor beneath the bar icon, clamped into the monitor. The icon is near the
  // right edge, so a naive centre-the-panel offset would push most of it
  // off-screen; when the anchor has never been written the panel falls back to
  // the right-most on-screen position rather than to `null`/0.
  const marginLeft = createComputed(() => {
    const rightMost = monitorWidth - width - 8
    const centre = anchorX()
    if (centre == null) return rightMost
    const left = Math.round(centre - width / 2)
    return Math.min(Math.max(left, 8), rightMost)
  })

  const host = { visible }
  const mount = createSurfaceMount(() => (
    <box class={surfaceClass} orientation={1} widthRequest={width}>
      {spec.body(host)}
    </box>
  ))

  const keyboard = spec.keyboard ?? (() => false)

  return (
    <window
      name={name}
      class={windowClass}
      gdkmonitor={gdkmonitor}
      anchor={TOP | LEFT}
      /* IGNORE (not NORMAL): a popup must not request an exclusive zone, or
         Hyprland offsets the overlay surface below the bar's reserved area and
         then applies marginTop — pushing the panel ~48px too low. */
      exclusivity={Astal.Exclusivity.IGNORE}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.NONE}
      marginTop={marginTop}
      marginLeft={marginLeft}
      visible={visible}
      $={(self) => {
        // Keymode NONE by default so the panel does not steal focus — that is
        // what lets the bar keep click activation (reliable same-spot collapse).
        // Switch to ON_DEMAND only while a field that needs TYPED input is on
        // screen; the spec's `keyboard` accessor is that condition.
        createEffect(() => {
          self.keymode = keyboard()
            ? Astal.Keymode.ON_DEMAND
            : Astal.Keymode.NONE
        })
        // Escape closes while the panel holds the keyboard (i.e. typed input).
        const key = new Gtk.EventControllerKey()
        key.connect("key-pressed", (_controller, keyval) => {
          if (keyval === Gdk.KEY_Escape) {
            onClose()
            return true
          }
          return false
        })
        self.add_controller(key)
      }}
    >
      <With value={visible}>{(v) => mount.render(v)}</With>
    </window>
  )
}

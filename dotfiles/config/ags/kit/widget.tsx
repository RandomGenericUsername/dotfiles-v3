import Gtk from "gi://Gtk?version=4.0"
import Gdk from "gi://Gdk?version=4.0"
import { createComputed, createEffect } from "ags"
import type { IconRef } from "./icon"
import { resolveIcon } from "./icon"

/**
 * A status-bar widget, as DATA. The bar renders a list of these through
 * `BarWidgetButton`; it knows no domain.
 *
 * `S` is the domain read model the widget observes. Stateless widgets use
 * `BarWidgetSpec<undefined>` and `read: () => undefined`.
 *
 * Reactivity contract (learned the hard way — see BluetoothContent.tsx): the
 * widget TREE is static, so only STATIC spec fields (does it have an icon?) may
 * branch the JSX. Everything that changes over time is a function of `state`
 * and is wrapped in `createComputed` by the renderer.
 */
export interface BarWidgetSpec<S> {
  readonly id: string
  /**
   * The domain read model: a plain getter (or an `Accessor`). The kit calls it
   * inside `createComputed`, so any reactive reads it performs subscribe.
   * Stateless widgets pass `() => undefined`.
   */
  readonly read: () => S
  readonly icon?: IconRef<S>
  /** Text beside the icon; absent renders no label at all. */
  readonly label?: (state: S) => string | null
  readonly tooltip?: (state: S) => string
  readonly visible?: (state: S) => boolean
  /** Extra CSS classes, joined after the mandatory `widget`. */
  readonly class?: string
  readonly pixelSize?: number
  /**
   * Primary activation. Receives the last recorded pointer x (surface coords ==
   * monitor coords, the bar spans the monitor) so the widget can anchor an
   * overlay beneath its own icon — the `lastIconX` pattern, owned here once.
   */
  readonly primary?: (state: S, anchorX: number | null) => void
  readonly secondary?: (state: S) => void
  readonly scroll?: (state: S, dy: number) => void
}

/**
 * The generic bar widget renderer: icon + optional label + tooltip + the three
 * gestures + the follower-anchor record. Behaviour comes entirely from the spec;
 * the renderer owns no domain policy.
 */
export function BarWidgetButton<S>({ spec }: { spec: BarWidgetSpec<S> }) {
  const state = (): S => spec.read()

  // Last pointer x, recorded by a motion controller (which does NOT claim
  // clicks, so the button's own activation still fires). Re-recorded on every
  // hover, so moving the icon in the bar just works.
  let lastX: number | null = null

  const icon = createComputed(() => (spec.icon ? resolveIcon(spec.icon, state()) : ""))
  const label = createComputed(() => (spec.label ? spec.label(state()) ?? "" : ""))
  const tooltip = createComputed(() => (spec.tooltip ? spec.tooltip(state()) : ""))
  const visible = createComputed(() => (spec.visible ? spec.visible(state()) : true))

  return (
    <button
      class={spec.class ? `widget ${spec.class}` : "widget"}
      visible={visible}
      tooltipText={tooltip}
      onClicked={() => spec.primary?.(state(), lastX)}
      $={(self) => {
        if (spec.primary) {
          const motion = new Gtk.EventControllerMotion()
          motion.connect("motion", () => {
            const event = motion.get_current_event()
            if (!event) return
            // Gdk.Event.get_position() -> [ok, x, y] in gjs.
            const pos = event.get_position() as unknown
            if (Array.isArray(pos) && pos.length >= 3) {
              const x = Number(pos[1])
              if (Number.isFinite(x) && x > 0) lastX = x
            }
          })
          self.add_controller(motion)
        }

        if (spec.secondary) {
          const secondary = new Gtk.GestureClick({ button: Gdk.BUTTON_SECONDARY })
          secondary.connect("pressed", () => spec.secondary?.(state()))
          self.add_controller(secondary)
        }

        if (spec.scroll) {
          const scroll = new Gtk.EventControllerScroll()
          scroll.set_flags(Gtk.EventControllerScrollFlags.VERTICAL)
          scroll.connect("scroll", (_c, _dx, dy) => {
            spec.scroll?.(state(), dy)
            return true
          })
          self.add_controller(scroll)
        }
      }}
    >
      {/* A GTK button holds a SINGLE child, so the icon and label are wrapped in
          one box. Rendering them as siblings made the label displace the icon —
          the button showed only the second child. */}
      <box spacing={4}>
        {spec.icon
          ? (
            <image
              pixel_size={spec.pixelSize ?? 28}
              class="widget-icon"
              $={(self) => {
                createEffect(() => self.set_from_file(icon()))
              }}
            />
          )
          : null}
        {spec.label
          ? <label visible={createComputed(() => label() !== "")} label={label} />
          : null}
      </box>
    </button>
  )
}

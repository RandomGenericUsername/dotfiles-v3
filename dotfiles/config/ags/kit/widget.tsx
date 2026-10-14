import Gtk from "gi://Gtk?version=4.0"
import Gdk from "gi://Gdk?version=4.0"
import { createComputed, createEffect } from "ags"
import type { BarWidgetSpec } from "./shapes"
import type * as Shapes from "./shapes"
import { resolveIcon } from "./icon"
import type { IconSource } from "./icon-source"

/**
 * Draw a tagged `IconSource` (AD-4) into a `Gtk.Image`: a FILE from its path
 * (the behavior every widget has always had), a NAME as a themed symbolic icon
 * (the bare-desktop fallback, AD-18), or blank (the image is cleared, never
 * thrown). Extracted from `BarWidgetButton` so every icon-bearing widget that
 * does not render through the generic descriptor — the audio, battery and
 * power-mode widgets — draws the resolution chain's result identically (AD-7).
 */
export function applyIconSource(image: Gtk.Image, source: IconSource | null): void {
  if (source === null) image.set_from_file("")
  else if (source.kind === "file") image.set_from_file(source.path)
  else image.set_from_icon_name(source.name)
}

/**
 * The shared widget vocabulary (spine AD-8) lives in `./shapes`, pure and
 * unit-testable without GTK. This file is the DescriptorSpec renderer plus the
 * app-facing specializations: the pure vocabulary leaves the rendered subtree
 * type opaque (`E`), and here `E` is gnim's `JSX.Element`. Re-exporting keeps the
 * public `kit/widget` import path unchanged for the bar.
 */
export type { Shell, DescriptorSpec, BarWidgetSpec } from "./shapes"

export type BarContext = Shapes.BarContext<JSX.Element>
export type RichWidgetSpec<S> = Shapes.RichWidgetSpec<S, JSX.Element>
export type CollectionSpec<I, S> = Shapes.CollectionSpec<I, S, JSX.Element>
export type ForeignCollectionSpec<I, S> = Shapes.ForeignCollectionSpec<I, S, JSX.Element>
export type WidgetSpec<S> = Shapes.WidgetSpec<S, JSX.Element>

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

  const icon = createComputed(() => (spec.icon ? resolveIcon(spec.icon, state()) : null))
  const label = createComputed(() => (spec.label ? spec.label(state()) ?? "" : ""))
  const tooltip = createComputed(() => (spec.tooltip ? spec.tooltip(state()) : ""))
  const visible = createComputed(() => (spec.visible ? spec.visible(state()) : true))

  // `class` may combine a STATIC class with a STATE-DERIVED one. gnim's `class`
  // prop accepts an accessor, so the whole string is built reactively — the
  // widget tree stays static and only the property re-evaluates.
  const classes = createComputed(() => {
    const parts = spec.class ? `widget ${spec.class}` : "widget"
    const extra = spec.stateClass ? spec.stateClass(state()) : null
    return extra ? `${parts} ${extra}` : parts
  })

  return (
    <button
      class={classes}
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
                // The tagged `IconSource` (AD-4): a FILE is drawn from its path
                // (the behavior this widget has always had); a NAME is a themed
                // symbolic icon (the bare-desktop fallback, AD-18); blank clears
                // the image rather than throwing.
                createEffect(() => applyIconSource(self, icon()))
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

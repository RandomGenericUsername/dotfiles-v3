import Gtk from "gi://Gtk?version=4.0"
import Gdk from "gi://Gdk?version=4.0"
import { For, createComputed, createEffect } from "ags"
import type { Accessor } from "ags"
import type { BarWidgetSpec } from "./shapes"
import type * as Shapes from "./shapes"
import { resolveIcon } from "ags-platform/adapters/icon"
import type { IconSource } from "ags-platform/ports/icon-source"

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
 * unit-testable without GTK. This file is the renderers plus the app-facing
 * specializations: the pure vocabulary leaves the rendered subtree type opaque
 * (`E`), and here `E` is gnim's `JSX.Element`. Re-exporting keeps the public
 * `kit/widget` import path unchanged for the bar.
 */
export type { Shell, DescriptorSpec, BarWidgetSpec } from "./shapes"

export type BarContext = Shapes.BarContext<JSX.Element>
export type RichWidgetSpec<S> = Shapes.RichWidgetSpec<S, JSX.Element>
export type CollectionSpec<I, S> = Shapes.CollectionSpec<I, S, JSX.Element>
export type ForeignCollectionSpec<I, S> = Shapes.ForeignCollectionSpec<I, S, JSX.Element>
export type WidgetSpec<S> = Shapes.WidgetSpec<S, JSX.Element>

/**
 * Any spec a `BarWidget` can render. The shapes are generic in their state
 * (`S`) and item (`I`) types, and a heterogeneous registry cannot name a single
 * concrete type for them; `any` here is the erasure that lets a map hold
 * descriptor, rich, collection and foreign specs side by side. The renderers
 * re-establish the concrete type at the call site.
 */
export type AnyWidgetSpec =
  | Shapes.DescriptorSpec<any>
  | Shapes.RichWidgetSpec<any, JSX.Element>
  | Shapes.CollectionSpec<any, any, JSX.Element>
  | Shapes.ForeignCollectionSpec<any, any, JSX.Element>

/**
 * The one implementation of the shared shell (AD-8). Every renderer builds its
 * class/visible/tooltip and installs its gestures through this, so anchoring,
 * gestures, tooltip, visibility and class handling can never diverge per shape.
 *
 * The pointer x is recorded by a motion controller (which does NOT claim
 * clicks, so the widget's own activation still fires). Re-recorded on every
 * hover, so moving the icon in the bar just works.
 */
function useShell<S>(spec: Shapes.Shell<S>): {
  state: () => S
  classes: Accessor<string>
  visible: Accessor<boolean>
  tooltip: Accessor<string>
  anchor: () => number | null
  setup: (self: Gtk.Widget, includePrimary: boolean) => void
} {
  const state = (): S => spec.read()
  let lastX: number | null = null

  // `class` may combine a STATIC class with a STATE-DERIVED one. gnim's `class`
  // prop accepts an accessor, so the whole string is built reactively — the
  // widget tree stays static and only the property re-evaluates.
  const classes = createComputed(() => {
    const parts = spec.class ? `widget ${spec.class}` : "widget"
    const extra = spec.stateClass ? spec.stateClass(state()) : null
    return extra ? `${parts} ${extra}` : parts
  })
  const visible = createComputed(() => (spec.visible ? spec.visible(state()) : true))
  const tooltip = createComputed(() => (spec.tooltip ? spec.tooltip(state()) : ""))

  const setup = (self: Gtk.Widget, includePrimary: boolean): void => {
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

      // A box-rooted shape has no `onClicked`; the shell supplies the primary
      // gesture itself so `primary` behaves the same on a button and a box.
      if (includePrimary) {
        const primary = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        primary.connect("released", () => spec.primary?.(state(), lastX))
        self.add_controller(primary)
      }
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
  }

  return { state, classes, visible, tooltip, anchor: () => lastX, setup }
}

/**
 * The generic bar widget renderer: icon + optional label + tooltip + the three
 * gestures + the follower-anchor record. Behaviour comes entirely from the spec;
 * the renderer owns no domain policy.
 */
export function BarWidgetButton<S>({ spec }: { spec: BarWidgetSpec<S> }) {
  const shell = useShell(spec)
  const icon = createComputed(() => (spec.icon ? resolveIcon(spec.icon, shell.state()) : null))
  const label = createComputed(() => (spec.label ? spec.label(shell.state()) ?? "" : ""))

  return (
    <button
      class={shell.classes}
      visible={shell.visible}
      tooltipText={shell.tooltip}
      onClicked={() => spec.primary?.(shell.state(), shell.anchor())}
      $={(self) => shell.setup(self, false)}
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

/**
 * The rich shape (AD-8): arbitrary content inside the shared shell. Rendered as
 * a button when the spec has a primary action (so it keeps button chrome and
 * click semantics), else as a box.
 */
export function RichWidget<S>(
  { spec, ctx }: { spec: RichWidgetSpec<S>; ctx: BarContext },
) {
  const shell = useShell(spec)
  const body = spec.content(shell.state(), ctx)

  if (spec.primary) {
    return (
      <button
        class={shell.classes}
        visible={shell.visible}
        tooltipText={shell.tooltip}
        onClicked={() => spec.primary?.(shell.state(), shell.anchor())}
        $={(self) => shell.setup(self, false)}
      >
        {body}
      </button>
    )
  }

  return (
    <box
      class={shell.classes}
      visible={shell.visible}
      tooltipText={shell.tooltip}
      $={(self) => shell.setup(self, true)}
    >
      {body}
    </box>
  )
}

/**
 * The collection shape (AD-8): items rendered by the widget's own renderer,
 * keyed for stable identity. `For` (gnim) owns the reactive diff, so a list that
 * changes over time re-renders without the widget re-implementing it.
 */
export function Collection<I, S>(
  { spec, ctx }: { spec: CollectionSpec<I, S>; ctx: BarContext },
) {
  const shell = useShell(spec)
  const each = createComputed(() => spec.items(shell.state()))

  return (
    <box
      class={shell.classes}
      visible={shell.visible}
      tooltipText={shell.tooltip}
      spacing={spec.spacing ?? 0}
      $={(self) => shell.setup(self, true)}
    >
      <For each={each} id={spec.key}>
        {(item) => renderLeaf(spec.item(item, shell.state(), ctx), ctx)}
      </For>
    </box>
  )
}

/**
 * The foreign-collection shape (AD-8): items and item renderer come from an
 * adapter (the tray's SNI items). Identity is the item reference by default
 * (`For`), which is stable for adapter-owned objects.
 */
export function ForeignCollection<I, S>(
  { spec, ctx }: { spec: ForeignCollectionSpec<I, S>; ctx: BarContext },
) {
  const shell = useShell(spec)
  const each = createComputed(() => spec.items(shell.state()))

  return (
    <box
      class={shell.classes}
      visible={shell.visible}
      tooltipText={shell.tooltip}
      spacing={spec.spacing ?? 0}
      $={(self) => shell.setup(self, true)}
    >
      <For each={each}>
        {(item) => spec.render(item, shell.state(), ctx)}
      </For>
    </box>
  )
}

/** A leaf is either a nested spec (rendered) or an element (returned as-is). */
function renderLeaf<S>(
  value: WidgetSpec<S> | JSX.Element,
  ctx: BarContext,
): JSX.Element {
  if (isWidgetSpec(value)) return <BarWidget spec={value} ctx={ctx} />
  return value
}

/** Discriminate a nested widget spec from a rendered element. */
function isWidgetSpec<S>(value: WidgetSpec<S> | JSX.Element): value is WidgetSpec<S> {
  return typeof (value as { read?: unknown }).read === "function"
}

/**
 * The one dispatcher: render any spec by its shape (AD-8). The shape is told
 * apart structurally — `content` (rich), `render` (foreign collection), `items`
 * (collection), else descriptor.
 */
export function BarWidget(
  { spec, ctx }: { spec: AnyWidgetSpec; ctx: BarContext },
) {
  if ("content" in spec) return <RichWidget spec={spec} ctx={ctx} />
  if ("render" in spec) return <ForeignCollection spec={spec} ctx={ctx} />
  if ("items" in spec) return <Collection spec={spec} ctx={ctx} />
  return <BarWidgetButton spec={spec} />
}

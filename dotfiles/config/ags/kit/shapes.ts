import type { IconRef } from "ags-platform/ports/icon-source"

/**
 * The bar widget vocabulary (spine AD-8; doc 101 §5).
 *
 * A widget used to be one type. Rendering outgrew it: a clock has two labels, a
 * recording indicator has a dot, a timer and buttons, workspaces are a
 * collection, and the tray is a collection owned by another app. Doc 101 §5
 * fixes FOUR shapes — and one shared `Shell<S>`, so anchoring, gestures,
 * tooltip, visibility and class handling can never diverge per widget.
 *
 * This module is PURE: no GTK, no AGS, no JSX runtime. The rendered subtree is
 * the type parameter `E` (default `unknown`) rather than `JSX.Element`, which is
 * what keeps the vocabulary unit-testable on a stock runner. The app specializes
 * `E` to gnim's `JSX.Element` in `widget.tsx` (`BarContext`, `RichWidgetSpec`,
 * `CollectionSpec`, `ForeignCollectionSpec`, `WidgetSpec` there are the
 * app-facing aliases).
 */

/**
 * The injected capabilities a shape may call (AD-8; doc 101 §4.7). `popup(...)`
 * and `hub.control(...)` are CAPABILITIES, not shapes: a widget that opens an
 * overlay or drives a job does so through this context, not by declaring another
 * spec kind. The full platform `BarContext` (hub, surfaces, notifier,
 * preferences, theme) is minted in the platform extraction; this is the seam the
 * shape signatures need today.
 *
 * `E` is the rendered subtree type (see the module note).
 */
export interface BarContext<E = unknown> {
  /** Open (and anchor) the single overlay at the bar icon (AD-9, AD-10). */
  readonly popup: (anchorX: number | null, content: () => E) => void
  /** Job control on the event hub (AD-5). */
  readonly hub: { readonly control: (jobId: string, action: string) => void }
}

/**
 * The shared shell every shape extends: identity, the domain read model, and the
 * one implementation of tooltip / visibility / class / gestures / anchoring
 * (AD-8). No shape may re-implement these.
 *
 * Reactivity contract (learned the hard way — see BluetoothContent.tsx): the
 * widget TREE is static, so only STATIC spec fields may branch the JSX.
 * Everything that changes over time is a function of `state` and is wrapped in
 * `createComputed` by the renderer.
 */
export interface Shell<S> {
  readonly id: string
  /**
   * The domain read model: a plain getter (or an `Accessor`). The renderer calls
   * it inside `createComputed`, so any reactive reads it performs subscribe.
   * Stateless widgets pass `() => undefined`.
   */
  readonly read: () => S
  readonly tooltip?: (state: S) => string
  readonly visible?: (state: S) => boolean
  /** Extra CSS classes, joined after the mandatory `widget`. */
  readonly class?: string
  /**
   * State-derived extra CSS classes, joined after `class`. The renderer builds
   * the `class` prop from a `createComputed`, so this is how a widget reacts to
   * state with a class — e.g. `(r) => r.speedTesting ? "speedtesting" : null`.
   */
  readonly stateClass?: (state: S) => string | null
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
 * A descriptor widget: an icon and/or a label. Realized from today's
 * `BarWidgetSpec<S>` (AD-8) — the four live descriptors (btop, thunderbird,
 * settings, power-menu) are this shape.
 */
export interface DescriptorSpec<S> extends Shell<S> {
  readonly icon?: IconRef<S>
  /** Text beside the icon; absent renders no label at all. */
  readonly label?: (state: S) => string | null
}

/**
 * Back-compat alias: the vocabulary this kit shipped before AD-8. Kept so the
 * four live descriptors typecheck unchanged; new code should say
 * `DescriptorSpec<S>`.
 */
export type BarWidgetSpec<S> = DescriptorSpec<S>

/**
 * A rich widget: arbitrary content, rendered inside the shared shell. The clock
 * (two labels) and the recording indicator (dot + timer + buttons) are this
 * shape.
 */
export interface RichWidgetSpec<S, E = unknown> extends Shell<S> {
  readonly content: (state: S, ctx: BarContext<E>) => E
}

/**
 * The leaf widget shapes a collection may render (AD-8). Collections do not nest
 * collections; `ForeignCollectionSpec` covers the adapter-owned case.
 */
export type WidgetSpec<S, E = unknown> = DescriptorSpec<S> | RichWidgetSpec<S, E>

/**
 * A collection rendered from the widget's own items (workspaces). The item
 * renderer is the widget's; `key` gives each item a stable identity.
 */
export interface CollectionSpec<I, S, E = unknown> extends Shell<S> {
  readonly items: (state: S) => readonly I[]
  readonly key: (item: I) => string
  readonly item: (
    item: I,
    state: S,
    ctx: BarContext<E>,
  ) => WidgetSpec<S, E> | E
  /**
   * The gap between items. A collection-specific presentation hint: the shared
   * `Shell` carries no spacing because the collection is the only shape whose
   * root box lays out more than one child (clock and recording put their own
   * spacing on an inner box). Defaults to 0.
   */
  readonly spacing?: number
}

/**
 * A collection whose items and item renderer come from an adapter (the tray,
 * whose SNI items belong to other apps). Same shell, adapter-supplied rendering.
 */
export interface ForeignCollectionSpec<I, S, E = unknown> extends Shell<S> {
  readonly items: (state: S) => readonly I[]
  readonly render: (item: I, state: S, ctx: BarContext<E>) => E
  /** The gap between items — see `CollectionSpec.spacing`. Defaults to 0. */
  readonly spacing?: number
}

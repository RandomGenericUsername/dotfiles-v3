/**
 * The pure icon contract (spine AD-4, AD-7; doc 101 §4.1, §7).
 *
 * This module holds NO GTK and NO AGS import, so the resolution chain is
 * unit-testable without the desktop stack. `platform/adapters/icon.ts` is the
 * registry-backed facade that adapts the real manifest to this contract.
 *
 * `IconSource` is a tagged union, not a bare path: a provider may answer with a
 * FILE (the runtime's rendered SVG) or a NAME (a themed symbolic icon on a bare
 * desktop, AD-18). The renderer decides how to draw each.
 */
export type IconSource =
  | { readonly kind: "file"; readonly path: string }
  | { readonly kind: "name"; readonly name: string }

/** The subset of a `bar_mappings` entry the chain reads. */
export interface IconBarMapping {
  /** state key -> variant name. */
  readonly states: Readonly<Record<string, string>>
}

/**
 * The icon provider port (AD-4). `resolve` is the override layer; `barMappings`
 * is optional because only providers with a state->variant table implement it.
 */
export interface IconProvider {
  /** The group's state->variant table, or null when it has none. */
  readonly barMappings?: (group: string) => IconBarMapping | null
  /** The art for a variant, or null when the provider has none. */
  readonly resolve: (group: string, variant: string) => IconSource | null
}

/**
 * A widget's icon, expressed declaratively: the manifest GROUP (the glyph
 * source) plus a pure function from the domain read model to a state key or
 * variant name.
 *
 * This is the piece the bar currently repeats per widget (`getBatteryIconPath`,
 * `getNetworkIconPath`, … each re-navigating `bar_mappings.states` by hand). One
 * `IconRef` per domain, resolved by the kit, means the widget never touches the
 * manifest and the runtime behavior (which state maps to which variant) is a
 * pure, testable function.
 */
export interface IconRef<S> {
  readonly group: string
  /** The state key / variant name for a state, or null when there is none. */
  readonly variant: (state: S) => string | null
  /**
   * Last-resort resolution when the provider has no table/art for the group
   * (AD-7). A single-glyph group declares an identity fallback
   * (`(v) => ({ kind: "name", name: v })`); a widget with no art returns null.
   */
  readonly fallback?: (variant: string) => IconSource | null
}

/** An icon addressed by a DIRECT variant name (no `bar_mappings` table). */
export function iconByVariant<S>(
  group: string,
  variantFn: (state: S) => string,
): IconRef<S> {
  return { group, variant: (state) => variantFn(state) || null }
}

/**
 * An icon addressed by a STATE KEY, resolved through the group's
 * `bar_mappings.states` table by the resolution chain (AD-7). The ref emits the
 * key; the chain maps `key -> variant -> art`.
 */
export function iconByStateKey<S>(
  group: string,
  key: (state: S) => string,
): IconRef<S> {
  return { group, variant: (state) => key(state) || null }
}

/**
 * The one resolution chain (AD-7, doc 101 §7):
 *
 *   v = ref.variant(state)
 *   1. provider.barMappings(group)?.states[v] -> provider.resolve(group, variant)
 *   2. ref.fallback(v)
 *   3. blank (null)
 *
 * A ref that emits no variant resolves to blank: there is nothing to map and
 * nothing for a fallback to fall back TO.
 */
export function resolveIconSource<S>(
  provider: IconProvider,
  ref: IconRef<S>,
  state: S,
): IconSource | null {
  const key = ref.variant(state)
  if (!key) return null

  const variant = provider.barMappings?.(ref.group)?.states[key] ?? key
  const resolved = provider.resolve(ref.group, variant)
  if (resolved) return resolved

  return ref.fallback?.(key) ?? null
}

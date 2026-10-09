import { registry } from "../lib/icon-registry"

/**
 * A widget's icon, expressed declaratively: the manifest GROUP (the glyph
 * SOURCE) plus a pure function from the domain read model to a variant name.
 *
 * This is the piece the bar currently repeats per widget (`getBatteryIconPath`,
 * `getNetworkIconPath`, … each re-navigating `bar_mappings.states` by hand). One
 * `IconRef` per domain, resolved by the kit, means the widget never touches the
 * manifest and the runtime behavior (which variant for which state) is a pure,
 * testable function.
 */
export interface IconRef<S> {
  readonly group: string
  /** The variant name for a state, or null when the group has no art for it. */
  readonly variant: (state: S) => string | null
}

/** An icon addressed by a DIRECT variant name (no `bar_mappings` table). */
export function iconByVariant<S>(
  group: string,
  variantFn: (state: S) => string,
): IconRef<S> {
  return { group, variant: (state) => variantFn(state) || null }
}

/** An icon addressed by a STATE KEY, resolved through the group's `bar_mappings`. */
export function iconByStateKey<S>(
  group: string,
  key: (state: S) => string,
): IconRef<S> {
  return {
    group,
    variant: (state) => registry.getBarMappings(group)?.states[key(state)] ?? null,
  }
}

/**
 * Resolve an `IconRef` to a rendered SVG path, or `""` when the group/variant
 * has no art. `""` (not null) is what `image.set_from_file` wants; a missing
 * icon therefore renders nothing rather than throwing.
 */
export function resolveIcon<S>(ref: IconRef<S>, state: S): string {
  const variant = ref.variant(state)
  return variant ? registry.resolve(ref.group, variant) ?? "" : ""
}

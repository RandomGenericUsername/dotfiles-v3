import { registry } from "./icon-registry"
import {
  resolveIconSource,
  type IconProvider,
  type IconRef,
  type IconSource,
} from "../ports/icon-source"

/**
 * The icon contract's public facade (spine AD-4, AD-7).
 *
 * The pure contract — `IconSource`, `IconProvider`, `IconRef`, the constructors
 * and the resolution chain — lives in `../ports/icon-source` so it is
 * unit-testable without GTK. This file binds it to the real manifest registry: it adapts
 * `registry` to the `IconProvider` port and exposes `resolveIcon` for callers.
 *
 * The re-exports are EXPLICIT (not `export *`): the per-app symbol gate
 * (`ags-symbol-check.mjs`) resolves a named import against the exporting
 * module's source, and it does not follow a star re-export.
 */
export { iconByStateKey, iconByVariant, resolveIconSource } from "../ports/icon-source"
export type { IconBarMapping, IconProvider, IconRef, IconSource } from "../ports/icon-source"

/**
 * The manifest registry as an `IconProvider`. `registry.resolve` returns a bare
 * path (or null); the port answers with the tagged union, so the file case keeps
 * the current path-returning behavior (AD-4).
 */
export const registryProvider: IconProvider = {
  barMappings: (group) => registry.getBarMappings(group),
  resolve: (group, variant) => {
    const path = registry.resolve(group, variant)
    return path ? { kind: "file", path } : null
  },
}

/**
 * Resolve an `IconRef` through the one chain (AD-7), or null (blank) when the
 * group/variant has no art and no fallback covers it. A blank renders nothing
 * rather than throwing.
 */
export function resolveIcon<S>(ref: IconRef<S>, state: S): IconSource | null {
  return resolveIconSource(registryProvider, ref, state)
}

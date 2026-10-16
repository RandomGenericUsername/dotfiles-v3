/**
 * The bar validators (spine AD-15; ags-bar-validation task 1.2).
 *
 * `validateLayout` + `validateIcons` are the ONE rule set with TWO
 * enforcements: provisioning runs both and fails the install on any error
 * (strict), while the bar runs the same functions at startup and degrades
 * (skip unknown widget, apply defaults, blank a missing glyph). Same rules,
 * different enforcement, so they cannot drift.
 *
 * Both run over the DECLARATIONS (`CapabilityDecl` / `IconGroupDecl` from
 * `bar-manifest`) plus the artifact — never over the runtime `Capability`
 * objects (which carry `create` and need the desktop stack). Doc 101 §6.2's
 * `validateLayout(layout, capabilities: readonly Capability[])` signature is
 * deliberately narrowed here per the spine AD-15 review: the validator must
 * be importable where no `create` can run.
 *
 * This module is PURE: `import type` only, zero runtime imports. Importing it
 * succeeds on a stock runner with no GJS/GTK/`ags` (`node --test` import).
 * Keep it that way.
 */

import type { BarEntry, BarLayout } from "../kit/layout"
import type { CapabilityDecl, IconGroupDecl } from "./bar-manifest"

/**
 * The validator issue codes with a declaration basis today.
 *
 * Doc 101 §6.2 also names `missing-param` and `bad-param`; neither is
 * implemented because the manifest declares params as bare names
 * (`CapabilityDecl.params: readonly string[]`) with no value schema, no
 * required set, and no defaults — there is nothing a missing/bad value could
 * be checked against. When a capability first declares a valued param, its
 * schema arrives with the declaration and these codes come with it.
 */
export type IssueCode =
  | "unknown-widget"
  | "duplicate-widget"
  | "unknown-param"
  | "missing-icon-key"

export interface BarIssue {
  readonly severity: "error" | "warning"
  readonly code: IssueCode
  readonly message: string
  readonly widgetId?: string
  readonly param?: string
  readonly iconGroup?: string
  readonly iconState?: string
}

export interface ValidationResult {
  readonly ok: boolean
  readonly issues: readonly BarIssue[]
}

/** A layout is placement only: every entry in every section, in order. */
function allEntries(layout: BarLayout): readonly BarEntry[] {
  return [
    ...(layout.sections.start ?? []),
    ...(layout.sections.center ?? []),
    ...(layout.sections.end ?? []),
  ]
}

/**
 * Validate a layout against the capability declarations.
 *
 * - An entry id with no declaration is `unknown-widget` (error).
 * - An entry param outside the declaration's closed `params` set is
 *   `unknown-param` (error). No widget takes params today, so any param
 *   at all is unknown — the empty list IS the declaration.
 * - A repeated id is `duplicate-widget` (error) unless the declaration sets
 *   `multi: true`.
 */
export function validateLayout(
  layout: BarLayout,
  capabilities: readonly CapabilityDecl[],
): ValidationResult {
  const byId = new Map(capabilities.map((c) => [c.id, c]))
  const issues: BarIssue[] = []
  const seen = new Set<string>()
  for (const entry of allEntries(layout)) {
    const decl = byId.get(entry.id)
    if (decl === undefined) {
      issues.push({
        severity: "error",
        code: "unknown-widget",
        message: `unknown widget "${entry.id}"`,
        widgetId: entry.id,
      })
      continue
    }
    for (const name of Object.keys(entry.params ?? {})) {
      if (!decl.params.includes(name)) {
        issues.push({
          severity: "error",
          code: "unknown-param",
          message: `unknown param "${name}" for widget "${entry.id}"`,
          widgetId: entry.id,
          param: name,
        })
      }
    }
    if (seen.has(entry.id)) {
      if (!decl.multi) {
        issues.push({
          severity: "error",
          code: "duplicate-widget",
          message: `duplicate widget "${entry.id}" (capability is single-instance)`,
          widgetId: entry.id,
        })
      }
    } else {
      seen.add(entry.id)
    }
  }
  return { ok: !issues.some((i) => i.severity === "error"), issues }
}

/** The `bar_mappings.states` table of one `icons.json` group, or empty. */
function stateTable(entry: unknown): Readonly<Record<string, string>> {
  if (entry === null || typeof entry !== "object") return {}
  const mappings = (entry as { bar_mappings?: unknown }).bar_mappings
  if (mappings === null || typeof mappings !== "object") return {}
  const states = (mappings as { states?: unknown }).states
  if (states === null || typeof states !== "object" || Array.isArray(states)) {
    return {}
  }
  const table: Record<string, string> = {}
  for (const [key, value] of Object.entries(states)) {
    if (typeof value === "string") table[key] = value
  }
  return table
}

/**
 * The variant names one `icons.json` group renders.
 *
 * The real artifact shape is `variants: [{ name, output }]`; a bare string
 * element is tolerated so hand-built fixtures stay small.
 */
function variantNames(entry: unknown): ReadonlySet<string> {
  if (entry === null || typeof entry !== "object") return new Set()
  const variants = (entry as { variants?: unknown }).variants
  if (!Array.isArray(variants)) return new Set()
  const names = new Set<string>()
  for (const variant of variants) {
    if (typeof variant === "string") {
      names.add(variant)
    } else if (variant !== null && typeof variant === "object") {
      const name = (variant as { name?: unknown }).name
      if (typeof name === "string") names.add(name)
    }
  }
  return names
}

/**
 * Validate the icons artifact against the icon-group declarations.
 *
 * `artifact` is the parsed `icons.json` top level (group names to group
 * objects; non-group keys such as `schemaVersion` are ignored). Only groups
 * declaring a non-empty `states` list are checked — groups the bar addresses
 * by variant directly (launchers, tray) declare none and are exempt. For a
 * checked group every declared state key must map to a variant that exists;
 * a missing key and a key mapping to a missing variant are both
 * `missing-icon-key` (error). Artifact groups with no declaration are out of
 * scope (e.g. `power-mode`, panel-only) and never reported.
 */
export function validateIcons(
  artifact: Readonly<Record<string, unknown>>,
  groups: readonly IconGroupDecl[],
): ValidationResult {
  const issues: BarIssue[] = []
  for (const group of groups) {
    if (group.states.length === 0) continue
    const entry = artifact[group.name]
    const table = stateTable(entry)
    const variants = variantNames(entry)
    for (const state of group.states) {
      const variant = table[state]
      if (variant === undefined) {
        issues.push({
          severity: "error",
          code: "missing-icon-key",
          message: `missing state key "${state}" in icon group "${group.name}"`,
          iconGroup: group.name,
          iconState: state,
        })
      } else if (!variants.has(variant)) {
        issues.push({
          severity: "error",
          code: "missing-icon-key",
          message: `state key "${state}" in icon group "${group.name}" maps to missing variant "${variant}"`,
          iconGroup: group.name,
          iconState: state,
        })
      }
    }
  }
  return { ok: !issues.some((i) => i.severity === "error"), issues }
}

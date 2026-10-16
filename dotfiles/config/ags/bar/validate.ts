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
 *
 * `unknown-schema-version` is the odd one out: it is ALWAYS a warning, never
 * an error (task 2.3). An artifact carrying no version or an unrecognised one
 * degrades — the bar warns and runs, and the strict install gate passes it.
 * Only the four rule violations above fail the install.
 */
export type IssueCode =
  | "unknown-widget"
  | "duplicate-widget"
  | "unknown-param"
  | "missing-icon-key"
  | "unknown-schema-version"

/**
 * The icons artifact schema version the bar understands (spine AD-16; task
 * 2.3).
 *
 * SINGLE-OWNER WARNING: the producer stamps
 * `compositor_configs_icon_manifest_schema_version`
 * (`src/provisioning/ansible/roles/compositor_configs/vars/main.yml`); this
 * const is the CONSUMER mirror for the lenient runtime path only. The strict
 * install gate does NOT read this const — provisioning passes its owned var
 * explicitly via the CLI's `--expect-schema-version`, so a stale deployed
 * artifact fails against the current expectation. Bump both together when the
 * manifest shape changes.
 */
export const EXPECTED_SCHEMA_VERSION = 1

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

/**
 * Check one artifact's `schemaVersion` (spine AD-16; task 2.3).
 *
 * TOTAL and WARNING-ONLY: never throws, never errors. A missing version (a
 * legacy artifact predates versioning), a non-numeric version, or an
 * unrecognised version each yield exactly one `unknown-schema-version`
 * WARNING — the bar warns and runs with the artifact as-is (degrade, never
 * crash), and the strict gate passes warnings (only errors fail the install).
 * A `null`/non-object artifact warns the same way rather than throwing, so a
 * corrupt file degrades instead of crashing startup.
 *
 * A `BarLayout` carries NO version field of its own (kit/layout.ts): when a
 * `bar.json` FILE exists, its top-level `schemaVersion` is the artifact
 * version checked here, and the layout value itself stays unversioned.
 */
export function checkSchemaVersion(
  artifact: unknown,
  artifactName: string,
  expected: number = EXPECTED_SCHEMA_VERSION,
): BarIssue[] {
  if (artifact === null || typeof artifact !== "object" || Array.isArray(artifact)) {
    return [
      {
        severity: "warning",
        code: "unknown-schema-version",
        message: `${artifactName} is not a versioned artifact: expected a JSON object, degrading without a version check`,
      },
    ]
  }
  const version = (artifact as { schemaVersion?: unknown }).schemaVersion
  if (version === undefined) {
    return [
      {
        severity: "warning",
        code: "unknown-schema-version",
        message: `${artifactName} carries no schemaVersion (expected ${expected}): assuming the deployed shape, degrading`,
      },
    ]
  }
  if (version !== expected) {
    return [
      {
        severity: "warning",
        code: "unknown-schema-version",
        message: `${artifactName} carries schemaVersion ${JSON.stringify(version)} (expected ${expected}): running with a degraded artifact`,
      },
    ]
  }
  return []
}

/** The lenient enforcement result: the renderable layout plus its warnings. */
export interface SanitizedLayout {
  readonly layout: BarLayout
  readonly warnings: readonly string[]
}

/**
 * The LENIENT enforcement of `validateLayout` (spine AD-15; task 2.2).
 *
 * The bar runs the SAME rule set as the strict gate but degrades instead of
 * failing: an unknown-widget entry is SKIPPED, a duplicate-widget repeat past
 * the first is SKIPPED (unless the capability declares `multi: true`), and
 * unknown params are STRIPPED so declared defaults apply (no widget declares
 * a param today, so any param at all is stripped). Section structure is
 * preserved — an absent section stays absent — and entries that survive keep
 * their identity, so the sanitized layout renders exactly the valid prefix of
 * the input.
 *
 * Missing glyphs are NOT handled here: the icon side degrades at resolve
 * time, in the kit's `resolveIcon` (`ags-platform/adapters/icon` returns null
 * for an unresolvable key and `applyIconSource` blanks the image) — pinned by
 * `tests/ts/icon-state-keys.test.ts`. Importing `icons.json` into the bar a
 * second time to run `validateIcons` at startup would duplicate the artifact
 * the platform already bundles, so the bar enforces the layout rules here
 * and the icon rule at resolve time.
 *
 * PURE: no GJS, no logging — warnings are returned and the caller (`Bar.tsx`)
 * reports them. Tolerant of a mistyped input: a missing `sections` table
 * degrades to an empty layout rather than throwing.
 */
export function sanitizeLayout(
  layout: BarLayout,
  capabilities: readonly CapabilityDecl[],
): SanitizedLayout {
  const byId = new Map(capabilities.map((c) => [c.id, c]))
  const warnings: string[] = []
  const seen = new Set<string>()
  const clean = (entries: readonly BarEntry[] | undefined): readonly BarEntry[] | undefined => {
    if (entries === undefined) return undefined
    const kept: BarEntry[] = []
    for (const entry of entries) {
      const decl = byId.get(entry.id)
      if (decl === undefined) {
        warnings.push(`unknown widget "${entry.id}" skipped`)
        continue
      }
      if (seen.has(entry.id)) {
        if (!decl.multi) {
          warnings.push(`duplicate widget "${entry.id}" skipped (single-instance)`)
          continue
        }
      } else {
        seen.add(entry.id)
      }
      const params = entry.params ?? {}
      const stripped = Object.keys(params).filter((name) => !decl.params.includes(name))
      if (stripped.length === 0) {
        kept.push(entry)
      } else {
        const keptParams: Record<string, unknown> = {}
        for (const name of decl.params) {
          if (name in params) keptParams[name] = params[name]
        }
        warnings.push(
          `unknown param(s) ${stripped.map((n) => `"${n}"`).join(", ")} for widget "${entry.id}" stripped (defaults apply)`,
        )
        kept.push(
          Object.keys(keptParams).length > 0 ? { id: entry.id, params: keptParams } : { id: entry.id },
        )
      }
    }
    return kept
  }
  const sections = layout?.sections ?? {}
  return {
    layout: {
      sections: {
        start: clean(sections.start),
        center: clean(sections.center),
        end: clean(sections.end),
      },
    },
    warnings,
  }
}

/**
 * The `ags-bar-validate` install gate (spine AD-15; ags-bar-validation task 1.3).
 *
 * A thin adapter over task 1.2: it reads the `icons.json` artifact and the
 * optional `bar.json` layout, runs the shared `validateLayout` +
 * `validateIcons` over the task-1.1 `BAR_MANIFEST` declarations, and exits
 * non-zero when either fails. Provisioning runs this strictly (a bad layout
 * or a bad icons table fails the install); the bar runs the SAME functions
 * leniently at startup (skip unknown widget, apply defaults, blank a missing
 * glyph) — one rule set, two enforcements, so they cannot drift.
 *
 * Usage:
 *   node validate-cli.ts --icons <icons.json> [--layout <bar.json>]
 *
 * `--layout` is optional: with no `bar.json` the repo-default layout is the
 * always-non-null floor of the chain (AD-9/AD-18), so the gate validates the
 * default against the deployed icons. Exit 0 means both artifacts validate;
 * exit 1 means a validation error (the `BarIssue`s print to stderr); exit 2
 * means usage, IO, or JSON failure.
 *
 * This module is PURE: `node:*` plus the pure manifest/validator/default
 * modules only — no GJS, no GTK, no `ags`. Importing or running it succeeds
 * on a stock runner with no desktop stack. Imports carry the explicit `.ts`
 * suffix the test files use (`tsconfig.tests.json` sets
 * `allowImportingTsExtensions` for exactly that) because plain `node`
 * type-stripping does no extensionless lookup — and provisioning runs this
 * file with plain `node`, not through the test resolve hook, so the suffix
 * here is load-bearing. The file is never bundled (`ags bundle` never sees
 * it), so the suffix costs the app nothing.
 */

import { readFileSync } from "node:fs"
import { dirname, join, resolve } from "node:path"
import { fileURLToPath } from "node:url"
import { BAR_MANIFEST } from "./bar-manifest.ts"
import { DEFAULT_LAYOUT } from "./layout.default.ts"
import { validateIcons, validateLayout } from "./validate.ts"
import type { BarLayout } from "../kit/layout.ts"

const HERE = dirname(fileURLToPath(import.meta.url))

function usage(): string {
  return "usage: node validate-cli.ts --icons <icons.json> [--layout <bar.json>]"
}

/** The argv shape this gate accepts. `--layout` is optional (see above). */
interface CliArgs {
  readonly iconsPath: string
  readonly layoutPath: string | null
}

/** Parse argv. Throws an `Error` whose message is the usage failure. */
function parseArgs(argv: readonly string[]): CliArgs {
  let iconsPath: string | null = null
  let layoutPath: string | null = null
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i]
    if (arg === "--icons" && i + 1 < argv.length) {
      iconsPath = argv[++i]
    } else if (arg === "--layout" && i + 1 < argv.length) {
      layoutPath = argv[++i]
    } else {
      throw new Error(`${usage()}\nunexpected argument: ${arg}`)
    }
  }
  if (iconsPath === null) throw new Error(usage())
  return { iconsPath, layoutPath }
}

/** Read + parse a JSON file. Throws an `Error` naming the path. */
function readJson(path: string): unknown {
  let text: string
  try {
    text = readFileSync(path, "utf8")
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    throw new Error(`cannot read ${path}: ${reason}`)
  }
  try {
    return JSON.parse(text) as unknown
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    throw new Error(`cannot parse ${path}: ${reason}`)
  }
}

/**
 * Narrow parsed JSON to a `BarLayout`. The validators own every semantic
 * check; this guard only keeps a non-layout file from reaching them as a
 * mistyped cast (a bare array or a string has no `sections` to walk).
 */
function asLayout(artifact: unknown, path: string): BarLayout {
  if (artifact === null || typeof artifact !== "object" || Array.isArray(artifact)) {
    throw new Error(`${path} is not a bar layout: expected an object with a sections table`)
  }
  if (!("sections" in artifact)) {
    throw new Error(`${path} is not a bar layout: expected an object with a sections table`)
  }
  return artifact as BarLayout
}

/**
 * Run the gate. Returns the process exit code; all reporting is the caller's
 * job so the exit-code contract stays in one place.
 */
export function run(argv: readonly string[]): { readonly code: number; readonly report: string } {
  let args: CliArgs
  try {
    args = parseArgs(argv)
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    return { code: 2, report: `${reason}\n` }
  }
  let icons: unknown
  try {
    icons = readJson(args.iconsPath)
  } catch (error) {
    const reason = error instanceof Error ? error.message : String(error)
    return { code: 2, report: `${reason}\n` }
  }
  if (icons === null || typeof icons !== "object" || Array.isArray(icons)) {
    return { code: 2, report: `${args.iconsPath} is not an icons artifact: expected a JSON object\n` }
  }
  let layout: BarLayout
  if (args.layoutPath !== null) {
    try {
      layout = asLayout(readJson(args.layoutPath), args.layoutPath)
    } catch (error) {
      const reason = error instanceof Error ? error.message : String(error)
      return { code: 2, report: `${reason}\n` }
    }
  } else {
    layout = DEFAULT_LAYOUT
  }
  const layoutResult = validateLayout(layout, BAR_MANIFEST.capabilities)
  const iconsResult = validateIcons(icons as Record<string, unknown>, BAR_MANIFEST.iconGroups)
  const lines: string[] = []
  for (const issue of [...layoutResult.issues, ...iconsResult.issues]) {
    lines.push(`${issue.severity} ${issue.code}: ${issue.message}`)
  }
  if (lines.length === 0) {
    const layoutName = args.layoutPath ?? "<repo-default layout>"
    return { code: 0, report: `ok: ${layoutName} + ${args.iconsPath} validate\n` }
  }
  return { code: 1, report: `${lines.join("\n")}\n` }
}

const invokedAsMain =
  process.argv.length > 1 && resolve(process.argv[1]) === join(HERE, "validate-cli.ts")

if (invokedAsMain) {
  const { code, report } = run(process.argv.slice(2))
  if (code === 0) {
    process.stdout.write(report)
  } else {
    process.stderr.write(report)
  }
  process.exit(code)
}

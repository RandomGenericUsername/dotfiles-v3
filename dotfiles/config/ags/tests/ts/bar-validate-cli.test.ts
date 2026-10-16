import assert from "node:assert/strict"
import { test } from "node:test"
import { spawnSync } from "node:child_process"
import { mkdtempSync, readFileSync, writeFileSync } from "node:fs"
import { tmpdir } from "node:os"
import { fileURLToPath } from "node:url"
import { dirname, join } from "node:path"

/**
 * The `ags-bar-validate` CLI (spine AD-15; ags-bar-validation task 1.3).
 *
 * The CLI is a thin adapter over `validateLayout` + `validateIcons` — the
 * rule set lives in `bar/validate.ts` and is pinned there, so this suite pins
 * only the adapter contract: exit 0 on a good layout, non-zero on a bad one,
 * with the `BarIssue`s on stderr. Each case spawns the CLI as a subprocess
 * with plain `node` (no resolve hook), which is exactly how provisioning
 * will invoke it — so a subprocess failure here is a broken install gate,
 * not a broken test harness.
 */

const HERE = dirname(fileURLToPath(import.meta.url))
const AGS = join(HERE, "..", "..")
const CLI = join(AGS, "bar", "validate-cli.ts")
const REAL_ICONS = join(AGS, "icons.json")

interface RunResult {
  readonly code: number | null
  readonly stdout: string
  readonly stderr: string
}

function runCli(args: readonly string[]): RunResult {
  const child = spawnSync(process.execPath, [CLI, ...args], { encoding: "utf8" })
  return { code: child.status, stdout: child.stdout, stderr: child.stderr }
}

function scratchDir(): string {
  return mkdtempSync(join(tmpdir(), "ags-bar-validate-"))
}

function writeJson(dir: string, name: string, value: unknown): string {
  const path = join(dir, name)
  writeFileSync(path, JSON.stringify(value), "utf8")
  return path
}

test("a good layout + the real icons.json exits 0", () => {
  const dir = scratchDir()
  const layout = writeJson(dir, "bar.json", { sections: { center: [{ id: "clock" }] } })
  const result = runCli(["--icons", REAL_ICONS, "--layout", layout])
  assert.equal(result.code, 0)
  assert.match(result.stdout, /^ok:/)
  assert.equal(result.stderr, "")
})

test("no --layout validates the repo-default layout and exits 0", () => {
  const result = runCli(["--icons", REAL_ICONS])
  assert.equal(result.code, 0)
  assert.match(result.stdout, /^ok:/)
})

test("a bad layout exits 1 and names the widget on stderr", () => {
  const dir = scratchDir()
  const layout = writeJson(dir, "bar.json", { sections: { center: [{ id: "clok" }] } })
  const result = runCli(["--icons", REAL_ICONS, "--layout", layout])
  assert.equal(result.code, 1)
  assert.match(result.stderr, /unknown-widget/)
  assert.match(result.stderr, /clok/)
})

test("a bad icons artifact exits 1", () => {
  const dir = scratchDir()
  const layout = writeJson(dir, "bar.json", { sections: { center: [{ id: "clock" }] } })
  const icons = writeJson(dir, "icons.json", {})
  const result = runCli(["--icons", icons, "--layout", layout])
  assert.equal(result.code, 1)
  assert.match(result.stderr, /missing-icon-key/)
})

test("missing flags exit 2 with usage", () => {
  const result = runCli([])
  assert.equal(result.code, 2)
  assert.match(result.stderr, /usage:/)
})

test("an unreadable file exits 2", () => {
  const result = runCli(["--icons", join(scratchDir(), "absent.json")])
  assert.equal(result.code, 2)
  assert.match(result.stderr, /cannot read/)
})

test("the real icons.json the good case relies on is the deployed artifact", () => {
  const parsed = JSON.parse(readFileSync(REAL_ICONS, "utf8")) as Record<string, unknown>
  assert.ok(parsed["battery"] !== undefined, "expected a battery group in icons.json")
})

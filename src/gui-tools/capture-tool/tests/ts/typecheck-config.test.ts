// ---------------------------------------------------------------------------
// Typecheck CONFIG tests (harden-capture-typecheck-config).
//
// THE DEFECT THESE PIN. `tsconfig.capture.json` declared neither `"types"` nor
// `"typeRoots"`. With both absent, TypeScript's default typeRoots walk takes
// every `node_modules/@types` from the config's own directory upwards and
// auto-includes ALL of it. So the APP's ambient-type surface was not a property
// of the app — it was a property of where a directory happened to sit on disk.
//
// The app is GJS, not Node: no `process`, no `Buffer`, no `require`. It should
// have an EMPTY ambient-type surface. It got one by accident: `@types/node`
// lives at `tests/node_modules/`, which the upward walk never descends into.
// That is luck, not design, and `git mv` away from luck.
//
// WHAT IS ACTUALLY ASSERTED HERE, and why it is a real assertion rather than a
// comment:
//
//   1. The app config PINS the surface explicitly: `compilerOptions.types` is
//      present AND is the empty array. Removing the pin, or renaming it to
//      `["node"]`, fails these tests immediately — they do not depend on
//      whether TypeScript happens to be installed.
//   2. The tests config still ASKS for node by name. This is the half that
//      could regress the other way: pinning the app must not have been
//      achieved by deleting node types from the world. The domain unit tests
//      genuinely need `node:test` and `node:assert`.
//   3. PROVENANCE-FREE EVIDENCE, when TypeScript is resolvable: run the real
//      `tsc --noEmit --listFiles` over the app project and assert that ZERO
//      files from `@types/node` are in the program. This is the assertion that
//      bites for the original defect — it is checked against the actual
//      compiler, not against the author's intent. It SKIPS (loudly, on the
//      console) when TypeScript is absent, exactly as the `capture-test`
//      target already does for its own typecheck step.
//
// On (3): `--listFiles` is the direct measurement of "what ambient types did
// this config actually admit", which is the property under test. Asserting it
// against `tsc` rather than re-deriving typeRoots resolution in JS avoids
// reimplementing the very walk whose behaviour is in question.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync, existsSync } from "node:fs"
import { spawnSync } from "node:child_process"
import { fileURLToPath } from "node:url"
import { dirname, resolve } from "node:path"

const HERE = dirname(fileURLToPath(import.meta.url))
const CAPTURE_TOOL = resolve(HERE, "../..")
const APP_CONFIG = resolve(CAPTURE_TOOL, "tsconfig.capture.json")
const TESTS_CONFIG = resolve(CAPTURE_TOOL, "tests/tsconfig.tests.json")
const REPO_ROOT = resolve(CAPTURE_TOOL, "../../..")

// The configs are JSONC (they carry a "//" rationale block and inline
// comments). Strip comments while respecting string literals — the top-level
// `"//"` KEY is itself a string containing slashes, so a naive regex strip
// would eat the file.
function parseJsonc(path: string): any {
  const raw = readFileSync(path, "utf8")
  let out = ""
  let inString = false
  let escaped = false
  for (let i = 0; i < raw.length; i++) {
    const ch = raw[i]
    if (inString) {
      out += ch
      if (escaped) escaped = false
      else if (ch === "\\") escaped = true
      else if (ch === '"') inString = false
      continue
    }
    if (ch === '"') {
      inString = true
      out += ch
      continue
    }
    if (ch === "/" && raw[i + 1] === "/") {
      while (i < raw.length && raw[i] !== "\n") i++
      out += "\n"
      continue
    }
    if (ch === "/" && raw[i + 1] === "*") {
      i += 2
      while (i < raw.length && !(raw[i] === "*" && raw[i + 1] === "/")) i++
      i++
      continue
    }
    out += ch
  }
  return JSON.parse(out)
}

const appConfig = parseJsonc(APP_CONFIG)
const appOptions = appConfig.compilerOptions ?? {}

test("app config pins its ambient-type surface to empty", () => {
  // The core regression assertion. Absent `"types"`, the surface is whatever
  // the typeRoots walk happens to find, which is not a property of the app.
  assert.ok(
    Object.prototype.hasOwnProperty.call(appOptions, "types"),
    "tsconfig.capture.json must declare compilerOptions.types explicitly; " +
      "omitting it makes the app's ambient types depend on directory layout",
  )
  assert.deepEqual(
    appOptions.types,
    [],
    "the GJS app must have an EMPTY ambient-type surface: it has no process, " +
      "no Buffer and no require. If a type genuinely belongs here, add it by " +
      "name and re-justify it — do not reopen the walk.",
  )
})

test("app config does not name node, and does not widen typeRoots", () => {
  const types = appOptions.types as unknown[]
  assert.ok(
    !types.includes("node"),
    "the capture app runs under GJS, not Node; @types/node must not be ambient in it",
  )
  // `typeRoots` is the other half of the surface. A typeRoots pointing at a
  // shared node_modules would reintroduce the same layout dependence that
  // `"types": []` exists to remove, so it must stay unset.
  assert.ok(
    !Object.prototype.hasOwnProperty.call(appOptions, "typeRoots"),
    "tsconfig.capture.json must not set typeRoots; the empty `types` list is " +
      "what pins the surface, and a typeRoots would reopen the walk",
  )
})

test("tests config still asks for node types by name", () => {
  // The other half of the change. Pinning the app must not have been achieved
  // by taking node types away from the tests, which genuinely need node:test.
  const testsOptions = parseJsonc(TESTS_CONFIG).compilerOptions ?? {}
  assert.ok(
    Array.isArray(testsOptions.types) && testsOptions.types.includes("node"),
    "tsconfig.tests.json must keep `\"types\": [\"node\"]`; the domain unit " +
      "tests import node:test and node:assert",
  )
})

test("app program contains no @types/node files (real compiler evidence)", (t) => {
  const tsc = [
    resolve(REPO_ROOT, "node_modules/.bin/tsc"),
    resolve(CAPTURE_TOOL, "node_modules/.bin/tsc"),
  ].find((p) => existsSync(p))

  if (!tsc) {
    // Mirrors the `capture-test` target's own behaviour: the runtime tests
    // still ran and still assert (1)-(3) above; only this compiler-evidence
    // check is unavailable.
    console.log(
      "NOTE: typescript not resolvable, skipping the tsc --listFiles evidence check. " +
        "The three static assertions above still ran.",
    )
    return t.skip("typescript not installed")
  }

  const res = spawnSync(tsc, ["--noEmit", "-p", APP_CONFIG, "--listFiles"], {
    encoding: "utf8",
  })
  // The app project does NOT typecheck with a bare exit 0: the generated
  // @girs/ closure carries ~28 errors inside /usr/share/ags/js, which the
  // `capture-typecheck` target tolerates by path (see its `thirdparty` grep).
  // Replicate that tolerance exactly rather than inventing a stricter one:
  // any error under src/gui-tools/capture-tool is a real failure, anything
  // under /usr/share/ags/js is the known third-party baseline.
  const errorLines = (res.stdout + res.stderr)
    .split("\n")
    .filter((l) => l.includes("error TS"))
  const ours = errorLines.filter((l) => l.includes("src/gui-tools/capture-tool/"))
  assert.deepEqual(
    ours,
    [],
    `the app project must have 0 errors of its own, but tsc reported ${ours.length}:\n${ours.join("\n")}`,
  )
  // And the compile must have actually run rather than bailing early.
  assert.ok(
    res.status === 0 || res.status === 2,
    `tsc exited ${res.status}, which is neither success (0) nor the tolerated ` +
      `third-party-error status (2):\n${res.stderr}`,
  )

  const programFiles = res.stdout.split("\n")
  const nodeTypeFiles = programFiles.filter((f) => /@types[\\/]node[\\/]/.test(f))

  // This is the assertion the original defect fails. @types/node is currently
  // at tests/node_modules/, out of the walk's reach — so it is not in the
  // program today — but the property being pinned is that the config forbids
  // it, so relocating it cannot silently join the app.
  assert.deepEqual(
    nodeTypeFiles,
    [],
    `@types/node leaked into the GJS app program (${nodeTypeFiles.length} files). ` +
      `The app's ambient-type surface must stay empty regardless of where ` +
      `@types/node is installed on disk.`,
  )

  // Sanity: the probe above must not pass vacuously by measuring an empty
  // program. If tsc listed nothing at all, the check would be meaningless.
  assert.ok(
    programFiles.filter((f) => f.trim().length > 0).length > 10,
    "tsc --listFiles returned an implausibly small program; the evidence check " +
      "would be passing vacuously",
  )
})

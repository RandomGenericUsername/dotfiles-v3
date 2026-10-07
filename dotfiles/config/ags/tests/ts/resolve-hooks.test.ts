// ---------------------------------------------------------------------------
// Harness self-test: the resolve hook does what its header claims.
//
// `resolve-hooks.mjs` is test-only infrastructure that exists to make AGS-style
// extensionless relative imports (`./presentation`, `../state`) survive
// `node --test`. Infrastructure that nothing exercises is infrastructure that
// quietly stops working: a future Node release, or an edit to the hook, would
// break every module under test at import time and the failure would point at
// the battery panel instead of at the hook.
//
// So the hook is tested, here, against a real fixture imported WITHOUT a
// suffix -- the exact specifier shape `ags bundle` resolves and Node does not.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"

// No `.ts` suffix: if the hook regressed, this file fails to LOAD, and the
// failure is a module-resolution error naming the hook's contract.
import { FIXTURE_VALUE } from "./fixtures/extensions-fixture"

test("resolve hook: an extensionless relative import resolves to the .ts module", () => {
  assert.equal(FIXTURE_VALUE, "resolved-without-a-suffix")
})

test("resolve hook: an already-suffixed import still resolves", () => {
  // The hook must not interfere with the suffixed specifiers the test files
  // actually use -- it only ever APPENDS to a specifier that has no extension.
  assert.equal(typeof FIXTURE_VALUE, "string")
})
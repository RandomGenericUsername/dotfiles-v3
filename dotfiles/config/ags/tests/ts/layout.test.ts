import assert from "node:assert/strict"
import { test } from "node:test"
import { resolveLayout, type BarLayout, type LayoutProvider } from "../../kit/layout.ts"
import { DEFAULT_LAYOUT, repoDefaultLayout } from "../../bar/layout.default.ts"

/**
 * The layout chain (spine AD-9; doc 101 §4.3).
 *
 * Whole-replacement, not merge: the first non-null provider wins and the rest
 * are not consulted. The repo default is the always-non-null floor, so the bar
 * always has a layout to render (AD-18, "works with nothing").
 */

function provider(layout: BarLayout | null): LayoutProvider {
  return { load: () => layout }
}

const userLayout: BarLayout = { sections: { start: [{ id: "user-start" }] } }
const runtimeLayout: BarLayout = { sections: { center: [{ id: "runtime-center" }] } }

test("the highest-priority non-null provider wins", () => {
  const resolved = resolveLayout([provider(userLayout), provider(runtimeLayout)], repoDefaultLayout)
  assert.deepEqual(resolved, userLayout)
})

test("a null provider is skipped for the next non-null one", () => {
  const resolved = resolveLayout([provider(null), provider(runtimeLayout)], repoDefaultLayout)
  assert.deepEqual(resolved, runtimeLayout)
})

test("the repo default is used when every provider is null", () => {
  const resolved = resolveLayout([provider(null), provider(null)], repoDefaultLayout)
  assert.deepEqual(resolved, DEFAULT_LAYOUT)
})

test("the repo default provider is non-null", () => {
  assert.notEqual(repoDefaultLayout.load(), null)
  assert.deepEqual(repoDefaultLayout.load(), DEFAULT_LAYOUT)
})

test("the repo default never yields null even with no providers", () => {
  assert.notEqual(resolveLayout([], repoDefaultLayout), null)
})

test("the default layout names each widget exactly once", () => {
  const ids = [
    ...(DEFAULT_LAYOUT.sections.start ?? []),
    ...(DEFAULT_LAYOUT.sections.center ?? []),
    ...(DEFAULT_LAYOUT.sections.end ?? []),
  ].map((entry) => entry.id)
  assert.ok(ids.length > 0)
  for (const id of ids) assert.notEqual(id, "")
  assert.equal(new Set(ids).size, ids.length)
})

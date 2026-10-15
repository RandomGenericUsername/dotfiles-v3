import { describe, it } from "node:test"
import assert from "node:assert/strict"

import { createPreferences, type PreferencesSource } from "../../platform/ports/preferences.ts"
import { fakeRuntime } from "./fixtures/reactive-fixture.ts"

/**
 * The `Preferences` port (spine AD-12), driven by a fake source: a fake config
 * FILE plus a fake `FileMonitor`. These prove the two things the port exists
 * for — an absent file degrades to the fallback, and the ADAPTER (not the
 * widget) owns the monitor lifecycle, so a change republishes reactively.
 */

function fakeSource(initial: Record<string, Record<string, unknown>> = {}) {
  const files = new Map<string, Record<string, unknown>>(Object.entries(initial))
  const watchCalls: string[] = []
  const watchers = new Map<string, () => void>()
  const source: PreferencesSource = {
    read(namespace) {
      return files.get(namespace) ?? null
    },
    watch(namespace, onChange) {
      watchCalls.push(namespace)
      watchers.set(namespace, onChange)
      return () => {
        watchers.delete(namespace)
      }
    },
  }
  return {
    source,
    watchCalls,
    set(namespace: string, record: Record<string, unknown>): void {
      files.set(namespace, record)
    },
    remove(namespace: string): void {
      files.delete(namespace)
    },
    /** The fake monitor firing: what a real FileMonitor "changed" signal does. */
    fire(namespace: string): void {
      watchers.get(namespace)?.()
    },
  }
}

describe("preferences port", () => {
  it("degrades to the fallback when the file is absent", () => {
    const fake = fakeSource()
    const preferences = createPreferences(fake.source, fakeRuntime())
    const compact = preferences.get("capture-tool", "bar_compact_controls", false)
    assert.equal(compact(), false)
  })

  it("reads a present value over the fallback", () => {
    const fake = fakeSource({ "capture-tool": { bar_compact_controls: true } })
    const preferences = createPreferences(fake.source, fakeRuntime())
    const compact = preferences.get("capture-tool", "bar_compact_controls", false)
    assert.equal(compact(), true)
  })

  it("degrades a wrong-typed value to the fallback", () => {
    const fake = fakeSource({ "capture-tool": { bar_compact_controls: 1 } })
    const preferences = createPreferences(fake.source, fakeRuntime())
    const compact = preferences.get("capture-tool", "bar_compact_controls", false)
    assert.equal(compact(), false)
  })

  it("re-reads on a monitor change and updates the accessor", () => {
    const fake = fakeSource({ "capture-tool": { bar_compact_controls: false } })
    const preferences = createPreferences(fake.source, fakeRuntime())
    const compact = preferences.get("capture-tool", "bar_compact_controls", false)
    assert.equal(compact(), false)
    fake.set("capture-tool", { bar_compact_controls: true })
    fake.fire("capture-tool")
    assert.equal(compact(), true)
  })

  it("degrades back to the fallback when the file disappears", () => {
    const fake = fakeSource({ "capture-tool": { bar_compact_controls: true } })
    const preferences = createPreferences(fake.source, fakeRuntime())
    const compact = preferences.get("capture-tool", "bar_compact_controls", false)
    assert.equal(compact(), true)
    fake.remove("capture-tool")
    fake.fire("capture-tool")
    assert.equal(compact(), false)
  })

  it("watches a namespace once across multiple keys", () => {
    const fake = fakeSource({ "capture-tool": { bar_compact_controls: true, other: 7 } })
    const preferences = createPreferences(fake.source, fakeRuntime())
    preferences.get("capture-tool", "bar_compact_controls", false)
    preferences.get("capture-tool", "other", 0)
    assert.deepEqual(fake.watchCalls, ["capture-tool"])
  })

  it("returns the same accessor for a repeated get", () => {
    const fake = fakeSource({ "capture-tool": { bar_compact_controls: true } })
    const preferences = createPreferences(fake.source, fakeRuntime())
    const first = preferences.get("capture-tool", "bar_compact_controls", false)
    const second = preferences.get("capture-tool", "bar_compact_controls", false)
    assert.equal(first, second)
    assert.deepEqual(fake.watchCalls, ["capture-tool"])
  })
})

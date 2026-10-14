import assert from "node:assert/strict"
import { test } from "node:test"
import { createSurfaceMount, createSurfaceRegistry } from "../../kit/surface.ts"
import type { SurfaceSpec } from "../../kit/surface.ts"
import { overlays } from "../../kit/overlay.ts"

/**
 * The AD-10 mount policy, proven without GTK.
 *
 * `createSurfaceMount` is the pure decision `PopupHost` drives from its
 * visibility accessor: the body is built only while visible and dropped when
 * hidden. These tests pin the two claims the spine makes — the body is mounted
 * lazily, and (wired to the one overlay coordinator) at most one body is live.
 */

test("a surface body is built only while visible and dropped when hidden", () => {
  let builds = 0
  let teardowns = 0
  const mount = createSurfaceMount(
    () => ({ n: ++builds }),
    () => { teardowns += 1 },
  )

  assert.equal(mount.isMounted(), false)
  assert.equal(mount.render(false), null)
  assert.equal(builds, 0, "the factory must not run while hidden")
  assert.equal(teardowns, 0)

  const first = mount.render(true)
  assert.deepEqual(first, { n: 1 })
  assert.equal(builds, 1, "showing builds exactly one body")
  assert.equal(mount.isMounted(), true)

  // Idempotent while visible: an unrelated re-render returns the same instance.
  assert.equal(mount.render(true), first)
  assert.equal(builds, 1, "a re-render must not rebuild a visible body")

  mount.render(false)
  assert.equal(teardowns, 1, "hiding tears the body down")
  assert.equal(mount.isMounted(), false)

  const second = mount.render(true)
  assert.deepEqual(second, { n: 2 }, "a re-show builds a fresh body")
  assert.equal(builds, 2)
})

test("wired to the overlay coordinator, at most one surface body is live", () => {
  let aOpen = false
  let bOpen = false
  overlays.register({
    id: "surface-mount-test-a",
    isOpen: () => aOpen,
    open: () => { aOpen = true },
    close: () => { aOpen = false },
  })
  overlays.register({
    id: "surface-mount-test-b",
    isOpen: () => bOpen,
    open: () => { bOpen = true },
    close: () => { bOpen = false },
  })

  const a = createSurfaceMount(() => ({ id: "a" }))
  const b = createSurfaceMount(() => ({ id: "b" }))
  const live = () =>
    [
      a.render(overlays.isOpen("surface-mount-test-a")),
      b.render(overlays.isOpen("surface-mount-test-b")),
    ].filter((body) => body !== null).length

  overlays.open("surface-mount-test-a")
  assert.equal(live(), 1)
  assert.equal(a.isMounted(), true)
  assert.equal(b.isMounted(), false)

  overlays.open("surface-mount-test-b")
  assert.equal(live(), 1, "exactly one body is live after the swap")
  assert.equal(a.isMounted(), false, "opening B must close A")
  assert.equal(b.isMounted(), true)

  overlays.closeAll()
  assert.equal(live(), 0)
})

test("the registry looks up surfaces by id", () => {
  const spec: SurfaceSpec<string> = { id: "demo", body: () => "body" }
  const registry = createSurfaceRegistry([spec])

  assert.equal(registry.get("demo"), spec)
  assert.deepEqual(registry.all(), [spec])
  assert.equal(registry.get("missing"), undefined)
})

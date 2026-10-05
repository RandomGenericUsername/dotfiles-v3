// ---------------------------------------------------------------------------
// State OWNERSHIP tests (fix-capture-per-monitor-state).
//
// The bug these pin: `ClassicWindow` used to allocate its own
// `screenshot`/`recording` objects, and `app.tsx` builds one window per monitor.
// Every window was therefore an independent OWNER of one logical value, and
// every window persisted to the same `$XDG_STATE_HOME/capture-tool/capture-ui.json`.
// Reproduced live (two `ClassicWindow(monitor, ports)` instances, real
// `glibUiStateStore`): window A saved `target: "screen"`, window B — whose copy
// had been loaded before A's save — then saved `target: "window"` and A's
// selection was gone from disk. Last writer wins.
//
// WHAT IS AND IS NOT TESTABLE HERE. `ClassicWindow` is a `.tsx` that imports
// `ags/gtk4` and `gi://GLib`, so `node --test` cannot construct one: this suite
// has no GTK and no display. Rather than assert nothing, it pins the two halves
// of the invariant that are reachable without GTK:
//
//   1. `createUiState()`'s semantics — fresh, independent, in-place-mutable
//      objects (the real factory, executed).
//   2. the WIRING — read from the real `app.tsx` and `ClassicWindow.tsx` source:
//      the window cannot allocate a state of its own, and the composition root
//      builds exactly one and hands it to every window.
//
// A shape guard on source text is weaker than executing the window, and it is
// labelled as such. It is still the assertion that fails first if someone
// re-introduces a per-window copy, which is the whole failure mode.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

import {
  DEFAULT_RECORDING,
  DEFAULT_SCREENSHOT,
  createUiState,
  type UiState,
} from "../../domain/ui-state.ts"

const APP = fileURLToPath(new URL("../../app.tsx", import.meta.url))
const WINDOW = fileURLToPath(new URL("../../ui/classic/ClassicWindow.tsx", import.meta.url))
// The per-monitor window construction moved here when hotplug support landed
// (fix-capture-monitor-lifecycle); the shared-state invariant is asserted
// against it below.
const WINDOW_SET = fileURLToPath(
  new URL("../../adapters/monitor-window-set.ts", import.meta.url),
)

/**
 * Source with `//` comment lines removed, so a rationale that NAMES the factory
 * (or a `{ ...DEFAULT_SCREENSHOT }` in prose) cannot satisfy — or trip — a
 * structural assertion. These files are comment-heavy by house style, so this
 * is not a hypothetical.
 */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("//"))
    .join("\n")
}

/**
 * A stand-in for what `ClassicWindow` does with the state it is handed: mutate
 * the objects in place, exactly as the three pages' `onClicked` handlers do.
 * `Object.assign` mirrors `applyStateToUi()`'s reload.
 */
function mutateInPlace(state: UiState, screenshotTarget: string): void {
  state.screenshot.target = screenshotTarget as UiState["screenshot"]["target"]
}

function reload(state: UiState, loaded: UiState): void {
  Object.assign(state.screenshot, loaded.screenshot)
  Object.assign(state.recording, loaded.recording)
}

// ---------------------------------------------------------------------------
// 1. The factory
// ---------------------------------------------------------------------------

test("createUiState: seeds the first-run defaults", () => {
  const state = createUiState()
  assert.deepEqual(state.screenshot, DEFAULT_SCREENSHOT)
  assert.deepEqual(state.recording, DEFAULT_RECORDING)
})

test("createUiState: hands out objects, never the shared constants", () => {
  // If it returned `DEFAULT_SCREENSHOT` itself, the first window's mutations
  // would become the defaults every later window starts from.
  const state = createUiState()
  assert.notEqual(state.screenshot, DEFAULT_SCREENSHOT)
  assert.notEqual(state.recording, DEFAULT_RECORDING)

  state.screenshot.target = "screen"
  state.recording.fps = 24
  assert.equal(DEFAULT_SCREENSHOT.target, "region")
  assert.equal(DEFAULT_RECORDING.fps, 60)
})

test("createUiState: is a factory, not a memoised singleton", () => {
  // Sharing is the composition root's decision, made once and visibly. A
  // module-level cache would make every window share by accident — invisible at
  // the call site, and impossible to reason about when a test wants its own.
  const a = createUiState()
  const b = createUiState()
  assert.notEqual(a, b)
  assert.notEqual(a.screenshot, b.screenshot)
  assert.notEqual(a.recording, b.recording)
})

// ---------------------------------------------------------------------------
// 2. Two windows, one state: the invariant itself
// ---------------------------------------------------------------------------

test("two windows given ONE state mutate ONE object", () => {
  const state = createUiState()

  // What the pages hold: the exact objects the window was constructed with.
  const windowA = state
  const windowB = state

  mutateInPlace(windowA, "screen")
  // The single-object property, asserted on identity rather than on values.
  assert.equal(windowB.screenshot, windowA.screenshot)
  assert.equal(windowB.screenshot.target, "screen")

  // And the write that used to clobber: a second window persisting "its own"
  // copy can no longer resurrect a stale value, because it has no stale value.
  mutateInPlace(windowB, "window")
  assert.equal(windowA.screenshot.target, "window")
  assert.equal(JSON.parse(JSON.stringify(state)).screenshot.target, "window")
})

test("two windows given SEPARATE states DO diverge (the bug, modelled)", () => {
  // The negative control, and the reason the fix exists. This is what
  // `ClassicWindow` used to do: `{ ...DEFAULT_SCREENSHOT }` per window.
  const windowA = { screenshot: { ...DEFAULT_SCREENSHOT }, recording: { ...DEFAULT_RECORDING } }
  const windowB = { screenshot: { ...DEFAULT_SCREENSHOT }, recording: { ...DEFAULT_RECORDING } }

  mutateInPlace(windowA, "screen")
  assert.equal(windowA.screenshot.target, "screen")
  assert.equal(windowB.screenshot.target, "region")

  // Window B, still holding the state as it was when IT was created, persists.
  // Window A's selection does not survive — this is the exact sequence the
  // live two-window harness reproduced against the real store.
  const persisted = JSON.parse(JSON.stringify({ screenshot: windowB.screenshot }))
  assert.equal(persisted.screenshot.target, "region")
  assert.notEqual(windowA.screenshot.target, persisted.screenshot.target)
})

test("reload assigns into the shared object instead of rebinding it", () => {
  // The other half of the invariant, and the reason `applyStateToUi()` keeps
  // using `Object.assign`: the pages were handed these exact objects, so a
  // rebind would orphan every subsequent page mutation.
  const state = createUiState()
  const held = state.screenshot
  reload(state, { screenshot: { ...DEFAULT_SCREENSHOT, target: "screen" }, recording: { ...DEFAULT_RECORDING } })
  assert.equal(state.screenshot, held)
  assert.equal(held.target, "screen")
})

// ---------------------------------------------------------------------------
// 3. The wiring, read from the real sources
// ---------------------------------------------------------------------------

test("ClassicWindow allocates no state of its own", () => {
  const source = code(WINDOW)
  assert.equal(
    /\{\s*\.\.\.DEFAULT_SCREENSHOT\s*\}/.test(source),
    false,
    "ClassicWindow re-allocates the screenshot state — every window would own a private copy",
  )
  assert.equal(
    /\{\s*\.\.\.DEFAULT_RECORDING\s*\}/.test(source),
    false,
    "ClassicWindow re-allocates the recording state — every window would own a private copy",
  )
  assert.match(
    source,
    /state:\s*UiState/,
    "ClassicWindow must take the shared state as a required parameter",
  )
})

test("the composition root builds ONE state and passes it to every window", () => {
  const source = code(APP)
  const factoryCalls = source.match(/createUiState\(\)/g) ?? []
  assert.equal(
    factoryCalls.length,
    1,
    `app.tsx must create the shared state exactly once, found ${factoryCalls.length} call(s)`,
  )
  // Every window construction hands over the same identifier, and the loop
  // over monitors must not construct one per iteration.
  const constructions = source.match(/ClassicWindow\([^)]*\)/g) ?? []
  assert.equal(constructions.length, 1, "expected exactly one ClassicWindow call site")
  assert.match(
    constructions[0],
    /,\s*state\s*\)/,
    "the window must receive the shared state, not just the ports",
  )
  // Where the per-monitor construction now happens. It was the body of
  // `for (const monitor of app.get_monitors())` in app.tsx; it is now the
  // `createWindow` factory the composition root hands the window set
  // (fix-capture-monitor-lifecycle moved the loop into the set, so that hotplug
  // can add and remove windows). The invariant being protected is UNCHANGED --
  // "the state is built outside the per-monitor construction" -- and it is now
  // checked against the call that replaced the loop, which is if anything
  // stronger: this would catch a `createUiState()` smuggled into the factory,
  // which the old "is it inside the loop body" check could not see at all.
  assert.match(
    source,
    /createWindow:\s*\(monitor\)\s*=>\s*ClassicWindow\(monitor, ports, state\)/,
    "the window factory must still hand every window the SAME shared state object",
  )
  // The window set itself must never construct a state: it is a pure adapter
  // over the domain's plan, and a state factory here would be a second owner of
  // the same value.
  const windowSet = code(WINDOW_SET)
  assert.equal(
    /\bcreateUiState\b/.test(windowSet),
    false,
    "the window set must not build a UI state — the composition root owns it",
  )
})

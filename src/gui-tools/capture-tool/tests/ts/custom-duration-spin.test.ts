// ---------------------------------------------------------------------------
// Custom-duration spin feedback-loop tests.
//
// A previous agent REPORTED two defects here. Both were investigated against a
// live AGS session driving the REAL `ClassicWindow` (real `glibUiStateStore`;
// only `launcher`/`backendProbe` stubbed), and BOTH ARE PHANTOMS:
//
//   "the customBox/customSpin editor is recreated on every `map`" — FALSE.
//   `$` is a CONSTRUCTION-time setup function, not a render hook. In gnim's
//   JSX runtime (`/usr/share/ags/js/node_modules/gnim/dist/jsx/jsx.ts`) the
//   `$` prop is stripped from the props at jsx.ts:230 and invoked exactly once,
//   at jsx.ts:343, immediately after `new ctor(props)` and after the children
//   are appended. Nothing re-invokes it; there is no reconciliation pass and no
//   re-render. A GTK4 `map` signal only walks the widget up the realisaton
//   tree — it does not reconstruct the JSX that built the tree. Measured live:
//   `spinButtons` in the window stayed at 1 across a first show, three
//   hide/show cycles, and a disk change that altered `customDuration`.
//
//   "`applyState`'s set_value re-fires the handler after the flag resets" —
//   FALSE. GTK4's `GtkAdjustment::value-changed` is emitted SYNCHRONOUSLY
//   from `gtk_adjustment_set_value`, on the same stack, before
//   `set_value` returns. There is no queued/async/idle emission. Measured live
//   by instrumenting the handler: it is entered BETWEEN `applyState`'s
//   `set_value` call and its return, i.e. while `applyingState` is still true.
//   The guard is therefore not merely adequate, it is exactly sufficient.
//
// So there is no defect to fix and none to invent. But the guard is NOT
// incidental: the same live harness, with the guard deleted, DID corrupt the
// selection — see the negative control below, which reproduces it exactly.
// Deleting `applyingState` is a real regression. These tests pin that, plus
// the construction-time property of `$` that makes the whole design sound.
//
// WHAT IS AND IS NOT TESTABLE HERE. `RecordingPage.tsx` imports `ags/gtk4`, so
// `node --test` cannot construct the page: this suite has no GTK and no
// display. Same honest split `ui-state-ownership.test.ts` uses:
//
//   1. the FEEDBACK-LOOP SEMANTICS — executed, against a faithful model of
//      `GtkAdjustment`'s synchronous value-changed, using the real
//      `createUiState()`/`durationSelection`.
//   2. the WIRING — read from the real `RecordingPage.tsx`: the guard exists,
//      and `applyState` writes the spin inside it.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

import { createUiState, durationSelection, type UiState } from "../../domain/ui-state.ts"

const PAGE = fileURLToPath(new URL("../../ui/classic/RecordingPage.tsx", import.meta.url))

/**
 * Source with `//` comment lines removed, so a rationale that NAMES
 * `applyingState` (or quotes the guard) cannot satisfy — or trip — a
 * structural assertion. This file is comment-heavy by house style.
 */
function code(path: string): string {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("//"))
    .join("\n")
}

/**
 * A faithful model of the only two behaviours of `Gtk.SpinButton` that matter
 * here, taken from the GTK4 implementation rather than invented:
 *
 *   - `set_value` writes the adjustment, and `GtkAdjustment` emits
 *     `value-changed` SYNCHRONOUSLY from inside that call. This is the whole
 *     reason `applyingState` is a sufficient guard: there is no queue and no
 *     idle to come back around after the `finally` resets the flag. Verified
 *     live — the handler is entered before `set_value` returns.
 *   - `set_value` does NOT emit when the value is unchanged, so a reload that
 *     re-asserts the value already displayed is silent.
 *
 * `synchronous` is the load-bearing word and the reason this is a model of the
 * real thing rather than a convenient stub.
 */
class SpinModel {
  value: number
  private readonly listeners: Array<() => void> = []

  constructor(initial: number) {
    this.value = initial
  }

  connect(fn: () => void): void {
    this.listeners.push(fn)
  }

  getValueAsInt(): number {
    return Math.trunc(this.value)
  }

  setValue(next: number): void {
    if (next === this.value) return
    this.value = next
    // Synchronous: still on this stack when setValue returns.
    for (const fn of this.listeners) fn()
  }
}

/**
 * `RecordingPage`'s custom-duration editor, transcribed: the `$` body builds
 * ONE spin and connects ONE handler, and `applyState` writes the spin inside
 * the `applyingState` window. `guard` selects between the shipped code and the
 * "somebody deleted the guard" variant, so the negative control is the same
 * code with one line changed rather than a separate hand-written bug.
 */
function makeEditor(
  recording: UiState["recording"],
  options: { guard: boolean; initialSpinValue: number },
): { applyState: () => void; spin: SpinModel } {
  let applyingState = false
  const spin = new SpinModel(options.initialSpinValue)

  spin.connect(() => {
    if (options.guard && applyingState) return
    recording.customDuration = spin.getValueAsInt()
    recording.duration = recording.customDuration
  })

  return {
    spin,
    applyState() {
      applyingState = true
      try {
        spin.setValue(recording.customDuration)
      } finally {
        applyingState = false
      }
    },
  }
}

// ---------------------------------------------------------------------------
// 1. The shipped behaviour: applyState never writes back through the handler
// ---------------------------------------------------------------------------

test("applyState re-asserting the spin leaves a preset duration selection alone", () => {
  const state = createUiState()
  const { recording } = state
  recording.duration = 30
  recording.customDuration = 120

  // The spin is showing something else entirely — a stale editor value from
  // before the window was hidden, or one another window last wrote.
  const editor = makeEditor(recording, { guard: true, initialSpinValue: 45 })
  editor.applyState()

  assert.equal(editor.spin.getValueAsInt(), 120, "the spin must show the loaded value")
  assert.equal(recording.duration, 30, "the 30s selection must survive the reload")
  assert.equal(durationSelection(recording), 30)
})

test("applyState does not turn a preset duration into a custom one", () => {
  // The user-visible shape of the same corruption: the DURATION row highlights
  // "30s" while the state actually says "custom", because `durationSelection`
  // no longer resolves to a preset. That mismatch is what a leaked handler
  // causes, and it is what makes the defect worth a guard at all.
  const state = createUiState()
  const { recording } = state
  recording.duration = 30
  recording.customDuration = 120

  const editor = makeEditor(recording, { guard: true, initialSpinValue: 45 })
  editor.applyState()

  assert.equal(durationSelection(recording), 30)
  assert.notEqual(durationSelection(recording), -1, "the duration row fell back to Custom")
})

test("applyState does not move customDuration either", () => {
  const state = createUiState()
  const { recording } = state
  recording.duration = 30
  recording.customDuration = 120

  const editor = makeEditor(recording, { guard: true, initialSpinValue: 45 })
  editor.applyState()

  assert.equal(recording.customDuration, 120)
})

test("applyState reloading the SAME custom value is silent either way", () => {
  // Nothing to assert about corruption — this pins WHY the common case is safe:
  // an unchanged `set_value` does not emit, so there is no write to guard.
  const state = createUiState()
  const { recording } = state
  recording.duration = 30
  recording.customDuration = 120

  const unguarded = makeEditor(recording, { guard: false, initialSpinValue: 120 })
  unguarded.applyState()

  assert.equal(recording.duration, 30, "an unchanged set_value must not emit at all")
})

test("the guard is released after applyState, so a real user edit still lands", () => {
  // The guard must not become a swallow-everything. After applyState returns,
  // typing in the editor has to reach the state again — otherwise the fix for
  // the feedback loop would be the bug.
  const state = createUiState()
  const { recording } = state
  recording.duration = -1
  recording.customDuration = 120

  const editor = makeEditor(recording, { guard: true, initialSpinValue: 45 })
  editor.applyState()

  editor.spin.setValue(90) // the user typed 90

  assert.equal(recording.customDuration, 90)
  assert.equal(recording.duration, 90)
  assert.equal(durationSelection(recording), -1, "90s is a custom duration and must read as such")
})

// ---------------------------------------------------------------------------
// 2. The negative control: delete the guard and the corruption is real
// ---------------------------------------------------------------------------

test("NEGATIVE CONTROL: without applyingState the handler clobbers the selection", () => {
  // This is the defect that was REPORTED — modelled, so the suite fails if the
  // guard is deleted. Live-measured numbers from the real `ClassicWindow`:
  // with the guard, five hide/show cycles left `duration` at 30 while the spin
  // moved 120 -> 300; with the guard removed, the same cycle ended with
  // `duration` 300 and the row still highlighting "30s".
  const state = createUiState()
  const { recording } = state
  recording.duration = 30
  recording.customDuration = 300

  const editor = makeEditor(recording, { guard: false, initialSpinValue: 120 })
  editor.applyState()

  assert.equal(recording.duration, 300, "the leaked handler overwrote the 30s selection")
  assert.notEqual(durationSelection(recording), 30, "the row and the state now disagree")
})

// ---------------------------------------------------------------------------
// 3. The wiring, read from the real source
// ---------------------------------------------------------------------------

test("RecordingPage's spin handler is guarded on applyingState", () => {
  const source = code(PAGE)
  assert.match(
    source,
    /if \(\s*applyingState\s*\|\|\s*customSpin === null\s*\)\s*return/,
    "the value-changed handler no longer checks applyingState — applyState's set_value will write back through it",
  )
})

test("applyState sets applyingState around the spin write and clears it in a finally", () => {
  // `finally` specifically: if `applyGifMode()` or `refreshCustomBox()` ever
  // threw, a plain trailing assignment would leave the flag stuck true and
  // silently deafen the editor for the rest of the session.
  const source = code(PAGE)
  const applyState = /function applyState\(\) \{[\s\S]*?\n {2}\}/.exec(source)
  assert.ok(applyState, "applyState() disappeared from RecordingPage")
  const body = applyState[0]

  assert.match(body, /applyingState = true/, "applyState must raise the guard")
  assert.match(body, /try \{/, "the guard needs a try so the finally is reachable")
  assert.match(body, /customSpin\.set_value\(recording\.customDuration\)/, "the spin write moved out of applyState")
  assert.match(body, /finally \{[\s\S]*applyingState = false/, "the guard must be lowered in a finally")
})

test("the custom spin is built ONCE, inside a $ setup callback", () => {
  // Pins the property that DISPROVED the "recreated on every map" report, and
  // that the design depends on: `customSpin` is assigned in a `$` body, which
  // gnim invokes exactly once per element at construction (jsx.ts:343). A
  // construction-time assignment is what makes `applyState`'s `customSpin`
  // non-null check safe to skip — by the time the window maps, the `$` has run.
  const source = code(PAGE)
  const dollarBody = /\$\=\{\(self\) => \{([\s\S]*?)customSpin = new Gtk\.SpinButton/.exec(source)
  assert.ok(dollarBody, "the custom spin is no longer constructed inside a $ callback")
  assert.match(
    dollarBody[1] || source,
    /customBox = self/,
    "the editor box should still be captured in the same $ callback",
  )
})

test("the spin's value-changed handler is connected exactly once", () => {
  // Two connections would mean two writes per keystroke; the reported
  // "recreated on every map" bug, had it been real, would have produced one
  // per map. One connection is the invariant.
  const source = code(PAGE)
  const connections = source.match(/customSpin\.connect\(/g) ?? []
  assert.equal(connections.length, 1, `expected one spin handler connection, found ${connections.length}`)
})
import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { levelVariant, clampVolume } from "../../audio/presentation/levels.ts"

/**
 * The shared level vocabulary, pinned.
 *
 * Three surfaces render a level-aware glyph — the bar's output indicator, the
 * panel's per-app mute button, and the settings-panel Sound card — and they MUST
 * resolve the same variant for the same reading. One threshold table, tested
 * here, is what makes a bar glyph and the panel it opens agree.
 */
describe("levelVariant", () => {
  it("reads a mute flag before the level", () => {
    // Mute wins over the level: a mute at 80% must not render "medium".
    assert.equal(levelVariant(true, 0.8), "muted")
    assert.equal(levelVariant(true, 0), "muted")
  })

  it("treats a zero gain as muted", () => {
    assert.equal(levelVariant(false, 0), "muted")
    assert.equal(levelVariant(false, -1), "muted")
  })

  it("buckets the level into the manifest's four audible variants", () => {
    // Upper-inclusive bounds, in percent: <=25 lowest, <=50 low, <=75 medium,
    // else max. 0.25 is 25% and belongs to "lowest", not "low".
    assert.equal(levelVariant(false, 0.01), "lowest")
    assert.equal(levelVariant(false, 0.25), "lowest")
    assert.equal(levelVariant(false, 0.5), "low")
    assert.equal(levelVariant(false, 0.5001), "medium")
    assert.equal(levelVariant(false, 0.75), "medium")
    assert.equal(levelVariant(false, 0.7501), "max")
    assert.equal(levelVariant(false, 1), "max")
  })
})

describe("clampVolume", () => {
  it("clamps into 0..1", () => {
    assert.equal(clampVolume(0.5), 0.5)
    assert.equal(clampVolume(-0.3), 0)
    assert.equal(clampVolume(1.7), 1)
  })

  it("reads a missing reading as 0, not NaN", () => {
    assert.equal(clampVolume(null), 0)
    assert.equal(clampVolume(undefined), 0)
    // The load-bearing case: AstalWp reports NaN during swaps, and `NaN ?? 0`
    // is still NaN. Left unguarded, NaN reaches levelVariant and renders "max"
    // for a reading that is actually absent.
    assert.equal(clampVolume(NaN), 0)
    // Infinities are errors, not large readings: treated like NaN, not clamped
    // to 1, so a bad value never masquerades as "full volume".
    assert.equal(clampVolume(Infinity), 0)
    assert.equal(clampVolume(-Infinity), 0)
  })
})

import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { batteryStateKey, BATTERY_ICON_GROUP } from "../../components/battery/battery-icon.ts"

/**
 * The battery state-key table, pinned.
 *
 * This module is shared by the status-bar indicator and the panel's nav header,
 * and the two MUST resolve to the same glyph for the same reading — a bar icon
 * that disagrees with the panel it opens is a bug neither file can be blamed for
 * alone, which is why the table lives in one place and is tested here.
 */
describe("batteryStateKey", () => {
  it("groups the level into the manifest's five steps", () => {
    // Upper-exclusive bounds: 0.25 belongs to the "25" bucket, not "0". A
    // boundary written `<=` instead would shift every device a step early.
    assert.equal(batteryStateKey(0, false), "discharging-0")
    assert.equal(batteryStateKey(0.24, false), "discharging-0")
    assert.equal(batteryStateKey(0.25, false), "discharging-25")
    assert.equal(batteryStateKey(0.49, false), "discharging-25")
    assert.equal(batteryStateKey(0.5, false), "discharging-50")
    assert.equal(batteryStateKey(0.74, false), "discharging-50")
    assert.equal(batteryStateKey(0.75, false), "discharging-75")
    assert.equal(batteryStateKey(0.99, false), "discharging-75")
    assert.equal(batteryStateKey(1, false), "discharging-100")
  })

  it("prefixes charging and discharging independently of level", () => {
    // The charging namespace is a DIFFERENT set of five states, not a suffix on
    // the discharging one — so a device at the same level must produce two
    // different keys, or the charge animation never appears.
    assert.equal(batteryStateKey(0.42, true), "charging-25")
    assert.equal(batteryStateKey(0.42, false), "discharging-25")
    for (const pct of [0, 0.3, 0.6, 0.8, 1]) {
      assert.ok(batteryStateKey(pct, true).startsWith("charging-"))
      assert.ok(batteryStateKey(pct, false).startsWith("discharging-"))
    }
  })

  it("reads percentage as a 0..1 FRACTION, not a percent", () => {
    // The load-bearing assertion of this file. AstalBattery reports 0..1, so
    // 83 means "83x full" — which every upper-exclusive bound puts in the "100"
    // bucket. Catching that here is the difference between a panel and a flat
    // battery glyph.
    assert.equal(batteryStateKey(83, false), "discharging-100")
    assert.notEqual(batteryStateKey(83, false), "discharging-75")
    assert.equal(batteryStateKey(0.83, false), "discharging-75")
  })

  it("produces every key the battery bar_mappings declares", () => {
    // Ten keys, and they must all exist in the manifest or `registry.resolve`
    // returns null and the widget silently renders no icon at all.
    const keys = new Set<string>()
    for (const pct of [0, 0.3, 0.6, 0.8, 1]) {
      for (const chg of [true, false]) keys.add(batteryStateKey(pct, chg))
    }
    assert.equal(keys.size, 10)
    for (const key of keys) {
      assert.match(key, /^(charging|discharging)-(0|25|50|75|100)$/)
    }
  })
})

describe("BATTERY_ICON_GROUP", () => {
  it("is the group both callers resolve against", () => {
    assert.equal(BATTERY_ICON_GROUP, "battery")
  })
})

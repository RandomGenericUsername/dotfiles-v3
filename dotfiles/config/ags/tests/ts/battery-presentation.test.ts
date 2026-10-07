// ---------------------------------------------------------------------------
// Battery panel -- PURE presentation logic.
//
// `components/battery/presentation.ts` holds every battery-panel decision that
// does not need a live widget: how a duration reads, which word tells the user
// whether that duration is a countdown or a charge target, which glyph a
// profile row shows, and which row carries the `.sel` class. Each of those has
// an edge case that reads fine in the source and is wrong in the panel:
//
//   * a daemon with no time estimate must not render "0m remaining" -- that
//     claims "no time left", not "no estimate";
//   * a daemon claiming 27h must not render "27h 3m" as if it were ordinary;
//   * `Powersave++` must reuse the base glyph, because the daemon's `++` tiers
//     are the same mode pushed further, not different modes;
//   * an unrecognised active profile must highlight NO row, not the first one.
//
// None of that needs GTK, so none of it lives in the widget. The panel widget
// keeps only what needs a live widget (the D-Bus subscription, the window,
// the CSS classes); it calls in here for every decision.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"

import {
  POWER_PROFILE_ORDER,
  MAX_RENDERED_SECONDS,
  formatBatteryTime,
  formatBatteryStatusLine,
  formatDuration,
  profileIconVariant,
  isActiveProfile,
  clampPercentage,
  formatPercentage,
} from "../../components/battery/presentation.ts"

// ---------------------------------------------------------------------------
// formatDuration -- the bare "2h 14m" line.
// ---------------------------------------------------------------------------

test("formatDuration: hours and minutes", () => {
  assert.equal(formatDuration(2 * 3600 + 14 * 60), "2h 14m")
  assert.equal(formatDuration(3600), "1h")
  assert.equal(formatDuration(276), "4m") // 4m36s truncates: we never round UP
  assert.equal(formatDuration(59), "0m") // sub-minute is still a real duration
})

test("formatDuration: zero minutes drops the minute part", () => {
  // "1h 0m" implies a precision the value does not have and reads as noise.
  assert.equal(formatDuration(3600), "1h")
  assert.equal(formatDuration(7200), "2h")
  assert.equal(formatDuration(24 * 3600), "24h")
})

test("formatDuration: zero and negative return null, not \"0m\"", () => {
  // The whole reason this returns string | null. "0m" says "no time left",
  // which is a different and much more alarming claim than "no estimate".
  assert.equal(formatDuration(0), null)
  assert.equal(formatDuration(-1), null)
  assert.equal(formatDuration(-3600), null)
})

test("formatDuration: NaN and Infinity return null", () => {
  // `NaN <= 0` is false, so without the finiteness guard NaN would flow into
  // Math.floor and render "NaNh NaNm".
  assert.equal(formatDuration(NaN), null)
  assert.equal(formatDuration(Infinity), null)
  assert.equal(formatDuration(-Infinity), null)
})

// ---------------------------------------------------------------------------
// formatBatteryTime -- the two-line block, and every branch of it.
// ---------------------------------------------------------------------------

test("formatBatteryTime: discharging reads \"remaining\"", () => {
  assert.deepEqual(formatBatteryTime(2 * 3600 + 14 * 60, false), {
    primary: "2h 14m",
    sub: "remaining",
  })
})

test("formatBatteryTime: charging reads \"full in\"", () => {
  // The number is the same; only the word changes. "2h 14m remaining" while
  // plugged in would be actively misleading -- it is a charge TARGET, not a
  // countdown, so the word has to differ or the panel lies.
  assert.deepEqual(formatBatteryTime(2 * 3600 + 14 * 60, true), {
    primary: "2h 14m",
    sub: "full in",
  })
})

test("formatBatteryTime: zero seconds falls back to the state word", () => {
  assert.deepEqual(formatBatteryTime(0, true), { primary: "", sub: "Charging" })
  assert.deepEqual(formatBatteryTime(0, false), { primary: "", sub: "Discharging" })
})

test("formatBatteryTime: negative seconds fall back too", () => {
  // A daemon that reports a negative estimate is reporting "unknown", and the
  // fallback is the honest rendering of that.
  assert.deepEqual(formatBatteryTime(-1, true), { primary: "", sub: "Charging" })
  assert.deepEqual(formatBatteryTime(-3600, false), { primary: "", sub: "Discharging" })
})

test("formatBatteryTime: non-finite seconds fall back", () => {
  assert.deepEqual(formatBatteryTime(NaN, false), { primary: "", sub: "Discharging" })
  assert.deepEqual(formatBatteryTime(Infinity, true), { primary: "", sub: "Charging" })
})

test("formatBatteryTime: 24h exactly is still rendered", () => {
  // The bound is INCLUSIVE: 24h is the largest value a reader can interpret
  // at a glance, so it is shown.
  assert.equal(MAX_RENDERED_SECONDS, 86400)
  assert.deepEqual(formatBatteryTime(MAX_RENDERED_SECONDS, false), {
    primary: "24h",
    sub: "remaining",
  })
})

test("formatBatteryTime: >24h is NOT rendered as an ordinary number", () => {
  // The bug this branch exists to prevent: "27h 3m" displayed as if it were a
  // real estimate. Clamping to 24h would DISPLAY a fabricated precise value,
  // so the number is dropped entirely and the state word carries it alone.
  for (const seconds of [MAX_RENDERED_SECONDS + 1, 27 * 3600 + 180, 400 * 3600]) {
    assert.deepEqual(formatBatteryTime(seconds, false), { primary: "", sub: "Discharging" })
    assert.deepEqual(formatBatteryTime(seconds, true), { primary: "", sub: "Charging" })
  }
})

test("formatBatteryTime: the fallback is capitalised, the tag is not", () => {
  // The casing difference is the panel's only cue that the number is MISSING.
  // If these ever converge, the panel has silently lost that cue.
  const withNumber = formatBatteryTime(3600, false)
  const withoutNumber = formatBatteryTime(0, false)
  assert.equal(withNumber.sub[0], withNumber.sub[0].toLowerCase())
  assert.equal(withoutNumber.sub[0], withoutNumber.sub[0].toUpperCase())
})

// ---------------------------------------------------------------------------
// POWER_PROFILE_ORDER -- an explicit, ordered list.
// ---------------------------------------------------------------------------

test("POWER_PROFILE_ORDER: exactly the five daemon profiles, cheapest first", () => {
  assert.deepEqual(POWER_PROFILE_ORDER, [
    "Powersave++",
    "Powersave",
    "Balanced",
    "Performance",
    "Performance++",
  ])
})

test("POWER_PROFILE_ORDER: the list is frozen and ordered lowest-power first", () => {
  // Frozen: the panel reads it at module scope. Ordered: the row order is a
  // product decision (cheapest -> hottest), NOT something derived from
  // `Object.keys` of whatever the daemon happened to serialise. If this ever
  // becomes a plain `string[]`, the ordering stops being a guarantee and the
  // menu reshuffles whenever the daemon's payload order changes.
  assert.ok(Object.isFrozen(POWER_PROFILE_ORDER), "POWER_PROFILE_ORDER must be frozen")
  const rank = new Map(POWER_PROFILE_ORDER.map((id, i) => [id.toLowerCase(), i]))
  assert.ok(rank.get("powersave++")! < rank.get("performance++")!)
})

// ---------------------------------------------------------------------------
// formatBatteryStatusLine -- the ONE-line form the bar tooltip prints.
//
// This exists so the tooltip cannot drift from the panel: before it, the widget
// chose the state word and the word order itself, so "Charging" in the panel and
// "charging" in the tooltip (or "0m remaining" for a missing estimate) were two
// independent renderings of one fact.
// ---------------------------------------------------------------------------

test("formatBatteryStatusLine: the same words formatBatteryTime decides", () => {
  assert.equal(formatBatteryStatusLine(2 * 3600 + 14 * 60, false), "2h 14m remaining")
  assert.equal(formatBatteryStatusLine(2 * 3600 + 14 * 60, true), "full in 2h 14m")
})

test("formatBatteryStatusLine: no estimate is the capitalised state word ALONE", () => {
  // Never "0m remaining" -- that claims no time is left, not that there is no
  // estimate. And the casing stays the panel's cue that the number is missing.
  assert.equal(formatBatteryStatusLine(0, false), "Discharging")
  assert.equal(formatBatteryStatusLine(-1, true), "Charging")
  assert.equal(formatBatteryStatusLine(NaN, false), "Discharging")
  assert.equal(formatBatteryStatusLine(MAX_RENDERED_SECONDS + 1, false), "Discharging")
  // Explicitly NOT the numeric fallback: if this ever becomes "0m remaining"
  // the line is a lie.
  assert.ok(!formatBatteryStatusLine(0, false).includes("0m"))
})

test("formatBatteryStatusLine: never leaves a leading/trailing space on the fallback", () => {
  assert.equal(formatBatteryStatusLine(0, false).trim(), formatBatteryStatusLine(0, false))
  assert.equal(formatBatteryStatusLine(0, true).trim(), formatBatteryStatusLine(0, true))
})

test("formatBatteryStatusLine: agrees with formatBatteryTime on EVERY case it is derived from", () => {
  // The whole point of deriving it: for any input, the words come from
  // formatBatteryTime. This walks the edge cases rather than a happy path.
  const SECONDS = [
    -3600, -1, 0, 1, 59, 60, 276, 3600, 7260, 24 * 3600,
    24 * 3600 + 1, 27 * 3600, NaN,
  ]
  for (const charging of [false, true]) {
    for (const seconds of SECONDS) {
      const { primary, sub } = formatBatteryTime(seconds, charging)
      const line = formatBatteryStatusLine(seconds, charging)
      const expected = primary === "" ? sub : charging ? `${sub} ${primary}` : `${primary} ${sub}`
      assert.equal(line, expected, `seconds=${seconds} charging=${charging}`)
      // And the degradation property survives derivation: no number, no digits.
      if (primary === "") assert.ok(!/[0-9]/.test(line), `seconds=${seconds} charging=${charging}`)
    }
  }
})

// ---------------------------------------------------------------------------
// profileIconVariant -- three glyphs for five profiles.
// ---------------------------------------------------------------------------

test("profileIconVariant: base profiles map to their own glyph", () => {
  assert.equal(profileIconVariant("Powersave"), "powersave")
  assert.equal(profileIconVariant("Balanced"), "balanced")
  assert.equal(profileIconVariant("Performance"), "performance")
})

test("profileIconVariant: BOTH ++ tiers reuse the BASE profile's glyph", () => {
  // The daemon's `++` tiers are the SAME mode pushed further -- a lower /
  // higher ceiling on the same governor -- not different modes. A distinct
  // glyph would claim a distinction the system does not make, so the `++` row
  // shows the base glyph and the row's TEXT carries the `++`.
  assert.equal(profileIconVariant("Powersave++"), profileIconVariant("Powersave"))
  assert.equal(profileIconVariant("Performance++"), profileIconVariant("Performance"))
  assert.equal(profileIconVariant("Powersave++"), "powersave")
  assert.equal(profileIconVariant("Performance++"), "performance")
})

test("profileIconVariant: every ordered profile resolves to one of the three declared variants", () => {
  // Ties the function to the ITR manifest: only `powersave`, `balanced` and
  // `performance` exist in the `power-mode` group, so a fourth return value
  // would be an unresolvable icon path at runtime.
  const DECLARED_VARIANTS = new Set(["powersave", "balanced", "performance"])
  for (const id of POWER_PROFILE_ORDER) {
    assert.ok(
      DECLARED_VARIANTS.has(profileIconVariant(id)),
      `${id} resolved to an icon variant that icons.yaml does not declare`,
    )
  }
})

// ---------------------------------------------------------------------------
// isActiveProfile -- the `.sel` class.
// ---------------------------------------------------------------------------

test("isActiveProfile: exact match", () => {
  for (const id of POWER_PROFILE_ORDER) {
    assert.equal(isActiveProfile(id, id), true, `${id} should match itself`)
  }
})

test("isActiveProfile: case difference still matches", () => {
  // The daemon's identifier and the label shown to the user differ in case in
  // practice. A mismatch here is invisible-but-wrong: the row simply never
  // lights up, which reads as "the panel does not know my mode", not as a bug.
  assert.equal(isActiveProfile("performance", "Performance"), true)
  assert.equal(isActiveProfile("PERFORMANCE", "Performance"), true)
  assert.equal(isActiveProfile("balanced", "Balanced"), true)
})

test("isActiveProfile: surrounding whitespace is tolerated", () => {
  assert.equal(isActiveProfile("  Balanced  ", "Balanced"), true)
})

test("isActiveProfile: a DIFFERENT profile does not match", () => {
  assert.equal(isActiveProfile("Balanced", "Performance"), false)
  // Prefix is not a match: "Performance" must not light up the
  // "Performance++" row.
  assert.equal(isActiveProfile("Performance", "Performance++"), false)
  assert.equal(isActiveProfile("Powersave", "Powersave++"), false)
})

test("isActiveProfile: an unknown or blank current highlights NOTHING", () => {
  // The failure this guards: highlighting the FIRST row as a fallback would
  // tell the user they are in Powersave++ when the daemon said something the
  // panel did not recognise. No highlight is the honest rendering.
  for (const current of ["", "   ", "Turbo", "performance-max", "unknown"]) {
    for (const id of POWER_PROFILE_ORDER) {
      assert.equal(isActiveProfile(current, id), false, `${JSON.stringify(current)} must match nothing`)
    }
  }
})

test("isActiveProfile: at most one row is ever highlighted", () => {
  // The panel loops the ordered list and applies `.sel` where this is true.
  // For any recognised current value that must yield exactly one row -- zero
  // is the "unknown" case above, more than one would be a bug.
  const current = "Balanced"
  const hits = POWER_PROFILE_ORDER.filter((id) => isActiveProfile(current, id))
  assert.deepEqual(hits, ["Balanced"])
})

// ---------------------------------------------------------------------------
// The nav header's percentage.
//
// Exported alongside the rest because the panel prints a percentage in TWO
// places (nav header and profile rows). A percentage rendered two ways is a
// rounding drift waiting to happen: clampPercentage/formatPercentage round and
// clamp once, for both callers.
// ---------------------------------------------------------------------------

test("clampPercentage: rounds and clamps into 0..100", () => {
  assert.equal(clampPercentage(83), 83)
  assert.equal(clampPercentage(83.4), 83)
  assert.equal(clampPercentage(83.5), 84)
  assert.equal(clampPercentage(-1), 0)
  assert.equal(clampPercentage(140), 100)
  assert.equal(clampPercentage(0), 0)
  assert.equal(clampPercentage(100), 100)
})

test("clampPercentage: no reading is null, never NaN or -1", () => {
  for (const input of [null, undefined, NaN, Infinity, -Infinity]) {
    assert.equal(clampPercentage(input), null, `${String(input)} must be a missing reading`)
  }
})

test("formatPercentage: renders \"83%\" or null", () => {
  assert.equal(formatPercentage(83), "83%")
  assert.equal(formatPercentage(100), "100%")
  assert.equal(formatPercentage(0), "0%")
  assert.equal(formatPercentage(NaN), null)
  assert.equal(formatPercentage(null), null)
  assert.equal(formatPercentage(undefined), null)
})
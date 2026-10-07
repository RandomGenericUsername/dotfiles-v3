// ---------------------------------------------------------------------------
// Battery panel -- PURE presentation logic.
//
// `components/battery/presentation.ts` holds every battery-panel decision that
// does not need a live widget: how a duration reads, which word tells the user
// whether that duration is a countdown or a charge target, and -- the
// load-bearing part of this file -- how a daemon profile resolves to a MODE
// through the declared tier grouping.
//
// The two-level model is the thing under test:
//
//   * a MODE owns a glyph; a VARIANT is a profile on a tier the mode declares;
//   * the stable key is the TIER (`base_profile`), never the editable name;
//   * a tier no mode declares falls back to the neutral glyph under an
//     `Unlisted` pseudo-mode, visibly, rather than disappearing;
//   * a mono-variant mode offers no choice, so no control renders.
//
// None of that needs GTK, so none of it lives in the widget. The panel widget
// keeps only what needs a live widget (the D-Bus subscription, the window,
// the CSS classes); it calls in here for every decision.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"

import {
  FALLBACK_GLYPH,
  MAX_RENDERED_SECONDS,
  POWER_MODES,
  UNLISTED_MODE,
  UNLISTED_MODE_NAME,
  UNMAPPED_TIER_LABEL,
  activeProfileOf,
  clampPercentage,
  formatBatteryStatusLine,
  formatBatteryTime,
  formatDuration,
  formatPercentage,
  glyphForTier,
  hasVariantChoice,
  isDeclaredTier,
  modeForTier,
  modeTooltip,
  profilesForMode,
  railMeta,
  railModes,
  resolveMode,
  variantToSelect,
  variantTooltip,
  type PowerProfile,
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
// formatBatteryStatusLine -- the ONE-line form the bar tooltip prints.
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
  assert.ok(!formatBatteryStatusLine(0, false).includes("0m"))
})

test("formatBatteryStatusLine: never leaves a leading/trailing space on the fallback", () => {
  assert.equal(formatBatteryStatusLine(0, false).trim(), formatBatteryStatusLine(0, false))
  assert.equal(formatBatteryStatusLine(0, true).trim(), formatBatteryStatusLine(0, true))
})

test("formatBatteryStatusLine: agrees with formatBatteryTime on EVERY case it is derived from", () => {
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
      if (primary === "") assert.ok(!/[0-9]/.test(line), `seconds=${seconds} charging=${charging}`)
    }
  }
})

// ---------------------------------------------------------------------------
// The declaration -- the tier -> mode grouping.
//
// Three glyphs, five selectable things. The grouping CANNOT be inferred: the
// name is editable, and the tier alone yields five tiers. So it is declared,
// and this block pins the declaration literally.
// ---------------------------------------------------------------------------

test("POWER_MODES: exactly the three declared modes, cheapest first", () => {
  assert.deepEqual(
    POWER_MODES.map((m) => m.mode),
    ["Powersave", "Balanced", "Performance"],
  )
})

test("POWER_MODES: each mode owns one glyph and the exact tiers it declares", () => {
  assert.deepEqual(
    POWER_MODES.map((m) => ({ mode: m.mode, glyph: m.glyph, tiers: [...m.tiers] })),
    [
      { mode: "Powersave", glyph: "powersave", tiers: ["Powersave", "Superpowersave"] },
      { mode: "Balanced", glyph: "balanced", tiers: ["Balanced"] },
      { mode: "Performance", glyph: "performance", tiers: ["Performance", "Ultraperformance"] },
    ],
  )
})

test("POWER_MODES: two tiers share the leaf, two share the engine", () => {
  // The whole reason there are three glyphs and not five: the artwork hangs on
  // the MODE, so any tier the mode declares inherits it with no extra art.
  const tiers = POWER_MODES.flatMap((m) => [...m.tiers])
  assert.equal(new Set(tiers).size, 5, "five distinct tiers")
  assert.equal(new Set(POWER_MODES.map((m) => m.glyph)).size, 3, "three distinct glyphs")
  assert.ok(Object.isFrozen(POWER_MODES))
})

// ---------------------------------------------------------------------------
// Tier -> mode resolution.
// ---------------------------------------------------------------------------

test("modeForTier: every live tier resolves to its declared mode", () => {
  // The live values on this machine (2026-10-07), quoted as the source of
  // truth. `Superpowersave` is a Powersave variant; `Ultraperformance` is a
  // Performance variant; neither shares a name with its mode.
  assert.equal(modeForTier("Powersave")?.mode, "Powersave")
  assert.equal(modeForTier("Superpowersave")?.mode, "Powersave")
  assert.equal(modeForTier("Balanced")?.mode, "Balanced")
  assert.equal(modeForTier("Performance")?.mode, "Performance")
  assert.equal(modeForTier("Ultraperformance")?.mode, "Performance")
})

test("modeForTier: case and surrounding whitespace are tolerated", () => {
  assert.equal(modeForTier("  ultraperformance  ")?.mode, "Performance")
  assert.equal(modeForTier("SUPERPOWERSAVE")?.mode, "Powersave")
})

test("modeForTier: an undeclared tier resolves to null, never to a nearest match", () => {
  // A Tier that merely LOOKS like a declared one must not resolve; the
  // fallback is the honest answer.
  for (const tier of ["Warp", "performance-max", "Power", ""]) {
    assert.equal(modeForTier(tier), null, JSON.stringify(tier))
  }
})

test("isDeclaredTier: true only for the five tiers the declaration names", () => {
  for (const tier of ["Powersave", "Superpowersave", "Balanced", "Performance", "Ultraperformance"]) {
    assert.equal(isDeclaredTier(tier), true, tier)
  }
  assert.equal(isDeclaredTier("Warp"), false)
  assert.equal(isDeclaredTier(""), false)
})

test("glyphForTier: the glyph hangs on the mode, so the ++ tiers share it", () => {
  assert.equal(glyphForTier("Powersave"), "powersave")
  assert.equal(glyphForTier("Superpowersave"), "powersave")
  assert.equal(glyphForTier("Balanced"), "balanced")
  assert.equal(glyphForTier("Performance"), "performance")
  assert.equal(glyphForTier("Ultraperformance"), "performance")
})

test("glyphForTier: an undeclared tier resolves to the neutral fallback", () => {
  assert.equal(glyphForTier("Warp"), FALLBACK_GLYPH)
  assert.equal(FALLBACK_GLYPH, "unknown")
})

// ---------------------------------------------------------------------------
// The fallback pseudo-mode -- an undeclared tier is never dropped or blanked.
// ---------------------------------------------------------------------------

test("resolveMode: an undeclared tier folds into the labelled Unlisted pseudo-mode", () => {
  const mode = resolveMode("Warp")
  assert.equal(mode.mode, UNLISTED_MODE_NAME)
  assert.equal(mode.mode, "Unlisted")
  assert.equal(mode.glyph, FALLBACK_GLYPH)
  assert.deepEqual(mode.tiers, [])
  assert.equal(mode, UNLISTED_MODE)
})

test("railModes: the three declared modes always render, in declaration order", () => {
  assert.deepEqual(railModes([]).map((m) => m.mode), ["Powersave", "Balanced", "Performance"])
})

test("railModes: the Unlisted cell appears ONLY when an undeclared tier exists", () => {
  const declared: PowerProfile[] = [
    { name: "Powersave", tier: "Powersave" },
    { name: "Balanced", tier: "Balanced" },
  ]
  assert.deepEqual(railModes(declared).map((m) => m.mode), ["Powersave", "Balanced", "Performance"])

  const unlisted: PowerProfile[] = [...declared, { name: "Hyperdrive", tier: "Warp" }]
  assert.deepEqual(railModes(unlisted).map((m) => m.mode), [
    "Powersave",
    "Balanced",
    "Performance",
    "Unlisted",
  ])
})

// ---------------------------------------------------------------------------
// Variants -- profiles that resolve into a mode.
// ---------------------------------------------------------------------------

const LIVE: PowerProfile[] = [
  { name: "Powersave++", tier: "Superpowersave" },
  { name: "Powersave", tier: "Powersave" },
  { name: "Balanced", tier: "Balanced" },
  { name: "Performance", tier: "Performance" },
  { name: "Performance++", tier: "Ultraperformance" },
]

test("profilesForMode: groups profiles by the mode their TIER resolves to", () => {
  const powersave = resolveMode("Powersave")
  assert.deepEqual(
    profilesForMode(powersave, LIVE).map((e) => e.profile.name),
    ["Powersave++", "Powersave"],
  )
  const performance = resolveMode("Performance")
  assert.deepEqual(
    profilesForMode(performance, LIVE).map((e) => e.profile.name),
    ["Performance", "Performance++"],
  )
  const balanced = resolveMode("Balanced")
  assert.deepEqual(
    profilesForMode(balanced, LIVE).map((e) => e.profile.name),
    ["Balanced"],
  )
})

test("profilesForMode: carries the daemon index so selection can use it", () => {
  const performance = profilesForMode(resolveMode("Performance"), LIVE)
  assert.deepEqual(performance.map((e) => e.index), [3, 4])
})

test("profilesForMode: an undeclared tier gathers under Unlisted", () => {
  const withUnknown: PowerProfile[] = [...LIVE, { name: "Hyperdrive", tier: "Warp" }]
  assert.deepEqual(
    profilesForMode(UNLISTED_MODE, withUnknown).map((e) => e.profile.name),
    ["Hyperdrive"],
  )
})

test("hasVariantChoice: true for 2+ variants, false for a mono-variant mode", () => {
  assert.equal(hasVariantChoice(resolveMode("Powersave"), LIVE), true)
  assert.equal(hasVariantChoice(resolveMode("Performance"), LIVE), true)
  // Balanced declares exactly one tier: a one-option picker is decoration, so
  // the panel renders no control at all.
  assert.equal(hasVariantChoice(resolveMode("Balanced"), LIVE), false)
  // Fewer than two profiles on a multi-tier mode is still not a choice.
  assert.equal(hasVariantChoice(resolveMode("Powersave"), [{ name: "Powersave", tier: "Powersave" }]), false)
  // Two profiles on the SAME tier are two sibling variants -- a real choice.
  assert.equal(
    hasVariantChoice(resolveMode("Powersave"), [
      { name: "Powersave", tier: "Powersave" },
      { name: "Meetings", tier: "Powersave" },
    ]),
    true,
  )
})

test("activeProfileOf: resolves the daemon's index to a profile", () => {
  assert.deepEqual(activeProfileOf(LIVE, 4), { profile: LIVE[4], index: 4 })
  assert.equal(activeProfileOf(LIVE, -1), null)
  assert.equal(activeProfileOf(LIVE, 5), null)
  assert.equal(activeProfileOf(LIVE, 1.5), null)
  assert.equal(activeProfileOf([], 0), null)
})

test("variantToSelect: clicking a mode selects its offered variant", () => {
  // Not active -> the first variant in daemon order.
  assert.equal(variantToSelect(resolveMode("Performance"), LIVE, -1), "Performance")
  assert.equal(variantToSelect(resolveMode("PowerSave"), LIVE, -1), "Powersave++")
  // Already active -> keeps the CURRENT variant rather than resetting it.
  assert.equal(variantToSelect(resolveMode("Performance"), LIVE, 4), "Performance++")
  // A mode with no variant has nothing to select.
  assert.equal(variantToSelect(resolveMode("Performance"), [], 0), null)
})

test("variantToSelect: a mode not offered by the daemon is a no-op", () => {
  const onlyBalanced: PowerProfile[] = [{ name: "Balanced", tier: "Balanced" }]
  assert.equal(variantToSelect(resolveMode("Powersave"), onlyBalanced, 0), null)
})

// ---------------------------------------------------------------------------
// A rename must not move the art: the TIER is the key.
// ---------------------------------------------------------------------------

test("a renamed profile still resolves through its tier, not its name", () => {
  // `Performance++` renamed to `Showtime`, tier unchanged (Ultraperformance).
  // The name is the user's; the tier is the daemon's; the art belongs to the
  // mode the tier declares.
  const renamed: PowerProfile[] = [
    { name: "Powersave++", tier: "Superpowersave" },
    { name: "Powersave", tier: "Powersave" },
    { name: "Balanced", tier: "Balanced" },
    { name: "Performance", tier: "Performance" },
    { name: "Showtime", tier: "Ultraperformance" },
  ]
  assert.equal(glyphForTier(renamed[4].tier), "performance")
  assert.deepEqual(
    profilesForMode(resolveMode("Performance"), renamed).map((e) => e.profile.name),
    ["Performance", "Showtime"],
  )
  // The mode cell that lights up is Performance, unchanged by the rename.
  assert.equal(resolveMode(renamed[4].tier).mode, "Performance")
})

// ---------------------------------------------------------------------------
// Tooltips and the selected-name-once meta line.
// ---------------------------------------------------------------------------

test("railMeta: the selected profile is named once, with its mode and tier", () => {
  assert.deepEqual(railMeta(LIVE[4]), {
    name: "Performance++",
    line: "Performance mode · Ultraperformance tier",
  })
  assert.deepEqual(railMeta(LIVE[1]), {
    name: "Powersave",
    line: "Powersave mode · Powersave tier",
  })
})

test("railMeta: an undeclared tier is labelled unmapped, never silently mapped", () => {
  assert.deepEqual(railMeta({ name: "Hyperdrive", tier: "Warp" }), {
    name: "Hyperdrive",
    line: `unlisted mode · ${UNMAPPED_TIER_LABEL}`,
  })
  assert.equal(UNMAPPED_TIER_LABEL, "unmapped tier")
})

test("railMeta: no active profile reads the fallback, never a made-up one", () => {
  assert.deepEqual(railMeta(null), { name: "—", line: "" })
})

test("modeTooltip: names the mode, its glyph and its variants", () => {
  assert.equal(
    modeTooltip(resolveMode("Performance"), LIVE),
    "Performance mode — performance glyph · variants: Performance, Performance++",
  )
  assert.equal(
    modeTooltip(resolveMode("Balanced"), LIVE),
    "Balanced mode — balanced glyph · variant: Balanced",
  )
  assert.equal(modeTooltip(UNLISTED_MODE, LIVE), "Unlisted tiers — the fallback glyph")
})

test("variantTooltip: the tier is stated; an undeclared tier says unmapped", () => {
  assert.equal(variantTooltip(LIVE[4]), "Performance++ · Ultraperformance tier")
  assert.equal(variantTooltip({ name: "Hyperdrive", tier: "Warp" }), "Hyperdrive · tier Warp · unmapped tier")
  assert.equal(variantTooltip({ name: "Mystery", tier: "" }), "Mystery · tier ? · unmapped tier")
})

// ---------------------------------------------------------------------------
// The nav header's percentage.
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

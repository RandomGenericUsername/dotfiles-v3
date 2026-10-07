/**
 * Battery status panel -- PURE presentation logic.
 *
 * Everything in this file is a total function of its arguments. There is no
 * GTK, no Gio, no Gdk, no `ags` import, no module-level mutable state and no
 * I/O, so the whole file is exercised by `make ags-test` through Node's
 * built-in `.ts` type-stripping. The panel widget owns every effect that
 * needs a live widget; this file owns every DECISION.
 *
 * The split is the point. If "what does 2h14m of discharge read as?" lives
 * inside the widget, it can only be checked by rendering the widget; if it
 * lives here, it is checked by a table of cases. See
 * openspec/changes/add-battery-status-panel/design.md.
 */

/**
 * The power-profiles the TLP daemon reports, in the order the panel lists
 * them. This is an EXPLICIT ordered array, deliberately NOT derived from
 * `Object.keys` or from whatever the daemon happens to return:
 *
 *  - the ROW ORDER is a product decision (cheapest first, hottest last), not a
 *    property of the profile names. `Object.keys` would put the list in
 *    whatever order the daemon's D-Bus/NMI payload happened to serialise, and
 *    that order is not a contract -- it can change between daemon versions and
 *    silently reshuffle the menu.
 *  - the list must be STABLE even when a profile is unavailable on the running
 *    machine, so the rows do not jump around. An explicit list is also the
 *    only place that says "these five, in this order" out loud.
 *
 * The `++` tiers are included because the daemon does report them as distinct
 * profiles -- they just are not distinct MODES (see `profileIconVariant`).
 */
export const POWER_PROFILE_ORDER = Object.freeze([
  "Powersave++",
  "Powersave",
  "Balanced",
  "Performance",
  "Performance++",
] as const)

/**
 * Resolves to exactly the union the panel is coded against:
 * `"Powersave++" | "Powersave" | "Balanced" | "Performance" | "Performance++"`.
 *
 * It is derived from `POWER_PROFILE_ORDER` rather than restated, because a
 * hand-written union beside a hand-written list is two declarations that drift:
 * adding a profile to the list and forgetting the union compiles fine under
 * `as` and then breaks the second agent's `switch`. Deriving it makes the
 * list the single source and makes the omission a compile error instead.
 */
export type PowerProfileId = (typeof POWER_PROFILE_ORDER)[number]

export interface BatteryTimePresentation {
  /** The large line, e.g. "2h 14m" */
  primary: string
  /** The line under it, e.g. "remaining" or "Charging" */
  sub: string
}

/**
 * Upper bound on a rendered duration.
 *
 * A machine that has been plugged in for a long time, or a battery chemistry
 * that reports a nonsense estimate, can produce values like 27h. Rendering
 * "27h 3m" as if it were an ordinary number reads as a bug and quietly
 * destroys trust in the other numbers the panel shows.
 *
 * The bound chosen is 24h -- one day. Rationale:
 *
 *  - it is the largest value a reader can still interpret at a glance;
 *  - it is the largest plausible REAL remaining/charging time for a laptop
 *    battery, so it does not clamp anything a user would believe;
 *  - it is a round number, so "24h" is not mistaken for a precise measurement.
 *
 * Anything strictly above 24h is treated as "the daemon is estimating badly"
 * and degrades to the same no-time fallback as `seconds <= 0`: the state word
 * ("Charging" / "Discharging") plus the percentage carries the information,
 * and a wrong-looking number does not. Clamping to exactly 24h would have been
 * the alternative, but it would DISPLAY a fabricated precise value, which is
 * the thing this branch exists to avoid.
 */
export const MAX_RENDERED_SECONDS = 24 * 60 * 60

/** Seconds in a minute. Named so the arithmetic below reads out loud. */
const SECONDS_PER_MINUTE = 60

/**
 * Render a duration the way the panel shows it: "2h 14m" when both parts are
 * worth showing, "1h" when the minutes are zero.
 *
 * WHY A `null` RETURN rather than "0m". The daemon reports no time at all
 * (capacity unknown, estimation not supported, or the value is out of range).
 * "0m remaining" is a LIE -- it says "no time left", which is a different and
 * much more alarming claim than "no estimate". Returning `null` hands the
 * decision back to the caller, which shows the state word instead.
 *
 * Used by `formatBatteryTime` and exported because a caller may want the
 * bare duration for a tooltip or a header where no state word exists.
 */
export function formatDuration(seconds: number): string | null {
  // Guard the whole range, not just zero: `NaN` fails every comparison, so it
  // would otherwise flow through to `Math.floor` and render "NaNh NaNm".
  if (!Number.isFinite(seconds) || seconds <= 0) return null

  const totalMinutes = Math.floor(seconds / SECONDS_PER_MINUTE)
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60

  // Sub-hour durations read as minutes, not "0h": a 59-second estimate is a
  // degenerate reading, but "0h" is not a duration in any language.
  if (hours === 0) return `${minutes}m`
  // Hours-only when the minutes are zero: "1h" reads better than "1h 0m", and a
  // trailing "0m" is visually noise that implies a precision the value does
  // not have.
  if (minutes === 0) return `${hours}h`
  return `${hours}h ${minutes}m`
}

/**
 * The two lines the panel draws for the battery: how long, and in which
 * direction the clock is running.
 *
 * The `sub` word is what makes the number mean something, so the two states
 * need different wording rather than a shared "time":
 *
 *  - discharging -> "remaining"  ("2h 14m remaining")
 *  - charging    -> "full in"    ("2h 14m full in")
 *
 * and when there is no usable estimate the state word alone carries it:
 *
 *  - discharging -> "Discharging" (no number at all)
 *  - charging    -> "Charging"
 *
 * The casing difference is intentional and is the panel's only cue that the
 * number is missing: a lowercase word tags a number, a capitalised word is
 * the number's replacement.
 */
export function formatBatteryTime(
  seconds: number,
  charging: boolean,
): BatteryTimePresentation {
  // Two ways to have no estimate, one treatment. `seconds <= 0` is the daemon
  // saying "unknown"; above MAX_RENDERED_SECONDS is the daemon saying something
  // so implausible that honouring it would be worse than ignoring it. Both
  // render the state word on its own -- see MAX_RENDERED_SECONDS.
  if (!Number.isFinite(seconds) || seconds <= 0 || seconds > MAX_RENDERED_SECONDS) {
    return { primary: "", sub: charging ? "Charging" : "Discharging" }
  }

  const primary = formatDuration(seconds)!
  return { primary, sub: charging ? "full in" : "remaining" }
}

/**
 * The whole status line for a caller that has ONE line to print with --
 * a tooltip, a notification, a bar label.
 *
 * WHY THIS IS NOT THE WIDGET'S JOB. The two words and their ORDER differ by
 * direction ("2h 14m remaining" vs "full in 2h 14m"), and the no-estimate case
 * has no number at all. Writing that composition in a widget means the state
 * word is now chosen in two places, and the bar's tooltip can drift from the
 * panel it opens: the panel says "Charging", the tooltip says "charging", or
 * worse the tooltip prints "0m remaining" for a missing estimate. It is derived
 * from `formatBatteryTime` rather than restated, so the words and the missing-
 * estimate degradation are decided in exactly one place and only the ORDER is
 * added here.
 */
export function formatBatteryStatusLine(seconds: number, charging: boolean): string {
  const { primary, sub } = formatBatteryTime(seconds, charging)
  // No number: the capitalised state word IS the line (design.md §4.3).
  if (primary === "") return sub
  // Charging reads "full in 2h 14m" (the word leads); discharging reads
  // "2h 14m remaining" (the number leads, because the countdown is the point).
  return charging ? `${sub} ${primary}` : `${primary} ${sub}`
}

/**
 * The icon variant a profile's ROW shows, from the guard-exempt `power-mode`
 * group in the ITR manifest.
 *
 * WHY THE `++` TIERS REUSE THE BASE VARIANT. The daemon's `Powersave++` and
 * `Performance++` are not different modes -- they are the SAME mode pushed
 * further (a lower ceiling / a higher floor on the same governor). There is no
 * sixth and seventh meaning to draw. Giving them distinct glyphs would claim a
 * distinction the system does not make, and the cheapest honest thing to
 * render is the base profile's glyph plus the `++` in the row's TEXT. So
 * `Powersave++` -> `powersave` and `Performance++` -> `performance`.
 *
 * This is also why the manifest declares exactly three variants and no
 * `system-*` copies: three glyphs for five profiles, consumed only on the
 * dark-glass panel.
 */
export function profileIconVariant(id: PowerProfileId): string {
  // Normalise the tier suffix rather than enumerating five cases: the mapping
  // is "the profile with any ++ suffix removed", and spelling that once means a
  // future `Powersave+++` needs no edit here.
  return id.replace(/\+\+$/, "").toLowerCase()
}

/**
 * Whether `candidate` is the profile currently in effect, i.e. whether its row
 * carries the `.sel` class.
 *
 * WHY CASE-INSENSITIVE. The daemon's identifier and the label shown to the
 * user differ in case in practice (`performance` vs `Performance`), and a
 * mismatch here is invisible-but-wrong: the row simply never lights up, which
 * reads as "the panel does not know what mode I am in" rather than as a bug.
 * Comparing case-insensitively makes the highlight depend only on WHICH mode
 * is active.
 *
 * An unknown/blank `current` matches nothing, so no row is highlighted rather
 * than the first one being highlighted by accident.
 */
export function isActiveProfile(current: string, candidate: PowerProfileId): boolean {
  if (!current) return false
  return current.trim().toLowerCase() === candidate.toLowerCase()
}

/**
 * The percentage shown in the nav header.
 *
 * Exported as a pure function (not inlined in the widget) for the same reason
 * as the rest of this file: the panel has TWO places that print a percentage
 * -- the nav header and the profile rows -- and a percentage rendered two ways
 * is a rounding drift waiting to happen. `formatPercentage` rounds once, and
 * `clampPercentage` clamps once, for both callers.
 *
 * `clampPercentage` clamps to 0..100 AND reports an unknown reading as `null`.
 * A daemon that reports no capacity must not render "NaN%" or "-1%"; the
 * caller shows the fallback word instead, exactly as `formatBatteryTime`
 * degrades to a state word with no number.
 */
export function clampPercentage(percent: number | null | undefined): number | null {
  if (percent === null || percent === undefined || !Number.isFinite(percent)) return null
  return Math.min(100, Math.max(0, Math.round(percent)))
}

/** The header's percentage text, e.g. "83%" -- or `null` for "no reading". */
export function formatPercentage(percent: number | null | undefined): string | null {
  const clamped = clampPercentage(percent)
  return clamped === null ? null : `${clamped}%`
}
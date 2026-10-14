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

/* ────────────────────────────────────────────────────────────────────────────
 * The two-level power model: a MODE owns a glyph; a VARIANT is a selectable
 * profile on a tier the mode DECLARES.
 *
 * WHY THE GROUPING IS DECLARED. The daemon reports each profile with a stable
 * `base_profile` tier and a user-editable `profile_name`. Neither field states
 * the grouping on its own:
 *
 *  - `profile_name` is editable (`UpdateProfileName`), so any rule that strips
 *    a `++` suffix to recover a mode breaks the moment a profile is renamed
 *    (`Performance++` -> `Showtime` has nothing to strip).
 *  - `base_profile` is stable but yields FIVE distinct tiers, not three. The
 *    live values are `Powersave++` -> `Superpowersave` and `Performance++` ->
 *    `Ultraperformance`; a rule that keys one glyph off the tier therefore
 *    asks for five glyphs, which is the wrong answer.
 *
 * So the grouping is an EXPLICIT declaration, keyed by the stable tier. Three
 * modes, one glyph each; any tier a mode declares shares its glyph.
 * ──────────────────────────────────────────────────────────────────────────── */

/** A power profile exactly as the daemon reports it. */
export interface PowerProfile {
  /** `profile_name` -- the user's arbitrary, editable instance label. */
  readonly name: string
  /** `base_profile` -- the daemon's stable semantic tier. The lookup key. */
  readonly tier: string
}

/** A profile together with its index in the daemon's `profiles[]` array. */
export interface IndexedProfile {
  readonly profile: PowerProfile
  readonly index: number
}

/** A declared mode: it owns a glyph and the tiers that are its variants. */
export interface PowerMode {
  /** The mode's label (`Powersave`, `Balanced`, `Performance`). */
  readonly mode: string
  /** The `power-mode` icon variant the mode's tiers share. */
  readonly glyph: string
  /** The `base_profile` tiers this mode declares, in daemon vocabulary. */
  readonly tiers: readonly string[]
}

/**
 * THE DECLARATION -- the one place that says which tiers share a glyph.
 *
 * Three modes, five tiers, three glyphs. The tier is the stable key; this
 * table is the grouping. Ordered cheapest-first so the rail reads lowest-power
 * -> highest-power, which is a product decision rather than a daemon artefact.
 */
export const POWER_MODES: readonly PowerMode[] = Object.freeze([
  Object.freeze({
    mode: "Powersave",
    glyph: "powersave",
    tiers: Object.freeze(["Powersave", "Superpowersave"]),
  }),
  Object.freeze({
    mode: "Balanced",
    glyph: "balanced",
    tiers: Object.freeze(["Balanced"]),
  }),
  Object.freeze({
    mode: "Performance",
    glyph: "performance",
    tiers: Object.freeze(["Performance", "Ultraperformance"]),
  }),
])

/** The pseudo-mode an undeclared tier gathers under. Never dropped, never blank. */
export const UNLISTED_MODE_NAME = "Unlisted"

/** The `power-mode` icon variant for a tier no mode declares (the fallback). */
export const FALLBACK_GLYPH = "unknown"

/** The words the rail meta line prints for an undeclared tier. */
export const UNMAPPED_TIER_LABEL = "unmapped tier"

/** The neutral pseudo-mode for an undeclared tier. It declares no tier. */
export const UNLISTED_MODE: PowerMode = Object.freeze({
  mode: UNLISTED_MODE_NAME,
  glyph: FALLBACK_GLYPH,
  tiers: Object.freeze([]),
})

/**
 * The mode a `base_profile` tier resolves to, or `null` when no mode declares
 * it. Case-insensitive and whitespace-tolerant: the daemon's canonical casing
 * is `Superpowersave`, but a tier that differs only in case is still the same
 * tier, and a near-miss here would silently move a user's profile.
 */
export function modeForTier(tier: string): PowerMode | null {
  const key = tier.trim().toLowerCase()
  if (key === "") return null
  return POWER_MODES.find((m) => m.tiers.some((t) => t.toLowerCase() === key)) ?? null
}

/** Whether `tier` is declared by one of `POWER_MODES`. */
export function isDeclaredTier(tier: string): boolean {
  return modeForTier(tier) !== null
}

/**
 * The mode a tier resolves to, folding the undeclared case into the neutral
 * `UNLISTED_MODE`. This is what the view uses: every profile resolves to a
 * mode, so nothing is ever dropped or drawn blank.
 */
export function resolveMode(tier: string): PowerMode {
  return modeForTier(tier) ?? UNLISTED_MODE
}

/** The `power-mode` glyph variant for a tier: its mode's glyph, or the fallback. */
export function glyphForTier(tier: string): string {
  return resolveMode(tier).glyph
}

/**
 * The `power-mode` icon-group STATE KEY for a mode (spine AD-7).
 *
 * The panel emits this key; the manifest's `bar_mappings.states` maps it to the
 * mode's variant, and the registry maps the variant to art. An undeclared tier
 * folds to the neutral `unknown` glyph, whose `power-mode-unknown` key is
 * deliberately absent from the table: it blanks rather than crashing.
 */
export function powerModeStateKey(mode: PowerMode): string {
  return `power-mode-${mode.glyph}`
}

/**
 * The modes the rail draws: the three declared modes in declaration order,
 * plus the neutral `Unlisted` cell ONLY when an undeclared tier is actually
 * present. The declared cells are daemon-independent -- they render before the
 * first reply and keep their positions as profiles come and go.
 */
export function railModes(profiles: readonly PowerProfile[]): PowerMode[] {
  const modes: PowerMode[] = [...POWER_MODES]
  if (profiles.some((p) => !isDeclaredTier(p.tier))) modes.push(UNLISTED_MODE)
  return modes
}

/**
 * The profiles that resolve into `mode`, in daemon order, each with its index
 * so the view can mark the active one by `index === active_profile`.
 */
export function profilesForMode(
  mode: PowerMode,
  profiles: readonly PowerProfile[],
): IndexedProfile[] {
  const out: IndexedProfile[] = []
  profiles.forEach((profile, index) => {
    if (resolveMode(profile.tier).mode === mode.mode) out.push({ profile, index })
  })
  return out
}

/**
 * The variant control renders IFF the selected mode declares more than one
 * variant. A one-option picker is decoration, not a decision.
 */
export function hasVariantChoice(
  mode: PowerMode,
  profiles: readonly PowerProfile[],
): boolean {
  return profilesForMode(mode, profiles).length > 1
}

/** The active profile by index, or `null` before the daemon answers. */
export function activeProfileOf(
  profiles: readonly PowerProfile[],
  index: number,
): IndexedProfile | null {
  if (!Number.isInteger(index) || index < 0 || index >= profiles.length) return null
  return { profile: profiles[index], index }
}

/**
 * The `profile_name` a click on a mode cell writes.
 *
 * Selection is by index, resolved to a profile: clicking a mode selects the
 * variant the daemon currently offers for it, or -- when the mode is already
 * active -- keeps the current variant rather than resetting it. Returns `null`
 * for a mode with no variant (nothing to select), so the caller can no-op.
 */
export function variantToSelect(
  mode: PowerMode,
  profiles: readonly PowerProfile[],
  activeIndex: number,
): string | null {
  const entries = profilesForMode(mode, profiles)
  if (entries.length === 0) return null
  const current = entries.find((e) => e.index === activeIndex)
  return (current ?? entries[0]).profile.name
}

/** The tooltip a mode cell names itself and its variants with. */
export function modeTooltip(mode: PowerMode, profiles: readonly PowerProfile[]): string {
  if (mode.mode === UNLISTED_MODE_NAME) {
    return `Unlisted tiers — the fallback glyph`
  }
  const stem = `${mode.mode} mode — ${mode.glyph} glyph`
  const names = profilesForMode(mode, profiles).map((e) => e.profile.name)
  if (names.length === 0) return stem
  const word = names.length === 1 ? "variant" : "variants"
  return `${stem} · ${word}: ${names.join(", ")}`
}

/**
 * The tooltip a variant pill names itself with. The tier is the daemon's
 * stable vocabulary; an undeclared tier says so rather than pretending.
 */
export function variantTooltip(profile: PowerProfile): string {
  if (isDeclaredTier(profile.tier)) {
    return `${profile.name} · ${profile.tier} tier`
  }
  const tier = profile.tier.trim() === "" ? "?" : profile.tier.trim()
  return `${profile.name} · tier ${tier} · ${UNMAPPED_TIER_LABEL}`
}

/**
 * The selected profile named ONCE: its name, and the `<mode> mode · <tier>
 * tier` line that makes the resolution explicit. An undeclared tier reads
 * `unlisted mode · unmapped tier`; no active profile reads `—`.
 */
export function railMeta(profile: PowerProfile | null): { name: string; line: string } {
  if (profile === null) return { name: "—", line: "" }
  if (!isDeclaredTier(profile.tier)) {
    return { name: profile.name, line: `unlisted mode · ${UNMAPPED_TIER_LABEL}` }
  }
  return {
    name: profile.name,
    line: `${resolveMode(profile.tier).mode} mode · ${profile.tier} tier`,
  }
}

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
 * The percentage shown in the nav header.
 *
 * Exported as a pure function (not inlined in the widget) for the same reason
 * as the rest of this file: the panel prints a percentage in TWO places --
 * the nav header and the profile rows -- and a percentage rendered two ways
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

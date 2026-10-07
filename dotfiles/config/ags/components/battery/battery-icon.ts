/**
 * Battery state → icon state key. PURE (no GTK, no I/O).
 *
 * WHY THIS IS ITS OWN MODULE rather than living in the bar widget. Both the
 * status-bar indicator and the panel's nav header draw the SAME battery glyph,
 * and they must be the same glyph: a header showing "50%" beside a low-charge
 * battery art, or a bar glyph that disagrees with the panel it opens, reads as
 * a bug in the panel rather than as two independent widgets. One threshold
 * table, two callers — the same argument as `lib/wifi-signal.ts` and the same
 * reason `presentation.ts` owns every panel DECISION.
 *
 * Registered in `dotfiles/config/ags/tests/tsconfig.tests.json`'s explicit
 * module list, which is itself the statement that this file is pure.
 */

/**
 * The percentage step table, in the manifest's own `bar_mappings` vocabulary.
 *
 * Thresholds are upper-exclusive (`< 0.25` is "0") and derived from the
 * ICON_NAMESPACE constant below rather than repeated, so the two cannot drift.
 */
const ICON_NAMESPACE = "battery"

/**
 * The `bar_mappings` state key for a reading.
 *
 * Exported so the mapping is testable; the icon PATH resolution needs
 * `icon-registry` and therefore stays in the widgets.
 *
 * `percentage` arrives from the Astal binding as a 0..1 FRACTION, which is why
 * every bound below is a fraction and not a percent — a factor-of-100 mistake
 * here would put every device permanently in the "0" bucket and the panel would
 * show a flat empty battery, so the unit is stated at the only place it is used.
 */
export function batteryStateKey(percentage: number, charging: boolean): string {
  const level =
    percentage < 0.25 ? "0"
    : percentage < 0.5 ? "25"
    : percentage < 0.75 ? "50"
    : percentage < 1 ? "75"
    : "100"
  return charging
    ? `charging-${level}`
    : `discharging-${level}`
}

/** The `battery` icon group this module's keys belong to. */
export const BATTERY_ICON_GROUP = ICON_NAMESPACE

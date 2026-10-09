/**
 * Level vocabulary — PURE (no `ags`, no GTK, no Gio, no I/O).
 *
 * Shared by every audio surface that renders a level-aware glyph: the bar's
 * output indicator, the panel's per-app mute button, and the settings-panel
 * Sound card. One threshold table for all of them, so a bar glyph can never
 * disagree with the panel it opens.
 *
 * Extracted verbatim from the legacy `audio/state.ts` (which is retired by
 * `finish-audio-bar-migration`). Registered in
 * `dotfiles/config/ags/tests/tsconfig.tests.json`'s purity list and exercised by
 * `tests/ts/levels.test.ts` through Node's native type-stripping.
 */

/** The `volume` icon-group variant for a mute flag and a 0..1 gain level. */
export function levelVariant(muted: boolean, value: number): string {
  if (muted || value <= 0) return "muted"
  const percent = Math.min(100, value * 100)
  if (percent <= 25) return "lowest"
  if (percent <= 50) return "low"
  if (percent <= 75) return "medium"
  return "max"
}

/**
 * Clamp a volume to [0,1].
 *
 * Guarded against non-finite input, not just null/undefined: AstalWp can briefly
 * report NaN during swaps, and `Number(NaN ?? 0)` is still NaN, so a plain
 * `?? 0` fallback would pass NaN straight through to `levelVariant` (which would
 * then read "max" for a missing reading). A non-finite value reads as 0 — the
 * same "no reading" the null case gets.
 */
export function clampVolume(value: number | null | undefined): number {
  const n = Number(value)
  if (!Number.isFinite(n)) return 0
  return Math.max(0, Math.min(1, n))
}

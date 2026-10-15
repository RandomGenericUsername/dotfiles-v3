// Preview controls for the component schematic (design D11, capability
// `btop-theme-studio`).
//
// The load control, fixed-fill levels, and backdrop toggle affect ONLY the
// component schematic. The live preview always shows btop's real data, so
// injecting synthetic load there would break its contract.
//
// These helpers are pure: they compute an appearance and never touch the theme
// map, so toggling them cannot alter a theme colour.

export type Backdrop = "theme" | "neutral";

export interface PreviewControls {
  /** Meter/utilisation level (0–100) the schematic renders. */
  readonly load: number;
  /** When set, every meter renders at this fixed level regardless of load. */
  readonly fixedFill: FixedFill | null;
  /** Theme background vs a neutral backdrop. */
  readonly backdrop: Backdrop;
}

export type FixedFill = 0 | 25 | 50 | 100;

export const FIXED_FILL_LEVELS: readonly FixedFill[] = [0, 25, 50, 100];

/** A neutral backdrop for judging a theme off its own background. */
export const NEUTRAL_BACKDROP = "#1b1d21";

export const DEFAULT_CONTROLS: PreviewControls = { load: 35, fixedFill: null, backdrop: "theme" };

export interface PreviewAppearance {
  /** The fill level every meter should render at. */
  readonly fill: number;
  /** The backdrop colour the schematic sits on. */
  readonly backdrop: string;
}

/** The fill level for one meter: fixed fill wins over the load control. */
export function meterFill(controls: PreviewControls, baseLevel: number): number {
  const raw = controls.fixedFill !== null ? controls.fixedFill : baseLevel;
  return Math.max(0, Math.min(100, raw));
}

/** The schematic backdrop colour for the current controls. */
export function backdropColour(controls: PreviewControls, themeBackground: string): string {
  return controls.backdrop === "neutral" ? NEUTRAL_BACKDROP : themeBackground;
}

/** The full appearance the schematic renders with, given a theme background. */
export function previewAppearance(
  controls: PreviewControls,
  themeBackground: string,
): PreviewAppearance {
  return {
    fill: meterFill(controls, controls.load),
    backdrop: backdropColour(controls, themeBackground),
  };
}

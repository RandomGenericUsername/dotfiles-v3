import type { BarLayout, LayoutProvider } from "../kit/layout"

/**
 * The repo-default bar layout (spine AD-9; doc 101 §4.3).
 *
 * This is the always-non-null floor of the layout chain: with no user override
 * and no runtime `bar.json`, the bar still places every widget (AD-18, "works
 * with nothing"). The order is the composition `Bar.tsx` hardcoded before the
 * migration, preserved exactly:
 *
 *   start  : workspaces
 *   center : clock
 *   end    : tray, recording, audio-output, audio-mic, battery, bluetooth,
 *            network, btop, thunderbird, settings, power-menu
 *
 * The recording indicator is placed here rather than inside the tray (its old
 * home), so placement is data (AD-9). The four launchers (btop, thunderbird,
 * settings, power-menu) were already descriptors; they are entries now too.
 *
 * PURE: this module imports only the pure layout vocabulary, so the default
 * layout is unit-testable on a stock runner.
 */
export const DEFAULT_LAYOUT: BarLayout = {
  sections: {
    start: [{ id: "workspaces" }],
    center: [{ id: "clock" }],
    end: [
      { id: "tray" },
      { id: "recording" },
      { id: "audio-output" },
      { id: "audio-mic" },
      { id: "battery" },
      { id: "bluetooth" },
      { id: "network" },
      { id: "btop" },
      { id: "thunderbird" },
      { id: "settings" },
      { id: "power-menu" },
    ],
  },
}

/**
 * The repo-default `LayoutProvider`. `load()` always returns a layout — the
 * AD-9 invariant that makes the bar renderable with no external provider.
 */
export const repoDefaultLayout: LayoutProvider = {
  load: () => DEFAULT_LAYOUT,
}

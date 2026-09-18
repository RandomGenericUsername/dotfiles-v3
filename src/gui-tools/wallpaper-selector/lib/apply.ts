// Apply pipeline entry point (GJS side).
//
// The GUI shells the engine exactly like the capture window shells
// `capture-tool`: `dotfiles-runtime wallpaper set <image>` runs the full
// derive → cache → swap → reload chain. No special-casing for variants —
// the runtime detects WEG-derived inputs by path and skips regeneration
// itself (mechanism A), while palette/icons still derive from the
// variant's pixels. Progress and completion arrive via the
// `wallpaper.state` domain event, not via this promise (AD-37).

import { execAsync } from "ags/process";

/** Apply a wallpaper (or a WEG variant path).
 *
 * `contrast` is the explicit icon-contrast policy for a never-applied
 * wallpaper whose content hash is still a placeholder: the runtime
 * computes the real governing hash at set time, persists the choice under
 * it, and renders accordingly (backend `icon-contrast-opt-out` D2). Omit
 * it for the normal `auto` path (runtime resolves store → default ON).
 */
export function applyWallpaper(
  imagePath: string,
  contrast?: "on" | "off",
): Promise<string> {
  const args = ["dotfiles-runtime", "wallpaper", "set", imagePath];
  if (contrast !== undefined) args.push("--contrast", contrast);
  return execAsync(args);
}

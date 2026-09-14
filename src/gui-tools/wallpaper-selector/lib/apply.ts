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

export function applyWallpaper(imagePath: string): Promise<string> {
  return execAsync(["dotfiles-runtime", "wallpaper", "set", imagePath]);
}

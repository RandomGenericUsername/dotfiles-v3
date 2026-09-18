// Per-wallpaper icon-contrast preference + icons-only regeneration (GJS).
//
// The selector NEVER reads or writes the preference store directly: the
// runtime's `icons preference` accessor is the sole interface
// (`icon-contrast-opt-out` D1b/D2a). These helpers shell `dotfiles-runtime`
// and parse `--format json` output; progress for a regenerate arrives on
// the `wallpaper.state` topic (applying → done/error, never `visible`).

import { execAsync } from "ags/process";

export interface ContrastPref {
  hash: string;
  enabled: boolean;
  source: string;
}

function parsePref(stdout: string): ContrastPref {
  const parsed = JSON.parse(stdout) as Partial<ContrastPref>;
  if (typeof parsed.hash !== "string" || typeof parsed.enabled !== "boolean") {
    throw new Error(`unexpected icons preference output: ${stdout.trim()}`);
  }
  return {
    hash: parsed.hash,
    enabled: parsed.enabled,
    source: typeof parsed.source === "string" ? parsed.source : "",
  };
}

/** Read the resolved preference for `hash` (store → default ON). */
export async function getContrastPref(hash: string): Promise<ContrastPref> {
  const stdout = await execAsync([
    "dotfiles-runtime",
    "icons",
    "preference",
    hash,
    "--format",
    "json",
  ]);
  return parsePref(stdout);
}

/** Persist the choice for `hash` and return the resolved value. */
export async function setContrastPref(
  hash: string,
  enabled: boolean,
): Promise<ContrastPref> {
  const stdout = await execAsync([
    "dotfiles-runtime",
    "icons",
    "preference",
    hash,
    "--set",
    enabled ? "on" : "off",
    "--format",
    "json",
  ]);
  return parsePref(stdout);
}

/** Icons-only re-render under the forced policy (no wallpaper re-set). */
export function regenerateIcons(enabled: boolean): Promise<string> {
  return execAsync([
    "dotfiles-runtime",
    "icons",
    "regenerate",
    "--contrast",
    enabled ? "on" : "off",
    "--format",
    "json",
  ]);
}

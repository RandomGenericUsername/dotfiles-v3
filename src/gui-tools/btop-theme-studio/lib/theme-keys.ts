// The fixed btop theme vocabulary.
//
// btop's theme is a FIXED set of keys defined by `Default_theme` in
// btop_theme.cpp. There is no way to add keys: btop ignores unknown ones. The
// list below is the exact 48-key set (locked against the generated
// key_widgets.json artifact and the vendored btop source by tests).
//
// Grouping mirrors the mock's tree: surface / box chrome / consumption /
// load-heat / network-process / process state.

export const THEME_KEYS: readonly string[] = [
  // Surface
  "main_bg",
  "main_fg",
  "title",
  "hi_fg",
  "selected_bg",
  "selected_fg",
  "inactive_fg",
  "graph_text",
  // Box chrome
  "meter_bg",
  "proc_misc",
  "cpu_box",
  "mem_box",
  "net_box",
  "proc_box",
  "div_line",
  // Consumption
  "used_start",
  "used_mid",
  "used_end",
  "free_start",
  "free_mid",
  "free_end",
  "available_start",
  "available_mid",
  "available_end",
  // Load / heat
  "cpu_start",
  "cpu_mid",
  "cpu_end",
  "temp_start",
  "temp_mid",
  "temp_end",
  "cached_start",
  "cached_mid",
  "cached_end",
  // Network / process
  "download_start",
  "download_mid",
  "download_end",
  "upload_start",
  "upload_mid",
  "upload_end",
  "process_start",
  "process_mid",
  "process_end",
  // Process state
  "proc_pause_bg",
  "proc_follow_bg",
  "proc_banner_bg",
  "proc_banner_fg",
  "followed_bg",
  "followed_fg",
];

export interface KeyGroup {
  readonly name: string;
  readonly keys: readonly string[];
}

export const KEY_GROUPS: readonly KeyGroup[] = [
  {
    name: "Surface",
    keys: [
      "main_bg",
      "main_fg",
      "title",
      "hi_fg",
      "selected_bg",
      "selected_fg",
      "inactive_fg",
      "graph_text",
    ],
  },
  { name: "Box chrome", keys: ["meter_bg", "proc_misc", "cpu_box", "mem_box", "net_box", "proc_box", "div_line"] },
  {
    name: "Consumption",
    keys: [
      "used_start",
      "used_mid",
      "used_end",
      "free_start",
      "free_mid",
      "free_end",
      "available_start",
      "available_mid",
      "available_end",
    ],
  },
  {
    name: "Load / heat",
    keys: [
      "cpu_start",
      "cpu_mid",
      "cpu_end",
      "temp_start",
      "temp_mid",
      "temp_end",
      "cached_start",
      "cached_mid",
      "cached_end",
    ],
  },
  {
    name: "Network / process",
    keys: [
      "download_start",
      "download_mid",
      "download_end",
      "upload_start",
      "upload_mid",
      "upload_end",
      "process_start",
      "process_mid",
      "process_end",
    ],
  },
  {
    name: "Process state",
    keys: ["proc_pause_bg", "proc_follow_bg", "proc_banner_bg", "proc_banner_fg", "followed_bg", "followed_fg"],
  },
];

/** The gradient families: each has `_start` / `_mid` / `_end` stops. */
export const GRADIENT_FAMILIES: readonly string[] = [
  "used",
  "free",
  "available",
  "cpu",
  "temp",
  "cached",
  "download",
  "upload",
  "process",
];

/** Named palette tokens btop understands in a generated theme. */
export const NAMED_TOKENS: readonly string[] = ["background", "foreground", "cursor"];

/** The boxes btop can draw, in schematic column order. */
export const BOXES: readonly string[] = ["cpu", "gpu", "mem", "net", "disks", "proc"];

export type RoleSuffix = "_start" | "_mid" | "_end";

const ROLE_SUFFIXES: readonly RoleSuffix[] = ["_start", "_mid", "_end"];

/** The role suffix of a key (`used_start` → `_start`), or null. */
export function roleSuffix(key: string): RoleSuffix | null {
  for (const suffix of ROLE_SUFFIXES) {
    if (key.endsWith(suffix)) return suffix;
  }
  return null;
}

/** The gradient family of a key (`used_start` → `used`), or the key itself. */
export function familyOf(key: string): string {
  const suffix = roleSuffix(key);
  return suffix ? key.slice(0, -suffix.length) : key;
}

/** True when `key` is a gradient stop (`*_start` / `*_mid` / `*_end`). */
export function isGradientStop(key: string): boolean {
  return roleSuffix(key) !== null;
}

/** True when `key` is one of the three stops of a known gradient family. */
export function isGradientKey(key: string): boolean {
  return isGradientStop(key) && GRADIENT_FAMILIES.includes(familyOf(key));
}

/** The three stop keys of a family, in order. */
export function gradientStops(family: string): [string, string, string] {
  return [`${family}_start`, `${family}_mid`, `${family}_end`];
}

/**
 * A two-stop gradient has an EMPTY mid value. btop allows at most three stops,
 * so the studio offers "add middle colour" exactly in this case.
 */
export function isTwoStop(map: Readonly<Record<string, string>>, family: string): boolean {
  const mid = map[`${family}_mid`];
  return mid === undefined || mid === "";
}

/** Every key sharing a role suffix with `key` (for the "Same role" scope). */
export function sameRoleKeys(key: string): string[] {
  const suffix = roleSuffix(key);
  if (suffix === null) return [key];
  return THEME_KEYS.filter((candidate) => candidate.endsWith(suffix));
}

/** All keys present in `map`, in canonical order, plus any unexpected extras. */
export function keysOf(map: Readonly<Record<string, string>>): string[] {
  const known = THEME_KEYS.filter((key) => key in map);
  const extras = Object.keys(map)
    .filter((key) => !THEME_KEYS.includes(key))
    .sort();
  return [...known, ...extras];
}

/** True when every one of the 48 keys is present in `map`. */
export function hasAllKeys(map: Readonly<Record<string, string>>): boolean {
  return THEME_KEYS.every((key) => key in map);
}

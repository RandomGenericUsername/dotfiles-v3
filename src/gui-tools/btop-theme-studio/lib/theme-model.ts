// Theme model, pending edits, picker scopes, diagnosis, and the one-click
// meter fixes (design D7/D9, capability `btop-theme-studio`).
//
// Pure and I/O-free: the UI layer owns file reads/writes and the AGS
// containers. Everything here is unit-testable with plain node.

import {
  GRADIENT_FAMILIES,
  NAMED_TOKENS,
  THEME_KEYS,
  keysOf,
  familyOf,
  isGradientStop,
  roleSuffix,
  sameRoleKeys,
} from "./theme-keys.ts";

export type ThemeKind = "generated" | "authored";

export interface Palette {
  readonly background: string;
  readonly foreground: string;
  readonly cursor: string;
  /** Deduped ramp stops (the generated theme's `ramp[i]` source). */
  readonly ramp: readonly string[];
  /** The full color0–color15 palette. */
  readonly colors: readonly string[];
}

export interface Theme {
  readonly id: string;
  readonly name: string;
  readonly kind: ThemeKind;
  readonly active: boolean;
  readonly map: Readonly<Record<string, string>>;
}

/** Pending edits: theme key → new (unwritten) value. */
export type PendingEdits = ReadonlyMap<string, string>;

export type Scope = "key" | "role" | "all";

export const TRANSPARENT = "";

const FALLBACK = "#ff00ff";

/** Resolve a theme value (token or literal) to a hex colour; "" = transparent. */
export function resolveHex(value: string | undefined, palette: Palette): string {
  if (value === undefined) return FALLBACK;
  if (value === "") return TRANSPARENT;
  if (value.startsWith("#")) return value;
  if (value === "background") return palette.background;
  if (value === "foreground") return palette.foreground;
  if (value === "cursor") return palette.cursor;
  if (value.startsWith("ramp[")) {
    const index = Number(value.slice(5, -1));
    return palette.ramp[index] ?? FALLBACK;
  }
  if (/^color\d+$/.test(value)) {
    const index = Number(value.slice(5));
    return palette.colors[index] ?? FALLBACK;
  }
  return FALLBACK;
}

/** True when a value is a generated-theme palette reference (not a literal). */
export function isPaletteReference(value: string): boolean {
  return (
    value.startsWith("ramp[") ||
    /^color\d+$/.test(value) ||
    (NAMED_TOKENS as readonly string[]).includes(value)
  );
}

/** The effective theme map: on-disk map overlaid with pending edits. */
export function effectiveMap(
  map: Readonly<Record<string, string>>,
  edits: PendingEdits,
): Record<string, string> {
  const next: Record<string, string> = { ...map };
  for (const [key, value] of edits) next[key] = value;
  return next;
}

/** The keys a pick applies to for a scope (spec: This key / Same role / All). */
export function scopeKeys(
  key: string,
  scope: Scope,
  map: Readonly<Record<string, string>>,
): string[] {
  if (scope === "key") return [key];
  if (scope === "role") return sameRoleKeys(key);
  return keysOf(map);
}

/** Apply a pick at a scope; returns the next pending-edit map. */
export function applyPick(
  edits: PendingEdits,
  key: string,
  value: string,
  scope: Scope,
  map: Readonly<Record<string, string>>,
): Map<string, string> {
  const next = new Map(edits);
  for (const target of scopeKeys(key, scope, map)) next.set(target, value);
  return next;
}

export interface DiffEntry {
  readonly key: string;
  readonly from: string;
  readonly to: string;
}

/** The pending edits as an ordered diff against the on-disk map. */
export function diffEdits(
  map: Readonly<Record<string, string>>,
  edits: PendingEdits,
): DiffEntry[] {
  const entries: DiffEntry[] = [];
  for (const key of keysOf(map)) {
    if (!edits.has(key)) continue;
    const from = map[key] ?? "";
    const to = edits.get(key) as string;
    if (from !== to) entries.push({ key, from, to });
  }
  return entries;
}

/** Revert discards every pending edit (spec scenario: diff returns to empty). */
export function revert(): Map<string, string> {
  return new Map();
}

// ── One-click meter fixes ───────────────────────────────────────────────────

/**
 * "Reserve surface for meters": the unfilled meter is drawn from the theme's
 * surface (`main_bg`) and the used floor is raised (`used_start` ← `used_mid`),
 * so a low-load meter no longer reads as full.
 */
export function fixReserveSurface(map: Readonly<Record<string, string>>): Record<string, string> {
  const next = { ...map };
  next.meter_bg = next.main_bg ?? TRANSPARENT;
  if (next.used_mid) next.used_start = next.used_mid;
  return next;
}

/** "Transparent meters": the unfilled meter becomes transparent (empty value). */
export function fixTransparentMeters(map: Readonly<Record<string, string>>): Record<string, string> {
  return { ...map, meter_bg: TRANSPARENT };
}

// ── Gradient editor ─────────────────────────────────────────────────────────

export const GRADIENT_LIMIT_NOTE =
  "btop gradients have exactly three stops (start / mid / end). New theme keys cannot be added — btop ignores unknown ones.";

/** True when a family's mid stop is empty (a two-stop gradient). */
export function isTwoStop(map: Readonly<Record<string, string>>, family: string): boolean {
  const mid = map[`${family}_mid`];
  return mid === undefined || mid === "";
}

/**
 * "Add middle colour" for a two-stop gradient: set `*_mid` to the start colour
 * (falling back to the end), turning it into a three-stop gradient.
 */
export function addMiddleColour(map: Readonly<Record<string, string>>, family: string): Record<string, string> {
  if (!GRADIENT_FAMILIES.includes(family)) return { ...map };
  const next = { ...map };
  next[`${family}_mid`] = next[`${family}_start`] || next[`${family}_end`] || TRANSPARENT;
  return next;
}

// ── Diagnosis ───────────────────────────────────────────────────────────────

export type DiagnosisLevel = "error" | "warn" | "ok";

export interface Diagnosis {
  readonly level: DiagnosisLevel;
  readonly message: string;
}

function relativeLuminance(hex: string): number {
  if (!hex.startsWith("#") || hex.length !== 7) return 0.5;
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const linear = channels.map((v) => (v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4)));
  return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2];
}

/**
 * Meter-contrast defects. The motivating defect: `used_start` and `meter_bg`
 * resolve to the same colour, so a low-load meter block vanishes into the empty
 * meter. Also flags an unfilled meter that competes with the background.
 */
export function diagnose(map: Readonly<Record<string, string>>, palette: Palette): Diagnosis[] {
  const out: Diagnosis[] = [];
  const usedStart = resolveHex(map.used_start, palette);
  const meterBg = resolveHex(map.meter_bg, palette);
  const background = resolveHex(map.main_bg, palette);

  if (map.used_start !== undefined && map.meter_bg !== undefined && usedStart === meterBg) {
    out.push({
      level: "error",
      message:
        `used_start and meter_bg are the SAME colour (${usedStart}) — ` +
        "low-load meter blocks vanish into the empty meter.",
    });
  }

  if (map.meter_bg !== undefined && map.main_bg !== undefined) {
    if (meterBg === TRANSPARENT) {
      out.push({ level: "ok", message: "meter_bg is transparent — the unfilled meter shows the surface behind it." });
    } else {
      const delta = Math.abs(relativeLuminance(meterBg) - relativeLuminance(background));
      if (delta > 0.02) {
        out.push({
          level: "warn",
          message:
            `meter_bg differs from the background (Δ ${delta.toFixed(2)}) — ` +
            "the unfilled part of every meter competes with the data.",
        });
      } else {
        out.push({ level: "ok", message: `meter_bg sits against the background (Δ ${delta.toFixed(2)}).` });
      }
    }
  }

  if (map.used_start !== undefined && map.meter_bg !== undefined && usedStart !== TRANSPARENT) {
    const delta = Math.abs(relativeLuminance(usedStart) - relativeLuminance(meterBg));
    if (delta < 0.05) {
      out.push({
        level: "warn",
        message: `used low-end is close to meter_bg (Δ ${delta.toFixed(2)}) — a low-load meter may still read as full.`,
      });
    }
  }

  return out;
}

// ── Theme library ───────────────────────────────────────────────────────────

export interface LibraryState {
  readonly themes: readonly Theme[];
}

/** The generated base is read-only and palette-linked: it can be forked, not deleted. */
export function canDelete(theme: Theme): boolean {
  return theme.kind !== "generated";
}

export function deleteTheme(library: LibraryState, id: string): LibraryState {
  const theme = library.themes.find((candidate) => candidate.id === id);
  if (!theme || !canDelete(theme)) return library;
  return { themes: library.themes.filter((candidate) => candidate.id !== id) };
}

/** Fork a theme: freeze its current resolved colours into a new authored theme. */
export function forkTheme(theme: Theme, id: string, name: string, palette: Palette): Theme {
  const map: Record<string, string> = {};
  for (const key of keysOf(theme.map)) map[key] = resolveHex(theme.map[key], palette);
  return { id, name, kind: "authored", active: false, map };
}

/** Duplicate a theme as-is (keeping its token form) into a new authored theme. */
export function duplicateTheme(theme: Theme, id: string, name: string): Theme {
  return { id, name, kind: "authored", active: false, map: { ...theme.map } };
}

/** Create a fresh authored theme from a base map. */
export function createTheme(id: string, name: string, map: Readonly<Record<string, string>>): Theme {
  return { id, name, kind: "authored", active: false, map: { ...map } };
}

/** Mark exactly one theme active (the one btop uses via `color_theme`). */
export function markActive(library: LibraryState, id: string): LibraryState {
  if (!library.themes.some((theme) => theme.id === id)) return library;
  return { themes: library.themes.map((theme) => ({ ...theme, active: theme.id === id })) };
}

// ── Serialization ───────────────────────────────────────────────────────────

/** Serialize a theme to btop's `.theme` body (`theme[key]="value"` per line). */
export function serializeTheme(map: Readonly<Record<string, string>>): string {
  return keysOf(map)
    .map((key) => `theme[${key}]="${map[key]}"`)
    .join("\n")
    .concat("\n");
}

/** Parse a btop `.theme` body into a key→value map. */
export function parseTheme(text: string): Record<string, string> {
  const map: Record<string, string> = {};
  const re = /^theme\[([A-Za-z0-9_]+)\]="([^"]*)"/gm;
  let match: RegExpExecArray | null;
  while ((match = re.exec(text)) !== null) map[match[1]] = match[2];
  return map;
}

/** A default generated-theme map (token form) for a fresh studio session. */
export function generatedDefaultMap(): Record<string, string> {
  const map: Record<string, string> = {};
  for (const key of THEME_KEYS) map[key] = "";
  map.main_bg = "background";
  map.main_fg = "foreground";
  map.title = "foreground";
  map.hi_fg = "ramp[6]";
  map.selected_bg = "ramp[3]";
  map.selected_fg = "foreground";
  map.inactive_fg = "ramp[2]";
  map.graph_text = "ramp[6]";
  map.meter_bg = "ramp[1]";
  map.proc_misc = "ramp[6]";
  map.cpu_box = "ramp[2]";
  map.mem_box = "ramp[2]";
  map.net_box = "ramp[2]";
  map.proc_box = "ramp[2]";
  map.div_line = "ramp[1]";
  const stops: Record<string, [string, string, string]> = {
    used: ["ramp[1]", "ramp[4]", "ramp[7]"],
    free: ["ramp[0]", "ramp[3]", "ramp[6]"],
    available: ["ramp[0]", "ramp[3]", "ramp[6]"],
    cpu: ["ramp[3]", "ramp[5]", "ramp[7]"],
    temp: ["ramp[3]", "ramp[5]", "ramp[7]"],
    cached: ["ramp[3]", "ramp[5]", "ramp[7]"],
    download: ["ramp[0]", "", "ramp[6]"],
    upload: ["ramp[0]", "", "ramp[6]"],
    process: ["ramp[1]", "ramp[4]", "ramp[7]"],
  };
  for (const [family, [start, mid, end]] of Object.entries(stops)) {
    map[`${family}_start`] = start;
    map[`${family}_mid`] = mid;
    map[`${family}_end`] = end;
  }
  map.proc_pause_bg = "ramp[5]";
  map.proc_follow_bg = "ramp[6]";
  map.proc_banner_bg = "ramp[3]";
  map.proc_banner_fg = "foreground";
  map.followed_bg = "ramp[6]";
  map.followed_fg = "foreground";
  return map;
}

export { THEME_KEYS, GRADIENT_FAMILIES, NAMED_TOKENS, familyOf, isGradientStop, roleSuffix };

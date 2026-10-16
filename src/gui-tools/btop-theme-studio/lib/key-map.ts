// Consume the generated key→widget map (design D8, capability
// `btop-key-widget-map`).
//
// The map is generated from btop's own source by `tools/key_widgets.py` and
// committed as `lib/key_widgets.json` (canonical, drift-checked) plus
// `lib/key-widgets.generated.ts` (the importable form). The studio NEVER
// hand-traces attribution: "where does this key show?" is answered from this
// artifact, and a drift guard re-derives it from source.

import { KEY_WIDGETS } from "./key-widgets.generated.ts";
import { THEME_KEYS } from "./theme-keys.ts";

export interface KeyWidgetEntry {
  readonly modules: readonly string[];
  readonly calls: number;
  readonly sites: readonly string[];
}

export interface KeyWidgetMap {
  readonly draw_source: string;
  readonly theme_source: string;
  readonly method: string;
  readonly note: string;
  readonly keys: Readonly<Record<string, KeyWidgetEntry>>;
}

export const KEY_WIDGET_MAP: KeyWidgetMap = KEY_WIDGETS as unknown as KeyWidgetMap;

/** The modules a key paints, or [] when the key is unknown. */
export function modulesFor(key: string): string[] {
  return [...(KEY_WIDGET_MAP.keys[key]?.modules ?? [])];
}

/** The call sites that produced a key's attribution (auditable). */
export function sitesFor(key: string): string[] {
  return [...(KEY_WIDGET_MAP.keys[key]?.sites ?? [])];
}

/** True when btop's draw source never references the key (e.g. main_bg). */
export function isUnreferenced(key: string): boolean {
  const entry = KEY_WIDGET_MAP.keys[key];
  return !!entry && entry.calls === 0 && entry.sites.some((site) => site.startsWith("not referenced"));
}

/** True when the map carries an entry for every one of btop's 48 keys. */
export function hasCompleteCoverage(): boolean {
  return THEME_KEYS.every((key) => key in KEY_WIDGET_MAP.keys);
}

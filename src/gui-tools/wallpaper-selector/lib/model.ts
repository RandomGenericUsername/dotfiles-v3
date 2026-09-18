// Pure selector model: wallpaper/variant grouping with NO GJS imports.
// Node-testable (`node tests/model.mjs`). Filesystem access and hashing
// live in `scan.ts`; this module only shapes plain data.

export interface RawWallpaper {
  name: string;
  path: string;
  hash: string;
}

export interface RawVariant {
  name: string;
  group: string;
  path: string;
}

export interface RawEffectsEntry {
  sourceHash: string;
  variants: RawVariant[];
}

export interface RawCurrent {
  wallpaperHash: string;
  wallpaperPath: string;
}

export interface WallpaperEntry {
  name: string;
  path: string;
  hash: string;
  variantCount: number;
  live: boolean;
}

export interface VariantEntry {
  name: string;
  group: string;
  path: string;
  live: boolean;
}

export interface SelectorModel {
  wallpapers: WallpaperEntry[];
  /** Wallpaper content-hash → its variants (empty when never applied). */
  variants: Map<string, VariantEntry[]>;
  liveWallpaperHash: string;
  liveVariantPath: string;
}

const IMAGE_EXTS = new Set(["png", "jpg", "jpeg", "webp", "gif", "bmp"]);

export function isImageFile(name: string): boolean {
  const dot = name.lastIndexOf(".");
  if (dot < 0) return false;
  return IMAGE_EXTS.has(name.slice(dot + 1).toLowerCase());
}

export function stemOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot < 0 ? filename : filename.slice(0, dot);
}

// ── Zero-hash spine mapping ────────────────────────────────────────────
// The runtime's wallpaper cache meta.json carries {content_hash,
// source_path} per applied wallpaper, so spine files map to hashes WITHOUT
// reading file bytes. Size-guarded: the cached import is only trusted when
// the spine file size still matches the imported bytes (edited-in-place
// files fall back to a real sha256).

export interface WallpaperCacheMeta {
  hash: string;
  sourcePath: string;
  size: number;
}

export interface SpineFileStat {
  name: string;
  path: string;
  size: number;
}

/** Map spine paths → content hashes via runtime metas (sourcePath + size
 * must both match). Files with no size-matching meta are ABSENT from the
 * map — the caller decides between a real sha256 and a placeholder. */
export function mapSpineHashes(
  spine: SpineFileStat[],
  metas: WallpaperCacheMeta[],
): Map<string, string> {
  const bySource = new Map<string, WallpaperCacheMeta[]>();
  for (const m of metas) {
    const list = bySource.get(m.sourcePath) ?? [];
    list.push(m);
    bySource.set(m.sourcePath, list);
  }
  const out = new Map<string, string>();
  for (const f of spine) {
    const hit = (bySource.get(f.path) ?? []).find((c) => c.size === f.size);
    if (hit !== undefined) out.set(f.path, hit.hash);
  }
  return out;
}

/** Preference default for a hash never queried: matches the backend's
 * store → default-ON resolution (`icon-contrast-opt-out` D1b). */
export const DEFAULT_CONTRAST_ENABLED = true;

/** Whether `w` governs what is currently live: the live wallpaper itself,
 * or the parent of a live promoted variant. A variant flip therefore
 * regenerates icons for its whole gallery. */
export function isWallpaperLive(
  w: WallpaperEntry,
  variants: VariantEntry[],
): boolean {
  return w.live || variants.some((v) => v.live);
}

/** Cached contrast preference for `hash` (render-time map read), falling
 * back to the default-ON policy while the async lookup is in flight. */
export function cachedContrastPref(
  prefs: Map<string, boolean>,
  hash: string,
): boolean {
  return prefs.get(hash) ?? DEFAULT_CONTRAST_ENABLED;
}

/** L2 sublabel's scope phrase for a wallpaper's variant count. */
export function contrastScopeLabel(variantCount: number): string {
  if (variantCount <= 0) return "no variants yet";
  return `applies to all ${variantCount} ${variantCount === 1 ? "variant" : "variants"}`;
}

export const UNAPPLIED_PREFIX = "unapplied:";

/** True when `hash` is a real 64-hex content hash — not the `unapplied:`
 * placeholder and not the `""` empty live-state sentinel. The runtime
 * `icons preference` accessor rejects anything else, so the GUI must never
 * shell it for a non-real hash (never-applied wallpaper: no store entry
 * can exist until the first set computes the content hash). */
export function isRealHash(hash: string): boolean {
  return /^[0-9a-f]{64}$/.test(hash);
}

/** Placeholder hash for never-applied files: no variants exist under an
 * unknown hash and it cannot be live — the placeholder can never equal a
 * real 64-hex hash or the "" empty state. */
export function unappliedPlaceholder(path: string): string {
  return `${UNAPPLIED_PREFIX}${path}`;
}

/** Whether an unmapped file deserves a real sha256: its path was imported
 * before (edited in place) or its size matches some known import
 * (byte-twin under a different name). Otherwise the placeholder is sound —
 * a different size can never share a sha256 with a known import. */
export function needsRealHash(
  file: SpineFileStat,
  mapping: Map<string, string>,
  knownSources: Set<string>,
  knownSizes: Set<number>,
): boolean {
  if (mapping.has(file.path)) return false;
  return knownSources.has(file.path) || knownSizes.has(file.size);
}

/** Re-resolve cached `unapplied:` placeholders against a fresh path→hash
 * mapping (built from current runtime metas). A placeholder means "never
 * applied when last scanned"; a later apply creates runtime metas WITHOUT
 * touching spine stats, so any fast path that reuses cached hashes must run
 * this first — otherwise the gallery (keyed by real content hash) shows zero
 * variants for the wallpaper forever, no matter how often it is selected.
 * Entries without a fresh mapping keep their placeholder. */
export function resolvePlaceholders(
  cached: { name: string; path: string; hash: string; mtime: string; size: number }[],
  mapping: Map<string, string>,
): { name: string; path: string; hash: string; mtime: string; size: number }[] {
  return cached.map((c) =>
    c.hash.startsWith(UNAPPLIED_PREFIX) && mapping.has(c.path)
      ? {
          name: c.name,
          path: c.path,
          hash: mapping.get(c.path) as string,
          mtime: c.mtime,
          size: c.size,
        }
      : c,
  );
}

export function buildModel(
  spine: RawWallpaper[],
  effects: RawEffectsEntry[],
  current: RawCurrent | null,
): SelectorModel {
  const variants = new Map<string, VariantEntry[]>();
  for (const entry of effects) {
    const list = variants.get(entry.sourceHash) ?? [];
    for (const v of entry.variants) {
      list.push({ name: v.name, group: v.group, path: v.path, live: false });
    }
    variants.set(entry.sourceHash, list);
  }
  const liveHash = current?.wallpaperHash ?? "";
  const livePath = current?.wallpaperPath ?? "";
  for (const list of variants.values()) {
    for (const v of list) {
      // A promoted variant is LIVE by source path (no file hashing needed):
      // `current.json` points at the exact effects-cache file that was set.
      // A live variant hash never equals a spine wallpaper hash (variant
      // bytes differ), so exactly one of wallpaper/variant is live.
      if (livePath !== "" && v.path === livePath) v.live = true;
    }
    // The live variant is pinned FIRST in its gallery (same behavior as the
    // main grid, which pins the live wallpaper / a live variant's parent);
    // everything else keeps the stable group+name order.
    list.sort((a, b) => {
      if (a.live !== b.live) return a.live ? -1 : 1;
      return a.group === b.group ? a.name.localeCompare(b.name) : a.group.localeCompare(b.group);
    });
  }
  const wallpapers = spine
    .filter((w) => isImageFile(w.name))
    .map((w) => ({
      name: w.name,
      path: w.path,
      hash: w.hash,
      variantCount: variants.get(w.hash)?.length ?? 0,
      live: w.hash === liveHash,
    }))
    .sort((a, b) => a.name.localeCompare(b.name));
  // Pin the live wallpaper (or a live variant's parent) first in the grid;
  // everything else keeps name order. No pin when nothing live matches.
  const pinHash = pinTargetHash(
    wallpapers.map((w) => w.hash),
    variants,
    liveHash,
    livePath,
  );
  if (pinHash !== null) {
    const idx = wallpapers.findIndex((w) => w.hash === pinHash);
    if (idx > 0) {
      const [pinned] = wallpapers.splice(idx, 1);
      wallpapers.unshift(pinned);
    }
  }
  return { wallpapers, variants, liveWallpaperHash: liveHash, liveVariantPath: livePath };
}

export function variantsFor(model: SelectorModel, wallpaperHash: string): VariantEntry[] {
  return model.variants.get(wallpaperHash) ?? [];
}

/** Hash of the wallpaper to pin first in the grid: the live wallpaper
 * itself, or — when a variant is live — its parent (variants are keyed by
 * parent hash, so the parent is found through the live variant's path).
 * Null when nothing live matches (absent state, stale hash, pruned
 * variants) — plain name order then. Ordering only; the `live` flags are
 * untouched (a live variant keeps its own badge, the parent does not gain
 * one). */
export function pinTargetHash(
  wallpaperHashes: string[],
  variants: Map<string, VariantEntry[]>,
  liveHash: string,
  liveVariantPath: string,
): string | null {
  if (liveHash !== "" && wallpaperHashes.includes(liveHash)) return liveHash;
  if (liveVariantPath !== "") {
    for (const [sourceHash, list] of variants) {
      if (list.some((v) => v.path === liveVariantPath)) return sourceHash;
    }
  }
  return null;
}

export function filterWallpapers(
  wallpapers: WallpaperEntry[],
  query: string,
): WallpaperEntry[] {
  const q = query.trim().toLowerCase();
  if (q === "") return wallpapers;
  return wallpapers.filter((w) => w.name.toLowerCase().includes(q));
}

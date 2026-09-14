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

export const UNAPPLIED_PREFIX = "unapplied:";

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
  for (const list of variants.values()) {
    list.sort((a, b) =>
      a.group === b.group ? a.name.localeCompare(b.name) : a.group.localeCompare(b.group),
    );
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
  return { wallpapers, variants, liveWallpaperHash: liveHash, liveVariantPath: livePath };
}

export function variantsFor(model: SelectorModel, wallpaperHash: string): VariantEntry[] {
  return model.variants.get(wallpaperHash) ?? [];
}

export function filterWallpapers(
  wallpapers: WallpaperEntry[],
  query: string,
): WallpaperEntry[] {
  const q = query.trim().toLowerCase();
  if (q === "") return wallpapers;
  return wallpapers.filter((w) => w.name.toLowerCase().includes(q));
}

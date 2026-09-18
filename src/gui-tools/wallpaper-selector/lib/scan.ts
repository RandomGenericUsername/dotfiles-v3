// Filesystem scan for the wallpaper selector (GJS side).
//
// Reads the three sources and shapes them into the pure `model.ts` inputs:
//   - spine wallpapers: `<install>/wallpapers/` (inputs only, read-only)
//   - variant gallery:  `$XDG_STATE_HOME/dotfiles/cache/effects/*/meta.json`
//     (`source_wallpaper_hash` links each effects entry to its parent)
//   - live state:       `$XDG_STATE_HOME/dotfiles/current.json`
// Thumbnails are NOT produced here (see `thumbnails.ts`).

import GdkPixbuf from "gi://GdkPixbuf?version=2.0";
import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";
import {
  buildModel,
  isImageFile,
  mapSpineHashes,
  needsRealHash,
  resolvePlaceholders,
  unappliedPlaceholder,
  UNAPPLIED_PREFIX,
  stemOf,
  type RawCurrent,
  type RawEffectsEntry,
  type RawVariant,
  type RawWallpaper,
  type SelectorModel,
  type SpineFileStat,
  type WallpaperCacheMeta,
} from "./model";
import { thumbnailCacheDir } from "./thumbnails";

export function spineHome(): string {
  return `${GLib.get_user_data_dir()}/dotfiles`;
}

export function stateHome(): string {
  return `${GLib.get_user_state_dir()}/dotfiles`;
}

export function spineWallpapersDir(): string {
  return `${spineHome()}/wallpapers`;
}

export function sha256File(path: string): string {
  const [ok, bytes] = GLib.file_get_contents(path);
  if (!ok || bytes === null) throw new Error(`cannot read ${path}`);
  return GLib.compute_checksum_for_bytes(
    GLib.ChecksumType.SHA256,
    new GLib.Bytes(bytes),
  );
}

function listDirNames(dir: string): string[] {
  const enumerator = Gio.File.new_for_path(dir).enumerate_children(
    "standard::name,standard::type",
    Gio.FileQueryInfoFlags.NONE,
    null,
  );
  const names: string[] = [];
  let info = enumerator.next_file(null);
  while (info !== null) {
    if (info.get_file_type() !== Gio.FileType.DIRECTORY) names.push(info.get_name());
    info = enumerator.next_file(null);
  }
  return names;
}

function listFilesRecursive(dir: string): string[] {
  const out: string[] = [];
  const walk = (current: string) => {
    const enumerator = Gio.File.new_for_path(current).enumerate_children(
      "standard::name,standard::type",
      Gio.FileQueryInfoFlags.NONE,
      null,
    );
    let info = enumerator.next_file(null);
    while (info !== null) {
      const child = `${current}/${info.get_name()}`;
      if (info.get_file_type() === Gio.FileType.DIRECTORY) walk(child);
      else out.push(child);
      info = enumerator.next_file(null);
    }
  };
  walk(dir);
  return out;
}

/** Spine wallpapers with content hashes (skips unreadable files loudly-logged). */
export function scanSpine(dir?: string): RawWallpaper[] {
  const root = dir ?? spineWallpapersDir();
  const out: RawWallpaper[] = [];
  let names: string[];
  try {
    names = listDirNames(root);
  } catch (error) {
    console.error(`wallpaper-selector: cannot list ${root}: ${error}`);
    return out;
  }
  for (const name of names.sort()) {
    if (!isImageFile(name)) continue;
    const path = `${root}/${name}`;
    try {
      // Header-only format probe: the spine may hold extension-masquerading
      // junk (e.g. a stray test.png) that would otherwise decode-fail later.
      // NOTE: GJS marshals this as [format|null, width, height], never null.
      const probe = GdkPixbuf.Pixbuf.get_file_info(path);
      if (probe === null || probe[0] === null) {
        console.error(`wallpaper-selector: unsupported image format, skipping ${path}`);
        continue;
      }
      out.push({ name, path, hash: sha256File(path) });
    } catch (error) {
      console.error(`wallpaper-selector: cannot hash ${path}: ${error}`);
    }
  }
  return out;
}

/** Top-level effects entries: name + mtime only (write-once dirs — an
 * unchanged name+mtime means unchanged contents, no recursive walk). */
export interface EffectsEntryStat {
  name: string;
  dir: string;
  mtime: string;
}

export function listEffectsEntries(root?: string): EffectsEntryStat[] {
  const effectsRoot = root ?? `${stateHome()}/cache/effects`;
  const out: EffectsEntryStat[] = [];
  try {
    const enumerator = Gio.File.new_for_path(effectsRoot).enumerate_children(
      "standard::name,standard::type,time::modified",
      Gio.FileQueryInfoFlags.NONE,
      null,
    );
    let info = enumerator.next_file(null);
    while (info !== null) {
      if (info.get_file_type() === Gio.FileType.DIRECTORY) {
        out.push({
          name: info.get_name(),
          dir: `${effectsRoot}/${info.get_name()}`,
          mtime: info.get_modification_date_time()?.format_iso8601() ?? "",
        });
      }
      info = enumerator.next_file(null);
    }
  } catch {
    return out; // no effects cache yet — zero variants, not an error
  }
  return out.sort((a, b) => (a.name < b.name ? -1 : 1));
}

/** Scan ONE effects entry dir (meta + recursive file walk). */
export function scanEffectsEntry(entryDir: string): RawEffectsEntry | null {
  let meta: Record<string, unknown>;
  try {
    const [ok, bytes] = GLib.file_get_contents(`${entryDir}/meta.json`);
    if (!ok || bytes === null) return null;
    meta = JSON.parse(new TextDecoder().decode(bytes));
  } catch {
    return null;
  }
  const sourceHash = meta["source_wallpaper_hash"];
  if (typeof sourceHash !== "string") return null;
  const variants: RawVariant[] = [];
  let files: string[];
  try {
    files = listFilesRecursive(entryDir);
  } catch {
    return null;
  }
  for (const file of files.sort()) {
    const base = file.slice(entryDir.length + 1);
    if (base === "meta.json") continue;
    const filename = base.slice(base.lastIndexOf("/") + 1);
    if (!isImageFile(filename)) continue;
    const parent = base.includes("/") ? base.slice(0, base.lastIndexOf("/")) : "";
    const group = parent.includes("/") ? parent.slice(parent.lastIndexOf("/") + 1) : parent;
    variants.push({ name: stemOf(filename), group, path: file });
  }
  return { sourceHash, variants };
}

/** Variant gallery grouped by parent wallpaper hash (never generates anything). */
export function scanEffects(root?: string): RawEffectsEntry[] {
  const out: RawEffectsEntry[] = [];
  for (const e of listEffectsEntries(root)) {
    const entry = scanEffectsEntry(e.dir);
    if (entry !== null) out.push(entry);
  }
  return out;
}

/** Live state from `current.json` (null when the runtime never ran).
 *
 * Wire shape note: `WallpaperEntry.content_hash` serializes as
 * `wallpaper.hash` (`json_state_repository.py`) — read the wire key, not
 * the dataclass field.
 */
export function readCurrent(path?: string): RawCurrent | null {
  const currentPath = path ?? `${stateHome()}/current.json`;
  try {
    const [ok, bytes] = GLib.file_get_contents(currentPath);
    if (!ok || bytes === null) return null;
    const data = JSON.parse(new TextDecoder().decode(bytes));
    const wallpaper = data?.wallpaper;
    if (typeof wallpaper?.hash !== "string") return null;
    return {
      wallpaperHash: wallpaper.hash,
      wallpaperPath: typeof wallpaper.source_path === "string" ? wallpaper.source_path : "",
    };
  } catch {
    return null;
  }
}

/** Full model: scan all three sources and shape them (re-run on every open). */
export function loadModel(): SelectorModel {
  return buildModel(scanSpine(), scanEffects(), readCurrent());
}

// ── Zero-hash fast scan + incremental model cache ───────────────────────
// Warm opens validate top-level stats only (~10-50ms) and reuse hashes plus
// variant entries; only new/changed layers are re-read. The cache doc is
// best-effort (never fatal) and versioned — bump on shape changes.

function statOne(path: string): { mtime: string; size: number } | null {
  try {
    const info = Gio.File.new_for_path(path).query_info(
      "time::modified,standard::size",
      Gio.FileQueryInfoFlags.NONE,
      null,
    );
    return {
      mtime: info.get_modification_date_time()?.format_iso8601() ?? "",
      size: info.get_size(),
    };
  } catch {
    return null;
  }
}

export interface SpineStat extends SpineFileStat {
  mtime: string;
}

/** Magic-byte image sniff (16-byte header read). Replaces
 * GdkPixbuf.get_file_info here: the pixbuf probe costs ~50ms PER FILE
 * (loader sniffing), this costs microseconds and catches the same
 * extension-masquerading junk (e.g. stray test.png). */
function hasImageMagic(path: string): boolean {
  try {
    const stream = Gio.File.new_for_path(path).read(null);
    let raw: number[] = [];
    try {
      const bytes = stream.read_bytes(16, null);
      raw = Array.from(bytes.get_data() ?? []);
    } finally {
      stream.close(null);
    }
    if (raw.length < 4) return false;
    if (raw[0] === 0x89 && raw[1] === 0x50 && raw[2] === 0x4e && raw[3] === 0x47) return true;
    if (raw[0] === 0xff && raw[1] === 0xd8 && raw[2] === 0xff) return true;
    if (raw[0] === 0x47 && raw[1] === 0x49 && raw[2] === 0x46 && raw[3] === 0x38) return true;
    if (raw[0] === 0x42 && raw[1] === 0x4d) return true;
    if (
      raw.length >= 12 &&
      raw[0] === 0x52 && raw[1] === 0x49 && raw[2] === 0x46 && raw[3] === 0x46 &&
      raw[8] === 0x57 && raw[9] === 0x45 && raw[10] === 0x42 && raw[11] === 0x50
    ) {
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

/** Stat-only spine listing in ONE enumeration (no per-file roundtrips, no
 * byte reads): names + mtime + size + magic sniff. ~5ms for the spine. */
export function statSpineFiles(dir?: string): SpineStat[] {
  const root = dir ?? spineWallpapersDir();
  const out: SpineStat[] = [];
  try {
    const enumerator = Gio.File.new_for_path(root).enumerate_children(
      "standard::name,standard::type,standard::size,time::modified",
      Gio.FileQueryInfoFlags.NONE,
      null,
    );
    let info = enumerator.next_file(null);
    while (info !== null) {
      if (info.get_file_type() !== Gio.FileType.DIRECTORY) {
        const name = info.get_name();
        if (isImageFile(name)) {
          const path = `${root}/${name}`;
          if (!hasImageMagic(path)) {
            console.error(`wallpaper-selector: unsupported image format, skipping ${path}`);
          } else {
            out.push({
              name,
              path,
              mtime: info.get_modification_date_time()?.format_iso8601() ?? "",
              size: info.get_size(),
            });
          }
        }
      }
      info = enumerator.next_file(null);
    }
  } catch (error) {
    console.error(`wallpaper-selector: cannot list ${root}: ${error}`);
    return out;
  }
  return out.sort((a, b) => (a.name < b.name ? -1 : 1));
}

/** Runtime's own wallpaper cache metas: {content_hash, source_path} + size. */
export function scanWallpaperMetas(root?: string): WallpaperCacheMeta[] {
  const cacheRoot = root ?? `${stateHome()}/cache/wallpapers`;
  const out: WallpaperCacheMeta[] = [];
  let entries: string[];
  try {
    const enumerator = Gio.File.new_for_path(cacheRoot).enumerate_children(
      "standard::name,standard::type",
      Gio.FileQueryInfoFlags.NONE,
      null,
    );
    entries = [];
    let info = enumerator.next_file(null);
    while (info !== null) {
      if (info.get_file_type() === Gio.FileType.DIRECTORY) {
        entries.push(`${cacheRoot}/${info.get_name()}`);
      }
      info = enumerator.next_file(null);
    }
  } catch {
    return out;
  }
  for (const entryDir of entries.sort()) {
    try {
      const [ok, bytes] = GLib.file_get_contents(`${entryDir}/meta.json`);
      if (!ok || bytes === null) continue;
      const meta = JSON.parse(new TextDecoder().decode(bytes));
      if (typeof meta["content_hash"] !== "string") continue;
      if (typeof meta["source_path"] !== "string") continue;
      const st = statOne(`${entryDir}/wallpaper.png`);
      if (st === null) continue;
      out.push({ hash: meta["content_hash"], sourcePath: meta["source_path"], size: st.size });
    } catch {
      continue;
    }
  }
  return out;
}

/** Zero-hash spine scan: map via runtime metas (sourcePath+size); byte-twin
 * files (same bytes, different name — e.g. default.png ≡ animated.png) and
 * edited-in-place files resolve via size-prefiltered sha256 (size ∉ known
 * sizes ⟹ no hash can match, so unhashed files safely take the `unapplied:`
 * placeholder: no variants exist under an unknown hash, cannot be live —
 * the placeholder can never equal a real 64-hex hash or "" empty state). */
export function scanSpineFast(
  dir?: string,
  metas?: WallpaperCacheMeta[],
): { wallpapers: RawWallpaper[]; hashedFallback: number } {
  const stats = statSpineFiles(dir);
  const metaList = metas ?? scanWallpaperMetas();
  const mapping = mapSpineHashes(stats, metaList);
  const knownSources = new Set(metaList.map((m) => m.sourcePath));
  const knownSizes = new Set(metaList.map((m) => m.size));
  const knownHashes = new Set(metaList.map((m) => m.hash));
  const wallpapers: RawWallpaper[] = [];
  let hashedFallback = 0;
  for (const f of stats) {
    const hit = mapping.get(f.path);
    if (hit !== undefined) {
      wallpapers.push({ name: f.name, path: f.path, hash: hit });
      continue;
    }
    if (needsRealHash(f, mapping, knownSources, knownSizes)) {
      try {
        const real = sha256File(f.path);
        hashedFallback++;
        if (knownHashes.has(real)) {
          wallpapers.push({ name: f.name, path: f.path, hash: real });
          continue;
        }
      } catch (error) {
        console.error(`wallpaper-selector: cannot hash ${f.path}: ${error}`);
        continue;
      }
    }
    wallpapers.push({ name: f.name, path: f.path, hash: unappliedPlaceholder(f.path) });
  }
  return { wallpapers, hashedFallback };
}

export interface CachedEffectsEntry extends RawEffectsEntry {
  entryName: string;
  entryMtime: string;
}

export interface ModelCacheDoc {
  version: 1;
  spine: { name: string; path: string; hash: string; mtime: string; size: number }[];
  effects: CachedEffectsEntry[];
  currentMtime: string;
  current: RawCurrent | null;
}

const MODEL_CACHE_NAME = "model-cache.json";

function readModelCache(path: string): ModelCacheDoc | null {
  try {
    const [ok, bytes] = GLib.file_get_contents(path);
    if (!ok || bytes === null) return null;
    const data = JSON.parse(new TextDecoder().decode(bytes));
    if (data?.version !== 1 || !Array.isArray(data?.spine) || !Array.isArray(data?.effects)) {
      return null;
    }
    return data as ModelCacheDoc;
  } catch {
    return null;
  }
}

/** Smart model, incremental by layer:
 * - spine: stat-validate cached hashes; remap only new/changed files
 *   (zero-hash via runtime metas, sha256 fallback, unapplied placeholder);
 * - effects: entry dirs are write-once — reuse entries whose name+mtime
 *   match, scan ONLY new/changed entry dirs (no recursive walk otherwise);
 * - current.json: mtime match reuses, else one tiny re-read.
 * Warm validation is top-level stats only (~100ms). */
export function loadModelSmart(cachePath?: string): SelectorModel {
  const cacheFile = cachePath ?? `${thumbnailCacheDir()}/${MODEL_CACHE_NAME}`;
  const prev = readModelCache(cacheFile);

  // ── spine layer ──
  const spineStats = statSpineFiles();
  let wallpapers: RawWallpaper[];
  let spineCache: ModelCacheDoc["spine"];
  if (prev !== null) {
    const cachedByPath = new Map(prev.spine.map((c) => [c.path, c]));
    const freshByPath = new Map(spineStats.map((f) => [f.path, f]));
    let intact = prev.spine.length === spineStats.length;
    if (intact) {
      for (const c of prev.spine) {
        const f = freshByPath.get(c.path);
        if (f === undefined || f.name !== c.name || f.mtime !== c.mtime || f.size !== c.size) {
          intact = false;
          break;
        }
      }
    }
    if (intact) {
      wallpapers = prev.spine.map((c) => ({ name: c.name, path: c.path, hash: c.hash }));
      spineCache = prev.spine;
      // A cached `unapplied:` placeholder pins forever under this fast path:
      // applying a wallpaper creates runtime metas WITHOUT touching spine
      // stats, so intact stays true and the gallery (keyed by real hash)
      // would show zero variants forever. Re-resolve placeholders against
      // fresh metas (cheap, and only when a placeholder is actually cached).
      if (spineCache.some((c) => c.hash.startsWith(UNAPPLIED_PREFIX))) {
        const mapping = mapSpineHashes(spineStats, scanWallpaperMetas());
        const fixed = resolvePlaceholders(spineCache, mapping);
        spineCache = fixed;
        wallpapers = fixed.map((c) => ({ name: c.name, path: c.path, hash: c.hash }));
      }
    } else {
      const freshMetas = scanWallpaperMetas();
      const mapping = mapSpineHashes(spineStats, freshMetas);
      const knownSources = new Set(freshMetas.map((m) => m.sourcePath));
      const knownSizes = new Set(freshMetas.map((m) => m.size));
      const knownHashes = new Set(freshMetas.map((m) => m.hash));
      wallpapers = [];
      spineCache = [];
      for (const f of spineStats) {
        const old = cachedByPath.get(f.path);
        if (
          old !== undefined &&
          old.name === f.name &&
          old.mtime === f.mtime &&
          old.size === f.size &&
          // A cached placeholder must not pin here either: the file may
          // have been applied since it was cached (runtime metas exist
          // without spine stat changes) — fall through to the fresh
          // mapping below instead of reusing the stale placeholder.
          !old.hash.startsWith(UNAPPLIED_PREFIX)
        ) {
          wallpapers.push({ name: old.name, path: old.path, hash: old.hash });
          spineCache.push(old);
          continue;
        }
        const hit = mapping.get(f.path);
        let hash: string | null = hit ?? null;
        if (hash === null && needsRealHash(f, mapping, knownSources, knownSizes)) {
          try {
            const real = sha256File(f.path);
            console.log(`wallpaper-selector: re-hashed ${f.name} (size changed since import)`);
            if (knownHashes.has(real)) hash = real;
          } catch (error) {
            console.error(`wallpaper-selector: cannot hash ${f.path}: ${error}`);
            continue;
          }
        }
        if (hash === null) hash = unappliedPlaceholder(f.path);
        wallpapers.push({ name: f.name, path: f.path, hash });
        spineCache.push({ name: f.name, path: f.path, hash, mtime: f.mtime, size: f.size });
      }
    }
  } else {
    const scanned = scanSpineFast();
    wallpapers = scanned.wallpapers;
    const statByPath = new Map(spineStats.map((f) => [f.path, f]));
    spineCache = [];
    for (const item of wallpapers) {
      const st = statByPath.get(item.path);
      if (st !== undefined) {
        spineCache.push({
          name: item.name,
          path: item.path,
          hash: item.hash,
          mtime: st.mtime,
          size: st.size,
        });
      }
    }
  }

  // ── effects layer (entry-diff; write-once dirs, no recursion on hit) ──
  const entryStats = listEffectsEntries();
  let effects: CachedEffectsEntry[];
  if (prev !== null) {
    const cachedByName = new Map(prev.effects.map((e) => [e.entryName, e]));
    let intact = prev.effects.length === entryStats.length;
    if (intact) {
      for (const s of entryStats) {
        const c = cachedByName.get(s.name);
        if (c === undefined || c.entryMtime !== s.mtime) {
          intact = false;
          break;
        }
      }
    }
    if (intact) {
      effects = prev.effects;
    } else {
      effects = [];
      for (const s of entryStats) {
        const c = cachedByName.get(s.name);
        if (c !== undefined && c.entryMtime === s.mtime) {
          effects.push(c);
          continue;
        }
        const scanned = scanEffectsEntry(s.dir);
        if (scanned !== null) {
          console.log(`wallpaper-selector: scanned new effects entry ${s.name}`);
          effects.push({ ...scanned, entryName: s.name, entryMtime: s.mtime });
        }
      }
    }
  } else {
    effects = [];
    for (const s of entryStats) {
      const scanned = scanEffectsEntry(s.dir);
      if (scanned !== null) effects.push({ ...scanned, entryName: s.name, entryMtime: s.mtime });
    }
  }

  // ── current layer ──
  const cst = statOne(`${stateHome()}/current.json`);
  const currentMtime = cst?.mtime ?? "";
  let live: RawCurrent | null;
  if (prev !== null && prev.currentMtime === currentMtime) {
    live = prev.current;
  } else {
    live = readCurrent();
  }

  try {
    const doc: ModelCacheDoc = {
      version: 1,
      spine: spineCache,
      effects,
      currentMtime,
      current: live,
    };
    GLib.file_set_contents(cacheFile, JSON.stringify(doc));
  } catch (error) {
    console.error(`wallpaper-selector: cannot write model cache: ${error}`);
  }
  return buildModel(wallpapers, effects, live);
}

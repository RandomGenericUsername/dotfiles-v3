// Disk-cached thumbnails (GJS side).
//
// Full-resolution wallpapers (and their variants) are far too heavy to
// decode on every open, and the runtime owns no thumbnails — so the
// selector keeps its own cache under the user cache dir. A cache entry is
// keyed by `sha256(path + mtime + size)`: content changes under a stable
// path (re-provisioned tarball) invalidate naturally, renames just miss.

import Gdk from "gi://Gdk?version=4.0";
import GdkPixbuf from "gi://GdkPixbuf?version=2.0";
import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";

export const THUMB_MAX_DIM = 360;

// JPEG cache: photos encode ~4x faster than PNG and decode faster too.
// Wallpapers are opaque photographs, so the missing alpha is irrelevant.
const CACHE_FORMAT = "jpeg";
const CACHE_EXT = "jpg";
const CACHE_QUALITY = "82";

const memoryCache = new Map<string, Gdk.Texture>();

export function thumbnailCacheDir(): string {
  const dir = `${GLib.get_user_cache_dir()}/dotfiles-wallpaper-selector`;
  GLib.mkdir_with_parents(dir, 0o755);
  return dir;
}

function cacheKey(sourcePath: string): string | null {
  try {
    const info = Gio.File.new_for_path(sourcePath).query_info(
      "time::modified,standard::size",
      Gio.FileQueryInfoFlags.NONE,
      null,
    );
    const mtime = info.get_modification_date_time()?.format_iso8601() ?? "";
    const stamp = `${sourcePath}\0${mtime}\0${info.get_size()}`;
    return GLib.compute_checksum_for_string(GLib.ChecksumType.SHA256, stamp);
  } catch {
    return null;
  }
}

function cachedPath(sourcePath: string, maxDim: number): string | null {
  const key = cacheKey(sourcePath);
  return key === null ? null : `${thumbnailCacheDir()}/${key}-${maxDim}.${CACHE_EXT}`;
}

function textureFromPixbuf(pixbuf: GdkPixbuf.Pixbuf): Gdk.Texture {
  return Gdk.Texture.new_for_pixbuf(pixbuf);
}

function remember(memKey: string, texture: Gdk.Texture): Gdk.Texture {
  memoryCache.set(memKey, texture);
  return texture;
}

/** Fast path: disk-cache hit → texture, WITHOUT decoding the source.
 * Returns null on miss (the caller decodes off the critical path). */
export function cachedTexture(
  sourcePath: string,
  maxDim: number = THUMB_MAX_DIM,
): Gdk.Texture | null {
  const memKey = `${sourcePath}:${maxDim}`;
  const mem = memoryCache.get(memKey);
  if (mem !== undefined) return mem;
  try {
    const cached = cachedPath(sourcePath, maxDim);
    if (cached !== null && GLib.file_test(cached, GLib.FileTest.EXISTS)) {
      return remember(memKey, textureFromPixbuf(GdkPixbuf.Pixbuf.new_from_file(cached)));
    }
  } catch (error) {
    console.error(`wallpaper-selector: cannot read thumb cache for ${sourcePath}: ${error}`);
  }
  return null;
}

/** Slow path: full decode + scale + cache write (call off the UI thread —
 * from a GLib idle pump, never in a render loop). Null when undecodable. */
export function generateThumb(
  sourcePath: string,
  maxDim: number = THUMB_MAX_DIM,
): Gdk.Texture | null {
  const memKey = `${sourcePath}:${maxDim}`;
  const mem = memoryCache.get(memKey);
  if (mem !== undefined) return mem;
  try {
    const pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(sourcePath, maxDim, maxDim);
    const cached = cachedPath(sourcePath, maxDim);
    if (cached !== null) {
      try {
        pixbuf.savev(cached, CACHE_FORMAT, ["quality"], [CACHE_QUALITY]);
      } catch (error) {
        console.error(`wallpaper-selector: cannot write thumb cache ${cached}: ${error}`);
      }
    }
    return remember(memKey, textureFromPixbuf(pixbuf));
  } catch (error) {
    console.error(`wallpaper-selector: cannot thumbnail ${sourcePath}: ${error}`);
    return null;
  }
}

/** Sync convenience (single images: breadcrumb, first paint). Grid cards
 * MUST use the async pump in the window (cachedTexture + generateThumb),
 * never this — a cold cache decodes ~5s for the full spine. */
export function thumbTexture(sourcePath: string, maxDim: number = THUMB_MAX_DIM): Gdk.Texture | null {
  return cachedTexture(sourcePath, maxDim) ?? generateThumb(sourcePath, maxDim);
}

/** Drop in-memory textures (disk cache survives); called after rescan. */
export function clearMemoryCache(): void {
  memoryCache.clear();
}

// History document access + clipboard copy-back (the Gio/GLib seam).
//
// Reads are the GUI's hydration source (design D7: the overlay owns no state).
// Favorite/delete are user-initiated, rare mutations written atomically via
// GLib.file_set_contents; the daemon is the frequent writer and re-reads the
// document on every operation, so the window for a lost update is a
// user-click-scale event. See design D4 for the single-writer trade-off.

import GLib from "gi://GLib?version=2.0"
import Gio from "gi://Gio?version=2.0"
import { parseHistory, type ClipboardItem } from "./clipboard-types"

const HISTORY_VERSION = 1

export function historyPath(): string {
  const stateHome = GLib.getenv("XDG_STATE_HOME") ?? `${GLib.get_home_dir()}/.local/state`
  return `${stateHome}/hypr-pano/history.json`
}

/** Read + parse the history document; empty when absent or unreadable. */
export function readHistory(): ClipboardItem[] {
  const path = historyPath()
  if (!GLib.file_test(path, GLib.FileTest.EXISTS)) return []
  try {
    const [ok, bytes] = GLib.file_get_contents(path)
    if (!ok || bytes === null) return []
    return parseHistory(new TextDecoder().decode(bytes))
  } catch (error) {
    console.error(`hypr-pano: cannot read history: ${error}`)
    return []
  }
}

function serialize(items: ClipboardItem[]): string {
  return JSON.stringify({
    version: HISTORY_VERSION,
    items: items.map((item) => ({
      hash: item.hash,
      kind: item.kind,
      timestamp: item.timestamp,
      favorite: item.favorite,
      ...(item.text !== null ? { text: item.text } : {}),
      ...(item.path !== null ? { path: item.path } : {}),
    })),
  })
}

/** Atomically replace the history document (temp file + rename). */
function writeHistory(items: ClipboardItem[]): void {
  try {
    const dir = GLib.path_get_dirname(historyPath())
    GLib.mkdir_with_parents(dir, 0o755)
    GLib.file_set_contents(historyPath(), serialize(items))
  } catch (error) {
    console.error(`hypr-pano: cannot write history: ${error}`)
  }
}

/** Toggle an item's favorite flag and persist it. */
export function toggleFavorite(hash: string): void {
  const items = readHistory()
  const next = items.map((item) =>
    item.hash === hash ? { ...item, favorite: !item.favorite } : item,
  )
  writeHistory(next)
}

/** Remove an item (and its cached image) and persist it. */
export function deleteItem(hash: string): void {
  const items = readHistory()
  const target = items.find((item) => item.hash === hash)
  if (target === undefined) return
  writeHistory(items.filter((item) => item.hash !== hash))
  if (target.path !== null) {
    try {
      Gio.File.new_for_path(target.path).delete(null)
    } catch (error) {
      console.error(`hypr-pano: cannot remove image ${target.path}: ${error}`)
    }
  }
}

/** Wipe the whole history and delete every cached image it referenced. */
export function clearHistory(): void {
  const items = readHistory()
  writeHistory([])
  for (const item of items) {
    if (item.path === null) continue
    try {
      Gio.File.new_for_path(item.path).delete(null)
    } catch (error) {
      console.error(`hypr-pano: cannot remove image ${item.path}: ${error}`)
    }
  }
}

/** Put an item back on the system clipboard with the right representation. */
export function copyItem(item: ClipboardItem): Promise<void> {
  if (item.kind === "image" && item.path !== null) {
    try {
      const [, bytes] = GLib.file_get_contents(item.path)
      if (bytes === null) {
        return Promise.reject(new Error(`image not found: ${item.path}`))
      }
      return spawnWithStdin(["wl-copy", "--type", "image/png"], bytes)
    } catch (error) {
      return Promise.reject(error)
    }
  }
  return spawnWithStdin(["wl-copy"], new TextEncoder().encode(item.text ?? ""))
}

// `wl-copy` writes nothing to stdout and keeps the selection alive, so AGS's
// `execAsync` (which decodes stdout) fails with "Argument result may not be
// null". Spawn it directly and feed stdin instead.
function spawnWithStdin(argv: string[], bytes: Uint8Array): Promise<void> {
  return new Promise((resolve, reject) => {
    try {
      const proc = Gio.Subprocess.new(argv, Gio.SubprocessFlags.STDIN_PIPE)
      const stdin = proc.get_stdin_pipe()
      stdin.write_bytes(new GLib.Bytes(bytes), null)
      stdin.close(null)
      proc.wait_async(null, (_src: unknown, res: Gio.AsyncResult) => {
        try {
          proc.wait_finish(res)
          resolve()
        } catch (error) {
          reject(error)
        }
      })
    } catch (error) {
      reject(error)
    }
  })
}

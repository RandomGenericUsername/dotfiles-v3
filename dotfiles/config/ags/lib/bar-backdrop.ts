import GLib from "gi://GLib?version=2.0"

export type BarBackdrop = "light" | "dark" | null

/** Pure reader for schema-version-2 current.json monitor appearance. */
export function parseBarBackdrop(raw: string, connector: string | null): BarBackdrop {
  if (!connector) return null
  try {
    const state: unknown = JSON.parse(raw)
    if (!state || typeof state !== "object") return null
    const root = state as Record<string, unknown>
    if (root.schema_version !== 2 || !root.monitors || typeof root.monitors !== "object") {
      return null
    }
    const monitor = (root.monitors as Record<string, unknown>)[connector]
    if (!monitor || typeof monitor !== "object") return null
    const value = (monitor as Record<string, unknown>).bar_backdrop
    return value === "light" || value === "dark" ? value : null
  } catch {
    return null
  }
}

/** Read the active runtime state once at bar construction; any failure is unknown. */
export function readBarBackdrop(connector: string | null): BarBackdrop {
  const stateDir = GLib.getenv("XDG_STATE_HOME") || `${GLib.get_home_dir()}/.local/state`
  const statePath = `${stateDir}/dotfiles/current.json`
  try {
    const [ok, bytes] = GLib.file_get_contents(statePath)
    if (!ok) return null
    return parseBarBackdrop(new TextDecoder().decode(bytes), connector)
  } catch {
    return null
  }
}

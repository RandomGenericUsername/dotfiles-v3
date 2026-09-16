// Capture-tool icon resolver — consumes the SAME rendered-icon pipeline as
// the bar and hypr-pano.
//
// Templates live in the repo (`dotfiles/assets/icon-templates/capture-tool/`),
// are mapped in `icon-mappings/icons.yaml`, rendered by ITR into
// `$XDG_STATE_HOME/dotfiles/current/icons/`, and advertised through an AGS
// manifest JSON. This module resolves a `(group, variant)` to an on-disk SVG
// path exactly like the sibling `lib/icon-registry.ts` files, so a palette
// change restyles this window too.
//
// Manifest lookup prefers the capture instance's own manifest
// (`~/.config/ags-capture/icons.json`, provisioned by the compositor_configs
// story) and falls back to the shared bar manifest (`~/.config/ags/icons.json`).
// A missing manifest or missing render yields null — callers keep a text label
// fallback — never a crash.

import GLib from "gi://GLib?version=2.0"

interface Variant {
  name: string
  output: string
}

interface IconGroup {
  variants: Variant[]
}

type IconManifest = Record<string, IconGroup>

const RUNTIME_ICONS_DIR = `${
  GLib.getenv("XDG_STATE_HOME") || `${GLib.get_home_dir()}/.local/state`
}/dotfiles/current/icons`

const MANIFEST_PATHS = [
  `${GLib.get_user_config_dir()}/ags-capture/icons.json`,
  `${GLib.get_user_config_dir()}/ags/icons.json`,
]

let manifest: IconManifest | null = null

function loadManifest(): IconManifest {
  if (manifest !== null) return manifest
  let fallback: IconManifest = {}
  for (const path of MANIFEST_PATHS) {
    try {
      const [ok, bytes] = GLib.file_get_contents(path)
      if (!ok || bytes === null) continue
      const parsed = JSON.parse(new TextDecoder().decode(bytes)) as IconManifest
      // Prefer a manifest that actually advertises the capture-tool group.
      if (parsed["capture-tool"] !== undefined) {
        manifest = parsed
        return manifest
      }
      if (Object.keys(fallback).length === 0) fallback = parsed
    } catch (error) {
      console.error(`capture-tool: cannot read icon manifest ${path}: ${error}`)
    }
  }
  manifest = fallback
  return manifest
}

export const registry = {
  /** Absolute path to the rendered SVG for `group`/`variant`, or null. */
  resolve(group: string, variant: string): string | null {
    const groupData = loadManifest()[group]
    if (groupData === undefined) return null
    const entry = groupData.variants?.find((candidate) => candidate.name === variant)
    if (entry === undefined) return null
    const path = `${RUNTIME_ICONS_DIR}/${entry.output}`
    return GLib.file_test(path, GLib.FileTest.EXISTS) ? path : null
  },

  /** Force a manifest re-read (after provisioning regenerates icons.json). */
  reload(): void {
    manifest = null
  },
}

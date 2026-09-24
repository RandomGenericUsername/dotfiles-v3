import GLib from "gi://GLib?version=2.0"

interface IconVariant {
  name: string
  output: string
}

interface IconGroup {
  variants?: IconVariant[]
}

type IconManifest = Record<string, IconGroup>

const ICONS_DIR = `${GLib.getenv("XDG_STATE_HOME") || `${GLib.get_home_dir()}/.local/state`}/dotfiles/current/icons`
const MANIFEST_PATH = `${GLib.get_user_config_dir()}/ags/icons.json`

let manifest: IconManifest | null = null

function loadManifest(): IconManifest {
  if (manifest !== null) return manifest
  try {
    const [ok, bytes] = GLib.file_get_contents(MANIFEST_PATH)
    manifest = ok && bytes !== null
      ? JSON.parse(new TextDecoder().decode(bytes)) as IconManifest
      : {}
  } catch (error) {
    console.error(`notifications: cannot read icon manifest: ${error}`)
    manifest = {}
  }
  return manifest
}

/** Resolve an icon from the palette-rendered current icon set. */
export function resolveIcon(group: string, variant: string): string | null {
  const entry = loadManifest()[group]?.variants?.find((item) => item.name === variant)
  if (entry === undefined) return null
  const path = `${ICONS_DIR}/${entry.output}`
  return GLib.file_test(path, GLib.FileTest.EXISTS) ? path : null
}

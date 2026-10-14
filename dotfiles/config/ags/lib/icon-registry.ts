import GLib from "gi://GLib?version=2.0"
import iconsData from "../icons.json"

interface Variant {
  name: string
  template: string
  output: string
}

interface BarMapping {
  widget: string
  icon_size: number
  states: Record<string, string>
}

interface IconGroup {
  color_mappings: Record<string, string>
  variants: Variant[]
  bar_mappings?: BarMapping
}

/** The group map: `group -> IconGroup`, with the reserved version key removed. */
type IconManifest = Record<string, IconGroup>

/**
 * The generated manifest is the group map PLUS the artifact's own
 * `schemaVersion` (spine AD-16/AD-21). The version is a RESERVED top-level key,
 * not a group: it is split off here so `getBarMappings`/`resolve`/`hasGroup`
 * read only named groups and can never mistake the version for one. The bar's
 * build-time `import icons.json` is this same artifact (a bundling detail), not
 * a second source.
 */
const manifestData = iconsData as Record<string, unknown>

/** The artifact's schema version, or `null` when absent (unknown degrades). */
export const manifestSchemaVersion: number | null =
  typeof manifestData.schemaVersion === "number" ? manifestData.schemaVersion : null

const manifest: IconManifest = Object.fromEntries(
  Object.entries(manifestData).filter(([name]) => name !== "schemaVersion"),
) as IconManifest

const stateDir =
  GLib.getenv("XDG_STATE_HOME") ||
  `${GLib.get_home_dir()}/.local/state`

const RUNTIME_ICONS_DIR = `${stateDir}/dotfiles/current/icons`

class IconRegistry {
  getBarMappings(group: string): BarMapping | null {
    return manifest[group]?.bar_mappings ?? null
  }

  resolve(group: string, variant: string): string | null {
    const groupData = manifest[group]
    if (!groupData) return null

    const variantEntry = groupData.variants.find((v) => v.name === variant)
    if (!variantEntry) return null

    const runtimePath = `${RUNTIME_ICONS_DIR}/${variantEntry.output}`
    if (GLib.file_test(runtimePath, GLib.FileTest.EXISTS)) return runtimePath

    return null
  }

  hasGroup(group: string): boolean {
    return group in manifest
  }

  hasVariant(group: string, variant: string): boolean {
    const groupData = manifest[group]
    if (!groupData) return false
    return groupData.variants.some((v) => v.name === variant)
  }
}

export const registry = new IconRegistry()

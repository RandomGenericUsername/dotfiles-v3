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

type IconManifest = Record<string, IconGroup>

const manifest: IconManifest = iconsData as unknown as IconManifest

const stateDir =
  GLib.getenv("XDG_STATE_HOME") ||
  `${GLib.get_home_dir()}/.local/state`
const dataDir =
  GLib.getenv("XDG_DATA_HOME") ||
  `${GLib.get_home_dir()}/.local/share`

const RUNTIME_ICONS_DIR = `${stateDir}/dotfiles/current/icons`
const PROVISION_ICONS_DIR = `${dataDir}/dotfiles/generated/icons`

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

    const provisionPath = `${PROVISION_ICONS_DIR}/${variantEntry.output}`
    if (GLib.file_test(provisionPath, GLib.FileTest.EXISTS)) return provisionPath

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

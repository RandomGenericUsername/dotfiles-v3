import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"

function getPowerMenuIconPath(): string | null {
  const mappings = registry.getBarMappings("power-menu")
  if (!mappings) return null

  const variant = mappings.states["default"]
  if (!variant) return null

  return registry.resolve("power-menu", variant)
}

export function PowerMenu() {
  return (
    <button
      class="widget power-menu-widget"
      onClicked={() => execAsync(["wlogout"])}
    >
      <image
        class="widget-icon"
        icon={getPowerMenuIconPath() ?? ""}
      />
    </button>
  )
}

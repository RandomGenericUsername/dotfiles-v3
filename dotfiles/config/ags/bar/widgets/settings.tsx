import { registry } from "../../lib/icon-registry"
import { toggle } from "../../settings-panel/state"

function getSettingsIconPath(): string | null {
  return registry.resolve("settings", "default")
}

export function Settings() {
  return (
    <button
      class="widget settings-widget"
      tooltipText="Settings"
      onClicked={() => toggle()}
    >
      <image
        pixel_size={28}
        class="widget-icon"
        $={(self) => self.set_from_file(getSettingsIconPath() ?? "")}
      />
    </button>
  )
}

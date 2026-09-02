import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"

export function Btop() {
  return (
    <button
      class="widget btop-widget"
      tooltipText="System monitor (btop)"
      onClicked={() => execAsync(["kitty", "--", "btop"]).catch(console.error)}
    >
      <image
        pixel_size={16}
        class="widget-icon"
        $={(self) => self.set_from_file(registry.resolve("btop", "btop") ?? "")}
      />
    </button>
  )
}

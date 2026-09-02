import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"

export function Thunderbird() {
  return (
    <button
      class="widget thunderbird-widget"
      tooltipText="Mail (Thunderbird)"
      onClicked={() => execAsync(["thunderbird"]).catch(console.error)}
    >
      <image
        pixel_size={24}
        class="widget-icon"
        $={(self) => self.set_from_file(registry.resolve("thunderbird", "thunderbird") ?? "")}
      />
    </button>
  )
}

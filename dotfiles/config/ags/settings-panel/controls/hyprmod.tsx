import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"
import { close } from "../state"

/**
 * Hyprmod action tile — no toggle state. Closing the panel first keeps focus
 * behavior predictable when the launcher opens.
 */
export function HyprmodTile() {
  return (
    <button
      class="settings-mini"
      onClicked={() => {
        close()
        execAsync(["hyprmod"]).catch(() => {
          /* hyprmod is provisioned; a launch failure is non-fatal here */
        })
      }}
      canFocus={false}
      tooltipText="Open Hyprmod"
    >
      <box spacing={9}>
        <image
          pixel_size={28}
          class="settings-mini-icon"
          $={(self) =>
            self.set_from_file(registry.resolve("settings-panel", "hyprmod") ?? "")
          }
        />
        <label class="settings-mini-title" label="Hyprmod" />
      </box>
    </button>
  )
}

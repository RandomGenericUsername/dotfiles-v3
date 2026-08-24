import Hyprland from "gi://AstalHyprland"
import { createBinding } from "ags"

const hyprland = Hyprland.get_default()
const focusedWorkspace = createBinding(hyprland, "focused-workspace")

const WORKSPACE_COUNT = 5

export function Workspaces() {
  return (
    <box class="workspace-indicator" spacing={4}>
      {Array.from({ length: WORKSPACE_COUNT }, (_, i) => {
        const wsId = i + 1
        return (
          <button
            class={focusedWorkspace((fw) => fw?.get_id() === wsId ? "workspace-btn active" : "workspace-btn")}
            onClicked={() => hyprland.dispatch("workspace", wsId.toString())}
          >
            <label label={wsId.toString()} />
          </button>
        )
      })}
    </box>
  )
}

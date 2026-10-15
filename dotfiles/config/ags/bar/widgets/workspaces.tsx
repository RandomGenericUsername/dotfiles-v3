import Hyprland from "gi://AstalHyprland"
import { createBinding } from "ags"
import type { CollectionSpec } from "../../kit/widget"

const hyprland = Hyprland.get_default()
const focusedWorkspace = createBinding(hyprland, "focusedWorkspace")

const WORKSPACE_COUNT = 5

/**
 * The workspace indicator, as a `CollectionSpec` (spine AD-8; doc 101 §5): its
 * own items, rendered by its own item renderer. The shared shell owns the root
 * box (`workspace-indicator`), the class and the spacing; the item renderer
 * binds each button's active class straight to the focused-workspace binding, so
 * the tree stays static and only the class re-evaluates.
 */
export const workspacesWidget: CollectionSpec<number, undefined> = {
  id: "workspaces",
  read: () => undefined,
  class: "workspace-indicator",
  spacing: 4,
  items: () => Array.from({ length: WORKSPACE_COUNT }, (_, i) => i + 1),
  key: (wsId) => String(wsId),
  item: (wsId) => (
    <button
      class={focusedWorkspace((fw) =>
        fw?.get_id() === wsId ? "workspace-btn active" : "workspace-btn"
      )}
      onClicked={() => hyprland.dispatch(`hl.dsp.focus({workspace=${wsId}})`, "")}
    >
      <label label={wsId.toString()} />
    </button>
  ),
}

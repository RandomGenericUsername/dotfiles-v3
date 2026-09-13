import Gtk from "gi://Gtk?version=4.0"
import Gdk from "gi://Gdk?version=4.0"
import AstalTray from "gi://AstalTray"
import { For, createBinding, createState } from "ags"
import { registry } from "../../lib/icon-registry"
import { RecordingIndicator } from "./recording"

const tray = AstalTray.get_default()

/**
 * Apps whose tray icon should be replaced by a runtime-generated SVG from the
 * icon pipeline (icons.yaml group `tray`). Matched against the StatusNotifier
 * item's id / item-id / title; anything unmatched keeps its native pixbuf.
 */
const TRAY_ICON_OVERRIDES: Array<[string, [string, string]]> = [
  ["tidal", ["tray", "tidal"]],
]

function overrideIconPath(item: AstalTray.TrayItem): string | null {
  const identity = `${item.id ?? ""} ${item.item_id ?? ""} ${item.title ?? ""}`.toLowerCase()
  for (const [match, [group, variant]] of TRAY_ICON_OVERRIDES) {
    if (identity.includes(match)) return registry.resolve(group, variant)
  }
  return null
}

function TrayIcon({ item }: { item: AstalTray.TrayItem }) {
  return (
    <image
      pixel_size={28}
      class="widget-icon"
      $={(self) => {
        const refresh = () => {
          const override = overrideIconPath(item)
          if (override) {
            self.set_from_file(override)
          } else if (item.gicon) {
            self.set_from_gicon(item.gicon)
          } else if (item.icon_name) {
            self.set_from_icon_name(item.icon_name)
          } else {
            self.set_from_icon_name("image-missing")
          }
        }

        refresh()
        item.connect("notify::gicon", refresh)
        item.connect("notify::icon-name", refresh)
        item.connect("notify::icon-pixbuf", refresh)
      }}
    />
  )
}

/**
 * One StatusNotifier item: left click activates it (restore the app), right
 * click pops the item's D-Bus menu. The menu model and its "dbusmenu" action
 * group are bound live so Electron/GTK items (tidal, nm-applet) work.
 */
function TrayItem({ item }: { item: AstalTray.TrayItem }) {
  return (
    <box
      class="tray-item"
      tooltipMarkup={createBinding(item, "tooltip-markup")}
      $={(self) => {
        const popover = new Gtk.PopoverMenu()
        popover.set_parent(self)
        popover.menu_model = item.menu_model
        if (item.action_group) {
          popover.insert_action_group("dbusmenu", item.action_group)
        }

        const menuHandler = item.connect("notify::menu-model", () => {
          popover.menu_model = item.menu_model
        })
        const actionHandler = item.connect("notify::action-group", () => {
          if (item.action_group) {
            popover.insert_action_group("dbusmenu", item.action_group)
          }
        })

        const primary = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        primary.connect("pressed", (_gesture, _n, x, y) => item.activate(x, y))
        self.add_controller(primary)

        const secondary = new Gtk.GestureClick({ button: Gdk.BUTTON_SECONDARY })
        secondary.connect("pressed", () => {
          item.about_to_show()
          popover.popup()
        })
        self.add_controller(secondary)

        self.connect("destroy", () => {
          item.disconnect(menuHandler)
          item.disconnect(actionHandler)
          popover.unparent()
        })
      }}
    >
      <TrayIcon item={item} />
    </box>
  )
}

export function Tray() {
  const [items, setItems] = createState<AstalTray.TrayItem[]>(tray.get_items())
  const refresh = () => setItems(tray.get_items())
  tray.connect("item-added", refresh)
  tray.connect("item-removed", refresh)

  return (
    <box class="bar-tray" spacing={8}>
      <For each={items} id={(item) => item.item_id ?? item.id}>
        {(item) => <TrayItem item={item} />}
      </For>
      <RecordingIndicator />
    </box>
  )
}

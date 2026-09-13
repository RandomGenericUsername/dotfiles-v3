import Gtk from "gi://Gtk?version=4.0"
import Gdk from "gi://Gdk?version=4.0"
import { For, createBinding, createState } from "ags"
import { registry } from "../../lib/icon-registry"
import {
  isNetworkItem,
  popupItemMenu,
  tray,
  type TrayItem as Item,
} from "../../lib/status-notifier"
import { RecordingIndicator } from "./recording"

/**
 * Apps whose tray icon should be replaced by a runtime-generated SVG from the
 * icon pipeline (icons.yaml group `tray`). Matched against the StatusNotifier
 * item's id / item-id / title; anything unmatched keeps its native pixbuf.
 */
const TRAY_ICON_OVERRIDES: Array<[string, [string, string]]> = [
  ["tidal", ["tray", "tidal"]],
]

function overrideIconPath(item: Item): string | null {
  const identity = `${item.id ?? ""} ${item.item_id ?? ""} ${item.title ?? ""}`.toLowerCase()
  for (const [match, [group, variant]] of TRAY_ICON_OVERRIDES) {
    if (identity.includes(match)) return registry.resolve(group, variant)
  }
  return null
}

function TrayIcon({ item }: { item: Item }) {
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
 * click pops the item's D-Bus menu. The network item (nm-applet) is excluded
 * here — it is merged into the NetworkStatus widget instead.
 */
function TrayItem({ item }: { item: Item }) {
  return (
    <box
      class="tray-item"
      tooltipMarkup={createBinding(item, "tooltip-markup")}
      $={(self) => {
        const primary = new Gtk.GestureClick({ button: Gdk.BUTTON_PRIMARY })
        primary.connect("pressed", (_gesture, _n, x, y) => item.activate(x, y))
        self.add_controller(primary)

        const secondary = new Gtk.GestureClick({ button: Gdk.BUTTON_SECONDARY })
        secondary.connect("pressed", () => popupItemMenu(item, self))
        self.add_controller(secondary)
      }}
    >
      <TrayIcon item={item} />
    </box>
  )
}

export function Tray() {
  const visible = (): Item[] => (tray.get_items() as Item[]).filter((item) => !isNetworkItem(item))
  const [items, setItems] = createState<Item[]>(visible())
  const refresh = () => setItems(visible())
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

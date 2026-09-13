import Gtk from "gi://Gtk?version=4.0"
import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import AstalTray from "gi://AstalTray"

export const tray = AstalTray.get_default()

export type TrayItem = AstalTray.TrayItem

/** Lowercased id/item-id/title used for identity matching. */
export function itemIdentity(item: TrayItem): string {
  return `${item.id ?? ""} ${item.item_id ?? ""} ${item.title ?? ""}`.toLowerCase()
}

export function isNetworkItem(item: TrayItem): boolean {
  const id = (item.id ?? "").toLowerCase()
  return id.includes("nm-applet") || id.includes("nm_applet")
}

export function findNetworkItem(): TrayItem | null {
  return (tray.get_items() as TrayItem[]).find(isNetworkItem) ?? null
}

// libastal-tray's menu model and action group have unstable lifetimes: binding
// a Gtk.PopoverMenu to them directly segfaults GTK (g_menu_item_get_attribute)
// and activating a forwarded action trips a GLib refcount underflow
// (g_atomic_ref_count_dec) that takes the whole AGS process down. So we build
// a private copy of the model and forward to the item through our own actions.
const COPIED_ATTRS = [
  Gio.MENU_ATTRIBUTE_LABEL,
  Gio.MENU_ATTRIBUTE_ACTION,
  Gio.MENU_ATTRIBUTE_TARGET,
  Gio.MENU_ATTRIBUTE_ICON,
]

function copyMenu(model: Gio.MenuModel): Gio.Menu {
  const menu = new Gio.Menu()
  const count = model.get_n_items()
  for (let i = 0; i < count; i++) {
    const item = new Gio.MenuItem()
    for (const attr of COPIED_ATTRS) {
      const value = model.get_item_attribute_value(i, attr, null)
      if (value) item.set_attribute_value(attr, value)
    }
    const submenu = model.get_item_link(i, Gio.MENU_LINK_SUBMENU)
    if (submenu) item.set_submenu(copyMenu(submenu))
    const section = model.get_item_link(i, Gio.MENU_LINK_SECTION)
    if (section) item.set_section(copyMenu(section))
    menu.append_item(item)
  }
  return menu
}

/**
 * A private action group that forwards to the tray item's own group. Holding
 * the item's group directly corrupts its refcount on activation, so each
 * action is mirrored here and the activation is relayed on demand.
 */
function forwardingGroup(source: Gio.ActionGroup | null): Gio.SimpleActionGroup {
  const group = new Gio.SimpleActionGroup()
  if (!source) return group

  for (const name of source.list_actions()) {
    const enabled = source.get_action_enabled(name)
    const parameterType = source.get_action_parameter_type(name)
    const props: Gio.SimpleAction.ConstructorProps = { name, enabled }
    if (parameterType) props.parameter_type = parameterType

    const action = new Gio.SimpleAction(props)
    action.connect("activate", (_self, parameter) => {
      try {
        source.activate_action(name, parameter)
      } catch (error) {
        console.error(`tray: action ${name} failed: ${error}`)
      }
    })
    group.add_action(action)
  }
  return group
}

/**
 * Pop an item's StatusNotifier menu anchored to `parent`. A fresh popover is
 * built per open from a private menu copy and a forwarding action group, so
 * nothing from libastal-tray is referenced after this call returns.
 */
export function popupItemMenu(item: TrayItem, parent: Gtk.Widget): void {
  const show = () => {
    // The model is only valid after about_to_show(); bail if it is still empty.
    const model = item.menu_model
    if (!model || model.get_n_items() === 0) return

    const popover = Gtk.PopoverMenu.new_from_model(copyMenu(model))
    popover.set_parent(parent)
    popover.insert_action_group("dbusmenu", forwardingGroup(item.action_group))
    popover.connect("closed", () => popover.unparent())
    popover.popup()
  }

  try {
    item.about_to_show()

    // DBusMenu builds the layout lazily: wait for the model to arrive.
    const current = item.menu_model
    if (current && current.get_n_items() > 0) {
      show()
      return
    }

    let done = false
    const handler = item.connect("notify::menu-model", () => {
      if (done) return
      const model = item.menu_model
      if (model && model.get_n_items() > 0) {
        done = true
        item.disconnect(handler)
        show()
      }
    })
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 400, () => {
      if (!done) {
        done = true
        item.disconnect(handler)
        show()
      }
      return GLib.SOURCE_REMOVE
    })
  } catch (error) {
    console.error(`tray: failed to open menu: ${error}`)
  }
}

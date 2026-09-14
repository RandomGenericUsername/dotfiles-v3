import { Gtk } from "ags/gtk4"
import { kindIcon, type ClipboardItem } from "../lib/clipboard-types"
import { Preview } from "./Preview"

/**
 * One clipboard history card: preview + footer, click selects.
 *
 * ``index`` is the 1-based position in the visible list, shown as a solid
 * badge in the footer (not over the preview text) so the ``Ctrl+1..9``
 * shortcut is discoverable.
 */
export function ItemCard(
  item: ClipboardItem,
  index: number,
  onSelect: (item: ClipboardItem) => void,
): Gtk.Box {
  const card = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    spacing: 6,
    css_classes: ["pano-card"],
  })
  card.set_size_request(200, -1)

  card.append(Preview(item))

  const footer = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 })
  footer.add_css_class("pano-card-footer")
  const badge = new Gtk.Label({ label: String(index) })
  badge.add_css_class("pano-index")
  footer.append(badge)
  footer.append(Gtk.Image.new_from_icon_name(kindIcon(item.kind)))
  if (item.favorite) {
    footer.append(Gtk.Image.new_from_icon_name("starred-symbolic"))
  }
  card.append(footer)

  const gesture = new Gtk.GestureClick()
  gesture.connect("released", () => onSelect(item))
  card.add_controller(gesture)

  return card
}

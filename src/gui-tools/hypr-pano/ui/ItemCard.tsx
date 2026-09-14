import { Gtk } from "ags/gtk4"
import type { ClipboardItem } from "../lib/clipboard-types"
import { resolveIcon } from "../lib/icon-registry"
import { Preview } from "./Preview"

//: Stock symbolic fallbacks (used only until the themed `ui-*.svg` renders).
const FALLBACK_ICON: Record<string, string> = {
  search: "system-search-symbolic",
  text: "text-x-generic-symbolic",
  image: "image-x-generic-symbolic",
  link: "insert-link-symbolic",
  code: "text-x-script-symbolic",
  color: "applications-graphics-symbolic",
  emoji: "face-smile-symbolic",
}

/**
 * Shared UI glyph from the themed `ui` group (ITR-rendered, palette-tinted),
 * falling back to a stock symbolic icon until the render exists. Exported so
 * any overlay surface (cards, search field, …) uses the same icon set.
 */
export function uiIcon(variant: string, size = 18): Gtk.Widget {
  const path = resolveIcon("ui", variant)
  if (path !== null) {
    const image = Gtk.Image.new_from_file(path)
    image.set_pixel_size(size)
    image.add_css_class("pano-ui-icon")
    return image
  }
  const fallback = Gtk.Image.new_from_icon_name(
    FALLBACK_ICON[variant] ?? "text-x-generic-symbolic",
  )
  fallback.set_pixel_size(size)
  return fallback
}

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
  footer.append(uiIcon(item.kind))
  if (item.favorite) {
    footer.append(Gtk.Image.new_from_icon_name("starred-symbolic"))
  }
  card.append(footer)

  const gesture = new Gtk.GestureClick()
  gesture.connect("released", () => onSelect(item))
  card.add_controller(gesture)

  return card
}

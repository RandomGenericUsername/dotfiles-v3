import { Gtk } from "ags/gtk4"
import Gdk from "gi://Gdk?version=4.0"
import GdkPixbuf from "gi://GdkPixbuf?version=2.0"
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

//: Rasterized-at-size icon textures, shared across cards. Loading the SVG and
//: rasterizing it per card per rebuild was the freeze source under fast arrow
//: repeats; one texture per (path, size) is reused instead.
const textureCache = new Map<string, Gdk.Texture>()

function iconTexture(path: string, size: number): Gdk.Texture {
  const key = `${path}:${size}`
  const cached = textureCache.get(key)
  if (cached !== undefined) return cached
  let pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
  // Some SVG loaders ignore the requested size; guarantee a bounded pixbuf.
  if (pixbuf.get_width() > size || pixbuf.get_height() > size) {
    const factor = Math.min(size / pixbuf.get_width(), size / pixbuf.get_height())
    pixbuf = pixbuf.scale_simple(
      Math.max(1, Math.round(pixbuf.get_width() * factor)),
      Math.max(1, Math.round(pixbuf.get_height() * factor)),
      GdkPixbuf.InterpType.BILINEAR,
    )
  }
  const texture = Gdk.Texture.new_for_pixbuf(pixbuf)
  textureCache.set(key, texture)
  return texture
}

/**
 * Shared UI glyph from the themed `ui` group (ITR-rendered, palette-tinted),
 * falling back to a stock symbolic icon until the render exists. Exported so
 * any overlay surface (cards, search field, …) uses the same icon set.
 */
export function uiIcon(variant: string, size = 18): Gtk.Widget {
  const path = resolveIcon("ui", variant)
  if (path !== null) {
    try {
      const picture = Gtk.Picture.new_for_paintable(iconTexture(path, size))
      picture.set_content_fit(Gtk.ContentFit.CONTAIN)
      picture.set_size_request(size, size)
      picture.add_css_class("pano-ui-icon")
      return picture
    } catch (error) {
      console.error(`hypr-pano: cannot load icon ${path}: ${error}`)
    }
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

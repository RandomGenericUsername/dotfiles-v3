import { Gtk } from "ags/gtk4"
import Pango from "gi://Pango?version=1.0"
import type { ClipboardItem } from "../lib/clipboard-types"
import { itemTitle } from "../lib/clipboard-types"

function parseHexColor(value: string | null): { r: number; g: number; b: number } | null {
  if (value === null) return null
  const match = value.trim().match(/^#?([0-9a-fA-F]{6})$/)
  if (match === null) return null
  const int = Number.parseInt(match[1], 16)
  return {
    r: ((int >> 16) & 0xff) / 255,
    g: ((int >> 8) & 0xff) / 255,
    b: (int & 0xff) / 255,
  }
}

/** Type-appropriate preview body for a card. */
export function Preview(item: ClipboardItem): Gtk.Widget {
  if (item.kind === "image" && item.path !== null) {
    try {
      const picture = Gtk.Picture.new_for_filename(item.path)
      picture.set_content_fit(Gtk.ContentFit.COVER)
      picture.set_size_request(236, 118)
      const wrap = new Gtk.Box({ css_classes: ["pano-thumb-wrap"] })
      wrap.set_overflow(Gtk.Overflow.HIDDEN)
      wrap.append(picture)
      return wrap
    } catch (error) {
      console.error(`hypr-pano: cannot load image ${item.path}: ${error}`)
    }
  }

  if (item.kind === "color") {
    const box = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 8 })
    box.add_css_class("pano-color")
    const area = new Gtk.DrawingArea()
    area.set_content_width(236)
    area.set_content_height(64)
    const rgb = parseHexColor(item.text)
    area.set_draw_func((_widget, cr, width, height) => {
      if (rgb !== null) cr.setSourceRGB(rgb.r, rgb.g, rgb.b)
      else cr.setSourceRGB(0.2, 0.2, 0.2)
      cr.rectangle(0, 0, width, height)
      cr.fill()
    })
    const wrap = new Gtk.Box({ css_classes: ["pano-swatch-wrap"] })
    wrap.set_overflow(Gtk.Overflow.HIDDEN)
    wrap.append(area)
    box.append(wrap)
    const hex = Gtk.Label({ label: (item.text ?? "").trim() })
    hex.add_css_class("pano-hex")
    box.append(hex)
    return box
  }

  const label = new Gtk.Label({ label: itemTitle(item), xalign: 0, yalign: 0 })
  label.set_wrap(true)
  label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
  label.set_ellipsize(Pango.EllipsizeMode.END)
  label.set_lines(item.kind === "code" ? 6 : 5)
  label.add_css_class("pano-text")
  if (item.kind === "code") label.add_css_class("pano-code")
  if (item.kind === "link") label.add_css_class("pano-link")
  if (item.kind === "emoji") label.add_css_class("pano-emoji")
  return label
}

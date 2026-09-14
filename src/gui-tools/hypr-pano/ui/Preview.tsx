import { Gtk } from "ags/gtk4"
import Pango from "gi://Pango?version=1.0"
import { itemTitle, type ClipboardItem } from "../lib/clipboard-types"

/** Type-appropriate preview body for a card. */
export function Preview(item: ClipboardItem): Gtk.Widget {
  if (item.kind === "image" && item.path !== null) {
    try {
      const picture = Gtk.Picture.new_for_filename(item.path)
      picture.set_content_fit(Gtk.ContentFit.COVER)
      picture.set_size_request(180, 120)
      picture.add_css_class("pano-image")
      return picture
    } catch (error) {
      console.error(`hypr-pano: cannot load image ${item.path}: ${error}`)
    }
  }
  const label = new Gtk.Label({ label: itemTitle(item), xalign: 0, yalign: 0 })
  label.set_wrap(true)
  label.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
  label.set_ellipsize(Pango.EllipsizeMode.END)
  label.set_lines(4)
  label.set_size_request(180, 120)
  label.add_css_class("pano-text")
  if (item.kind === "color") {
    label.add_css_class("pano-color")
  }
  if (item.kind === "code") {
    label.add_css_class("pano-code")
  }
  return label
}

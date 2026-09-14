import { Gtk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import Gdk from "gi://Gdk?version=4.0"
import GdkPixbuf from "gi://GdkPixbuf?version=2.0"
import type { ClipboardItem, ItemKind } from "../lib/clipboard-types"
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

//: Rasterized-at-size icon textures, shared across cards.
const textureCache = new Map<string, Gdk.Texture>()

function iconTexture(path: string, size: number): Gdk.Texture {
  const key = `${path}:${size}`
  const cached = textureCache.get(key)
  if (cached !== undefined) return cached
  let pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, size, size)
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
 * falling back to a stock symbolic icon until the render exists.
 */
export function uiIcon(variant: string, size = 18): Gtk.Widget {
  const path = resolveIcon("ui", variant)
  if (path !== null) {
    try {
      const picture = Gtk.Picture.new_for_paintable(iconTexture(path, size))
      picture.set_content_fit(Gtk.ContentFit.CONTAIN)
      picture.set_size_request(size, size)
      picture.set_halign(Gtk.Align.CENTER)
      picture.set_valign(Gtk.Align.CENTER)
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
  fallback.set_halign(Gtk.Align.CENTER)
  fallback.set_valign(Gtk.Align.CENTER)
  return fallback
}

//: Each content type is themed by a generated-palette token (never a fixed
//: hex) so the header follows the wallpaper like the rest of the desktop.
const TYPE_TOKEN: Record<ItemKind, string> = {
  text: "color_06",
  code: "color_00",
  color: "color_13",
  image: "color_09",
  link: "color_04",
  emoji: "color_12",
}

const TYPE_LABEL: Record<ItemKind, string> = {
  text: "Text",
  code: "Code",
  color: "Color",
  image: "Image",
  link: "Link",
  emoji: "Emoji",
}

let tokenCache: Record<string, string> | null = null

function paletteTokens(): Record<string, string> {
  if (tokenCache !== null) return tokenCache
  const tokens: Record<string, string> = {}
  try {
    const path = `${GLib.get_user_config_dir()}/ags/colors.css`
    const [ok, bytes] = GLib.file_get_contents(path)
    if (ok && bytes !== null) {
      const text = new TextDecoder().decode(bytes)
      for (const match of text.matchAll(/@define-color\s+([\w-]+)\s+(#[0-9a-fA-F]{6})/g)) {
        tokens[match[1]] = match[2]
      }
    }
  } catch (error) {
    console.error(`hypr-pano: cannot read palette tokens: ${error}`)
  }
  tokenCache = tokens
  return tokens
}

function relativeLuminance(hex: string): number {
  const int = Number.parseInt(hex.slice(1), 16)
  const channel = (value: number): number => {
    const c = value / 255
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4
  }
  const r = channel((int >> 16) & 0xff)
  const g = channel((int >> 8) & 0xff)
  const b = channel(int & 0xff)
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

//: "on-dark" (light text) when the type token is dark, else "on-light".
function headerTextClass(kind: ItemKind): string {
  const hex = paletteTokens()[TYPE_TOKEN[kind]]
  if (hex === undefined) return "on-dark"
  return relativeLuminance(hex) < 0.45 ? "on-dark" : "on-light"
}

function relativeTime(timestamp: number): string {
  const seconds = Math.max(0, Math.floor(Date.now() / 1000 - timestamp))
  if (seconds < 45) return "just now"
  const minutes = Math.round(seconds / 60)
  if (minutes < 60) return `${Math.max(1, minutes)} min${minutes === 1 ? "" : "s"} ago`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `${hours} hour${hours === 1 ? "" : "s"} ago`
  const days = Math.round(hours / 24)
  return `${days} day${days === 1 ? "" : "s"} ago`
}

/**
 * One clipboard history card: a palette-themed type header
 * (index + glyph + type label + relative time) over a type-appropriate
 * preview body. ``index`` is the 1-based position for ``Ctrl+1..9``.
 */
export function ItemCard(
  item: ClipboardItem,
  index: number,
  onSelect: (item: ClipboardItem) => void,
  onOpenLink?: (item: ClipboardItem) => void,
): Gtk.Box {
  const card = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    spacing: 0,
    css_classes: ["pano-card", `kind-${item.kind}`],
  })
  // Clip children to the rounded card corners (GTK does not do this by
  // default), so the header/body follow the card radius like the mockup.
  card.set_overflow(Gtk.Overflow.HIDDEN)
  card.set_size_request(260, -1)
  card.set_hexpand(false)
  card.set_halign(Gtk.Align.START)

  // CenterBox lays start/end out itself — no child hexpand, which would
  // otherwise propagate up and make the card stretch in the list.
  const header = new Gtk.CenterBox({
    css_classes: ["pano-head", headerTextClass(item.kind)],
  })
  const headStart = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 4 })
  const badge = new Gtk.Label({ label: String(index), xalign: 0.5 })
  badge.add_css_class("pano-index")
  badge.set_size_request(18, 18)
  badge.set_halign(Gtk.Align.CENTER)
  badge.set_valign(Gtk.Align.CENTER)
  headStart.append(badge)
  headStart.append(uiIcon(item.kind, 18))
  const label = new Gtk.Label({ label: TYPE_LABEL[item.kind], xalign: 0 })
  label.add_css_class("pano-head-label")
  headStart.append(label)
  header.set_start_widget(headStart)

  const time = new Gtk.Label({ label: relativeTime(item.timestamp) })
  time.add_css_class("pano-time")
  header.set_end_widget(time)
  card.append(header)

  const body = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL })
  body.add_css_class("pano-body")
  body.append(Preview(item))
  card.append(body)

  // Left click copies the item back.
  const gesture = new Gtk.GestureClick()
  gesture.set_button(Gdk.BUTTON_PRIMARY)
  gesture.connect("released", () => onSelect(item))
  card.add_controller(gesture)

  // Right click on a LINK card opens the URL via the desktop handler.
  if (item.kind === "link" && onOpenLink !== undefined) {
    const rightClick = new Gtk.GestureClick()
    rightClick.set_button(Gdk.BUTTON_SECONDARY)
    rightClick.connect("released", () => onOpenLink(item))
    card.add_controller(rightClick)
  }

  return card
}

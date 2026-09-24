import { Gdk, Gtk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"

let paletteProvider: Gtk.CssProvider | null = null

/** Replace only the generated palette CSS; keep the app stylesheet and GTK theme. */
export function refreshPaletteCss(): void {
  const display = Gdk.Display.get_default()
  if (display === null) throw new Error("no default GDK display")

  const path = `${GLib.get_user_config_dir()}/ags/colors.css`
  const next = new Gtk.CssProvider()
  let parseError: string | null = null
  next.connect("parsing-error", (_provider, _section, error) => {
    parseError = error.message
  })
  next.load_from_path(path)
  if (parseError !== null) throw new Error(`palette CSS parse failed: ${parseError}`)

  Gtk.StyleContext.add_provider_for_display(display, next, Gtk.STYLE_PROVIDER_PRIORITY_USER)
  if (paletteProvider !== null) {
    Gtk.StyleContext.remove_provider_for_display(display, paletteProvider)
  }
  paletteProvider = next
}

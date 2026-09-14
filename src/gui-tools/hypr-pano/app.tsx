import app from "ags/gtk4/app"
import Gio from "gi://Gio?version=2.0"
import GLib from "gi://GLib?version=2.0"
import Gdk from "gi://Gdk?version=4.0"
import Gtk from "gi://Gtk?version=4.0"
import style from "./style.css"
import { PanoWindow } from "./ui/PanoWindow"

// The generated palette fragment the shell applies (a symlink into the runtime
// `current/` pointer). The bar is restarted by the runtime on a palette change,
// but this overlay is its own AGS instance, so it watches the palette and
// reloads the CSS provider in place instead of restarting.
const PALETTE_FILE = `${GLib.get_user_config_dir()}/ags/colors.css`
const PALETTE_WATCH_DIRS = [
  // Repointed by the runtime on every wallpaper/palette change.
  `${GLib.getenv("XDG_STATE_HOME") ?? `${GLib.get_home_dir()}/.local/state`}/dotfiles/current`,
  // Covers the palette symlink itself being (re)created by provisioning.
  `${GLib.get_user_config_dir()}/ags`,
]

const paletteProvider = new Gtk.CssProvider()
const paletteMonitors: Gio.FileMonitor[] = []

function applyPalette(): void {
  try {
    paletteProvider.load_from_path(PALETTE_FILE)
  } catch (error) {
    console.error(`hypr-pano: palette reload failed: ${error}`)
  }
}

function watchPalette(): void {
  let pending: number | null = null
  const schedule = (): void => {
    if (pending !== null) GLib.source_remove(pending)
    pending = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 150, () => {
      pending = null
      console.log("hypr-pano: palette changed; reloading theme")
      applyPalette()
      return GLib.SOURCE_REMOVE
    })
  }
  for (const dir of PALETTE_WATCH_DIRS) {
    try {
      const monitor = Gio.File.new_for_path(dir).monitor_directory(
        Gio.FileMonitorFlags.NONE,
        null,
      )
      monitor.connect("changed", schedule)
      paletteMonitors.push(monitor)
    } catch (error) {
      console.error(`hypr-pano: cannot watch palette dir ${dir}: ${error}`)
    }
  }
}

app.start({
  instanceName: "hypr-pano",
  css: style,
  main() {
    // A reloadable palette provider (not a one-shot apply_css) so a wallpaper
    // change restyles the overlay in place, keeping it open.
    Gtk.StyleContext.add_provider_for_display(
      Gdk.Display.get_default()!,
      paletteProvider,
      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
    applyPalette()
    watchPalette()
    for (const monitor of app.get_monitors()) {
      app.add_window(PanoWindow(monitor))
    }
  },
})

import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import { PanoWindow } from "./ui/PanoWindow"

app.start({
  instanceName: "hypr-pano",
  css: style,
  main() {
    // Reuse the shell's generated palette so the overlay matches the bar.
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    for (const monitor of app.get_monitors()) {
      app.add_window(PanoWindow(monitor))
    }
  },
})

import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import { NotificationsWindow } from "./ui/NotificationsWindow"

app.start({
  instanceName: "notifications",
  css: style,
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    // A single top-right stack: every window would render the SAME daemon
    // stream, so (unlike the capture picker) this instance shows on one
    // monitor only instead of one window per monitor.
    const monitors = app.get_monitors()
    const primary = monitors[0]
    if (primary !== undefined) {
      app.add_window(NotificationsWindow(primary))
    }
  },
})

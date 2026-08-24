import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import Bar from "./bar/Bar"

app.start({
  css: style,
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    app.get_monitors().map(Bar)
  },
})

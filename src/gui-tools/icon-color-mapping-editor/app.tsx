import app from "ags/gtk4/app";
import GLib from "gi://GLib?version=2.0";
import style from "./style.css";
import { EditorWindow } from "./ui/EditorWindow";

app.start({
  css: style,
  instanceName: "icon-color-mapping-editor",
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`);
    // Single centered window on the primary monitor (dev tool, not chrome).
    const monitor = app.get_monitors()[0];
    if (monitor) app.add_window(EditorWindow(monitor));
  },
});

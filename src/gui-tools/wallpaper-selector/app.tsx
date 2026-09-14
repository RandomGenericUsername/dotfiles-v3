import app from "ags/gtk4/app";
import GLib from "gi://GLib?version=2.0";
import style from "./style.css";
import { WallpaperSelectorWindow } from "./ui/WallpaperSelectorWindow";

app.start({
  css: style,
  instanceName: "wallpaper-selector",
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`);
    // Single centered window on the primary monitor (settings-style tool,
    // not per-monitor chrome — same pattern as the ICME editor window).
    const monitor = app.get_monitors()[0];
    if (monitor) app.add_window(WallpaperSelectorWindow(monitor));
  },
});

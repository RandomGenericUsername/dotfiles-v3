import app from "ags/gtk4/app";
import style from "./style.css";
import { refreshPaletteCss } from "./lib/theme";
import { WallpaperSelectorWindow } from "./ui/WallpaperSelectorWindow";

app.start({
  css: style,
  instanceName: "wallpaper-selector",
  main() {
    refreshPaletteCss();
    // Single centered window on the primary monitor (settings-style tool,
    // not per-monitor chrome — same pattern as the ICME editor window).
    const monitor = app.get_monitors()[0];
    if (monitor) app.add_window(WallpaperSelectorWindow(monitor));
  },
});

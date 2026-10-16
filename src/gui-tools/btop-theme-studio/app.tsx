import app from "ags/gtk4/app";
import style from "./style.css";
import { StudioWindow } from "./ui/StudioWindow";

app.start({
  css: style,
  instanceName: "btop-theme-studio",
  main() {
    // Single centered window on the primary monitor (an authoring tool, not
    // chrome). Launch-on-demand only: never registered in the bar, never
    // autostarted (see openspec change add-btop-theme-studio).
    const monitor = app.get_monitors()[0];
    if (monitor) app.add_window(StudioWindow(monitor));
  },
});

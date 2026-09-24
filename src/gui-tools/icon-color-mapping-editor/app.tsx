import app from "ags/gtk4/app";
import style from "./style.css";
import { refreshPaletteCss } from "./lib/theme";
import { EditorWindow } from "./ui/EditorWindow";

app.start({
  css: style,
  instanceName: "icon-color-mapping-editor",
  main() {
    refreshPaletteCss();
    // Single centered window on the primary monitor (dev tool, not chrome).
    const monitor = app.get_monitors()[0];
    if (monitor) app.add_window(EditorWindow(monitor));
  },
});

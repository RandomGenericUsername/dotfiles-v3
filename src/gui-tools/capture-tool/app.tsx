import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import { CaptureWindow } from "./ui/CaptureWindow"
import type { CapturePorts } from "./ports/capture-ports"
import { glibSettingsStore } from "./adapters/glib-settings-store"
import { glibUiStateStore } from "./adapters/glib-ui-state-store"
import { execCaptureLauncher } from "./adapters/exec-capture-launcher"
import { execBackendProbe } from "./adapters/exec-backend-probe"

// Composition root (design.md §2): the one place that knows which adapter
// satisfies which port. A8 moves this to a `buildPorts()` factory; it is
// inline here because task 5.9's acceptance is that `CaptureWindow` receives
// its dependencies as parameters and no longer touches GLib's filesystem or
// `execAsync` itself.
const ports: CapturePorts = {
  settingsStore: glibSettingsStore(),
  uiStateStore: glibUiStateStore(),
  launcher: execCaptureLauncher(),
  backendProbe: execBackendProbe(),
}

app.start({
  instanceName: "capture",
  css: style,
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    for (const monitor of app.get_monitors()) {
      app.add_window(CaptureWindow(monitor, ports))
    }
  },
})

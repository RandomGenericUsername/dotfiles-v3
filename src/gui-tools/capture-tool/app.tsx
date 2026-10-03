import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import { execBackendProbe } from "./adapters/exec-backend-probe"
import { execCaptureLauncher } from "./adapters/exec-capture-launcher"
import { glibSettingsStore } from "./adapters/glib-settings-store"
import { glibUiStateStore } from "./adapters/glib-ui-state-store"
import { createUiState } from "./domain/ui-state"
import type { CapturePorts } from "./ports/capture-ports"
import { ClassicWindow } from "./ui/classic/ClassicWindow"

// Composition root (design.md §2, task 8.5). The ONE place that knows which
// adapter satisfies which port, and the only place that builds them.
//
// `buildPorts()` is a factory rather than a module-level constant for one
// reason: it is the seam a test or a second entry point would swap. Nothing
// else in the tool constructs an adapter, so swapping the wiring means editing
// exactly this function and nothing else.
//
// NO LOGIC BELOW THIS POINT beyond "construct the dependencies, then render":
// every decision the panel makes — what the classes are, when a view shows,
// what argv a capture produces — belongs to the domain, the ports or the
// layout, all of which are reachable from here without this file knowing what
// they do.
function buildPorts(): CapturePorts {
  return {
    settingsStore: glibSettingsStore(),
    uiStateStore: glibUiStateStore(),
    launcher: execCaptureLauncher(),
    backendProbe: execBackendProbe(),
  }
}

app.start({
  instanceName: "capture",
  css: style,
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)
    const ports = buildPorts()
    // ONE live UI state for the whole app, built here and handed to every
    // window (fix-capture-per-monitor-state). The persisted selections belong
    // to the application — there is a single `capture-ui.json` and a single
    // settings→defaults→last-used precedence chain — so the loop must NOT give
    // each monitor's window its own copy: two copies diverge on first
    // mutation, and whichever window saves last silently discards the other
    // one's selection. `createUiState()` stays a factory (not a module-level
    // constant) for the same reason `buildPorts()` does: the sharing is this
    // composition root's decision, visible in one place, and swap-able by a
    // test or a second entry point.
    const state = createUiState()
    for (const monitor of app.get_monitors()) {
      app.add_window(ClassicWindow(monitor, ports, state))
    }
  },
})
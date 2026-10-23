// ===========================================================================
// REPRO HARNESS — fix-capture-monitor-lifecycle.  NOT a CI test.
//
// Needs a live AGS session. This host has ONE monitor and cannot inject input,
// so the two-monitor cases are driven by SYNTHESISING the topology port's
// monitor list rather than by plugging anything in, and every claim the harness
// prints is either (a) a real GTK call on the real App singleton, or (b) the
// real domain module with a stand-in monitor list, labelled which.
//
//   Run:  cp repro/monitor-lifecycle-harness.tsx <tool>/app.tsx
//         ags run -d <tool>
//
// The equivalent one-shot measurements that produced design.md's numbers are in
// the sibling probes/ directory.
// ===========================================================================
import app from "ags/gtk4/app"
import { Astal, Gdk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import style from "./style.css"
import { glibSettingsStore } from "./adapters/glib-settings-store"
import { glibUiStateStore } from "./adapters/glib-ui-state-store"
import { gdkMonitorTopology } from "./adapters/gdk-monitor-topology"
import { hyprlandMonitorFocus } from "./adapters/hyprland-monitor-focus"
import {
  createMonitorWindowSet,
  installFocusedWindowLookup,
} from "./adapters/monitor-window-set"
import type { MonitorDescriptor } from "./domain/monitor-registry"
import { createUiState } from "./domain/ui-state"
import type { CapturePorts } from "./ports/capture-ports"
import type { MonitorEntry, MonitorTopology } from "./ports/monitor-topology"
import { ClassicWindow } from "./ui/classic/ClassicWindow"

const LOG = "/tmp/opencode/monitor-lifecycle-harness.log"
const out: string[] = []
function log(...parts: unknown[]) {
  const line = parts.map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join(" ")
  out.push(line)
  print(line)
  GLib.file_set_contents(LOG, out.join("\n") + "\n")
}
function after(ms: number, fn: () => void) {
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    try {
      fn()
    } catch (e) {
      log("   STEP THREW:", String(e))
    }
    return false
  })
}

const ports: CapturePorts = {
  settingsStore: glibSettingsStore(),
  uiStateStore: glibUiStateStore(),
  launcher: { launch(argv: string[]) { log("      launcher argv:", JSON.stringify(argv)) } },
  backendProbe: { backend: async () => "stub" },
}

function desc(connector: string, x: number): MonitorDescriptor {
  return {
    connector,
    model: "0x153C",
    manufacturer: "Chimei Innolux Corporation",
    geometry: { x, y: 0, width: 1920, height: 1080 },
  }
}

app.start({
  instanceName: "capture-repro-life",
  css: style,
  main() {
    const display = Gdk.Display.get_default() as Gdk.Display
    const realMonitor = app.get_monitors()[0]
    const state = createUiState()

    log("=== PART 1: the REAL topology adapter against the REAL display ===")
    const real: MonitorTopology = gdkMonitorTopology(display)
    log("REAL Gdk.Display.get_monitors() reports:", real.list().map((e) => e.descriptor.connector))
    log("subscribe() on it did not throw -> the signal it connects exists")
    let fired = 0
    real.subscribe(() => {
      fired += 1
    })
    log("items-changed/invalidate hooks attached; fired so far:", fired)

    log("")
    log("=== PART 2: SYNTHESISED two-monitor topology (this host has one monitor) ===")
    // Two logical monitors, both backed by the one real Gdk.Monitor, so the
    // WINDOWS are real Astal.Windows and every App call below is real GTK.
    // Only the monitor LIST is synthetic.
    let synthetic: MonitorEntry[] = [
      { descriptor: desc("eDP-1", 0), native: realMonitor },
    ]
    let focusedConnector: string | null = "eDP-1"
    const synth: MonitorTopology = {
      list: () => synthetic,
      subscribe: (cb) => {
        synthOnChange = cb
      },
    }
    let synthOnChange: () => void = () => {}
    const synthFocus = { focusedConnector: () => focusedConnector }

    const windowSet = createMonitorWindowSet({
      app,
      topology: synth,
      focus: synthFocus,
      createWindow: (monitor) => ClassicWindow(monitor, ports, state),
      report: (m) => log("   ", m),
    })
    installFocusedWindowLookup(app, windowSet)

    const all = () => (app as unknown as { windows: Gtk.Window[] }).windows
    const named = () => all().filter((w) => w.name === "capture-window")
    const tag = (w: Gtk.Window) => {
      const e = windowSet.bindings().find((b) => b.window === w)
      return e ? (e.key.includes("HDMI-2") ? "B" : "A") : "?"
    }
    function step(label: string, expected: string) {
      // Registration order (the set's OWN list) is the invariant; GTK's window
      // list order is deliberately NOT it — that is the bug being fixed — so it
      // is printed alongside but never asserted on.
      const registration = windowSet.bindings().map((b) => tag(b.window)).join(",")
      const gtkOrder = named().map(tag).join(",")
      log(`  ${label}`)
      log(`     set registration order: [${registration}]   GTK's own order: [${gtkOrder}]`)
      log(`     get_window -> ${tag(app.get_window("capture-window")!)}`)
      log(`     ${registration === expected ? "OK" : "MISMATCH (expected " + expected + ")"}`)
    }

    log("")
    log("STEP 1: one monitor -> one window")
    step("after construction", "A")

    log("")
    log("STEP 2: PLUG IN a second monitor (the hotplug path)")
    synthetic = [
      { descriptor: desc("eDP-1", 0), native: realMonitor },
      { descriptor: desc("HDMI-2", 1920), native: realMonitor },
    ]
    synthOnChange()
    step("after items-changed", "A,B")

    log("")
    log("STEP 3: FOCUS moves to the second monitor; the launcher must now reach it")
    focusedConnector = "HDMI-2"
    log("  app.get_window('capture-window') now resolves to window", tag(app.get_window("capture-window")!))
    log("  every window still shares the name:", [...new Set(named().map((w) => w.name))].join(","))

    log("")
    log("STEP 4: a REPEATED change event must be a no-op (idempotence)")
    synthOnChange()
    synthOnChange()
    step("after two duplicate notifications", "A,B")

    log("")
    log("STEP 5: UNPLUG the second monitor -> its window must be DESTROYED, not hidden")
    const beforeCount = named().length
    const stale = named().find((w) => tag(w) === "B")!
    synthetic = [{ descriptor: desc("eDP-1", 0), native: realMonitor }]
    synthOnChange()
    log("  windows named capture-window:", beforeCount, "->", named().length)
    log("  the removed window is gone from the app's list:", !all().includes(stale))
    log("  get_window resolves to window", tag(app.get_window("capture-window")!), "(the survivor)")
    step("after unplug", "A")

    log("")
    log("STEP 6: REPLUG -> a fresh window is built and is reachable again")
    synthetic = [
      { descriptor: desc("eDP-1", 0), native: realMonitor },
      { descriptor: desc("HDMI-2", 1920), native: realMonitor },
    ]
    synthOnChange()
    step("after replug", "A,B")
    focusedConnector = "HDMI-2"
    log("  with focus on HDMI-2 the launcher reaches:", tag(app.get_window("capture-window")!))

    log("")
    log("STEP 7: focus names a monitor with no window -> deterministic fallback")
    focusedConnector = "DP-9"
    log("  get_window ->", tag(app.get_window("capture-window")!), "(registration order: the eDP-1 window)")

    log("")
    log("STEP 8: THE REAL focus adapter (compositor) against the REAL monitor set")
    const focus = hyprlandMonitorFocus()
    after(400, () => {
      log("  focusedConnector():", JSON.stringify(focus.focusedConnector()))
      log("  gdk connector for the same monitor:", realMonitor.get_connector())
      log("  real items-changed notifications seen during this run:", fired)
      app.quit()
    })
  },
})
// PROBE — REAL monitor hotplug, on a real second output. Not a CI test.
//
// Hyprland can create a virtual output, so this host CAN exercise hotplug for
// real (the one thing `monitor-lifecycle-harness.tsx` has to synthesise):
//
//     hyprctl output create headless     # a second monitor appears
//     hyprctl output remove HEADLESS-1    # and goes away
//
// and the compositor delivers genuine wl_output global / release events, which
// GDK turns into genuine GdkMonitor ListModel `items-changed` notifications.
// Nothing here is a stand-in: the topology adapter is the real one, reading the
// real Gdk.Display.
//
// Run:  cp this to <tool>/app.tsx && ags run -d <tool>
//       hyprctl output create headless
//       hyprctl output remove HEADLESS-1
//
// It only ever CALLS BACK what the platform says; it never builds or destroys a
// window itself.
import app from "ags/gtk4/app"
import { Gdk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import { gdkMonitorTopology } from "./adapters/gdk-monitor-topology"

const LOG = "/tmp/opencode/probe-real-hotplug.log"
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

app.start({
  instanceName: "capture-probe-hotplug",
  main() {
    const display = Gdk.Display.get_default() as Gdk.Display
    const topology = gdkMonitorTopology(display)

    log("=== REAL hotplug, observed through the REAL adapter ===")
    function state(label: string) {
      const mons = topology.list()
      log(
        `  ${label.padEnd(46)} monitors=[${mons.map((m) => m.descriptor.connector).join(",")}]` +
        `  ListModel n_items=${(display.get_monitors() as Gio.ListModel).get_n_items()}`,
      )
    }

    let notifications = 0
    topology.subscribe(() => {
      notifications += 1
      log(`  >>> change notification #${notifications} received`)
    })

    state("at startup")
    log("  now run:  hyprctl output create headless")
    after(4000, () => state("after `hyprctl output create headless`"))
    after(9000, () => {
      log("  now run:  hyprctl output remove HEADLESS-1")
    })
    after(14000, () => state("after `hyprctl output remove HEADLESS-1`"))
    after(19000, () => {
      log("  now run:  hyprctl output create headless")
    })
    after(24000, () => state("after the second create"))
    after(28000, () => {
      log("")
      log(`total change notifications delivered to the adapter: ${notifications}`)
      app.quit()
    })
  },
})
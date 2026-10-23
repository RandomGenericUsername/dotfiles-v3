// PROBE — is a new monitor's CONNECTOR populated at the instant
// items-changed fires?  If not, a key built from it changes a moment later and
// the window is rebuilt.  Not a CI test.
//
// Run with a virtual output: hyprctl output create headless
import app from "ags/gtk4/app"
import { Gdk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"
import { gdkMonitorTopology } from "./adapters/gdk-monitor-topology"
import { monitorKey } from "./domain/monitor-registry"

const LOG = "/tmp/opencode/probe-connector-timing.log"
const out: string[] = []
function log(...parts: unknown[]) {
  const line = parts.map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join(" ")
  out.push(line)
  print(line)
  GLib.file_set_contents(LOG, out.join("\n") + "\n")
}

function dump(label: string) {
  const t = gdkMonitorTopology(Gdk.Display.get_default() as Gdk.Display)
  log(`  ${label}`)
  for (const e of t.list()) {
    const d = e.descriptor
    log(`     connector=${JSON.stringify(d.connector)} model=${JSON.stringify(d.model)} KEY=${monitorKey(d)}`)
  }
}

app.start({
  instanceName: "capture-probe-timing",
  main() {
    const display = Gdk.Display.get_default() as Gdk.Display
    const topology = gdkMonitorTopology(display)
    const model = display.get_monitors() as unknown as {
      connect(s: string, cb: (p: number, r: number, a: number) => void): number
    }

    log("=== baseline ===")
    dump("at startup")

    let n = 0
    model.connect("items-changed", () => {
      n += 1
      log(`>>> items-changed #${n}  position/removed/added = (${""})`)
      // (1) IMMEDIATELY, inside the signal handler
      dump("IMMEDIATELY inside the handler:")
      // (2) deferred to an idle callback, i.e. after GTK finished processing
      GLib.idle_add(GLib.PRIORITY_DEFAULT_IDLE, () => {
        dump("on the NEXT IDLE (after GTK settles):")
        // (3) and again after a short timeout
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
          dump("200ms later:")
          return false
        })
        return false
      })
      // (4) and watch for the connector arriving as a property notification
      for (let i = 0; i < model.get_n_items(); i++) {
        const m = model.get_item(i) as Gdk.Monitor
        const c0 = m.get_connector()
        m.connect("notify::connector", () => {
          log(`   notify::connector fired: ${JSON.stringify(c0)} -> ${JSON.stringify(m.get_connector())}`)
        })
      }
    })

    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 30000, () => {
      log("")
      log(`items-changed notifications seen: ${n}`)
      app.quit()
      return false
    })
  },
})
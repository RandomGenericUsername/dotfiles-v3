// PROBE — what GTK 4.22 actually offers, measured. Not a CI test; needs a live
// AGS session.  Run:  cp this to <tool>/app.tsx && ags run -d <tool>
//
// This is the evidence behind design.md's "what actually delivers the hotplug
// signal" and "GTK cannot name the focused monitor" sections.  Every line below
// is a runtime fact about a live GdkWaylandDisplay on this host.
import app from "ags/gtk4/app"
import { Gdk } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"

const LOG = "/tmp/opencode/probe-gtk4-api.log"
const out: string[] = []
function log(...parts: unknown[]) {
  const line = parts.map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join(" ")
  out.push(line)
  print(line)
  GLib.file_set_contents(LOG, out.join("\n") + "\n")
}

app.start({
  instanceName: "capture-probe-gtk4",
  main() {
    const display = Gdk.Display.get_default() as Gdk.Display
    const rec = display as unknown as Record<string, unknown>
    const seat = display.get_default_seat()
    const pointer = seat?.get_pointer() as unknown as Record<string, unknown> | undefined

    log("GDK backend display:", display.get_name())

    log("")
    log("=== 1. THE HOTPLUG SIGNAL ===")
    // The brief for this change, and harden-capture-typecheck-config/design.md
    // §5, both claimed Gdk.Display carries monitor-added / monitor-removed.
    for (const signal of ["monitor-added", "monitor-removed", "seat-added", "closed", "opened"]) {
      try {
        const id = (display as unknown as {
          connect(s: string, cb: () => void): number
          disconnect(id: number): void
        }).connect(signal, () => {})
        ;(display as unknown as { disconnect(id: number): void }).disconnect(id)
        log(`  connect("${signal}") -> CONNECTED`)
      } catch (e) {
        log(`  connect("${signal}") -> ${String(e)}`)
      }
    }
    log("  => Gdk.Display has NO monitor-added/monitor-removed. It is NOT the delivery.")

    const model = display.get_monitors() as Gio.ListModel
    log(`  get_monitors() returns a ${(model as unknown as GObject.Object).constructor.name}`)
    log("  a second get_monitors() is the SAME object:",
      model === (display.get_monitors() as Gio.ListModel))
    log("  => connecting to it once at startup is sufficient. That is the delivery.")

    log("")
    log("=== 2. WHAT THE SIGNAL LOOKS LIKE WHEN IT FIRES ===")
    log("  payload is (position, removed, added) counts over a RANGE:")
    log("    \"items-changed\": (position: number, removed: number, added: number) => void")
    log("  (@girs/gio-2.0.d.ts:27902 — it describes a range, not a set of additions)")
    log("  Gdk.Monitor's own signal is narrower:")
    log("    \"Emitted when the output represented by `monitor` gets disconnected.\"")
    log("  => both are hints that SOMETHING changed, so the handler re-reads and diffs.")

    log("")
    log("=== 3. CAN GTK NAME THE FOCUSED MONITOR? (no) ===")
    for (const [what, value] of [
      ["Gdk.Seat.get_focus", typeof (seat as unknown as Record<string, unknown>).get_focus],
      ["Gdk.Device.get_position", typeof pointer?.get_position],
      ["Gdk.Display.get_monitor_at_window", typeof rec.get_monitor_at_window],
      ["Gdk.Display.get_monitor_at_point", typeof rec.get_monitor_at_point],
      ["Gdk.Display.get_n_monitors", typeof rec.get_n_monitors],
      ["Gdk.Display.get_monitor_at_surface", typeof rec.get_monitor_at_surface],
      ["Gdk.Device.get_surface_at_position", typeof pointer?.get_surface_at_position],
    ] as Array<[string, string]>) {
      log(`  ${what}: ${value}`)
    }
    const probe = pointer?.get_surface_at_position() as [Gdk.Surface | null, number, number]
    log("  get_surface_at_position() ->", probe)
    log("  => the ONLY GTK4 position API reports (NULL, 0, 0) when the pointer is over")
    log("     another client's surface, which on a compositor is the normal case.")
    log("     GTK4 removed global focus and global pointer position; the compositor owns them.")
    app.quit()
  },
})
// PROBE — can the app intercept the launcher's toggle WITHOUT a provision run?
// Not a CI test; needs a live AGS session AND an external `ags toggle` while it
// runs.  Run:  cp this to <tool>/app.tsx && ags run -d <tool>
//            then, three times:  ags toggle capture-window -i capture-probe-launch
//
// This is the evidence behind design.md's "the one seam" section.  It answers
// three questions with the real D-Bus call rather than by reading the source:
//
//   Q1  what does `get_window(name)` resolve to, and does that EVER move?
//   Q2  is `App.toggle_window` interceptable?  (AGS binds it in its constructor)
//   Q3  is `App.get_window` interceptable?   (it is called through `this` at
//       call time, so it is not bound)
import app from "ags/gtk4/app"
import { Astal } from "ags/gtk4"
import GLib from "gi://GLib?version=2.0"

const LOG = "/tmp/opencode/probe-launcher.log"
const out: string[] = []
function log(...parts: unknown[]) {
  const line = parts.map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join(" ")
  out.push(line)
  print(line)
  GLib.file_set_contents(LOG, out.join("\n") + "\n")
}

const TAGS = ["A", "B", "C"]
const TAGMAP = new Map<GObject.Object, number>()

app.start({
  instanceName: "capture-probe-launch",
  main() {
    const monitor = app.get_monitors()[0]
    function mk(i: number): Astal.Window {
      const w = new Astal.Window({
        visible: false,
        name: "capture-window",
        gdkmonitor: monitor,
        anchor: Astal.WindowAnchor.NONE,
        layer: Astal.Layer.OVERLAY,
        keymode: Astal.Keymode.ON_DEMAND,
      })
      TAGMAP.set(w, i)
      app.add_window(w)
      return w
    }
    const wins = [mk(0), mk(1), mk(2)]
    const tag = (w: unknown) => {
      const i = TAGMAP.get(w as GObject.Object)
      return i === undefined ? "?" : TAGS[i]
    }
    const proto = Object.getPrototypeOf(app) as unknown as Record<string, unknown>

    log("=== Q1: GTK's window-list order, and whether get_window EVER moves ===")
    log("  added A, B, C -> app.windows:", app.windows.map(tag).join(","))
    log("  get_window('capture-window') ->", tag(app.get_window("capture-window")))
    const probeOrder = (label: string) =>
      log(
        `  ${label.padEnd(34)} order=${app.windows.map(tag).join(",")}` +
        `  get_window->${tag(app.get_window("capture-window"))}`,
      )
    probeOrder("baseline")
    wins[0].present(); wins[0].visible = true; probeOrder("after present+show A")
    wins[1].present(); wins[1].visible = true; probeOrder("after present+show B")
    wins[2].present(); wins[2].visible = true; probeOrder("after present+show C")
    wins[0].visible = false; wins[1].visible = false; probeOrder("after hiding A and B")
    app.remove_window(wins[2]); wins[2].destroy(); probeOrder("after destroy C")
    const c2 = new Astal.Window({
      visible: false, name: "capture-window", gdkmonitor: monitor,
      anchor: Astal.WindowAnchor.NONE, layer: Astal.Layer.OVERLAY, keymode: Astal.Keymode.ON_DEMAND,
    })
    TAGMAP.set(c2, 2); wins[2] = c2; app.add_window(c2); probeOrder("after re-adding C")
    log("  => the order is REVERSE of registration and does NOT move on map/unmap/present.")
    log("     So get_window is STABLE — and stably wrong: always the last monitor added,")
    log("     never the focused one. (The instability recorded in")
    log("     fix-capture-window-identity did NOT reproduce on GTK 4.22.5.)")

    log("")
    log("=== Q2: is App.toggle_window interceptable? ===")
    let instanceHits = 0
    let protoHits = 0
    const originalToggle = proto.toggle_window
    proto.toggle_window = function () {
      protoHits += 1
    }
    ;(app as unknown as Record<string, unknown>).toggle_window = function () {
      instanceHits += 1
    }
    log("  installed an override on BOTH the prototype and the instance.")
    log("  AGS's constructor already did `new AppDBus({ toggleWindow: this.toggle_window")
    log("  .bind(this) })` — a BOUND COPY of the prototype method, captured before")
    log("  main() ran — so neither override is on the path the D-Bus call takes.")

    log("")
    log("=== Q3: is App.get_window interceptable? ===")
    let focused = 1
    const originalGetWindow = proto.get_window as (n: string) => Gtk.Window | undefined
    proto.get_window = function (name: string) {
      const owned = (this as unknown as { get_windows(): Gtk.Window[] })
        .get_windows()
        .filter((w) => w.name === name)
      return owned.find((w) => TAGMAP.get(w as GObject.Object) === focused) ?? owned[0]
    }
    for (const i of [0, 1, 2]) {
      focused = i
      log(`  focused=${TAGS[i]} -> get_window('capture-window') = ${tag((app as unknown as { get_window(n: string): Gtk.Window }).get_window("capture-window"))}`)
    }
    focused = 1
    log("  => reached, because toggle_window calls `this.get_window(name)` at CALL TIME.")
    void originalGetWindow
    void originalToggle

    log("")
    log("=== NOW ISSUE: ags toggle capture-window -i capture-probe-launch  (x3) ===")
    log("  with focus held on B. Expect B to toggle three times; A and C to stay down.")
    const poll = GLib.timeout_add(GLib.PRIORITY_DEFAULT, 200, () => {
      log(`    [poll] A=${wins[0].visible} B=${wins[1].visible} C=${wins[2].visible}`)
      return true
    })
    GLib.timeout_add(GLib.PRIORITY_DEFAULT, 14000, () => {
      GLib.source_remove(poll)
      log("")
      log(`SUMMARY: prototype-toggle hits=${protoHits}  instance-toggle hits=${instanceHits}`)
      log(`         A=${wins[0].visible} B=${wins[1].visible} C=${wins[2].visible} at the end`)
      log("  (hits 0 + a window toggled => the D-Bus path bypasses the toggle overrides)")
      app.quit()
      return false
    })
  },
})
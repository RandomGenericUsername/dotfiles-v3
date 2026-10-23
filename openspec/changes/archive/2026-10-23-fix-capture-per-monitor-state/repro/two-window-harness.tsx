// REPRO HARNESS — not part of the repo. Constructs TWO ClassicWindow instances
// (as app.tsx does per monitor) against ONE injected state, and drives them
// through the scripted sequence that clobbered the pre-fix build.
import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import { Gtk } from "ags/gtk4"
import style from "./style.css"
import { glibSettingsStore } from "./adapters/glib-settings-store"
import { glibUiStateStore } from "./adapters/glib-ui-state-store"
import { createUiState } from "./domain/ui-state"
import type { CapturePorts } from "./ports/capture-ports"
import { ClassicWindow } from "./ui/classic/ClassicWindow"

const LOG = "/tmp/opencode/repro/run.log"
const out: string[] = []
function log(...parts: unknown[]) {
  const line = parts.map((p) => (typeof p === "string" ? p : JSON.stringify(p))).join(" ")
  out.push(line)
  print(line)
  GLib.file_set_contents(LOG, out.join("\n") + "\n")
}

function fileContents(): string {
  const path = `${GLib.getenv("XDG_STATE_HOME")}/capture-tool/capture-ui.json`
  const [ok, bytes] = GLib.file_get_contents(path)
  return ok ? new TextDecoder().decode(bytes) : "<no file>"
}

function walk(w: GObject.Object): GObject.Object[] {
  const out: GObject.Object[] = [w]
  let child = w.get_first_child?.()
  while (child) {
    out.push(...walk(child))
    child = child.get_next_sibling()
  }
  return out
}

function classes(w: GObject.Object): string[] {
  return w.get_css_classes() as string[]
}

function findTarget(win: GObject.Object, label: string): Gtk.Button {
  for (const w of walk(win)) {
    if (!(w instanceof Gtk.Button)) continue
    if (!classes(w).includes("target")) continue
    if (walk(w).some((c) => c instanceof Gtk.Label && c.label === label)) return w
  }
  throw new Error(`no target button "${label}"`)
}

function findPrimary(win: GObject.Object): Gtk.Button {
  for (const w of walk(win)) {
    if (w instanceof Gtk.Button && classes(w).includes("primary")) return w
  }
  throw new Error("no primary button")
}

function selectedTarget(win: GObject.Object): string {
  for (const w of walk(win)) {
    if (w instanceof Gtk.Button && classes(w).includes("target") && classes(w).includes("selected"))
      return (walk(w).find((c) => c instanceof Gtk.Label && c.label) as Gtk.Label).label
  }
  return "<none>"
}

const ports: CapturePorts = {
  settingsStore: glibSettingsStore(),
  uiStateStore: glibUiStateStore(),
  launcher: { launch(argv: string[]) { log("   launcher argv:", JSON.stringify(argv)) } },
  backendProbe: { backend: async () => "stub" },
}

function after(ms: number, fn: () => void) {
  GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
    fn()
    return false
  })
}

app.start({
  instanceName: "capture-repro",
  css: style,
  main() {
    const monitors = app.get_monitors()
    log(`monitors: ${monitors.length}`)
    const monitor = monitors[0]
    // EXACTLY what app.tsx does per monitor -- one state, two windows.
    const state = createUiState()
    const a = ClassicWindow(monitor, ports, state)
    app.add_window(a)
    const b = ClassicWindow(monitor, ports, state)
    app.add_window(b)
    log(`windows named capture-window: ${app.windows.filter((w) => w.name === "capture-window").length}`)

    after(400, () => {
      log("STEP 1: show window A")
      a.visible = true
    })
    after(900, () => {
      log("STEP 2: show window B")
      b.visible = true
    })
    after(1400, () => {
      log("STEP 3: on window A pick Screen, then capture")
      findTarget(a, "Screen").emit("clicked")
      log("   A selected:", selectedTarget(a), " B selected:", selectedTarget(b))
      findPrimary(a).emit("clicked")
      log("   state file after A capture:", fileContents())
    })
    after(1900, () => {
      log("STEP 4: re-show A (map -> reload from disk)")
      a.visible = true
      log("   A selected:", selectedTarget(a))
    })
    after(2400, () => {
      log("STEP 5: on window B pick Window, then capture")
      findTarget(b, "Window").emit("clicked")
      log("   A selected:", selectedTarget(a), " B selected:", selectedTarget(b))
      findPrimary(b).emit("clicked")
      log("   state file after B capture:", fileContents())
    })
    after(3000, () => {
      log("STEP 6: re-show A")
      a.visible = true
    })
    after(3500, () => {
      log("   A selected:", selectedTarget(a))
      log("   state file:", fileContents())
      log("STEP 7: press capture on window A (whose highlight says Screen, state says window)")
      findPrimary(a).emit("clicked")
      log("   state file after A capture:", fileContents())
      app.quit()
    })
  },
})

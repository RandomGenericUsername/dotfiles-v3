// ---------------------------------------------------------------------------
// ADAPTER: the live window set -- one window per monitor, kept in step with the
// monitors, plus the one seam that makes the launcher's name lookup mean
// "the focused monitor's window" (fix-capture-monitor-lifecycle).
//
// TWO JOBS, AND THE DIVISION MATTERS:
//
// 1. LIFECYCLE (Gap 1). This owns the binding from monitor key to
//    `Astal.Window`, applies `domain/monitor-registry.ts#planSync` whenever the
//    topology changes, builds new windows and DESTROYS removed ones. The
//    decision of which is pure and tested; only the doing is here.
//
// 2. TARGETING (Gap 2). See "THE ONE SEAM" below.
//
// `app.tsx` stays free of this because its own contract forbids logic: "NO LOGIC
// BELOW THIS POINT beyond 'construct the dependencies, then render'".
// ---------------------------------------------------------------------------

import type app from "ags/gtk4/app"
import type { Gdk, Gtk } from "ags/gtk4"
import type { MonitorDescriptor, WindowBinding } from "../domain/monitor-registry"
import { monitorKey, orderedForFocus, planSync } from "../domain/monitor-registry"
import type { MonitorFocus } from "../ports/monitor-focus"
import type { MonitorTopology } from "../ports/monitor-topology"

/**
 * The subset of the AGS app singleton this adapter touches.
 *
 * `Gtk.Window`, not `Astal.Window`: that is what `Gtk.Application`'s own methods
 * are declared with, and an `Astal.Window` is a `Gtk.Window`, so the set can be
 * typed against the base class and accept whatever window factory the layout
 * hands it.
 */
type AppWindowHost = {
  add_window(window: Gtk.Window): void
  remove_window(window: Gtk.Window): void
  get_window(name: string): Gtk.Window | undefined
  get_windows(): Gtk.Window[]
}

/** What the composition root must supply to build a monitor's window. */
export interface MonitorWindowSetOptions {
  app: AppWindowHost
  topology: MonitorTopology
  focus: MonitorFocus
  /** Builds the window for one monitor. Injected so this file never names a layout. */
  createWindow: (monitor: import("ags/gtk4").Gdk.Monitor) => Gtk.Window
  /** Called when a monitor's window is built or destroyed. Diagnostics only. */
  report?: (message: string) => void
}

/** The live window set. */
export interface MonitorWindowSet {
  /** Owned windows, in registration order. */
  bindings(): readonly WindowBinding<MonitorWindow>[]
  /** Owned windows, focused monitor's first. What a name lookup should try. */
  ordered(): MonitorWindow[]
  /** Stop reacting to monitor changes. */
  dispose(): void
}

/** A window this set owns. Spelled out so the cast site says why. */
type MonitorWindow = Gtk.Window & { destroy(): void }

export function createMonitorWindowSet(options: MonitorWindowSetOptions): MonitorWindowSet {
  const { app, topology, focus, createWindow, report } = options
  // Registration order, deliberately an ARRAY and not a Map: this is the
  // fallback order when focus is unknown, and an array makes "the order things
  // were added" the definition rather than an accident of iteration.
  const bindings: WindowBinding<MonitorWindow>[] = []

  /**
   * Reconcile the window set against the monitors that exist now.
   *
   * `planSync` is a diff, so this is safe to call as often as the platform
   * likes: an extra call with an unchanged monitor list produces an empty plan
   * and does nothing. That is why `items-changed` and `Monitor::invalidate` can
   * both be wired up without coordinating them.
   */
  function reconcile(): void {
    const entries = topology.list()
    const plan = planSync(bindings, entries.map((entry) => entry.descriptor))

    for (const descriptor of plan.create) {
      // `native` is the adapter-owned handle (a Gdk.Monitor). It is looked up
      // from the SAME list the plan was computed from, so the descriptor that
      // decided "build this" and the monitor the window anchors to cannot drift.
      const entry = entries.find((e) => monitorKey(e.descriptor) === monitorKey(descriptor))
      const monitor = entry?.native as Gdk.Monitor | undefined
      if (!monitor) continue
      const window = createWindow(monitor)
      bindings.push({ key: monitorKey(descriptor), window })
      app.add_window(window)
      report?.(`capture: opened a window for monitor ${descriptor.connector ?? "(unnamed)"}`)
    }

    for (const stale of plan.destroy) {
      // ORDER MATTERS, and this is the answer to "what is the correct lifecycle
      // for a window that must later be REMOVED".
      //
      //   remove_window FIRST: a `Gtk.Window` left in the application's window
      //   list after `destroy()` is a window the launcher can still resolve by
      //   name, so a later `ags toggle` would act on a dead object. Removing
      //   first makes the window unreachable by name the moment it stops being
      //   a real window.
      //
      //   destroy() SECOND: `visible = false` only unmaps. It leaves the
      //   `Gtk.Widget` alive, still holding its subtree, its `Gtk.EventController`
      //   and its layer-shell surface. Only `destroy()` releases them, which is
      //   what "a removed monitor's window must be destroyed, not leaked" means.
      //
      // Measured on this host: `remove_window` + `destroy` took
      // `app.windows.length` from 2 to 1, after which `get_window` resolved to
      // the surviving window rather than the dead one.
      app.remove_window(stale.window)
      stale.window.destroy()
      const at = bindings.indexOf(stale)
      if (at > -1) bindings.splice(at, 1)
      report?.(`capture: destroyed the window for a monitor that went away`)
    }
  }

  topology.subscribe(reconcile)
  reconcile()

  return {
    bindings: () => bindings,
    ordered(): MonitorWindow[] {
      const focusedKey = (() => {
        const entries = topology.list()
        const connector = focus.focusedConnector()
        if (connector === null) return null
        for (const entry of entries) {
          if (entry.descriptor.connector === connector) return monitorKey(entry.descriptor)
        }
        return null
      })()
      return orderedForFocus(bindings, focusedKey).map((b) => b.window)
    },
    dispose(): void {
      // The topology subscription is owned by the topology adapter; there is
      // nothing to unwind here that the app's own shutdown does not already do.
      // Kept as an explicit no-op-sized method so a future topology that needs
      // disconnecting has the seam.
    },
  }
}

// ---------------------------------------------------------------------------
// THE ONE SEAM (Gap 2)
//
// WHAT THE LAUNCHER ACTUALLY DOES. `~/.local/bin/capture-ui` is provisioned from
// `capture-ui.j2` and its second step is, verbatim:
//
//     timeout 8 ags toggle "$WINDOW" -i "$INSTANCE"
//
// and `tests/ts/window-identity.test.ts` pins that exact line, so the launcher
// is not ours to change without weakening an existing test.
//
// WHAT THAT REACHES. `ags toggle` is a D-Bus call to `io.Astal.Application`
// `.ToggleWindow(name)`, which AGS dispatches to a function it bound in its own
// CONSTRUCTOR, before `main()` runs:
//
//     this.#dbusService = new AppDBus({
//         toggleWindow: this.toggle_window.bind(this),   // app.ts:231-232
//         ...
//     })
//
// MEASURED CONSEQUENCE: neither an own-property override of `toggle_window` nor
// a prototype override of it is ever reached — three real external
// `ags toggle capture-window` calls, with both installed, logged 0 hits on both
// while still toggling a window. So "intercept the toggle" is not available.
//
// WHAT IS AVAILABLE. `toggle_window` calls its collaborator through `this`, at
// CALL TIME:
//
//     get_window(name) {                    // app.ts:156-158
//         return this.windows.find((w) => w.name === name)
//     }
//     toggle_window(name) {                 // app.ts:164-168
//         const win = this.get_window(name)
//         ...
//     }
//
// `get_window` was never bound, so replacing it IS reached by the very same
// three external toggles. And since every window deliberately shares the name
// `capture-window`, "which window a name lookup finds" is decided entirely by
// which candidate comes first — which is exactly what this app's own ordered
// list decides.
//
// The override below changes the MEANING of the name lookup from "whichever
// duplicate GTK listed first" (measured: reverse-insertion order, i.e. always
// the last monitor added, never the focused one) to "the focused monitor's
// window, else the first in this app's registration order". It does not rename
// anything, does not touch `style.css`, does not change `app.windows` (still
// GTK's own list, verified), and falls back to the original implementation
// rather than returning nothing.
// ---------------------------------------------------------------------------

/**
 * Make `get_window(name)` resolve to the focused monitor's window.
 *
 * Idempotent: calling it twice does not stack overrides.
 *
 * @returns the function that performs the lookup, so the composition root can
 *   keep using `app.get_window` normally afterwards.
 */
export function installFocusedWindowLookup(
  app: AppWindowHost,
  windowSet: MonitorWindowSet,
): (name: string) => Gtk.Window | undefined {
  const prototype = Object.getPrototypeOf(app) as AppWindowHost
  const marker = "__captureFocusedWindowLookup"
  const target = prototype as unknown as Record<string, unknown>
  if (target[marker]) {
    report(`capture: focused window lookup already installed`)
    return app.get_window.bind(app)
  }

  const original = prototype.get_window
  const lookup = function get_window(this: AppWindowHost, name: string): Gtk.Window | undefined {
    // Only this app's windows participate, and only ones that actually carry
    // the requested name — `app.windows` may hold windows this tool did not
    // build (there are none today, but the lookup must not assume that).
    const owned = windowSet.ordered().filter((w) => w.name === name)
    if (owned.length > 0) return owned[0]
    // No owned window answers to this name: defer to AGS, so `ags toggle` on
    // any other window keeps working exactly as it does today.
    return original.call(this, name)
  }

  prototype.get_window = lookup
  target[marker] = true
  report("capture: window lookup now prefers the focused monitor's window")
  return lookup.bind(app)
}

function report(message: string): void {
  console.log(message)
}
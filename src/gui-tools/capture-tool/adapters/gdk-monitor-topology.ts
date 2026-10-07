// ---------------------------------------------------------------------------
// ADAPTER: the monitor topology, read from Gdk.Display (fix-capture-monitor-lifecycle).
//
// WHAT ACTUALLY DELIVERS MONITOR HOTPLUG ON THIS STACK, measured rather than
// assumed. The brief for this change guessed "Gdk/GObject `monitor-added` /
// `monitor-removed` signals on Gdk.Display". That guess is WRONG, and so was the
// recorded version of it in
// openspec/changes/harden-capture-typecheck-config/design.md §5, which asserts
// "GTK/GdkMonitor carries a `monitor-added`/`monitor-removed` signal pair".
//
// Measured, connecting to a live `GdkWaylandDisplay` (GTK 4.22.5):
//
//   monitor-added   -> Error: No signal 'monitor-added' on object 'GdkWaylandDisplay'
//   monitor-removed -> Error: No signal 'monitor-removed' on object 'GdkWaylandDisplay'
//   seat-added      -> CONNECTED
//   closed          -> CONNECTED
//   opened          -> CONNECTED
//
// `Gdk.Display`'s complete signal set, from /usr/share/gir-1.0/Gdk-4.0.gir:
//
//   closed, opened, seat-added, seat-removed, setting-changed
//
// So there is no add/remove signal on `Gdk.Display` to connect to. What DOES
// exist is a model, and GDK documents it:
//
//   /** Gets the list of monitors associated with this display.
//    *  Subsequent calls to this function will always return the
//    *  same list for the same display.
//    *  You can listen to the GListModel::items-changed signal on this list to
//    *  monitor changes to the monitor of this display.
//    *  @returns a {@link Gio.ListModel} of {@link Gdk.Monitor} */
//   get_monitors(): Gio.ListModel;
//
// (src/gui-tools/capture-tool/@girs/gdk-4.0.d.ts:18037-18046; same text in
// /usr/share/gir-1.0/Gdk-4.0.gir.) Confirmed at runtime: the returned object is a
// `Gio_ListStore`, and two `get_monitors()` calls return the SAME object, which
// is what makes connecting to it once at startup sufficient.
//
// AGS independently relies on exactly this, in its own App constructor:
//
//   this.#display.get_monitors().connect("items-changed", () => {
//       this.notify("monitors")
//   })
//
// (/usr/share/ags/js/lib/gtk4/app.ts:240-242.) This adapter does NOT subscribe to
// that `notify("monitors")` re-emission: it is AGS' own convenience, not GDK's
// contract, and connecting to the documented `items-changed` means this file has
// one fewer third-party behaviour to depend on.
//
// `Gdk.Monitor::invalidate` ("Emitted when the output represented by `monitor`
// gets disconnected.") is connected as well. It is redundant with
// `items-changed` on purpose: it is idempotent because the handler re-reads and
// diffs, and it covers a compositor that invalidates a monitor before the model
// drops it.
// ---------------------------------------------------------------------------

import type { Gdk } from "ags/gtk4"
import type Gio from "gi://Gio?version=2.0"
import type { MonitorGeometry } from "../domain/monitor-registry"
import type { MonitorEntry, MonitorTopology } from "../ports/monitor-topology"

/** `Gdk.Rectangle` is four plain numbers; this is the domain's shape for them. */
function geometryOf(monitor: Gdk.Monitor): MonitorGeometry {
  const rect = monitor.get_geometry()
  return { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
}

function entryOf(monitor: Gdk.Monitor): MonitorEntry {
  return {
    descriptor: {
      connector: monitor.get_connector(),
      model: monitor.get_model() ?? "",
      manufacturer: monitor.get_manufacturer() ?? "",
      geometry: geometryOf(monitor),
    },
    native: monitor,
  }
}

/**
 * The live monitor list, from `Gdk.Display`.
 *
 * @param display the display to watch; `Gdk.Display.get_default()` in the
 *   composition root. Passing it in rather than looking it up keeps this
 *   adapter a reader, so a test could hand it a stand-in.
 */
export function gdkMonitorTopology(display: Gdk.Display): MonitorTopology {
  // `get_monitors()` returns the SAME Gio.ListModel for the same display on
  // every call (documented above, and verified at runtime), so holding this one
  // reference is both sufficient and required: connecting to a fresh list would
  // be connecting to an object nothing else ever emits from.
  const model = display.get_monitors() as Gio.ListModel

  // Monitors whose per-monitor hooks are already installed. A WeakSet, not a
  // Set: a removed monitor must not be kept alive by this adapter, and GTK owns
  // every monitor's lifetime anyway.
  const hooked = new WeakSet<Gdk.Monitor>()

  function list(): MonitorEntry[] {
    const entries: MonitorEntry[] = []
    for (let i = 0; i < model.get_n_items(); i++) {
      const monitor = model.get_item(i) as Gdk.Monitor
      if (monitor) entries.push(entryOf(monitor))
    }
    return entries
  }

  /**
   * Install the per-monitor hooks for any monitor not yet hooked.
   *
   * Called on every notification AND from `list()`, so a monitor that appears
   * later is hooked when the notification that announced it arrives. The
   * WeakSet makes repeat calls free.
   */
  function hookMonitors(onChange: () => void): void {
    for (let i = 0; i < model.get_n_items(); i++) {
      const monitor = model.get_item(i) as Gdk.Monitor
      if (!monitor || hooked.has(monitor)) continue
      hooked.add(monitor)
      // Disconnect. Carries no arguments ("Emitted when the output represented
      // by `monitor` gets disconnected.") and says only that this one monitor
      // is going away -- the same information `items-changed` delivers.
      monitor.connect("invalidate", () => onChange())
      // IDENTITY ARRIVING LATE. Measured: at the instant a hotplug notification
      // fires, a new monitor reports connector=null, model="" and geometry
      // 0,0,0,0; `notify::connector` lands a few hundred ms later with the real
      // name (see `domain/monitor-registry.ts#isIdentified`). Until then the
      // domain deliberately builds no window for it, so this notification is
      // what causes the window to be built -- once, with the right key, instead
      // of once with a throwaway key and again once the key changed.
      monitor.connect("notify::connector", () => onChange())
      // A mode change. The key deliberately excludes geometry, so this is a
      // no-op reconcile in practice; it is wired because it is the same kind of
      // "a property of a monitor settled" event and costs one diff.
      monitor.connect("notify::geometry", () => onChange())
    }
  }

  function subscribe(onChange: () => void): void {
    hookMonitors(onChange)

    // The one signal GDK documents for this. Payload is deliberately ignored:
    // it is (position, removed, added) counts over a range, and the domain
    // reconciles against the full set instead of applying the delta.
    //
    // The cast: `@girs` types `Gio.ListModel`'s `connect` through the generic
    // `ListModel.Interface<A>` helper, which resolves `SignalSignatures` to
    // `GObject.Object`'s and drops the interface's own signals — so
    // `"items-changed"` is rejected by the compiler even though the signal
    // exists and is documented. The SAME error occurs in AGS's own
    // /usr/share/ags/js/lib/gtk4/app.ts:240, where it is one of the 28 tolerated
    // third-party errors. Re-declaring the signal we rely on is the fix; it
    // changes no runtime behaviour, and the signature below is copied verbatim
    // from @girs/gio-2.0.d.ts:27902.
    ;(model as unknown as {
      connect(signal: "items-changed", cb: (position: number, removed: number, added: number) => void): number
    }).connect("items-changed", () => {
      // Wire first, then notify: a monitor that has just appeared must have its
      // per-monitor hooks in place before anything reads it, and the identity
      // that `isIdentified` waits for arrives on exactly those hooks.
      hookMonitors(onChange)
      onChange()
    })
  }

  return { list, subscribe }
}
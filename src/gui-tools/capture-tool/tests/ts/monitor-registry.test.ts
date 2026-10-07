// ---------------------------------------------------------------------------
// Monitor LIFECYCLE + LAUNCHER TARGETING tests (fix-capture-monitor-lifecycle).
//
// Two bugs are pinned here, and both were deferred by earlier changes as
// "behavioural changes to window lifecycle, out of scope for a typecheck".
//
//  GAP 1 -- no hotplug handler. `app.tsx` read `app.get_monitors()` once inside
//  `main()` and looped. A monitor plugged in after login got NO window; a
//  monitor unplugged kept its window alive and still resolvable by name.
//
//  GAP 2 -- the launcher opened the WRONG monitor's window. Every window
//  deliberately shares the name `capture-window` (style.css selects it with the
//  GTK id selector `window#capture-window`, and the provisioned launcher toggles
//  it by that name), so which window a name lookup reaches is decided purely by
//  which candidate comes first. `App.get_window` is `windows.find(...)` over
//  GTK's own window list.
//
// MEASURED on this host, GTK 4.22.5 / ags 3.1.2, three real external
// `ags toggle capture-window -i <instance>` calls against three live windows
// built in the order A, B, C:
//
//     app.windows order                get_window("capture-window") resolved to
//     C,B,A  (never changed)           C
//
// That order did NOT move across present(), visible=true and visible=false on
// each window in turn, nor across destroy+re-add. So the recorded instability in
// window-identity.test.ts ("B,A before any map, A,B after window A had mapped and
// unmapped") does NOT reproduce here; what reproduces is worse in the sense
// that matters: the answer is STABLE and it is always the LAST window added, so
// on a real multi-monitor host the panel opens on one fixed monitor forever and
// never on the focused one. The fix therefore does not restore an ordering
// property -- there is none to restore -- it makes the lookup consult a list
// this app owns.
//
// WHAT IS AND IS NOT TESTABLE HERE. `app.tsx`, the adapters and
// `ClassicWindow` all import `ags/gtk4` / `gi://*`, which `node --test` cannot
// load. What IS reachable, and what carries the decisions:
//
//   1. `domain/monitor-registry.ts` EXECUTED -- the real module. planSync,
//      orderedForFocus, focusKey and monitorKey are the whole of both fixes'
//      decision content, and they are pure precisely because the hexagon the
//      refactor established pushed them there.
//   2. the negative control: a faithful model of what `App.get_window` does over
//      GTK's measured list order, so the test would fail if someone "fixed" the
//      bug by ordering a list they do not control.
//   3. the WIRING, read from the real source: the subscription exists, the
//      destroy path is remove-then-destroy, the shared name survives, and
//      `style.css` still selects it.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"
import { readFileSync } from "node:fs"
import { fileURLToPath } from "node:url"

import {
  focusKey,
  isIdentified,
  monitorKey,
  orderedForFocus,
  planSync,
  type MonitorDescriptor,
  type WindowBinding,
} from "../../domain/monitor-registry.ts"

const APP = fileURLToPath(new URL("../../app.tsx", import.meta.url))
const TOPOLOGY = fileURLToPath(
  new URL("../../adapters/gdk-monitor-topology.ts", import.meta.url),
)
const WINDOW_SET = fileURLToPath(
  new URL("../../adapters/monitor-window-set.ts", import.meta.url),
)
const WINDOW = fileURLToPath(new URL("../../ui/classic/ClassicWindow.tsx", import.meta.url))
const CSS = fileURLToPath(new URL("../../style.css", import.meta.url))

function code(path: string): string {
  return readFileSync(path, "utf8")
    .split("\n")
    .filter((line) => !line.trimStart().startsWith("//"))
    .join("\n")
}

function monitor(connector: string | null, over: Partial<MonitorDescriptor> = {}): MonitorDescriptor {
  return {
    connector,
    model: "0x153C",
    manufacturer: "Chimei Innolux Corporation",
    geometry: { x: 0, y: 0, width: 1920, height: 1080 },
    ...over,
  }
}

/** A stand-in for `Astal.Window`; the domain is generic and never inspects it. */
interface FakeWindow {
  tag: string
  name: string
  visible: boolean
  destroyed: boolean
}

function fakeWindow(tag: string): FakeWindow {
  return { tag, name: "capture-window", visible: false, destroyed: false }
}

function binding(tag: string, connector: string | null): WindowBinding<FakeWindow> {
  return { key: monitorKey(monitor(connector)), window: fakeWindow(tag) }
}

// ---------------------------------------------------------------------------
// 1. planSync -- what a monitor change means (Gap 1)
// ---------------------------------------------------------------------------

test("planSync creates for every monitor and destroys nothing on first run", () => {
  const plan = planSync<number>([], [monitor("eDP-1"), monitor("HDMI-2")])
  assert.equal(plan.create.length, 2)
  assert.deepEqual(plan.create.map((m) => m.connector), ["eDP-1", "HDMI-2"])
  assert.deepEqual(plan.destroy, [])
})

test("a NEW monitor produces exactly one create and no destroy", () => {
  const owned = [binding("A", "eDP-1")]
  const plan = planSync(owned, [monitor("eDP-1"), monitor("HDMI-2")])
  assert.deepEqual(plan.create.map((m) => m.connector), ["HDMI-2"])
  assert.deepEqual(plan.destroy, [])
})

test("a REMOVED monitor produces exactly one destroy and no create", () => {
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2")]
  const plan = planSync(owned, [monitor("eDP-1")])
  assert.deepEqual(plan.create, [])
  assert.equal(plan.destroy.length, 1)
  assert.equal(plan.destroy[0].window.tag, "B")
})

test("removing EVERY monitor destroys every window (no leak on a full unplug)", () => {
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2"), binding("C", "DP-3")]
  const plan = planSync(owned, [])
  assert.deepEqual(plan.create, [])
  assert.deepEqual(plan.destroy.map((b) => b.window.tag).sort(), ["A", "B", "C"])
})

test("an unchanged monitor set is a NO-OP (this is what makes hotplug idempotent)", () => {
  // The hotplug delivery is not trustworthy about cardinality: GDK's
  // items-changed carries (position, removed, added) counts over a RANGE, and
  // this adapter ALSO connects Gdk.Monitor::invalidate, so one physical unplug
  // can arrive twice. A reconcile that is not a no-op on unchanged input would
  // build duplicate windows.
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2")]
  const list = [monitor("eDP-1"), monitor("HDMI-2")]
  for (let i = 0; i < 5; i++) {
    const plan = planSync(owned, list)
    assert.deepEqual(plan.create, [], `pass ${i} created a window`)
    assert.deepEqual(plan.destroy, [], `pass ${i} destroyed a window`)
  }
})

test("re-adding the SAME monitor reuses its key, so no stale window survives", () => {
  // Unplug then replug the same output. The window is destroyed on unplug and
  // rebuilt on replug, and the rebuilt one is keyed identically -- which is what
  // lets the launcher resolve it after the replug.
  const before = [binding("A", "eDP-1")]
  const unplug = planSync(before, [])
  assert.deepEqual(unplug.destroy.map((b) => b.window.tag), ["A"])
  const replug = planSync([], [monitor("eDP-1")])
  assert.deepEqual(replug.create.map((m) => m.connector), ["eDP-1"])
  assert.equal(monitorKey(replug.create[0]), before[0].key)
})

test("a RESOLUTION change does not re-key a monitor", () => {
  // The trap: if the key included geometry, every mode switch would read as
  // "remove this monitor, add a new one" and would destroy a window that is
  // still perfectly valid -- visibly, mid-session.
  const owned = [binding("A", "eDP-1")]
  const rescaled = monitor("eDP-1", { geometry: { x: 0, y: 0, width: 1280, height: 720 } })
  const plan = planSync(owned, [rescaled])
  assert.deepEqual(plan.create, [], "a resolution change must not rebuild the window")
  assert.deepEqual(plan.destroy, [], "a resolution change must not destroy the window")
})

test("a monitor with NO connector still gets a stable key", () => {
  // GDK documents that connector names "should not be relied on as stable
  // identifiers", and returns null when it has none. The key must still be
  // stable across a hotplug cycle, or a connector-less monitor would rebuild
  // its window on every event.
  const unnamed = monitor(null)
  assert.equal(monitorKey(unnamed), monitorKey(monitor(null)))
  assert.notEqual(monitorKey(unnamed), monitorKey(monitor("eDP-1")))
  const owned: WindowBinding<FakeWindow>[] = [{ key: monitorKey(unnamed), window: fakeWindow("A") }]
  const plan = planSync(owned, [unnamed])
  assert.deepEqual(plan.create, [])
  assert.deepEqual(plan.destroy, [])
})

test("two IDENTICAL unnamed monitors do not produce two windows for one key", () => {
  // Leak-free direction: the duplicate is dropped rather than both built.
  const a = monitor(null, { model: "Same", manufacturer: "SameCo" })
  const b = monitor(null, { model: "Same", manufacturer: "SameCo", geometry: { x: 1920, y: 0, width: 1920, height: 1080 } })
  assert.equal(monitorKey(a), monitorKey(b), "precondition: these collide")
  const plan = planSync<number>([], [a, b])
  assert.equal(plan.create.length, 1, "a key collision must build one window, not two")
})

test("a monitor with NO identity yet gets no window", () => {
  // MEASURED on this host (repro/probes/connector-timing-probe.tsx): at the
  // instant a hotplug notification fires, a newly appeared monitor reports
  // connector=null, model="", manufacturer="" and geometry 0,0,0,0. Keying it
  // then would be both useless and short-lived.
  const justArrived = monitor(null, {
    model: "",
    manufacturer: "",
    geometry: { x: 0, y: 0, width: 0, height: 0 },
  })
  assert.equal(isIdentified(justArrived), false, "precondition: nothing to key it by")
  const plan = planSync<number>([], [monitor("eDP-1"), justArrived])
  assert.deepEqual(plan.create.map((m) => m.connector), ["eDP-1"], "only the identified monitor")
  assert.deepEqual(plan.destroy, [])
})

test("TWO monitors arriving in one event do not collapse into one window", () => {
  // The measured failure this rule prevents: both report
  // geometry:0,0,0,0 at the instant of the notification, so without
  // `isIdentified` the second would be dropped as a key collision and one
  // monitor would silently get no window at all.
  const first = monitor(null, { model: "", manufacturer: "", geometry: { x: 0, y: 0, width: 0, height: 0 } })
  const second = monitor(null, { model: "", manufacturer: "", geometry: { x: 0, y: 0, width: 0, height: 0 } })
  assert.equal(monitorKey(first), monitorKey(second), "precondition: they collide while unidentified")
  assert.deepEqual(planSync<number>([], [first, second]).create, [], "no window until identified")
  // ...and once both are identified they each get their own.
  const plan = planSync<number>([], [monitor("HDMI-2"), monitor("DP-3")])
  assert.equal(plan.create.length, 2)
})

test("an unidentified monitor never causes a DESTROY", () => {
  // It must not count as "gone" — a monitor whose identity has not landed is
  // still present, and destroying its window would be a flicker, not a fix.
  const owned = [binding("A", "eDP-1")]
  const plan = planSync(owned, [monitor("eDP-1"), monitor(null, { model: "", manufacturer: "", geometry: { x: 0, y: 0, width: 0, height: 0 } })])
  assert.deepEqual(plan.destroy, [])
})

test("a monitor becomes addressed as soon as its connector lands", () => {
  // The sequence the adapter drives: unidentified, then `notify::connector`,
  // then identified. Exactly one window, built once.
  const unidentified = monitor(null, { model: "", manufacturer: "", geometry: { x: 0, y: 0, width: 0, height: 0 } })
  const identified = monitor("HEADLESS-10")
  const first = planSync<WindowBinding<FakeWindow>>([], [unidentified])
  assert.deepEqual(first.create, [], "no window while unidentified")
  const second = planSync<WindowBinding<FakeWindow>>([], [identified])
  assert.equal(second.create.length, 1)
  // And the reconcile after that is a no-op, so the window is not rebuilt.
  const third = planSync(second.create.map((d) => ({ key: monitorKey(d), window: fakeWindow("N") })), [identified])
  assert.deepEqual(third.create, [], "the window must be built once, not rebuilt when the key changes")
})

test("a swap in one pass both destroys and creates", () => {
  // Docking station unplugged and a different one plugged in between two
  // reconciles: the single diff handles it, no intermediate state needed.
  const owned = [binding("A", "eDP-1"), binding("B", "DP-3")]
  const plan = planSync(owned, [monitor("eDP-1"), monitor("HDMI-2")])
  assert.deepEqual(plan.create.map((m) => m.connector), ["HDMI-2"])
  assert.deepEqual(plan.destroy.map((b) => b.window.tag), ["B"])
})

// ---------------------------------------------------------------------------
// 2. orderedForFocus + focusKey -- which window the launcher reaches (Gap 2)
// ---------------------------------------------------------------------------

test("focusedForFocus puts the focused monitor's window FIRST", () => {
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2"), binding("C", "DP-3")]
  const key = focusKey([monitor("eDP-1"), monitor("HDMI-2"), monitor("DP-3")], "HDMI-2")
  assert.deepEqual(orderedForFocus(owned, key).map((b) => b.window.tag), ["B", "A", "C"])
})

test("focusKey matches the compositor's monitor name against the GDK connector", () => {
  // Measured agreement on this host: Gdk.Monitor.get_connector() and the
  // compositor service's focused monitor both report "eDP-1".
  const list = [monitor("eDP-1"), monitor("HDMI-2")]
  assert.equal(focusKey(list, "HDMI-2"), monitorKey(monitor("HDMI-2")))
  assert.equal(focusKey(list, "eDP-1"), monitorKey(monitor("eDP-1")))
})

test("focusKey is null when the focused monitor has NO window", () => {
  // Returning null rather than guessing is what lets the fallback be
  // deterministic instead of arbitrary.
  const list = [monitor("eDP-1")]
  assert.equal(focusKey(list, "DP-9"), null)
  assert.equal(focusKey(list, null), null)
})

test("UNKNOWN focus falls back to REGISTRATION order, deterministically", () => {
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2")]
  for (let i = 0; i < 5; i++) {
    assert.deepEqual(orderedForFocus(owned, null).map((b) => b.window.tag), ["A", "B"])
  }
})

test("focus naming a monitor this app has no window for changes nothing", () => {
  const owned = [binding("A", "eDP-1")]
  const key = focusKey([monitor("eDP-1")], "DP-9")
  assert.equal(key, null)
  assert.deepEqual(orderedForFocus(owned, key).map((b) => b.window.tag), ["A"])
})

test("orderedForFocus does not MUTATE or drop the caller's array", () => {
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2")]
  orderedForFocus(owned, monitorKey(monitor("HDMI-2")))
  assert.deepEqual(owned.map((b) => b.window.tag), ["A", "B"])
  assert.equal(owned.length, 2)
})

// ---------------------------------------------------------------------------
// 3. The negative control: what the UNFIXED lookup does (Gap 2)
// ---------------------------------------------------------------------------

/** A faithful model of AGS `App.get_window` over GTK's own window list. */
function agsLookup(windows: FakeWindow[], name: string): FakeWindow | undefined {
  return windows.find((w) => w.name === name)
}

test("NEGATIVE CONTROL: over GTK's list order the lookup ignores focus entirely", () => {
  // GTK's order, measured: reverse of registration, and it did not move across
  // present()/visible changes or a destroy+re-add. Every window shares the name,
  // so `find` returns the same one forever.
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2"), binding("C", "DP-3")]
  const gtkOrder = [owned[2].window, owned[1].window, owned[0].window] // C,B,A
  for (const focused of ["eDP-1", "HDMI-2", "DP-3"]) {
    assert.equal(agsLookup(gtkOrder, "capture-window")?.tag, "C", `focus ${focused} was ignored`)
  }
  // ...and the fixed lookup answers all three correctly.
  for (const focused of ["eDP-1", "HDMI-2", "DP-3"]) {
    const key = focusKey(
      [monitor("eDP-1"), monitor("HDMI-2"), monitor("DP-3")],
      focused,
    )
    assert.equal(orderedForFocus(owned, key)[0].window.tag,
      { "eDP-1": "A", "HDMI-2": "B", "DP-3": "C" }[focused], `focus ${focused} not honoured`)
  }
})

test("the fixed lookup reaches a DIFFERENT window per focus, the old one does not", () => {
  const owned = [binding("A", "eDP-1"), binding("B", "HDMI-2")]
  const monitors = [monitor("eDP-1"), monitor("HDMI-2")]
  const gtkOrder = [owned[1].window, owned[0].window]
  const reached = new Set<string>()
  for (const focused of ["eDP-1", "HDMI-2"]) {
    reached.add(orderedForFocus(owned, focusKey(monitors, focused))[0].window.tag)
  }
  assert.deepEqual([...reached].sort(), ["A", "B"], "both monitors must be reachable by focus")
  assert.equal(new Set([agsLookup(gtkOrder, "capture-window")?.tag]).size, 1)
})

// ---------------------------------------------------------------------------
// 4. The WIRING, read from the real source
// ---------------------------------------------------------------------------

test("app.tsx subscribes to monitor changes instead of reading the list once", () => {
  const source = code(APP)
  assert.match(
    source,
    /topology: gdkMonitorTopology\(/,
    "the composition root must hand the window set a real topology",
  )
  assert.match(
    source,
    /createMonitorWindowSet\(/,
    "the one-shot `for (const monitor of app.get_monitors())` loop must be gone from app.tsx",
  )
  assert.equal(
    /for \(const monitor of app\.get_monitors\(\)\)/.test(source),
    false,
    "app.tsx still builds windows from a one-shot monitor read",
  )
  assert.match(source, /installFocusedWindowLookup\(/, "the name lookup must be replaced")
})

test("the topology adapter subscribes to the signal GDK actually documents", () => {
  const source = code(TOPOLOGY)
  assert.match(source, /"items-changed"/, "Gdk.Display has no monitor-added/removed; the ListModel is the delivery")
  assert.match(source, /"invalidate"/, "per-monitor disconnect is wired too")
  assert.match(
    source,
    /"notify::connector"/,
    "a new monitor's connector lands AFTER items-changed (measured), and that is what lets the window be built once",
  )
  // The payload must NOT be applied as a delta: it is a (position, removed,
  // added) count over a range, and this is a diff-reconcile.
  assert.equal(
    /onChange\(\s*position|onChange\(position/.test(source),
    false,
    "the change callback must re-read and diff, not apply the items-changed payload",
  )
})

test("monitors that appear later are hooked, not just the ones present at startup", () => {
  // A `WeakSet` guard means hooking is idempotent and cannot keep a removed
  // monitor alive; the hook pass has to run on every notification for it to see
  // a monitor that did not exist when subscribe() was called.
  const source = code(TOPOLOGY)
  assert.match(source, /new WeakSet<Gdk\.Monitor>/, "per-monitor hooks must be tracked, not re-installed forever")
  const notifyHook = source.indexOf("hookMonitors(onChange)\n      onChange()")
  assert.ok(notifyHook > -1, "the items-changed handler must re-hook monitors before notifying")
})

test("a removed monitor's window is unregistered AND destroyed, in that order", () => {
  const source = code(WINDOW_SET)
  const remove = source.indexOf("remove_window(stale.window)")
  const destroy = source.indexOf("stale.window.destroy()")
  assert.ok(remove > -1, "the removed monitor's window must leave the app's window list")
  assert.ok(destroy > -1, "the removed monitor's window must be destroyed, not merely unmapped")
  assert.ok(
    remove < destroy,
    "unregister must come first: a destroyed window still in the list is one the launcher can reach by name",
  )
})

test("the bindings array is the registration order the fallback relies on", () => {
  // An array, not a Map: `orderedForFocus(null)` promises REGISTRATION order and
  // that has to be the definition, not an accident of Map iteration.
  const source = code(WINDOW_SET)
  assert.match(source, /const bindings: WindowBinding<MonitorWindow>\[\] = \[\]/)
})

test("every window still shares the name, and style.css still selects it", () => {
  // The constraint that shapes every option: `window#capture-window` is a GTK ID
  // selector, which matches the widget NAME. A per-monitor rename would kill the
  // transparency styling and revive a documented bug.
  const windowSource = code(WINDOW)
  assert.match(windowSource, /name="capture-window"/, "the shared name must survive")
  assert.equal(
    (windowSource.match(/name="capture-window"/g) ?? []).length,
    1,
    "the name must remain a single literal, shared by every monitor's window",
  )
  assert.match(
    readFileSync(CSS, "utf8"),
    /window#capture-window\b/,
    "style.css must still select the window by its name",
  )
})

test("no adapter renames a window to make it addressable", () => {
  // The rejected alternative, pinned so it stays rejected: a per-monitor unique
  // name would break `window#capture-window` AND `ags toggle capture-window`.
  for (const path of [WINDOW_SET, TOPOLOGY]) {
    assert.equal(
      /name\s*=\s*[`"'].*\$\{/.test(code(path)),
      false,
      `${path} builds a per-monitor window name`,
    )
  }
})
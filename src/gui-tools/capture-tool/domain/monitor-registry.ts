// ---------------------------------------------------------------------------
// DOMAIN: which window belongs to which monitor, and what a monitor change
// means (fix-capture-monitor-lifecycle).
//
// Two gaps are closed here, and both of their DECISIONS are pure:
//   1. monitor hotplug -- `planSync()` diffs the live monitor set against the
//      windows this app owns and says which to build and which to destroy.
//      Nothing in this module knows that GTK, a compositor or a file exists.
//   2. launcher targeting -- `orderedForFocus()` returns the owned windows in
//      the order a name lookup should try them: the focused monitor's window
//      first, then the rest in REGISTRATION order. It never reads GTK's window
//      list, so it cannot be destabilised by it.
//
// WHY A DOMAIN MODULE EXISTS AT ALL, rather than three lines in `app.tsx`:
// `app.tsx` is the composition root and its own comment forbids logic there
// ("NO LOGIC BELOW THIS POINT beyond 'construct the dependencies, then render'"),
// and this code is GTK-touching enough that it cannot be unit-tested where it
// would otherwise live. The hexagon the refactor established is what makes the
// decision testable at all: the ADAPTERS hold `Gdk.Monitor`/`Astal.Window`, and
// everything above this line sees plain data.
//
// PURE BY CONSTRUCTION: no `ags/*`, no `gi://*` (gate check 1), and no opaque
// handles either -- `WindowBinding<T>` is generic so this module never has to
// name a `Gtk.Window`.
// ---------------------------------------------------------------------------

/** A monitor's position and size, in the display's logical coordinate space. */
export interface MonitorGeometry {
  x: number
  y: number
  width: number
  height: number
}

/**
 * One monitor as plain data. Adapters build these from whatever the platform
 * calls a monitor; the domain never sees a `Gdk.Monitor`.
 */
export interface MonitorDescriptor {
  /**
   * The connector name (`eDP-1`, `HDMI-2`, ...) when the platform reports one,
   * else null.
   *
   * Measured: GDK's `gdk_monitor_get_connector` documents that connector names
   * "should not be relied on as stable identifiers of a specific monitor". It
   * is still the best key available, because it is the same string the
   * compositor reports for the same output and therefore the same string the
   * capture backend already keys on. `monitorKey()` falls back when it is null.
   */
  connector: string | null
  /** `gdk_monitor_get_model`, or "" when unknown. Part of the fallback key. */
  model: string
  /** `gdk_monitor_get_manufacturer`, or "". Part of the fallback key. */
  manufacturer: string
  geometry: MonitorGeometry
}

/** A window this app owns, tagged with the monitor key it was built for. */
export interface WindowBinding<T> {
  key: string
  window: T
}

/**
 * The identity a window is tagged with.
 *
 * Connector first, because a resolution or scale change must NOT re-key a
 * monitor: the geometry is deliberately excluded from the connector branch, or
 * every mode switch would read as "remove this monitor, add a new one" and
 * rebuild a window that is still perfectly valid.
 *
 * Without a connector the key falls back to model+manufacturer, and only then
 * to geometry. Two identical monitors with no connector name collide; the first
 * wins and `planSync` ignores the duplicate rather than leaking a window, which
 * is the safe direction for a leak.
 */
export function monitorKey(monitor: MonitorDescriptor): string {
  if (monitor.connector) return `connector:${monitor.connector}`
  const identity = `${monitor.manufacturer}|${monitor.model}`
  if (identity !== "|") return `model:${identity}`
  return `geometry:${monitor.geometry.x},${monitor.geometry.y},${monitor.geometry.width},${monitor.geometry.height}`
}

/**
 * Whether this monitor can be addressed stably YET.
 *
 * MEASURED, and this rule exists because of the measurement. On this host, at
 * the instant a hotplug notification fires, a newly appeared monitor reports
 * `connector = null`, `model = ""`, `manufacturer = ""` and geometry `0,0,0,0`;
 * `notify::connector` arrives a few hundred milliseconds later with the real
 * name (`repro/probes/connector-timing-probe.tsx`):
 *
 *     >>> items-changed #1
 *       IMMEDIATELY inside the handler: connector=null model="" KEY=geometry:0,0,0,0
 *       on the NEXT IDLE:             connector=null model="" KEY=geometry:0,0,0,0
 *        notify::connector fired: null -> "HEADLESS-10"
 *       200ms later:                  connector="HEADLESS-10" KEY=connector:HEADLESS-10
 *
 * So a key computed the instant the notification arrives is both useless
 * (`geometry:0,0,0,0` for every monitor that appears in the same event) and
 * short-lived (it changes once the connector lands). Two consequences, both
 * real:
 *   * two monitors appearing in one event would key identically, and the second
 *     window would be dropped as a "collision";
 *   * the window would be destroyed and rebuilt a moment later, when the
 *     connector arrives.
 *
 * Deferring the reconcile to an idle callback does NOT help -- measured above,
 * the connector is still null on the next idle.
 *
 * So the rule is: a monitor with nothing to key it by is not addressed yet. It
 * is left alone until it can be, and the topology adapter re-runs the reconcile
 * when it can (it subscribes to `notify::connector`).
 */
export function isIdentified(monitor: MonitorDescriptor): boolean {
  return Boolean(monitor.connector) || monitor.manufacturer !== "" || monitor.model !== ""
}

/** Which windows to build, and which to destroy, to match a monitor set. */
export interface SyncPlan<T> {
  create: MonitorDescriptor[]
  destroy: WindowBinding<T>[]
}

/**
 * Diff the windows this app owns against the monitors that now exist.
 *
 * DIFF-BASED, NOT INCREMENTAL, on purpose. The hotplug notification that GDK
 * actually delivers (`Gio.ListModel::items-changed`, see
 * `adapters/gdk-monitor-topology.ts`) carries only `(position, removed,
 * added)` counts, and a compositor is free to deliver one event describing
 * several changes, or several events describing one. Reconciling against the
 * full set makes the handler IDEMPOTENT: calling it twice with the same monitor
 * list does nothing the second time, so it does not matter how many events
 * arrive, in what order, or whether a monitor's `invalidate` also fires.
 *
 * A `destroy` is what keeps a removed monitor's window from leaking: the caller
 * is required to unregister AND destroy every binding this returns.
 */
export function planSync<T>(
  bindings: readonly WindowBinding<T>[],
  monitors: readonly MonitorDescriptor[],
): SyncPlan<T> {
  const wanted = new Map<string, MonitorDescriptor>()
  for (const monitor of monitors) {
    const key = monitorKey(monitor)
    // First wins: a key collision must not produce two windows for one key,
    // and the one already bound keeps its window.
    if (!wanted.has(key)) wanted.set(key, monitor)
  }
  // `create` walks `wanted`, not `monitors`, for two reasons.
  //
  // (1) Dedupe. Walking `monitors` would emit the same key twice for two
  //     monitors that key identically, and build two windows for one slot --
  //     the exact duplicate the window set can never reconcile away, because
  //     both would carry the same key. Walking the deduped map makes "first
  //     wins" mean it: the second is dropped rather than built. (Caught by the
  //     test that feeds two identical unnamed monitors.)
  //
  // (2) Skip monitors that cannot be addressed yet. `isIdentified` -- see its
  //     doc for the measurement behind it. An unidentified monitor contributes
  //     its (useless) key to `wanted`, so nothing is destroyed on its account,
  //     but no window is built for it until it can be addressed. The topology
  //     adapter re-runs the reconcile when the identity lands.
  return {
    create: [...wanted.values()].filter(
      (m) => isIdentified(m) && !bindings.some((b) => b.key === monitorKey(m)),
    ),
    destroy: bindings.filter((b) => !wanted.has(b.key)),
  }
}

/**
 * The windows a name lookup should try, in order: the focused monitor's window
 * first, then every other window in REGISTRATION order.
 *
 * This is the whole of Gap 2. `App.get_window` is
 * `this.windows.find((w) => w.name === name)`, so "which window" is decided
 * entirely by what comes first. Ordering here — in a list this module owns —
 * replaces depending on the order of GTK's window list, which was measured to
 * be reverse-insertion order and is not the focused monitor's window.
 *
 * Falls back to registration order when the focus is unknown (no compositor
 * focus source, or focus on a monitor this app has no window for). The fallback
 * is deterministic, which is the property that matters: two runs with the same
 * monitors and no focus information pick the same window.
 */
export function orderedForFocus<T>(
  bindings: readonly WindowBinding<T>[],
  focusedKey: string | null,
): WindowBinding<T>[] {
  if (focusedKey === null) return [...bindings]
  const focused = bindings.filter((b) => b.key === focusedKey)
  const rest = bindings.filter((b) => b.key !== focusedKey)
  return [...focused, ...rest]
}

/**
 * The monitor key for a compositor-reported monitor name, or null when this app
 * has no window for it.
 *
 * Matching is on the connector, which is the one identifier both sides publish
 * unchanged: measured on this host, `Gdk.Monitor.get_connector()` and
 * `AstalHyprland`'s focused monitor both report `eDP-1`. Returning null rather
 * than guessing is what lets `orderedForFocus` degrade to a deterministic
 * registration order instead of an arbitrary one.
 */
export function focusKey(
  monitors: readonly MonitorDescriptor[],
  focusedConnector: string | null,
): string | null {
  if (focusedConnector === null) return null
  for (const monitor of monitors) {
    if (monitor.connector === focusedConnector) return monitorKey(monitor)
  }
  return null
}
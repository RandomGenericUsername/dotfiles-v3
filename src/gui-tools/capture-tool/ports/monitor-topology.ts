// ---------------------------------------------------------------------------
// PORT: the monitor topology this app must mirror (fix-capture-monitor-lifecycle).
//
// The decision of WHAT to do about a monitor change is pure and lives in
// `domain/monitor-registry.ts`. This port is the seam that supplies the fact:
// the current monitor list, plus a subscription for changes.
//
// WHY A PORT AND NOT A DIRECT `Gdk.Display` READ: `app.tsx` currently reads
// `app.get_monitors()` once. Reading it again is not the problem — the problem
// is that nothing tells the app WHEN the answer changed, and which object
// delivers that is platform-specific (see `adapters/gdk-monitor-topology.ts`).
// Naming it as a port keeps the domain and the window set free of GDK.
// ---------------------------------------------------------------------------

import type { MonitorDescriptor } from "../domain/monitor-registry"

/** One monitor, as data plus the adapter's own opaque handle to it. */
export interface MonitorEntry {
  /** The plain-data half — the only half the domain ever sees. */
  descriptor: MonitorDescriptor
  /**
   * The adapter-owned object this entry came from (a `Gdk.Monitor` in
   * practice), because `Astal.Window` needs the real thing to anchor to.
   * Typed `unknown` so no consumer can reach through it by accident.
   */
  native: unknown
}

/** Read the monitors, and be told when they change. */
export interface MonitorTopology {
  /**
   * The monitors that exist now. Called once at startup and again after every
   * change notification; the reconciliation is a diff, so calling it
   * redundantly is harmless.
   */
  list(): MonitorEntry[]
  /**
   * Invoke `onChange` whenever the monitor set may have changed. The callback
   * takes no arguments on purpose: it must re-read `list()` and diff, because
   * the underlying notification describes a range, not a set of additions.
   *
   * Implementations MAY deliver the same change more than once, and MAY deliver
   * one notification for several changes. `planSync` is idempotent, so this is
   * safe; the alternative -- trusting the notification's own payload -- is not.
   */
  subscribe(onChange: () => void): void
}
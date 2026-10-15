/**
 * The Preferences port (spine AD-12; doc 101 §4.6).
 *
 * Settings are read through `get(namespace, key, fallback) -> Accessor<T>`; the
 * adapter owns the config file AND its `FileMonitor` lifecycle, and an absent
 * file degrades to the fallback. This module holds the port, the injected I/O
 * seam (`PreferencesSource`), and the pure core that owns the watch lifecycle,
 * so the same code runs against a fake source in `make ags-test` and against the
 * Gio adapter in the bar.
 *
 * WHY THE SEAM IS INJECTED. The module-scope-monitor GC trap AD-12 names is a
 * lifecycle bug: a `Gio.FileMonitor` held in a widget local is collected and
 * silently stops emitting. The core owns the lifecycle (one watch per
 * namespace, held until released); the adapter supplies the file and the
 * monitor. Because the seam is injected, the port module imports no `gi://*` and
 * no `ags`, which is what makes the lifecycle unit-testable.
 *
 * PURE: no `ags`, no `gi://*`, no I/O.
 */

import type { ReadAccessor, ReactiveRuntime, Setter } from "./reactive";

/** Reactive value for a namespaced key, with a fallback when unset (AD-12). */
export interface Preferences {
  get<T>(namespace: string, key: string, fallback: T): ReadAccessor<T>;
}

/**
 * The one thing the port needs from the host: read a namespace's record and be
 * told when it changes. The Gio adapter implements this with the config file and
 * a `Gio.FileMonitor`; a test implements it with a fake file + fake monitor.
 */
export interface PreferencesSource {
  /** The namespace's decoded record, or null when the file is absent/unreadable. */
  read(namespace: string): Record<string, unknown> | null;
  /** Watch a namespace; return a handle that releases the watch. */
  watch(namespace: string, onChange: () => void): () => void;
}

/**
 * Same-type-or-fallback coercion. A missing value AND a value of the wrong type
 * both degrade to the fallback: `false` (the capture-tool default) must not be
 * clobbered by a stray `0`, and a string key must not surface a number.
 */
function coerce<T>(value: unknown, fallback: T): T {
  return typeof value === typeof fallback ? (value as T) : fallback;
}

interface Cell {
  readonly get: ReadAccessor<unknown>;
  readonly set: Setter<unknown>;
  readonly fallback: unknown;
}

export function createPreferences(
  source: PreferencesSource,
  runtime: ReactiveRuntime,
): Preferences {
  //: One cell per (namespace, key); one watch per namespace. A namespace with
  //: several keys is read and watched once.
  const cells = new Map<string, Cell>();
  const namespaceKeys = new Map<string, Set<string>>();
  const unwatchers = new Map<string, () => void>();

  function refresh(namespace: string): void {
    const keys = namespaceKeys.get(namespace);
    if (keys === undefined) return;
    const record = source.read(namespace);
    for (const key of keys) {
      const cell = cells.get(`${namespace}\u0000${key}`);
      if (cell === undefined) continue;
      // An absent file degrades every key to its own fallback (AD-12).
      cell.set(record === null ? cell.fallback : coerce(record[key], cell.fallback));
    }
  }

  function ensureWatched(namespace: string): void {
    if (unwatchers.has(namespace)) return;
    unwatchers.set(
      namespace,
      source.watch(namespace, () => refresh(namespace)),
    );
  }

  return {
    get<T>(namespace: string, key: string, fallback: T): ReadAccessor<T> {
      const cellKey = `${namespace}\u0000${key}`;
      const existing = cells.get(cellKey);
      if (existing !== undefined) return existing.get as ReadAccessor<T>;

      const record = source.read(namespace);
      const initial = coerce(record === null ? undefined : record[key], fallback);
      const [get, set] = runtime.createState<unknown>(initial);
      cells.set(cellKey, { get, set, fallback });

      let keys = namespaceKeys.get(namespace);
      if (keys === undefined) {
        keys = new Set<string>();
        namespaceKeys.set(namespace, keys);
      }
      keys.add(key);
      ensureWatched(namespace);
      return get as ReadAccessor<T>;
    },
  };
}

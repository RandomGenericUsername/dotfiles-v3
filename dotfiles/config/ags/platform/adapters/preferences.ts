/**
 * The Gio `Preferences` adapter (spine AD-12; doc 101 §4.6).
 *
 * The pure port + core live in `../ports/preferences`; this file supplies the
 * two things the core cannot: the config FILE and its `Gio.FileMonitor`. The
 * adapter owns both, which is exactly the ownership AD-12 moves off the widget —
 * `bar/widgets/recording.tsx` used to read the file itself and hold the monitor
 * at module scope.
 *
 * WHY THE MONITOR IS A MAP, NOT A MODULE GLOBAL. A `Gio.FileMonitor` held in a
 * widget local is collected as soon as the component function returns, and a
 * collected monitor silently stops emitting (the bar then ignored later settings
 * changes — verified: flipping the setting left the old mode rendered). Holding
 * it at module scope fixes the collection but re-introduces the singleton AD-2
 * forbids. The adapter-owned map is the third option: the adapter's lifetime is
 * the session, and `watch`/its release handle own each monitor explicitly.
 */

import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";
import { agsRuntime } from "./astal";
import { createPreferences, type PreferencesSource } from "../ports/preferences";

/**
 * The namespace -> config file map. Only the capture-tool config exists today;
 * a new cross-app setting adds a row here, which is the point of the namespace:
 * the widget asks by name and the adapter owns the path.
 */
function configPath(namespace: string): string {
  return `${GLib.get_user_config_dir()}/${namespace}/config.json`;
}

class GioPreferencesSource implements PreferencesSource {
  //: Held per namespace so a live monitor cannot be collected (the GC trap).
  private readonly monitors = new Map<string, Gio.FileMonitor>();

  read(namespace: string): Record<string, unknown> | null {
    try {
      const [ok, bytes] = GLib.file_get_contents(configPath(namespace));
      if (!ok || bytes === null) return null;
      const raw = JSON.parse(new TextDecoder().decode(bytes)) as unknown;
      return raw !== null && typeof raw === "object"
        ? (raw as Record<string, unknown>)
        : null;
    } catch {
      // A missing/corrupt file is not an error: the port degrades to the
      // fallback (AD-12, "works with nothing").
      return null;
    }
  }

  watch(namespace: string, onChange: () => void): () => void {
    let monitor: Gio.FileMonitor;
    try {
      monitor = Gio.File.new_for_path(configPath(namespace)).monitor_file(
        Gio.FileMonitorFlags.NONE,
        null,
      );
    } catch (error) {
      console.error(`preferences: cannot watch ${configPath(namespace)}: ${error}`);
      return () => {};
    }
    this.monitors.set(namespace, monitor);
    const handler = monitor.connect("changed", () => onChange());
    return () => {
      try {
        monitor.disconnect(handler);
      } catch {
        /* already disconnected */
      }
      this.monitors.delete(namespace);
    };
  }
}

//: The bar's one Preferences client, bound to the AGS reactive runtime (AD-2).
export const preferences = createPreferences(new GioPreferencesSource(), agsRuntime);

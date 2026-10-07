// ---------------------------------------------------------------------------
// ADAPTER: the focused monitor, from the compositor's Astal service
// (fix-capture-monitor-lifecycle).
//
// WHY A COMPOSITOR AT ALL: GTK4 cannot answer this. Measured on this host, with
// the complete reason recorded in `ports/monitor-focus.ts` — `Gdk.Seat.get_focus`,
// `Gdk.Device.get_position`, `Gdk.Display.get_monitor_at_window` and
// `get_monitor_at_point` are all absent from GTK 4.22, and
// `Gdk.Device.get_surface_at_position()` returns `(NULL, 0, 0)` whenever the
// pointer is over another client's surface, which on a compositor is always.
// GTK4 deliberately removed global focus tracking; the compositor owns that
// knowledge and is the only place it exists.
//
// WHY `AstalHyprland` AND NOT `hyprctl`: the capture BACKEND already resolves
// the focused monitor from `hyprctl -j monitors`
// (`bin/capture-tool:203-205`, `resolve_target`), so "focused" already has a
// definition in this tool and the panel is being made to agree with it — the
// panel opens on the monitor a `--target screen` capture will actually grab.
// The service is preferred over the subprocess for three measured reasons:
//
//   * it is IN-PROCESS (a D-Bus service object), so answering costs no spawn
//     and no parse on a keystroke;
//   * it PUSHES `notify::focused-monitor`, so the panel's notion of focus can
//     never go stale — there is no poll interval to get wrong;
//   * `get_focused_monitor().name` was measured to be byte-identical to GDK's
//     `Gdk.Monitor.get_connector()` on this host (`eDP-1` both), which is what
//     `domain/monitor-registry.ts#focusKey` matches on.
//
// WHY THE IMPORT IS DYNAMIC: `AstalHyprland` is not guaranteed to be present on
// a host running some other Wayland compositor, and a failing static import
// would take the whole app down at startup. A rejected import degrades to "no
// focus information", which `orderedForFocus` handles by falling back to a
// deterministic registration order. The panel still opens; it just cannot prefer
// a monitor.
// ---------------------------------------------------------------------------

import type { MonitorFocus } from "../ports/monitor-focus"

/** The slice of AstalHyprland this adapter reads. Narrow on purpose. */
interface HyprlandFocusSource {
  get_focused_monitor(): { name: string } | null
}

/**
 * The compositor's focused monitor, or null.
 *
 * Returns a stable object immediately; before the service has loaded (or if it
 * never does) it answers null, which is the documented "unknown" case.
 */
export function hyprlandMonitorFocus(): MonitorFocus {
  let source: HyprlandFocusSource | null = null

  void import("gi://AstalHyprland?version=0.1")
    .then(({ default: Hyprland }) => {
      source = Hyprland.get_default() as unknown as HyprlandFocusSource
    })
    .catch(() => {
      // No compositor focus service on this host. Not an error to report: the
      // documented fallback is registration order, and a launcher error here
      // would be noise on a host that was never going to have focus data.
      source = null
    })

  return {
    focusedConnector(): string | null {
      return source?.get_focused_monitor()?.name ?? null
    },
  }
}
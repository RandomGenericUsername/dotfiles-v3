// ---------------------------------------------------------------------------
// PORT: which monitor the user is on (fix-capture-monitor-lifecycle).
//
// This port exists because of a MEASURED negative result, recorded here so the
// next reader does not retry it. On GTK 4.22 there is no GDK API that names the
// focused monitor:
//
//   Gdk.Seat.get_focus                      -> undefined (method absent)
//   Gdk.Device.get_position                 -> undefined (method absent)
//   Gdk.Display.get_monitor_at_window       -> undefined (method absent)
//   Gdk.Display.get_monitor_at_point        -> undefined (method absent)
//   Gdk.Display.get_n_monitors              -> undefined (method absent)
//   Gdk.Device.get_surface_at_position()    -> exists, but returns (NULL, 0, 0)
//                                              when the pointer is over another
//                                              client's surface, i.e. always, in
//                                              the case that matters
//
// GTK4 removed the global focus and global pointer position that GTK3 had, so
// the answer has to come from the compositor. That is why this is a PORT rather
// than a `Gdk` call: on Hyprland the compositor service answers in-process, and
// a non-Hyprland host degrades to "unknown" instead of failing to load.
//
// The value returned is the platform's monitor NAME (`eDP-1`, `HDMI-2`, ...),
// which `domain/monitor-registry.ts#focusKey` matches against the connector GDK
// reports. Both sides publish that string unchanged — verified on this host,
// where GDK says `eDP-1` and the compositor service says `eDP-1`.
// ---------------------------------------------------------------------------

/** Read the monitor the user is currently on, if the platform can say. */
export interface MonitorFocus {
  /**
   * The focused monitor's connector name, or null when it cannot be determined.
   *
   * null is a NORMAL answer, not an error: it is what a host without a
   * compositor focus source returns, and `orderedForFocus` degrades to a
   * deterministic registration order on it.
   */
  focusedConnector(): string | null
}
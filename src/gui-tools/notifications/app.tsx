import app from "ags/gtk4/app"
import GLib from "gi://GLib?version=2.0"
import Gio from "gi://Gio?version=2.0"
import Notifd from "gi://AstalNotifd?version=0.1"
import style from "./style.css"
import { NotificationsWindow } from "./ui/NotificationsWindow"

//: The well-known bus name this app claims (also used by dunst).
const NOTIFICATIONS_NAME = "org.freedesktop.Notifications"

/**
 * Whether some other process already owns org.freedesktop.Notifications.
 *
 * Checked BEFORE touching AstalNotifd: when the name is taken, AstalNotifd
 * emits a GLib *warning* ("cannot get proxy: dunst is already running") and
 * then hands out an object whose signals tear down with NULL-pointer
 * criticals — warnings are not catchable, so a try/catch around get_default()
 * cannot detect this. Asking the bus daemon directly is decisive.
 */
function foreignNotificationDaemon(): boolean {
  try {
    const bus = Gio.bus_get_sync(Gio.BusType.SESSION, null)
    const reply = bus.call_sync(
      "org.freedesktop.DBus",
      "/org/freedesktop/DBus",
      "org.freedesktop.DBus",
      "NameHasOwner",
      new GLib.Variant("(s)", [NOTIFICATIONS_NAME]),
      null,
      Gio.DBusCallFlags.NONE,
      2000,
      null,
    )
    const [hasOwner] = reply.deepUnpack() as [boolean]
    return hasOwner
  } catch (error) {
    // Can't tell — proceed; AstalNotifd will surface its own failure.
    console.error(`notifications: bus probe failed: ${error}`)
    return false
  }
}

app.start({
  instanceName: "notifications",
  css: style,
  main() {
    app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`)

    // A foreign daemon (dunst during the transition, or a duplicate instance)
    // holding the name means we cannot serve notifications. Exit cleanly
    // rather than lingering half-initialised; fallback behaviour is the
    // other daemon's (it keeps working) until the next login.
    if (foreignNotificationDaemon()) {
      console.error(
        `notifications: ${NOTIFICATIONS_NAME} already owned by another daemon (dunst?) — exiting without serving`,
      )
      app.quit()
      return
    }

    // Let the daemon honour declared expire-timeouts. It IGNORES them by
    // default, which is why notifications used to sit on screen forever; the
    // stack keeps its own timer as well so a sender that declares no timeout
    // still clears (see NotificationsWindow.scheduleExpiry).
    try {
      const notifd = Notifd.get_default()
      notifd.set_ignore_timeout(false)
    } catch (error) {
      console.error(`notifications: cannot acquire the notification daemon: ${error}`)
      app.quit()
      return
    }

    // A single top-right stack: every window would render the SAME daemon
    // stream, so (unlike the capture picker) this instance shows on one
    // monitor only instead of one window per monitor.
    const monitors = app.get_monitors()
    const primary = monitors[0]
    if (primary !== undefined) {
      app.add_window(NotificationsWindow(primary))
    }
  },
})

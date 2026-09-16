import { Astal, Gdk, Gtk } from "ags/gtk4"
import Notifd from "gi://AstalNotifd?version=0.1"
import Pango from "gi://Pango?version=1.0"
import GLib from "gi://GLib?version=2.0"
import app from "ags/gtk4/app"

// AstalNotifd.Urgency wire values (GIR-verified against
// /usr/share/gir-1.0/AstalNotifd-0.1.gir): LOW=0, NORMAL=1, CRITICAL=2.
// Compared numerically so a namespace-enum rename can never break the
// urgency mapping at runtime.
const URGENCY_CRITICAL = 2

// Oldest-overflow discipline (mirrors the old dunst `notification_limit`).
const MAX_VISIBLE = 5

const WINDOW_NAME = "notifications-window"

interface CardEntry {
  id: number
  notification: InstanceType<typeof Notifd.Notification>
  widget: Gtk.Widget
}

function hideWindow(): void {
  const window = app.get_window(WINDOW_NAME)
  if (window) window.visible = false
}

/** Absolute on-disk image for the notification, or null (fallback tile). */
function notificationImagePath(
  notification: InstanceType<typeof Notifd.Notification>,
): string | null {
  const candidates: Array<string | null> = [
    notification.get_image(),
    notification.get_app_icon(),
  ]
  for (const candidate of candidates) {
    if (candidate === null || candidate.length === 0) continue
    // Only absolute paths are usable as files; icon NAMES (e.g. from plain
    // `notify-send` traffic) fall through to the letter tile.
    if (!candidate.startsWith("/")) continue
    try {
      if (GLib.file_test(candidate, GLib.FileTest.EXISTS)) return candidate
    } catch {
      continue
    }
  }
  return null
}

function tileContent(
  notification: InstanceType<typeof Notifd.Notification>,
  critical: boolean,
): Gtk.Widget {
  const path = notificationImagePath(notification)
  if (path !== null) {
    try {
      const picture = Gtk.Picture.new_for_filename(path)
      picture.set_content_fit(Gtk.ContentFit.CONTAIN)
      picture.set_size_request(24, 24)
      picture.set_halign(Gtk.Align.CENTER)
      picture.set_valign(Gtk.Align.CENTER)
      return picture
    } catch (error) {
      console.error(`notifications: cannot load image ${path}: ${error}`)
    }
  }
  // Fallback tile: the app's initial (or "!" for critical) so icon-less
  // traffic (e.g. toggle-touchpad notify-send) still renders a tidy card.
  const appName = notification.get_app_name() ?? ""
  const glyph = critical ? "!" : (appName.charAt(0).toUpperCase() || "?")
  const label = new Gtk.Label({ label: glyph })
  label.add_css_class("notif-fallback")
  label.set_halign(Gtk.Align.CENTER)
  label.set_valign(Gtk.Align.CENTER)
  return label
}

/** One mockup `.toast` card for a daemon notification. */
function NotificationCard(
  notification: InstanceType<typeof Notifd.Notification>,
): Gtk.Box {
  const critical = notification.get_urgency() === URGENCY_CRITICAL

  const tile = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL })
  tile.add_css_class("notif-tile")
  if (critical) tile.add_css_class("critical")
  tile.set_halign(Gtk.Align.CENTER)
  tile.set_valign(Gtk.Align.START)
  tile.append(tileContent(notification, critical))

  const title = new Gtk.Label({ label: notification.get_summary() ?? "" })
  title.add_css_class("notif-title")
  title.set_halign(Gtk.Align.START)
  title.set_wrap(true)

  const body = new Gtk.Label({ label: notification.get_body() ?? "" })
  body.add_css_class("notif-body")
  body.set_halign(Gtk.Align.START)
  body.set_wrap(true)
  // Paths must break mid-token (mockup `word-break: break-all`).
  body.set_wrap_mode(Pango.WrapMode.WORD_CHAR)

  const text = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    spacing: 3,
    hexpand: true,
  })
  text.append(title)
  if ((notification.get_body() ?? "").length > 0) text.append(body)

  const actions = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 7,
  })
  actions.add_css_class("notif-actions")
  let hasActions = false
  try {
    for (const action of notification.get_actions() ?? []) {
      hasActions = true
      const chip = new Gtk.Button({ label: action.get_label() ?? action.get_id() })
      chip.add_css_class("notif-chip")
      const current = action
      chip.connect("clicked", () => {
        // Route the invocation back to the emitting client (the
        // capture backend's `dunstify --wait` resolves the matching
        // ActionInvoked and executes copy/open/reveal/details), then
        // dismiss locally so the card clears promptly.
        try {
          current.invoke()
        } catch (error) {
          console.error(`notifications: action invoke failed: ${error}`)
        }
        try {
          notification.dismiss()
        } catch (error) {
          console.error(`notifications: dismiss failed: ${error}`)
        }
      })
      actions.append(chip)
    }
  } catch (error) {
    console.error(`notifications: cannot read actions: ${error}`)
  }
  if (hasActions) text.append(actions)

  const card = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 13,
  })
  card.add_css_class("notif-card")
  if (critical) card.add_css_class("critical")
  card.append(tile)
  card.append(text)

  // Click anywhere on the card dismisses it.
  const click = new Gtk.GestureClick()
  click.connect("pressed", () => {
    try {
      notification.dismiss()
    } catch (error) {
      console.error(`notifications: dismiss failed: ${error}`)
    }
  })
  card.add_controller(click)

  return card
}

/** Top-right freedesktop notification stack (the session daemon). */
export function NotificationsWindow(gdkmonitor: Gdk.Monitor) {
  const notifd = Notifd.get_default()
  let stack: Gtk.Box | null = null
  let cards: CardEntry[] = []

  function removeCard(id: number): void {
    const index = cards.findIndex((entry) => entry.id === id)
    if (index === -1 || stack === null) return
    const [entry] = cards.splice(index, 1)
    if (entry !== undefined) stack.remove(entry.widget)
  }

  function addCard(
    notification: InstanceType<typeof Notifd.Notification>,
    newestOnTop: boolean,
  ): void {
    if (stack === null) return
    const id = notification.get_id()
    // A replaced notification reuses its id: drop the stale card first.
    removeCard(id)
    const widget = NotificationCard(notification)
    cards.push({ id, notification, widget })
    if (newestOnTop) stack.prepend(widget)
    else stack.append(widget)
    // Bound the stack: dismiss the oldest overflow through the DAEMON so
    // removal flows through the single `resolved` path below.
    while (cards.length > MAX_VISIBLE) {
      const oldest = cards[0]
      if (oldest === undefined) break
      try {
        oldest.notification.dismiss()
      } catch (error) {
        console.error(`notifications: overflow dismiss failed: ${error}`)
        removeCard(oldest.id)
        break
      }
      // If the daemon never resolves (sticky critical), avoid a hot loop:
      // drop the local card and move on.
      if (cards.length > 0 && cards[0] !== undefined && cards[0].id === oldest.id) {
        removeCard(oldest.id)
      }
    }
  }

  try {
    notifd.connect("notified", (_self, id: number, _replaced: boolean) => {
      try {
        const notification = notifd.get_notification(id)
        if (notification !== null) addCard(notification, true)
      } catch (error) {
        console.error(`notifications: notified handler failed: ${error}`)
      }
    })
    notifd.connect("resolved", (_self, id: number, _reason: number) => {
      removeCard(id)
    })
  } catch (error) {
    console.error(`notifications: cannot subscribe to the daemon: ${error}`)
  }

  function onKey(keyval: number): boolean {
    if (keyval === Gdk.KEY_Escape) {
      // Dismiss the newest card (or hide an empty stack window).
      const newest = cards[cards.length - 1]
      if (newest === undefined) {
        hideWindow()
        return true
      }
      try {
        newest.notification.dismiss()
      } catch (error) {
        console.error(`notifications: escape dismiss failed: ${error}`)
        removeCard(newest.id)
      }
      return true
    }
    return false
  }

  return (
    <window
      visible
      name={WINDOW_NAME}
      class="notifications-window"
      gdkmonitor={gdkmonitor}
      anchor={Astal.WindowAnchor.TOP | Astal.WindowAnchor.RIGHT}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      margin_top={12}
      margin_right={12}
      $={(self) => {
        // Capture phase so Escape clears a card even when a chip has focus.
        const keys = new Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", (_controller, keyval, _keycode, _state) =>
          onKey(keyval),
        )
        self.add_controller(keys)
        // Hydrate cards already live on the daemon (e.g. after a restart).
        self.connect("map", () => {
          try {
            const live = notifd.get_notifications()
            if (live !== null) {
              for (const notification of live) addCard(notification, false)
            }
          } catch (error) {
            console.error(`notifications: hydrate failed: ${error}`)
          }
        })
      }}
    >
      <box
        orientation={Gtk.Orientation.VERTICAL}
        spacing={12}
        css_classes={["notif-stack"]}
        $={(self) => {
          stack = self
        }}
      />
    </window>
  )
}

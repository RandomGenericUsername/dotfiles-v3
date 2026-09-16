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

// Fixed card width (the mockup `.toast-stack` measure). A fixed request makes
// long bodies wrap instead of letting the card grow, and guarantees no
// notification can ever expand past a toast-sized box.
const CARD_WIDTH = 380

// Icon size inside the 56px tile.
const TILE_ICON = 24

// Auto-expiry. AstalNotifd does not reliably resolve notifications on their
// own (verified live: a capture toast sent with an 8s timeout stayed on screen
// until dismissed), so the stack owns the timer. Critical cards persist until
// dismissed — the mockup's "Capture failed" card. A sender's 0 ("never") or
// -1 ("server default") is treated as the default so nothing sticks forever.
const DEFAULT_TIMEOUT_MS = 8000

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

/**
 * Map the stack window before a card lands. An empty layer-shell surface stays
 * mapped and the compositor keeps re-presenting its LAST PAINTED BUFFER, so a
 * card removed from the box would otherwise stay on screen forever (verified
 * live: removeCard ran, the widget was gone, the pixels were not).
 */
function showWindow(): void {
  const window = app.get_window(WINDOW_NAME)
  if (window) window.visible = true
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
      // Gtk.Image + pixel_size (bar precedent): forces the SVG to rasterize at
      // exactly TILE_ICON px. Gtk.Picture + set_size_request is NOT equivalent
      // — the request is only a minimum, so a 1024px icon (the capture-tool
      // set) measured at natural size and blew the card up to full screen.
      const image = Gtk.Image.new_from_file(path)
      image.set_pixel_size(TILE_ICON)
      image.set_halign(Gtk.Align.CENTER)
      image.set_valign(Gtk.Align.CENTER)
      return image
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
  onDismiss: () => void,
): Gtk.Box {
  const critical = notification.get_urgency() === URGENCY_CRITICAL

  // CenterBox, not Box: a Gtk.Box packs a non-expanding child at the START of
  // its main axis, so the 24px glyph sat at the TOP of the 56px tile. The
  // box's own valign/align cannot fix that (measured: tile 58x58, valign
  // CENTER, glyph still top-packed) — CenterBox centers its centre widget by
  // construction, which is what the mockup's flex centring does.
  const tile = new Gtk.CenterBox()
  tile.add_css_class("notif-tile")
  if (critical) tile.add_css_class("critical")
  tile.set_halign(Gtk.Align.CENTER)
  tile.set_valign(Gtk.Align.CENTER)
  tile.set_center_widget(tileContent(notification, critical))

  const title = new Gtk.Label({ label: notification.get_summary() ?? "" })
  title.add_css_class("notif-title")
  title.set_halign(Gtk.Align.START)
  title.set_wrap(true)
  // Bound the natural (unwrapped) width so the window sizes to the intended
  // card measure instead of the longest path's single-line width.
  title.set_max_width_chars(38)

  const body = new Gtk.Label({ label: notification.get_body() ?? "" })
  body.add_css_class("notif-body")
  body.set_halign(Gtk.Align.START)
  body.set_wrap(true)
  body.set_max_width_chars(44)
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
        // Route the invocation back to the emitting client (the capture
        // backend listens on D-Bus for ActionInvoked and executes
        // copy/open/reveal/details). Do NOT dismiss in the same tick: our
        // daemon emits NotificationClosed BEFORE ActionInvoked, and clearing
        // the card immediately raced the action delivery. The daemon closes
        // the notification for these actions, which removes the card through
        // `resolved`; the timeout is only a fallback for a daemon that keeps
        // it open.
        try {
          current.invoke()
        } catch (error) {
          console.error(`notifications: action invoke failed: ${error}`)
        }
        GLib.timeout_add(GLib.PRIORITY_DEFAULT, 600, () => {
          onDismiss()
          return GLib.SOURCE_REMOVE
        })
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
  card.set_size_request(CARD_WIDTH, -1)
  card.append(tile)
  card.append(text)

  // Click anywhere on the card dismisses it.
  const click = new Gtk.GestureClick()
  click.connect("pressed", () => onDismiss())
  card.add_controller(click)

  return card
}

/** Top-right freedesktop notification stack (the session daemon). */
export function NotificationsWindow(gdkmonitor: Gdk.Monitor) {
  const notifd = Notifd.get_default()
  let stack: Gtk.Box | null = null
  let cards: CardEntry[] = []
  /** id -> pending GLib timeout source for auto-expiry. */
  const timers = new Map<number, number>()

  function removeCard(id: number): void {
    const index = cards.findIndex((entry) => entry.id === id)
    if (index === -1 || stack === null) return
    clearExpiry(id)
    const [entry] = cards.splice(index, 1)
    if (entry !== undefined) stack.remove(entry.widget)
    // Unmap once the last card leaves: an empty surface would keep showing the
    // previous frame (see showWindow).
    if (cards.length === 0) hideWindow()
  }

  /**
   * Remove a card and tell the daemon. The local removal is AUTHORITATIVE:
   * `Notification.dismiss()` does not reliably emit `resolved` (verified live
   * — a card the daemon had already been told to dismiss stayed on screen), so
   * every user/expiry path clears the UI itself and treats `resolved` as a
   * bonus path for daemon-initiated closes.
   */
  function dismissCard(id: number): void {
    const index = cards.findIndex((entry) => entry.id === id)
    if (index === -1) return
    const entry = cards[index]
    removeCard(id)
    try {
      entry?.notification.dismiss()
    } catch (error) {
      console.error(`notifications: dismiss failed: ${error}`)
    }
  }

  /** Cancel a card's pending auto-expiry (called on every removal path). */
  function clearExpiry(id: number): void {
    const source = timers.get(id)
    if (source !== undefined) {
      GLib.source_remove(source)
      timers.delete(id)
    }
  }

  /**
   * Auto-dismiss a normal-urgency card after its timeout. Critical cards are
   * skipped entirely (sticky until the user dismisses them).
   */
  function scheduleExpiry(entry: CardEntry): void {
    if (entry.notification.get_urgency() === URGENCY_CRITICAL) return
    let ms = DEFAULT_TIMEOUT_MS
    try {
      const declared = entry.notification.get_expire_timeout()
      if (declared > 0) ms = declared
    } catch (error) {
      console.error(`notifications: cannot read expire timeout: ${error}`)
    }
    const id = entry.id
    const source = GLib.timeout_add(GLib.PRIORITY_DEFAULT, ms, () => {
      timers.delete(id)
      dismissCard(id)
      return GLib.SOURCE_REMOVE
    })
    timers.set(id, source)
  }

  function addCard(
    notification: InstanceType<typeof Notifd.Notification>,
    newestOnTop: boolean,
  ): void {
    if (stack === null) return
    const id = notification.get_id()
    // A replaced notification reuses its id: drop the stale card first.
    removeCard(id)
    showWindow()
    const widget = NotificationCard(notification, () => dismissCard(id))
    cards.push({ id, notification, widget })
    if (newestOnTop) stack.prepend(widget)
    else stack.append(widget)
    scheduleExpiry({ id, notification, widget })
    // Bound the stack: the oldest overflow is dismissed locally (authoritative)
    // and the daemon is told, so the cap holds even for sticky criticals.
    while (cards.length > MAX_VISIBLE) {
      const oldest = cards[0]
      if (oldest === undefined) break
      dismissCard(oldest.id)
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
      dismissCard(newest.id)
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
        // NOTE: earlier revisions hydrated the daemon's live notification list
        // on map. Removed deliberately: this process IS the notifd daemon
        // (AstalNotifd), so its list is always empty at startup — a hydrate
        // could only ever re-add cards the stack had already cleared,
        // resurrecting dismissed toasts and duplicating cards whenever the
        // window remapped. Notifications that arrive during startup are
        // covered by the `notified` handler.
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

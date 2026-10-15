/**
 * The bar's `Notifier` adapter (spine AD-11; doc 101 §4.5).
 *
 * The pure port + router live in `../ports/notifier`; this file supplies the
 * two wires. The freedesktop `notify` sink is the exact one-shot `Notify` call
 * the bar used to construct inside `services/bluetooth-service.ts`, moved here
 * so no sender knows the wire. The `card` sink is the event-card path.
 *
 * THE CARD SINK IS A SEAM, NOT A STUB. The contract has no generic
 * notification-card topic (`known_topic_only` in `contracts/event-contract.json`)
 * and AD-22 forbids an app emitting domain state, so the runtime-hosted card
 * producer is future work — and the bar has no keyed/progress sender today. The
 * route exists and is proven by the pure core's tests; a card call here is
 * logged loudly, never silently dropped, so the gap is visible the moment a
 * sender needs it.
 */

import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";
import {
  createNotifier,
  type NotificationIntent,
  type NotifierSinks,
} from "../ports/notifier";

const NOTIFICATIONS_BUS = "org.freedesktop.Notifications";
const NOTIFICATIONS_PATH = "/org/freedesktop/Notifications";
const NOTIFICATIONS_IFACE = "org.freedesktop.Notifications";

/**
 * `app_icon`: an absolute path to the rendered glyph, or a themed name. The
 * notifications host resolves an absolute path to a file and lets a NAME fall
 * through to the same initial-letter tile as an absent icon, so both are safe.
 */
function iconArg(intent: NotificationIntent): string {
  const icon = intent.icon;
  if (icon === undefined) return "";
  return icon.kind === "file" ? icon.path : icon.name;
}

/** The freedesktop transient sink: a one-shot `Notify` on the session bus. */
function notify(intent: NotificationIntent): void {
  try {
    Gio.bus_get_sync(Gio.BusType.SESSION, null).call_sync(
      NOTIFICATIONS_BUS,
      NOTIFICATIONS_PATH,
      NOTIFICATIONS_IFACE,
      "Notify",
      new GLib.Variant("(susssasa{sv}i)", [
        intent.app ?? "",
        0,
        iconArg(intent),
        intent.summary,
        intent.body ?? "",
        [],
        {},
        intent.timeoutMs ?? -1,
      ]),
      null,
      Gio.DBusCallFlags.NONE,
      5000,
      null,
    );
  } catch (error) {
    // A toast must never fail the action that produced it; the raw cause is
    // already in the log via the caller.
    console.error(`notifier: freedesktop Notify failed: ${error}`);
  }
}

/** The event-card sink (keyed/progress): see the file header for the gap. */
function card(intent: NotificationIntent): void {
  console.error(
    `notifier: keyed/progress intent (${intent.key ?? "progress"}) has no event-card producer yet`,
  );
}

const sinks: NotifierSinks = { notify, card };

//: The bar's one Notifier, routed by the pure core.
export const notifier = createNotifier(sinks);

// ICME → hub domain-event publisher (Phase 5, 5-4).
//
// The editor publishes its own domain event at the meaningful moment: on a
// successful save (not on exit) it emits `icme.saved { path }` through the
// hub's validated `Emit` method (AD-37/AD-38). The hub is the sole emitter;
// the editor never constructs a D-Bus signal. If the daemon owns no name,
// the call fails and is logged — absence is reduced functionality, never a
// crash (AD-34/AD-38).
//
// Contract literals are mirrored from `contracts/event-contract.json`; the
// runtime's per-language drift gate pins the Python side (there is no JS
// test runner in this repo).

import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";

const EVENTS_BUS_NAME = "org.dotfiles.Events";
const EVENTS_OBJECT_PATH = "/org/dotfiles/Events";
const EVENTS_INTERFACE = "org.dotfiles.Events1";
const EMIT_METHOD = "Emit";
const ICME_SAVED_TOPIC = "icme.saved";

let connection: Gio.DBusConnection | null = null;

function sessionBus(): Gio.DBusConnection {
  if (connection === null) connection = Gio.bus_get_sync(Gio.BusType.SESSION, null);
  return connection;
}

/** Publish `icme.saved {path}` after a successful save; never throws. */
export function publishIcmeSaved(path: string): void {
  if (path === "") return;
  try {
    sessionBus().call_sync(
      EVENTS_BUS_NAME,
      EVENTS_OBJECT_PATH,
      EVENTS_INTERFACE,
      EMIT_METHOD,
      new GLib.Variant("(sa{sv})", [ICME_SAVED_TOPIC, { path: new GLib.Variant("s", path) }]),
      null,
      Gio.DBusCallFlags.NONE,
      -1,
      null,
    );
  } catch (error) {
    console.error(`event-bus: icme.saved(${path}) failed: ${error}`);
  }
}

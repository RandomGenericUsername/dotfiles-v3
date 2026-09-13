// ICME → hub domain-event publisher (Phase 5, 5-4).
//
// The editor publishes its own domain event at the meaningful moment: on a
// successful save (not on exit) it emits `icme.saved { path }` through the
// hub's validated `Emit` method (AD-37/AD-38). The hub is the sole emitter;
// the editor never constructs a D-Bus signal. If the daemon owns no name,
// the call fails and is logged — absence is reduced functionality, never a
// crash (AD-34/AD-38).
//
// The contract shape lives in `event-contract.ts` (no GJS imports), pinned to
// `contracts/event-contract.{json,xml}` by the node drift test; this file is
// only the Gio seam.

import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";
import {
  EMIT_METHOD,
  EVENTS_BUS_NAME,
  EVENTS_INTERFACE,
  EVENTS_OBJECT_PATH,
  publishIcmeSavedVia,
  type EmitPort,
} from "./event-contract";

let connection: Gio.DBusConnection | null = null;

function sessionBus(): Gio.DBusConnection {
  if (connection === null) connection = Gio.bus_get_sync(Gio.BusType.SESSION, null);
  return connection;
}

const gioPort: EmitPort = {
  emit(topic: string, payload: Record<string, unknown>): void {
    sessionBus().call_sync(
      EVENTS_BUS_NAME,
      EVENTS_OBJECT_PATH,
      EVENTS_INTERFACE,
      EMIT_METHOD,
      new GLib.Variant("(sa{sv})", [
        topic,
        { path: new GLib.Variant("s", String(payload.path ?? "")) },
      ]),
      null,
      Gio.DBusCallFlags.NONE,
      -1,
      null,
    );
  },
};

/** Publish `icme.saved {path}` after a successful save; never throws. */
export function publishIcmeSaved(path: string): void {
  try {
    publishIcmeSavedVia(gioPort, path);
  } catch (error) {
    console.error(`event-bus: icme.saved(${path}) failed: ${error}`);
  }
}

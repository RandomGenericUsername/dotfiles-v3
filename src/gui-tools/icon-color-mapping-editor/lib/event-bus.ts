// ICME ↔ hub domain-event seam (Phase 5, 5-4 + live palette refresh).
//
// PUBLISHER — the editor publishes its own domain event at the meaningful
// moment: on a successful save (not on exit) it emits `icme.saved { path }`
// through the hub's validated `Emit` method (AD-37/AD-38). The hub is the
// sole emitter; the editor never constructs a D-Bus signal. If the daemon
// owns no name, the call fails and is logged — absence is reduced
// functionality, never a crash (AD-34/AD-38).
//
// CONSUMER — the editor also consumes `wallpaper.state` (like the wallpaper
// selector) so a palette swap restyles it live. The runtime deliberately
// skips this instance on a set (`ags-icme` is in
// `AgsReloader.DEFAULT_SKIP_CONFIG_DIRS`) because a restart would discard
// unsaved edits; the event-driven refresh preserves them instead.
//
// Contract shapes live in `event-contract.ts` (publisher) and
// `event-bus-core.ts` (consumer state machine), both GJS-free and pinned to
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
import {
  CONTROL_METHOD,
  DBUS_BUS_NAME,
  DBUS_OBJECT_PATH,
  DOMAIN_EVENT_SIGNAL,
  DomainEventBusCore,
  HYDRATION_METHOD,
  HYDRATION_TIMEOUT_MS,
  JOBS_CLEARED_SIGNAL,
  NAME_OWNER_CHANGED_SIGNAL,
  WALLPAPER_STATE_TOPIC,
  type EventBusTransport,
} from "./event-bus-core";

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

// ── Domain-event consumer (live palette refresh) ─────────────────────────
//
// Mirrors the wallpaper selector's consumer: subscribe to the contract
// `DomainEvent` signal, filter by topic, hydrate `(epoch, seq)` before reading
// so a swapped-while-hidden editor picks up the current state on the next
// event. Gio transport only; the state machine is in `event-bus-core.ts`.

class GioEventBusTransport implements EventBusTransport {
  startSignals(
    onDomainEvent: (params: unknown[]) => void,
    onJobsCleared: (params: unknown[]) => void,
    onHubRestart: () => void,
  ): void {
    const connection = sessionBus();
    connection.signal_subscribe(
      null,
      EVENTS_INTERFACE,
      DOMAIN_EVENT_SIGNAL,
      EVENTS_OBJECT_PATH,
      null,
      Gio.DBusSignalFlags.NONE,
      (_c, _s, _p, _i, _sig, parameters) =>
        onDomainEvent(parameters.recursiveUnpack() as unknown[]),
    );
    connection.signal_subscribe(
      null,
      EVENTS_INTERFACE,
      JOBS_CLEARED_SIGNAL,
      EVENTS_OBJECT_PATH,
      null,
      Gio.DBusSignalFlags.NONE,
      (_c, _s, _p, _i, _sig, parameters) =>
        onJobsCleared(parameters.recursiveUnpack() as unknown[]),
    );
    connection.signal_subscribe(
      DBUS_BUS_NAME,
      DBUS_BUS_NAME,
      NAME_OWNER_CHANGED_SIGNAL,
      DBUS_OBJECT_PATH,
      EVENTS_BUS_NAME,
      Gio.DBusSignalFlags.NONE,
      (_c, _s, _p, _i, _sig, parameters) => {
        const body = parameters.recursiveUnpack() as string[];
        if (body.length === 3 && body[2]) onHubRestart();
      },
    );
  }

  getTopicState(topic: string): Record<string, unknown> | null {
    const reply = sessionBus().call_sync(
      EVENTS_BUS_NAME,
      EVENTS_OBJECT_PATH,
      EVENTS_INTERFACE,
      HYDRATION_METHOD,
      new GLib.Variant("(s)", [topic]),
      null,
      Gio.DBusCallFlags.NONE,
      HYDRATION_TIMEOUT_MS,
      null,
    );
    const unpacked = reply.recursiveUnpack() as unknown[];
    if (!Array.isArray(unpacked) || unpacked.length === 0) return null;
    const state = unpacked[0];
    return state !== null && typeof state === "object"
      ? (state as Record<string, unknown>)
      : null;
  }

  control(jobId: string, action: string): void {
    sessionBus().call_sync(
      EVENTS_BUS_NAME,
      EVENTS_OBJECT_PATH,
      EVENTS_INTERFACE,
      CONTROL_METHOD,
      new GLib.Variant("(ss)", [jobId, action]),
      null,
      Gio.DBusCallFlags.NONE,
      -1,
      null,
    );
  }
}

// One shared consumer for the whole editor; `subscribe` lazily connects.
export const domainEvents = new DomainEventBusCore(new GioEventBusTransport());

export { WALLPAPER_STATE_TOPIC } from "./event-bus-core";
export type { DomainPayload, TopicHandler } from "./event-bus-core";

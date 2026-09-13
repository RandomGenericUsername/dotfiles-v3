// Gio transport for the bar's domain-event consumer (Phase 5, AD-34/AD-37).
//
// The bar is a THIN CONSUMER of the hub's `org.dotfiles.Events1` surface:
// it subscribes to the contract `DomainEvent` signal, filters by topic, and
// never imports the runtime. UI indicators are driven by DOMAIN events only
// (`DomainEvent`), never by `JobStarted`/`JobFinished` (AD-37). Control
// actions go back through the hub's `Control` method — the single control
// path — never by shelling the tool.
//
// The subscribe-before-read hydration state machine and every contract
// literal live in `event-bus-core.ts` (no GJS imports), pinned to
// `contracts/event-contract.{json,xml}` by the node drift test. This file is
// only the Gio seam.

import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";
import {
  CONTROL_METHOD,
  DBUS_BUS_NAME,
  DBUS_OBJECT_PATH,
  DOMAIN_EVENT_SIGNAL,
  DomainEventBusCore,
  EVENTS_BUS_NAME,
  EVENTS_INTERFACE,
  EVENTS_OBJECT_PATH,
  HYDRATION_METHOD,
  HYDRATION_TIMEOUT_MS,
  JOBS_CLEARED_SIGNAL,
  NAME_OWNER_CHANGED_SIGNAL,
  type EventBusTransport,
} from "./event-bus-core";

class GioEventBusTransport implements EventBusTransport {
  private connection: Gio.DBusConnection | null = null;

  private ensure(): Gio.DBusConnection {
    if (this.connection === null) {
      this.connection = Gio.bus_get_sync(Gio.BusType.SESSION, null);
    }
    return this.connection;
  }

  //: Install the match rules. Called before any hydration so a signal racing
  //: the read is either delivered after the rule is installed or superseded
  //: by the hydrated `(epoch, seq)` baseline.
  startSignals(
    onDomainEvent: (params: unknown[]) => void,
    onJobsCleared: (params: unknown[]) => void,
    onHubRestart: () => void,
  ): void {
    const connection = this.ensure();
    connection.signal_subscribe(
      null,
      EVENTS_INTERFACE,
      DOMAIN_EVENT_SIGNAL,
      EVENTS_OBJECT_PATH,
      null,
      Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, parameters) =>
        onDomainEvent(parameters.deepUnpack() as unknown[]),
    );
    connection.signal_subscribe(
      null,
      EVENTS_INTERFACE,
      JOBS_CLEARED_SIGNAL,
      EVENTS_OBJECT_PATH,
      null,
      Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, parameters) =>
        onJobsCleared(parameters.deepUnpack() as unknown[]),
    );
    // Belt-and-braces restart: a new owner of the well-known name (arg0
    // filter) is a hub start even if `JobsCleared` was lost. Ownership loss
    // (empty new owner) is the supervisor's concern, not the bar's.
    connection.signal_subscribe(
      DBUS_BUS_NAME,
      DBUS_BUS_NAME,
      NAME_OWNER_CHANGED_SIGNAL,
      DBUS_OBJECT_PATH,
      EVENTS_BUS_NAME,
      Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, parameters) => {
        const body = parameters.deepUnpack() as string[];
        if (body.length === 3 && body[2]) onHubRestart();
      },
    );
  }

  getTopicState(topic: string): Record<string, unknown> | null {
    const reply = this.ensure().call_sync(
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
    const unpacked = reply.deepUnpack() as unknown[];
    if (!Array.isArray(unpacked) || unpacked.length === 0) return null;
    const state = unpacked[0];
    return state !== null && typeof state === "object"
      ? (state as Record<string, unknown>)
      : null;
  }

  control(jobId: string, action: string): void {
    this.ensure().call_sync(
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

// One shared consumer for the whole bar; `subscribe` lazily connects.
export const domainEvents = new DomainEventBusCore(new GioEventBusTransport());

export {
  CAPTURE_STATE_TOPIC,
  CONTROL_METHOD,
  DOMAIN_EVENT_SIGNAL,
  EVENTS_BUS_NAME,
  EVENTS_INTERFACE,
  EVENTS_OBJECT_PATH,
  HYDRATION_METHOD,
  JOBS_CLEARED_SIGNAL,
  SPEEDTEST_FINISHED_TOPIC,
} from "./event-bus-core";
export type { DomainPayload, RestartHandler, TopicHandler } from "./event-bus-core";

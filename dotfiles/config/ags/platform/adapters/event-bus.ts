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
// literal live in the platform seam `../ports/event-client.ts` (no GJS
// imports), pinned to `contracts/event-contract.{json,xml}` by the node drift
// test. This file is only the Gio seam and the app binding of the reactive
// runtime `EventHub.select` needs.

import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";
import { agsRuntime } from "./astal";
import {
  CONTROL_METHOD,
  DBUS_BUS_NAME,
  DBUS_OBJECT_PATH,
  DOMAIN_EVENT_SIGNAL,
  EMIT_METHOD,
  DomainEventBusCore,
  EVENTS_BUS_NAME,
  EVENTS_INTERFACE,
  EVENTS_OBJECT_PATH,
  HYDRATION_METHOD,
  HYDRATION_TIMEOUT_MS,
  JOBS_CLEARED_SIGNAL,
  NAME_OWNER_CHANGED_SIGNAL,
  SPEEDTEST_STATE_TOPIC,
  type EventBusTransport,
} from "../ports/event-client";

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
        onDomainEvent(parameters.recursiveUnpack() as unknown[]),
    );
    connection.signal_subscribe(
      null,
      EVENTS_INTERFACE,
      JOBS_CLEARED_SIGNAL,
      EVENTS_OBJECT_PATH,
      null,
      Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, parameters) =>
        onJobsCleared(parameters.recursiveUnpack() as unknown[]),
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
        const body = parameters.recursiveUnpack() as string[];
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
    const unpacked = reply.recursiveUnpack() as unknown[];
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

// One shared consumer for the whole bar; `subscribe` lazily connects. The
// reactive runtime is injected here (AD-2) so `EventHub.select` works in the
// app; the state machine itself stays pure in the platform seam.
export const domainEvents = new DomainEventBusCore(new GioEventBusTransport(), agsRuntime);

//: Lifecycle states of `speedtest.state` (mirrors the contract enum).
export type SpeedTestState = "starting" | "done" | "error";

//: What started the run. The notification card's footer and its failure copy
//: both distinguish a scheduled run from one you asked for, and `wallpaper.state`
//: already established `trigger` as the contract's name for "the operation that
//: produced this transition".
export type SpeedTestTrigger = "scheduled" | "manual" | "connect";

export type SpeedTestMeasurements = {
  down_mbps: number
  up_mbps: number
  latency_ms: number
  //: The CONTEXT of the measurement, so the card can name what it measured
  //: rather than only that something ran. Both are strings and BOTH MAY BE
  //: EMPTY: "" is the honest value for "unavailable" (a wired connection has no
  //: SSID, some backends report no server name), and it is what a consumer can
  //: test on. Making them optional instead would let an absent key and an empty
  //: value mean different things, and nothing downstream distinguishes them.
  ssid: string
  server_name: string
}

//: One-line, human-readable. Never a traceback: the card has ~44 wrapped
//: characters of body text and the panel's `lastError` row already carries the
//: detail for anyone who wants it.
export type SpeedTestReason = string

/**
 * Publish the contract-shaped speed-test lifecycle event.
 *
 * The hub validates the topic: `state` and `trigger` are required on every
 * payload, the three measurements must be doubles, and both are enums — a
 * value outside them is rejected as a schema failure, not silently coerced.
 *
 * `measurements` rides only on `done` and `reason` only on `error`; the
 * signatures make that a compile error rather than a payload the hub rejects at
 * runtime, so an `error` can never be published carrying numbers or a `done`
 * carrying a failure string.
 *
 * A missing hub is non-fatal to the speed-test UI, exactly as the publisher
 * this replaces: the run still executes, the panel rows still update.
 */
export function publishSpeedTestState(
  state: SpeedTestState,
  trigger: SpeedTestTrigger,
  terminal?: SpeedTestMeasurements | SpeedTestReason,
): void {
  const payload: Record<string, GLib.Variant> = {
    state: new GLib.Variant("s", state),
    trigger: new GLib.Variant("s", trigger),
  }
  if (state === "done") {
    const measured = terminal as SpeedTestMeasurements
    payload.down_mbps = new GLib.Variant("d", measured.down_mbps)
    payload.up_mbps = new GLib.Variant("d", measured.up_mbps)
    payload.latency_ms = new GLib.Variant("d", measured.latency_ms)
    // Always sent, even when empty. The contract carries them on `done` and the
    // card falls back on an empty string, so omitting them would leave the
    // consumer guessing whether "" means "unavailable" or "never sent".
    payload.ssid = new GLib.Variant("s", measured.ssid ?? "")
    payload.server_name = new GLib.Variant("s", measured.server_name ?? "")
  } else if (state === "error") {
    payload.reason = new GLib.Variant("s", terminal as SpeedTestReason)
  }
  try {
    Gio.bus_get_sync(Gio.BusType.SESSION, null).call_sync(
      EVENTS_BUS_NAME,
      EVENTS_OBJECT_PATH,
      EVENTS_INTERFACE,
      EMIT_METHOD,
      new GLib.Variant("(sa{sv})", [SPEEDTEST_STATE_TOPIC, payload]),
      null,
      Gio.DBusCallFlags.NONE,
      2000,
      null,
    );
  } catch (error) {
    console.error(`event-bus: publish ${SPEEDTEST_STATE_TOPIC} (${state}) failed: ${error}`);
  }
}

export {
  CAPTURE_STATE_TOPIC,
  CONTROL_METHOD,
  DOMAIN_EVENT_SIGNAL,
  EVENTS_BUS_NAME,
  EVENTS_INTERFACE,
  EVENTS_OBJECT_PATH,
  HYDRATION_METHOD,
  JOBS_CLEARED_SIGNAL,
  SPEEDTEST_STATE_TOPIC,
} from "../ports/event-client";
export type { DomainPayload, EventPayload, RestartHandler, TopicHandler } from "../ports/event-client";

// Domain-event binding for the AGS bar (Phase 5, AD-34/AD-37).
//
// The bar is a THIN CONSUMER of the hub's `org.dotfiles.Events1` surface:
// it subscribes to the contract `DomainEvent` signal, filters by topic, and
// never imports the runtime. UI indicators are driven by DOMAIN events only
// (`DomainEvent`), never by `JobStarted`/`JobFinished` (AD-37). Control
// actions go back through the hub's `Control` method — the single control
// path — never by shelling the tool.
//
// The contract literals below are pinned to `contracts/event-contract.json`
// by the runtime's per-language drift gate (there is no JS test runner in
// this repo).

import Gio from "gi://Gio?version=2.0";
import GLib from "gi://GLib?version=2.0";

export const EVENTS_BUS_NAME = "org.dotfiles.Events";
export const EVENTS_OBJECT_PATH = "/org/dotfiles/Events";
export const EVENTS_INTERFACE = "org.dotfiles.Events1";
export const DOMAIN_EVENT_SIGNAL = "DomainEvent";
export const JOBS_CLEARED_SIGNAL = "JobsCleared";
export const CONTROL_METHOD = "Control";

export type DomainPayload = { [key: string]: unknown };
export type TopicHandler = (topic: string, payload: DomainPayload) => void;
export type RestartHandler = () => void;

// One shared connection for the whole bar; `subscribe` lazily connects.
class DomainEventBus {
  private connection: Gio.DBusConnection | null = null;
  private readonly handlers = new Map<string, Set<TopicHandler>>();
  private readonly restartHandlers = new Set<RestartHandler>();

  private connect(): Gio.DBusConnection {
    if (this.connection !== null) return this.connection;
    const connection = Gio.bus_get_sync(Gio.BusType.SESSION, null);
    connection.signal_subscribe(
      null,
      EVENTS_INTERFACE,
      DOMAIN_EVENT_SIGNAL,
      EVENTS_OBJECT_PATH,
      null,
      Gio.DBusSignalFlags.NONE,
      (_connection, _sender, _path, _iface, _signal, parameters) =>
        this.dispatchDomainEvent(parameters),
    );
    connection.signal_subscribe(
      null,
      EVENTS_INTERFACE,
      JOBS_CLEARED_SIGNAL,
      EVENTS_OBJECT_PATH,
      null,
      Gio.DBusSignalFlags.NONE,
      () => this.dispatchRestart(),
    );
    this.connection = connection;
    return connection;
  }

  subscribe(topic: string, handler: TopicHandler): void {
    this.connect();
    let handlers = this.handlers.get(topic);
    if (handlers === undefined) {
      handlers = new Set<TopicHandler>();
      this.handlers.set(topic, handlers);
    }
    handlers.add(handler);
  }

  onRestart(handler: RestartHandler): void {
    this.connect();
    this.restartHandlers.add(handler);
  }

  // Hub restart (new epoch) invalidates all hydrated state; consumers
  // re-read on the next push. The bar holds no cached state to discard but
  // re-arms its handlers so a stale UI cannot linger.
  control(jobId: string, action: string): void {
    const connection = this.connect();
    try {
      connection.call_sync(
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
    } catch (error) {
      console.error(`event-bus: Control(${jobId}, ${action}) failed: ${error}`);
    }
  }

  private dispatchDomainEvent(parameters: GLib.Variant): void {
    const [topic, _producer, _seq, _epoch, payload] = parameters.deepUnpack() as [
      string,
      string,
      number,
      number,
      DomainPayload,
    ];
    const handlers = this.handlers.get(topic);
    if (handlers === undefined) return;
    for (const handler of handlers) {
      try {
        handler(topic, payload);
      } catch (error) {
        console.error(`event-bus: handler for ${topic} failed: ${error}`);
      }
    }
  }

  private dispatchRestart(): void {
    for (const handler of this.restartHandlers) {
      try {
        handler();
      } catch (error) {
        console.error(`event-bus: restart handler failed: ${error}`);
      }
    }
  }
}

export const domainEvents = new DomainEventBus();

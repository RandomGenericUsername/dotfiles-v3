// The ONE domain-event client (spine AD-5; the port surface is corrected by
// AD-4 and defined in doc 101 §4.2).
//
// This module holds the contract constants and the subscribe-before-read
// hydration state machine with **no GJS imports**, so the node test runner can
// import and exercise it. `platform/adapters/event-bus.ts` supplies the Gio
// transport and the app supplies the reactive runtime the `EventHub.select` accessors are built
// on. This is the single state machine: the bar imports this seam, and the
// app-local copies under `src/gui-tools/**` are the `ags-apps` epic's to migrate
// (AD-20 step 8).
//
// Contract literals are pinned to `contracts/event-contract.json` / `.xml` by
// `src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`
// (executed, never text-scanned).

import type { ReadAccessor, ReactiveRuntime } from "./reactive";

export const EVENTS_BUS_NAME = "org.dotfiles.Events";
export const EVENTS_OBJECT_PATH = "/org/dotfiles/Events";
export const EVENTS_INTERFACE = "org.dotfiles.Events1";
export const DOMAIN_EVENT_SIGNAL = "DomainEvent";
export const JOBS_CLEARED_SIGNAL = "JobsCleared";
export const CONTROL_METHOD = "Control";
export const EMIT_METHOD = "Emit";
export const HYDRATION_METHOD = "GetTopicState";
export const RESERVED_EPOCH = "_epoch";
export const RESERVED_SEQ = "_seq";
export const CAPTURE_STATE_TOPIC = "capture.state";
//: The terminal-only predecessor topic was removed: it had no subscriber, and
//: the topic now covers the whole run lifecycle (`{state, trigger}`) so the
//: notifications app can build one card and mutate it in place, exactly as the
//: wallpaper change does, instead of learning only that something finished. The
//: dead name is intentionally not repeated here so a tree-wide `git grep` scan
//: stays clean.
export const SPEEDTEST_STATE_TOPIC = "speedtest.state";

//: Bus-daemon interface/object/signal used as the restart fallback.
export const DBUS_BUS_NAME = "org.freedesktop.DBus";
export const DBUS_OBJECT_PATH = "/org/freedesktop/DBus";
export const NAME_OWNER_CHANGED_SIGNAL = "NameOwnerChanged";

//: Client-side hydration timeout (contract: a hub call may time out; a caller
//: treats that as transient and re-hydrates). Kept short so a missing hub
//: cannot stall the bar at start-up.
export const HYDRATION_TIMEOUT_MS = 2000;

export type EventPayload = { [key: string]: unknown };
//: The pre-AD-4 name for the same shape, kept so existing importers do not
//: churn on a rename that changes no behaviour.
export type DomainPayload = EventPayload;
export type Pair = [number, number];
export type TopicHandler = (topic: string, payload: EventPayload) => void;
export type RestartHandler = () => void;
export type EventMap = Record<string, unknown>;

//: Transport seam: the only thing the domain bus needs from Gio. Production
//: injects the Gio implementation; tests inject a scripted fake (no bus).
export interface EventBusTransport {
  startSignals(
    onDomainEvent: (params: unknown[]) => void,
    onJobsCleared: (params: unknown[]) => void,
    onHubRestart: () => void,
  ): void;
  getTopicState(topic: string): Record<string, unknown> | null;
  control(jobId: string, action: string): void;
}

//: AD-4 corrected `EventSource`: `subscribe`/`onRestart` return unsubscribe
//: handles. `current`/`onRestart`/`control` stay optional on the SOURCE (a
//: baseline source may implement none of them); the HUB below makes control
//: first-class.
export interface EventSource {
  subscribe(topic: string, handler: TopicHandler): () => void;
  current?(topic: string): EventPayload | null;
  onRestart?(handler: RestartHandler): () => void;
  control?(jobId: string, action: string): void;
}

//: AD-4 `EventHub`: a reactive `select` plus first-class job `control`.
export interface EventHub<M extends EventMap> {
  select<T extends keyof M>(topic: T): ReadAccessor<M[T] | null>;
  on<T extends keyof M>(topic: T, handler: (payload: M[T]) => void): () => void;
  control(jobId: string, action: string): void;
}

//: Coerce a wire `u` member; anything unexpected becomes ``0``.
export function asUint(value: unknown): number {
  return typeof value === "number" && Number.isFinite(value) && value > 0
    ? Math.floor(value)
    : 0;
}

//: Contract `delivery`: compare `(epoch, seq)` lexicographically, never `seq`
//: alone, so an epoch bump (which resets seq) still wins.
export function isNewer(baseline: Pair | undefined, epoch: number, seq: number): boolean {
  const baseEpoch = baseline === undefined ? 0 : baseline[0];
  const baseSeq = baseline === undefined ? 0 : baseline[1];
  return epoch > baseEpoch || (epoch === baseEpoch && seq > baseSeq);
}

export interface ParsedTopicState {
  epoch: number;
  seq: number;
  payload: EventPayload;
}

//: Split the reserved hydration members from the payload. `GetTopicState`
//: returns the last payload plus `_epoch`/`_seq` (contract `delivery`).
export function parseTopicState(raw: unknown): ParsedTopicState {
  if (raw === null || typeof raw !== "object") {
    return { epoch: 0, seq: 0, payload: {} };
  }
  const record = raw as Record<string, unknown>;
  const payload: EventPayload = {};
  for (const key of Object.keys(record)) {
    if (key !== RESERVED_EPOCH && key !== RESERVED_SEQ) payload[key] = record[key];
  }
  return {
    epoch: asUint(record[RESERVED_EPOCH]),
    seq: asUint(record[RESERVED_SEQ]),
    payload,
  };
}

type SelectCell = [ReadAccessor<EventPayload | null>, (value: EventPayload | null) => void];

export class DomainEventBusCore<M extends EventMap = EventMap>
  implements EventSource, EventHub<M>
{
  private readonly transport: EventBusTransport;
  private readonly runtime: ReactiveRuntime | undefined;
  private readonly handlers = new Map<string, Set<TopicHandler>>();
  private readonly restartHandlers = new Set<RestartHandler>();
  private readonly cells = new Map<string, SelectCell>();
  private readonly hydrated = new Map<string, Pair>();
  private readonly lastPayloads = new Map<string, EventPayload>();
  private started = false;
  private lastEpoch = 0;

  //: The reactive runtime is injected (AD-2): it is needed only by `select`.
  //: A subscribe-only consumer may omit it, and `select` then fails loudly
  //: rather than silently returning a non-reactive value.
  constructor(transport: EventBusTransport, runtime?: ReactiveRuntime) {
    this.transport = transport;
    this.runtime = runtime;
  }

  //: Subscribe the signal match rules FIRST, then hydrate the topic
  //: (subscribe-before-read). The hydrated payload is delivered straight to
  //: handlers, so a bar that starts mid-recording renders the current state
  //: without waiting for the next transition/tick. Returns an unsubscribe
  //: handle (AD-4).
  subscribe(topic: string, handler: TopicHandler): () => void {
    const unsubscribe = this.track(topic, handler);
    this.hydrateTopic(topic);
    return unsubscribe;
  }

  //: AD-4 `EventHub.on`: the payload-only form of `subscribe`, returning an
  //: unsubscribe handle.
  on<T extends keyof M>(topic: T, handler: (payload: M[T]) => void): () => void {
    return this.subscribe(String(topic), (_topic, payload) => handler(payload as M[T]));
  }

  //: AD-4 `EventHub.select`: a reactive accessor over the topic's latest
  //: payload. `null` until any state is known (a `(0, 0)` hydration is "no
  //: state yet", AD-5).
  select<T extends keyof M>(topic: T): ReadAccessor<M[T] | null> {
    const key = String(topic);
    const existing = this.cells.get(key);
    if (existing !== undefined) {
      return existing[0] as unknown as ReadAccessor<M[T] | null>;
    }
    if (this.runtime === undefined) {
      throw new Error(
        "event-client: select() requires an injected reactive runtime (AD-2)",
      );
    }
    const [get, set] = this.runtime.createState<EventPayload | null>(null);
    this.cells.set(key, [get, set]);
    this.track(key, (_topic, payload) => set(payload));
    this.hydrateTopic(key);
    return get as unknown as ReadAccessor<M[T] | null>;
  }

  //: AD-4 `EventSource.current`: the last delivered/hydrated payload, or null.
  current(topic: string): EventPayload | null {
    return this.lastPayloads.get(topic) ?? null;
  }

  onRestart(handler: RestartHandler): () => void {
    this.connect();
    this.restartHandlers.add(handler);
    return () => {
      this.restartHandlers.delete(handler);
    };
  }

  control(jobId: string, action: string): void {
    this.connect();
    try {
      this.transport.control(jobId, action);
    } catch (error) {
      console.error(`event-bus: Control(${jobId}, ${action}) failed: ${error}`);
    }
  }

  private track(topic: string, handler: TopicHandler): () => void {
    this.connect();
    let handlers = this.handlers.get(topic);
    if (handlers === undefined) {
      handlers = new Set<TopicHandler>();
      this.handlers.set(topic, handlers);
    }
    handlers.add(handler);
    return () => {
      const current = this.handlers.get(topic);
      if (current === undefined) return;
      current.delete(handler);
      if (current.size === 0) this.handlers.delete(topic);
    };
  }

  private connect(): void {
    if (this.started) return;
    this.started = true;
    this.transport.startSignals(
      (params) => this.dispatchDomainEvent(params),
      (params) => this.dispatchJobsCleared(params),
      () => this.handleHubRestart(),
    );
  }

  private hydrateTopic(topic: string): void {
    let raw: Record<string, unknown> | null = null;
    try {
      raw = this.transport.getTopicState(topic);
    } catch (error) {
      // Absence is a no-op, never an error (contract Rules).
      console.error(`event-bus: hydration of ${topic} failed: ${error}`);
    }
    const state = parseTopicState(raw);
    this.hydrated.set(topic, [state.epoch, state.seq]);
    this.lastEpoch = Math.max(this.lastEpoch, state.epoch);
    // A `(0, 0)` hydration means "no state yet" (AD-5): deliver nothing.
    if (state.epoch > 0 || Object.keys(state.payload).length > 0) {
      this.deliver(topic, state.payload);
    }
  }

  private dispatchDomainEvent(params: unknown[]): void {
    if (params.length < 5) return;
    const topic = params[0];
    const seq = asUint(params[2]);
    const epoch = asUint(params[3]);
    const payload = params[4];
    if (typeof topic !== "string" || !this.handlers.has(topic)) return;
    if (!isNewer(this.hydrated.get(topic), epoch, seq)) return; // stale/replayed
    // Advance the baseline as soon as the pair is accepted (at-most-once).
    this.hydrated.set(topic, [epoch, seq]);
    this.lastEpoch = Math.max(this.lastEpoch, epoch);
    if (payload === null || typeof payload !== "object") return;
    this.deliver(topic, payload as EventPayload);
  }

  //: Hub (re)start: every prior `(epoch, seq)` and payload is invalid. Reset
  //: the UI first, then re-read every tracked topic so a still-live capture
  //: re-renders instead of lingering stale.
  private dispatchJobsCleared(params: unknown[]): void {
    const epoch = asUint(params.length > 0 ? params[0] : 0);
    if (epoch <= this.lastEpoch) return; // duplicate/replayed restart
    this.lastEpoch = epoch;
    this.handleHubRestart();
  }

  //: Restart path shared by `JobsCleared` and (belt-and-braces, per contract
  //: `delivery`) a `NameOwnerChanged` new owner — `JobsCleared` is itself
  //: at-most-once. Idempotent: a reset + re-hydrate is safe to repeat. The
  //: selected accessors are reset to `null` (no state yet) before re-hydration.
  handleHubRestart(): void {
    this.hydrated.clear();
    this.lastPayloads.clear();
    for (const cell of this.cells.values()) cell[1](null);
    for (const handler of this.restartHandlers) {
      try {
        handler();
      } catch (error) {
        console.error(`event-bus: restart handler failed: ${error}`);
      }
    }
    for (const topic of this.handlers.keys()) this.hydrateTopic(topic);
  }

  private deliver(topic: string, payload: EventPayload): void {
    this.lastPayloads.set(topic, payload);
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

  // ── Observability (tests / diagnostics) ────────────────────────────

  hydratedPair(topic: string): Pair {
    const pair = this.hydrated.get(topic);
    return pair === undefined ? [0, 0] : [pair[0], pair[1]];
  }

  get lastEpochSeen(): number {
    return this.lastEpoch;
  }
}

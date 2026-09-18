// Pure core for the ICME editor's `org.dotfiles.Events1` consumer.
// Copied from the wallpaper-selector proven core
// (`src/gui-tools/wallpaper-selector/lib/event-bus-core.ts`) — a standalone AGS
// app cannot import across config directories. ICME consumes `wallpaper.state`
// so a palette swap restyles the editor live, without a restart (the runtime
// skips this instance to protect unsaved edits; see the shared
// `AgsReloader.DEFAULT_SKIP_CONFIG_DIRS`).
//
// This module holds the contract constants and the subscribe-before-read
// hydration state machine with **no GJS imports**, so the node test runner can
// import and exercise it. `event-bus.ts` supplies the Gio transport.
//
// Contract literals are pinned to `contracts/event-contract.json` / `.xml` by
// `src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`
// (executed, never text-scanned).

export const EVENTS_BUS_NAME = "org.dotfiles.Events";
export const EVENTS_OBJECT_PATH = "/org/dotfiles/Events";
export const EVENTS_INTERFACE = "org.dotfiles.Events1";
export const DOMAIN_EVENT_SIGNAL = "DomainEvent";
export const JOBS_CLEARED_SIGNAL = "JobsCleared";
export const CONTROL_METHOD = "Control";
export const HYDRATION_METHOD = "GetTopicState";
export const RESERVED_EPOCH = "_epoch";
export const RESERVED_SEQ = "_seq";
export const WALLPAPER_STATE_TOPIC = "wallpaper.state";

//: Bus-daemon interface/object/signal used as the restart fallback.
export const DBUS_BUS_NAME = "org.freedesktop.DBus";
export const DBUS_OBJECT_PATH = "/org/freedesktop/DBus";
export const NAME_OWNER_CHANGED_SIGNAL = "NameOwnerChanged";

//: Client-side hydration timeout (contract: a hub call may time out; a caller
//: treats that as transient and re-hydrates). Kept short so a missing hub
//: cannot stall the editor at start-up.
export const HYDRATION_TIMEOUT_MS = 2000;

export type DomainPayload = { [key: string]: unknown };
export type Pair = [number, number];
export type TopicHandler = (topic: string, payload: DomainPayload) => void;
export type RestartHandler = () => void;

//: `wallpaper.state` payload (contract topics). `trigger` is an
//: optional/additive discriminator naming the palette-affecting operation;
//: older publishers omit it and consumers must tolerate its absence.
export interface WallpaperStatePayload extends DomainPayload {
  state: "applying" | "visible" | "done" | "error";
  wallpaper_hash: string;
  trigger?: "set" | "regenerate" | "reconcile" | "reactive";
}

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
  payload: DomainPayload;
}

//: Split the reserved hydration members from the payload. `GetTopicState`
//: returns the last payload plus `_epoch`/`_seq` (contract `delivery`).
export function parseTopicState(raw: unknown): ParsedTopicState {
  if (raw === null || typeof raw !== "object") {
    return { epoch: 0, seq: 0, payload: {} };
  }
  const record = raw as Record<string, unknown>;
  const payload: DomainPayload = {};
  for (const key of Object.keys(record)) {
    if (key !== RESERVED_EPOCH && key !== RESERVED_SEQ) payload[key] = record[key];
  }
  return {
    epoch: asUint(record[RESERVED_EPOCH]),
    seq: asUint(record[RESERVED_SEQ]),
    payload,
  };
}

export class DomainEventBusCore {
  private readonly transport: EventBusTransport;
  private readonly handlers = new Map<string, Set<TopicHandler>>();
  private readonly restartHandlers = new Set<RestartHandler>();
  private readonly hydrated = new Map<string, Pair>();
  private started = false;
  private lastEpoch = 0;

  constructor(transport: EventBusTransport) {
    this.transport = transport;
  }

  //: Subscribe the signal match rules FIRST, then hydrate the topic
  //: (subscribe-before-read). The hydrated payload is delivered straight to
  //: handlers, so an editor opened mid-apply renders the current state
  //: without waiting for the next transition.
  subscribe(topic: string, handler: TopicHandler): void {
    this.connect();
    let handlers = this.handlers.get(topic);
    if (handlers === undefined) {
      handlers = new Set<TopicHandler>();
      this.handlers.set(topic, handlers);
    }
    handlers.add(handler);
    this.hydrateTopic(topic);
  }

  onRestart(handler: RestartHandler): void {
    this.connect();
    this.restartHandlers.add(handler);
  }

  control(jobId: string, action: string): void {
    this.connect();
    try {
      this.transport.control(jobId, action);
    } catch (error) {
      console.error(`event-bus: Control(${jobId}, ${action}) failed: ${error}`);
    }
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
    this.deliver(topic, payload as DomainPayload);
  }

  //: Hub (re)start: every prior `(epoch, seq)` and payload is invalid. Reset
  //: the UI first, then re-read every tracked topic so a still-live apply
  //: re-renders instead of lingering stale.
  private dispatchJobsCleared(params: unknown[]): void {
    const epoch = asUint(params.length > 0 ? params[0] : 0);
    if (epoch <= this.lastEpoch) return; // duplicate/replayed restart
    this.lastEpoch = epoch;
    this.handleHubRestart();
  }

  //: Restart path shared by `JobsCleared` and (belt-and-braces, per contract
  //: `delivery`) a `NameOwnerChanged` new owner — `JobsCleared` is itself
  //: at-most-once. Idempotent: a reset + re-hydrate is safe to repeat.
  handleHubRestart(): void {
    this.hydrated.clear();
    for (const handler of this.restartHandlers) {
      try {
        handler();
      } catch (error) {
        console.error(`event-bus: restart handler failed: ${error}`);
      }
    }
    for (const topic of this.handlers.keys()) this.hydrateTopic(topic);
  }

  private deliver(topic: string, payload: DomainPayload): void {
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

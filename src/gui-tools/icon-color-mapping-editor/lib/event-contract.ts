// Contract-shaped `icme.saved` publisher core (Phase 5, 5-4).
//
// Pure (no GJS imports) so the node test runner can exercise the emit shape
// against a mocked bus; `event-bus.ts` supplies the Gio transport. Contract
// literals are pinned to `contracts/event-contract.{json,xml}` by
// `tests/event-contract-drift.mjs` (executed, never text-scanned).

export const EVENTS_BUS_NAME = "org.dotfiles.Events";
export const EVENTS_OBJECT_PATH = "/org/dotfiles/Events";
export const EVENTS_INTERFACE = "org.dotfiles.Events1";
export const EMIT_METHOD = "Emit";
export const ICME_SAVED_TOPIC = "icme.saved";

export interface IcmeSavedEmit {
  topic: string;
  payload: { path: string };
}

//: The exact `icme.saved` emit: topic + `{ path }` payload (contract topics).
export function buildIcmeSavedEmit(path: string): IcmeSavedEmit {
  return { topic: ICME_SAVED_TOPIC, payload: { path } };
}

//: Bus seam: production wraps Gio; tests inject a recording fake.
export interface EmitPort {
  emit(topic: string, payload: Record<string, unknown>): void;
}

//: Publish `icme.saved {path}` through the hub's validated `Emit`. An empty
//: path is a no-op (nothing meaningful to announce); success/absence is the
//: transport's concern.
export function publishIcmeSavedVia(port: EmitPort, path: string): void {
  if (path === "") return;
  const event = buildIcmeSavedEmit(path);
  port.emit(event.topic, event.payload);
}

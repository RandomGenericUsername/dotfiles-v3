import assert from "node:assert/strict"
import { AudioSessionRuntime } from "../../../../dotfiles/config/ags/audio/application/runtime/audio-session-runtime.ts"

class FakeObservation {
  listeners = new Set()
  constructor(initial) { this.initial = initial }
  async hydrate() { return { kind: "snapshot", session: this.initial } }
  subscribe(listener) { this.listeners.add(listener); return () => this.listeners.delete(listener) }
  emit(session) { for (const listener of this.listeners) listener({ kind: "snapshot", session }) }
}

const stream = (id, { appId = "browser", effective = "C", requested = null, intent = { kind: "unknown" } } = {}) => ({
  id, appId, direction: "output", endpointId: effective, requestedEndpointId: requested,
  routeIntent: intent, volume: { level: 0.7, muted: false }, current: true,
})
const session = (preferred, streams) => ({
  preferredOutputId: preferred, preferredInputId: null,
  outputs: ["A", "B", "C"].map((id) => ({ id, name: id, available: true, volume: { level: 0.5, muted: false } })),
  inputs: [], input: null, apps: [{ id: "browser", displayName: "Browser" }], streams, players: [],
})

const startup = session("C", [
  stream("existing-default"),
  stream("existing-override", { requested: "A" }),
])
const pw = new FakeObservation(startup)
const mpris = {
  async hydrate() { return { kind: "snapshot", players: [] } },
  subscribe() { return () => {} },
}
const writes = []
const pipewire = { setStreamTarget: async (id, endpoint) => writes.push([id, endpoint]) }
const runtime = new AudioSessionRuntime(pw, mpris, pipewire)
await runtime.start()

let current = runtime.current()
assert.equal(current.streams.find((item) => item.id === "existing-default").routeIntent.kind, "unknown",
  "target-less streams present at startup retain unknown history")
assert.deepEqual(current.streams.find((item) => item.id === "existing-override").routeIntent,
  { kind: "explicit", endpointId: "A" }, "requested target restores authoritative explicit intent")

pw.emit(session("C", [
  stream("existing-default"),
  stream("existing-override", { requested: "A" }),
  stream("new-follow"),
]))
current = runtime.current()
assert.equal(current.streams.find((item) => item.id === "new-follow").routeIntent.kind, "follow-preferred",
  "new target-less streams follow preferred even when the effective endpoint happens to equal it")

pw.emit(session("C", [
  stream("existing-default"),
  stream("existing-override", { requested: "A" }),
  stream("new-follow", { requested: "B" }),
]))
assert.deepEqual(runtime.current().streams.find((item) => item.id === "new-follow").routeIntent,
  { kind: "explicit", endpointId: "B" }, "external requested-target change becomes explicit")

pw.emit(session("C", [
  stream("existing-default"),
  stream("existing-override", { requested: "A" }),
  stream("new-follow"),
]))
assert.equal(runtime.current().streams.find((item) => item.id === "new-follow").routeIntent.kind, "follow-preferred",
  "clearing the requested target restores follow-preferred")

runtime.record("new-follow", { kind: "explicit", endpointId: "A" })
pw.emit(session("B", [
  stream("existing-default", { effective: "B" }),
  stream("existing-override", { effective: "B", requested: "B" }),
  stream("new-follow", { effective: "B", requested: "B" }),
]))
current = runtime.current()
assert.deepEqual(current.streams.find((item) => item.id === "new-follow").routeIntent,
  { kind: "explicit", endpointId: "A" }, "default-induced target churn does not erase recorded explicit intent")
assert.deepEqual(writes.at(-1), ["new-follow", "A"], "explicit route is reasserted on preferred-output change")
assert.equal(current.streams.find((item) => item.id === "existing-default").routeIntent.kind, "unknown",
  "effective endpoint changes do not turn unknown into follow-preferred")

pw.emit(session("B", [stream("existing-default"), stream("existing-override", { requested: "B" })]))
assert.equal(runtime.current().streams.some((item) => item.id === "new-follow"), false, "unlink removes current stream")
runtime.record("new-follow", { kind: "explicit", endpointId: "C" })
pw.emit(session("B", [stream("existing-default"), stream("existing-override", { requested: "B" }), stream("new-follow", { requested: "B" })]))
assert.deepEqual(runtime.current().streams.find((item) => item.id === "new-follow").routeIntent,
  { kind: "explicit", endpointId: "A" }, "same stream ID relink retains intent and stale commands cannot overwrite it")

pw.emit(session("B", [stream("existing-default"), stream("existing-override", { requested: "B" }), stream("new-id-same-app")]))
// CHANGED 2026-10-07 (owner decision). This asserted 'follow-preferred': "a
// different stream ID does not inherit intent based only on app identity".
// That was right while intent was per-stream only, and it is what broke the
// paused case -- Tidal releases its stream while paused, so on resume a NEW
// stream ID appeared, inherited nothing, and the route the user had set was
// silently dropped.
//
// The distinction that matters: this is not inferring intent from app identity.
// `recordApp`/`record` stored an EXPLICIT user choice for that app, and the new
// stream is inheriting a recorded decision, not a guess. Inference from
// identity alone remains forbidden -- that is the 'unknown' assertion below.
assert.equal(runtime.current().streams.find((item) => item.id === "new-id-same-app").routeIntent.kind, "explicit",
  "a new stream for an app with recorded app-scoped intent inherits that decision")
assert.notEqual(runtime.current().streams.find((item) => item.id === "existing-default").routeIntent.kind, "follow-preferred",
  "identity alone still never proves intent")

// Regression: an app with NO live stream must still publish.
//
// A paused app has released its stream, so its identity is absent from
// `session.apps` (derived from live streams). The first version of recordApp
// published only when the app was already in `apps`, so setting a paused app's
// route stored the intent and emitted nothing -- the row kept its old label
// until an unrelated event republished the session. Reported as "I select
// speakers and it won't change".
let publishes = 0
const unsub = runtime.subscribe(() => { publishes += 1 })
const before = publishes
runtime.recordApp("paused-app-with-no-stream", { kind: "explicit", endpointId: "A" })
assert.ok(publishes > before, "recordApp publishes for an app with no live stream")
assert.deepEqual(runtime.current().appIntents["paused-app-with-no-stream"],
  { kind: "explicit", endpointId: "A" }, "app intent is readable from the published session")
unsub()

runtime.dispose()
console.log("audio session runtime route-intent scenarios passed")

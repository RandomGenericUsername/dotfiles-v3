import { describe, it } from "node:test"
import assert from "node:assert/strict"

import { DomainEventBusCore, type EventBusTransport } from "../../platform/event-client.ts"
import { fakeRuntime } from "./fixtures/reactive-fixture.ts"

/**
 * The ONE domain-event client (AD-5), driven by a scripted fake transport and a
 * fake reactive runtime. These prove the mandatory contract the port exists for:
 * subscribe-before-read hydration, `(epoch, seq)` dedup, unsubscribe handles,
 * and the reset-then-re-hydrate restart path — none of which needs the bus.
 */

type CapturePayload = { state: "idle" | "recording" | "paused"; elapsed_seconds?: number }
type TestEvents = Record<string, unknown> & { "capture.state": CapturePayload }

function fakeTransport(initial: Record<string, Record<string, unknown>> = {}) {
  const calls: string[] = []
  let state: Record<string, Record<string, unknown>> = { ...initial }
  const signals = {
    onDomainEvent: (_params: unknown[]): void => {},
    onJobsCleared: (_params: unknown[]): void => {},
    onHubRestart: (): void => {},
  }
  const transport: EventBusTransport = {
    startSignals(onDomainEvent, onJobsCleared, onHubRestart) {
      calls.push("startSignals")
      signals.onDomainEvent = onDomainEvent
      signals.onJobsCleared = onJobsCleared
      signals.onHubRestart = onHubRestart
    },
    getTopicState(topic) {
      calls.push(`getTopicState:${topic}`)
      return topic in state ? state[topic] : null
    },
    control(jobId, action) {
      calls.push(`control:${jobId}:${action}`)
    },
  }
  return {
    transport,
    calls,
    signals,
    setState(next: Record<string, Record<string, unknown>>): void {
      state = { ...next }
    },
    dispatch(topic: string, seq: number, epoch: number, payload: unknown): void {
      signals.onDomainEvent([topic, "producer", seq, epoch, payload])
    },
  }
}

describe("one event client", () => {
  it("subscribes signal rules before reading topic state (subscribe-before-read)", () => {
    const fake = fakeTransport()
    const bus = new DomainEventBusCore(fake.transport)
    bus.subscribe("capture.state", () => {})
    assert.deepEqual(fake.calls, ["startSignals", "getTopicState:capture.state"])
  })

  it("delivers the hydrated payload immediately", () => {
    const fake = fakeTransport({
      "capture.state": { _epoch: 4, _seq: 7, state: "recording", elapsed_seconds: 12 },
    })
    const bus = new DomainEventBusCore(fake.transport)
    const seen: Array<[string, unknown]> = []
    bus.subscribe("capture.state", (topic, payload) => seen.push([topic, payload]))
    assert.equal(seen.length, 1)
    assert.equal(seen[0][0], "capture.state")
    assert.equal((seen[0][1] as CapturePayload).state, "recording")
    assert.deepEqual(bus.hydratedPair("capture.state"), [4, 7])
  })

  it("drops stale/replayed (epoch, seq) and advances on newer pairs", () => {
    const fake = fakeTransport({
      "capture.state": { _epoch: 4, _seq: 7, state: "recording" },
    })
    const bus = new DomainEventBusCore(fake.transport)
    const seen: unknown[] = []
    bus.subscribe("capture.state", (_topic, payload) => seen.push(payload))
    assert.equal(seen.length, 1)
    fake.dispatch("capture.state", 7, 4, { state: "paused" })
    fake.dispatch("capture.state", 6, 4, { state: "paused" })
    assert.equal(seen.length, 1, "equal and lower seq dropped")
    fake.dispatch("capture.state", 8, 4, { state: "paused" })
    assert.equal(seen.length, 2)
    assert.deepEqual(bus.hydratedPair("capture.state"), [4, 8])
    fake.dispatch("capture.state", 1, 5, { state: "recording" })
    assert.equal(seen.length, 3, "epoch bump wins over lower seq")
    assert.deepEqual(bus.hydratedPair("capture.state"), [5, 1])
  })

  it("unsubscribe stops delivery and removes the restart handler", () => {
    const fake = fakeTransport()
    const bus = new DomainEventBusCore(fake.transport)
    const seen: unknown[] = []
    const unsubscribe = bus.subscribe("capture.state", (_topic, payload) => seen.push(payload))
    fake.dispatch("capture.state", 1, 1, { state: "recording" })
    assert.equal(seen.length, 1)
    unsubscribe()
    fake.dispatch("capture.state", 2, 1, { state: "paused" })
    assert.equal(seen.length, 1, "no delivery after unsubscribe")

    let restarts = 0
    const offRestart = bus.onRestart(() => {
      restarts += 1
    })
    offRestart()
    fake.signals.onJobsCleared([9])
    assert.equal(restarts, 0, "restart handler removed by its handle")
  })

  it("resets select on JobsCleared, then re-hydrates under the new epoch", () => {
    const fake = fakeTransport({
      "capture.state": { _epoch: 1, _seq: 1, state: "recording", elapsed_seconds: 5 },
    })
    const bus = new DomainEventBusCore<TestEvents>(fake.transport, fakeRuntime())
    const selected = bus.select("capture.state")
    assert.equal(selected()?.state, "recording")

    let duringRestart: CapturePayload | null = null
    bus.onRestart(() => {
      duringRestart = selected()
    })

    fake.setState({ "capture.state": { _epoch: 2, _seq: 0, state: "idle", elapsed_seconds: 0 } })
    fake.signals.onJobsCleared([2])

    assert.equal(duringRestart, null, "the accessor is reset before re-hydration")
    assert.equal(selected()?.state, "idle", "re-hydrated under the new epoch")
    assert.deepEqual(bus.hydratedPair("capture.state"), [2, 0])
  })

  it("ignores a replayed JobsCleared at or below the last epoch", () => {
    const fake = fakeTransport({
      "capture.state": { _epoch: 5, _seq: 2, state: "recording" },
    })
    const bus = new DomainEventBusCore<TestEvents>(fake.transport, fakeRuntime())
    const selected = bus.select("capture.state")
    let restarts = 0
    bus.onRestart(() => {
      restarts += 1
    })
    fake.signals.onJobsCleared([5])
    assert.equal(restarts, 0)
    assert.equal(selected()?.state, "recording")
    fake.signals.onJobsCleared([4])
    assert.equal(restarts, 0)
  })

  it("treats a (0, 0) hydration as 'no state yet'", () => {
    const fake = fakeTransport()
    const bus = new DomainEventBusCore<TestEvents>(fake.transport, fakeRuntime())
    const selected = bus.select("capture.state")
    assert.equal(selected(), null)
    assert.deepEqual(bus.hydratedPair("capture.state"), [0, 0])
    assert.equal(bus.current("capture.state"), null)
  })

  it("selects the latest payload reactively and tracks current()", () => {
    const fake = fakeTransport()
    const bus = new DomainEventBusCore<TestEvents>(fake.transport, fakeRuntime())
    const selected = bus.select("capture.state")
    assert.equal(selected(), null)
    fake.dispatch("capture.state", 1, 1, { state: "recording", elapsed_seconds: 3 })
    assert.equal(selected()?.state, "recording")
    assert.equal(selected()?.elapsed_seconds, 3)
    assert.deepEqual(bus.current("capture.state"), { state: "recording", elapsed_seconds: 3 })
    assert.equal(bus.current("nope"), null)
  })

  it("select fails loudly without an injected reactive runtime (AD-2)", () => {
    const fake = fakeTransport()
    const bus = new DomainEventBusCore(fake.transport)
    assert.throws(() => bus.select("capture.state"), /injected reactive runtime/)
  })

  it("the NameOwnerChanged fallback resets and re-hydrates like JobsCleared", () => {
    const fake = fakeTransport({
      "capture.state": { _epoch: 1, _seq: 1, state: "recording" },
    })
    const bus = new DomainEventBusCore<TestEvents>(fake.transport, fakeRuntime())
    const selected = bus.select("capture.state")
    let restarts = 0
    bus.onRestart(() => {
      restarts += 1
    })
    fake.setState({ "capture.state": { _epoch: 2, _seq: 0, state: "idle" } })
    fake.signals.onHubRestart()
    assert.equal(restarts, 1)
    assert.equal(selected()?.state, "idle")
  })

  it("control() is first-class and goes through the injected transport", () => {
    const fake = fakeTransport()
    const bus = new DomainEventBusCore(fake.transport)
    bus.control("job-1", "pause")
    assert.deepEqual(fake.calls, ["startSignals", "control:job-1:pause"])
  })
})

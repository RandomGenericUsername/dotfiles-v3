import { describe, it } from "node:test"
import assert from "node:assert/strict"

import {
  createBatteryReadModel,
  type BatteryService,
} from "../../domains/battery/read-model.ts"
import { fakeRuntime, makeEmitter } from "./fixtures/reactive-fixture.ts"

/**
 * The battery read model, driven by a FAKE AstalBattery and a FAKE runtime.
 * Injectable + reactive, with no live Astal.
 */

function fakeBattery(overrides: Partial<BatteryService> = {}): {
  service: BatteryService
  emitter: ReturnType<typeof makeEmitter>
} {
  const emitter = makeEmitter()
  const service = {
    percentage: 0.82,
    charging: false,
    isPresent: true,
    timeToFull: 0,
    timeToEmpty: 7200,
    ...overrides,
    connect: emitter.connect,
    disconnect: emitter.disconnect,
  } as BatteryService
  return { service, emitter }
}

describe("battery read model", () => {
  it("publishes the injected service's snapshot (injectable)", () => {
    const { service } = fakeBattery()
    const reading = createBatteryReadModel(service, fakeRuntime())
    assert.deepEqual(reading(), {
      percentage: 0.82,
      charging: false,
      isPresent: true,
      timeToFull: 0,
      timeToEmpty: 7200,
    })
  })

  it("republishes when charging changes (reactive)", () => {
    const { service, emitter } = fakeBattery()
    const reading = createBatteryReadModel(service, fakeRuntime())

    service.charging = true
    service.timeToEmpty = 0
    service.timeToFull = 5400
    emitter.emit("notify::charging")

    assert.equal(reading().charging, true)
    assert.equal(reading().timeToFull, 5400)
  })

  it("republishes on a percentage change", () => {
    const { service, emitter } = fakeBattery()
    const reading = createBatteryReadModel(service, fakeRuntime())

    service.percentage = 0.31
    emitter.emit("notify::percentage")

    assert.equal(reading().percentage, 0.31)
  })

  it("keeps a missing estimate as its raw sentinel, never invents one", () => {
    const { service } = fakeBattery({ charging: false, timeToEmpty: 0 })
    const reading = createBatteryReadModel(service, fakeRuntime())
    assert.equal(reading().timeToEmpty, 0)
  })
})

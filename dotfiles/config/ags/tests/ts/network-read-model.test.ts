import { describe, it } from "node:test"
import assert from "node:assert/strict"

import {
  createNetworkReadModel,
  type NetworkService,
  type WifiDevice,
} from "../../domains/network/read-model.ts"
import { fakeRuntime, makeEmitter } from "./fixtures/reactive-fixture.ts"

/**
 * The network read model, driven by a FAKE device and a FAKE runtime.
 *
 * This is the proof the extraction exists for: the read model is injectable
 * (it takes the service, not a global) and reactive (a device property change
 * republishes), and both are observable without a live AstalNetwork.
 */

function fakeWifi(overrides: Partial<WifiDevice> = {}): { device: WifiDevice; emitter: ReturnType<typeof makeEmitter> } {
  const emitter = makeEmitter()
  const device = {
    enabled: true,
    state: 100,
    strength: 90,
    ...overrides,
    connect: emitter.connect,
    disconnect: emitter.disconnect,
  } as WifiDevice
  return { device, emitter }
}

function fakeNetwork(): {
  network: NetworkService
  wifi: ReturnType<typeof fakeWifi>
  emitter: ReturnType<typeof makeEmitter>
  setWifi(next: WifiDevice | null): void
} {
  const emitter = makeEmitter()
  const wifi = fakeWifi()
  let current: WifiDevice | null = wifi.device
  const network: NetworkService = {
    get wifi() {
      return current
    },
    wired: null,
    connectivity: 3,
    connect: emitter.connect,
    disconnect: emitter.disconnect,
  }
  return {
    network,
    wifi,
    emitter,
    setWifi(next) {
      current = next
    },
  }
}

describe("network read model", () => {
  it("publishes the injected device's snapshot (injectable)", () => {
    const { network } = fakeNetwork()
    const reading = createNetworkReadModel(network, fakeRuntime())
    assert.deepEqual(reading(), {
      wifi: { enabled: true, state: 100, strength: 90 },
      wired: null,
      connectivity: 3,
    })
  })

  it("republishes when a watched wifi property changes (reactive)", () => {
    const { network, wifi } = fakeNetwork()
    const reading = createNetworkReadModel(network, fakeRuntime())

    wifi.device.strength = 20
    wifi.emitter.emit("notify::strength")

    assert.equal(reading().wifi?.strength, 20)
  })

  it("republishes when connectivity changes", () => {
    const { network, emitter } = fakeNetwork()
    const reading = createNetworkReadModel(network, fakeRuntime())

    network.connectivity = 2
    emitter.emit("notify::connectivity")

    assert.equal(reading().connectivity, 2)
  })

  it("rebinds when the wifi device is replaced, and stops hearing the old one", () => {
    const net = fakeNetwork()
    const reading = createNetworkReadModel(net.network, fakeRuntime())

    const replacement = fakeWifi({ strength: 10 })
    net.setWifi(replacement.device)
    net.emitter.emit("notify::wifi")
    assert.equal(reading().wifi?.strength, 10)

    replacement.device.strength = 99
    replacement.emitter.emit("notify::strength")
    assert.equal(reading().wifi?.strength, 99)

    // The replaced device's handlers were torn down: its changes are silent.
    net.wifi.device.strength = 1
    net.wifi.emitter.emit("notify::strength")
    assert.equal(reading().wifi?.strength, 99)
  })
})

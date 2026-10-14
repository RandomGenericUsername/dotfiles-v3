import { describe, it } from "node:test"
import assert from "node:assert/strict"

import {
  createBluetoothReadModel,
  type BluetoothDeviceReading,
  type BluetoothReading,
  type BluetoothSource,
} from "../../domains/bluetooth/read-model.ts"
import { fakeRuntime } from "./fixtures/reactive-fixture.ts"

/**
 * The Bluetooth read model, driven by a FAKE source and a FAKE runtime.
 * Injectable + reactive, with no live BlueZ and no `ags`.
 */

interface FakeState {
  powered: boolean
  discovering: boolean
  ready: boolean
  adapterAddress: string
  devices: readonly BluetoothDeviceReading[]
  busy: BluetoothReading["busy"]
  audioTarget: string | null
}

function device(overrides: Partial<BluetoothDeviceReading> = {}): BluetoothDeviceReading {
  return {
    path: "/org/bluez/hci0/dev_AA",
    address: "AA:BB:CC:DD:EE:FF",
    alias: "Headphones",
    name: "Headphones",
    connected: false,
    paired: true,
    trusted: true,
    rssi: -55,
    lastHeardAt: 1000,
    icon: "audio-headphones",
    adapter: "/org/bluez/hci0",
    battery: 0,
    ...overrides,
  }
}

function fakeSource(): { source: BluetoothSource; change(next: Partial<FakeState>): void } {
  let state: FakeState = {
    powered: false,
    discovering: false,
    ready: false,
    adapterAddress: "",
    devices: [],
    busy: { address: null, action: null },
    audioTarget: null,
  }
  const listeners = new Set<() => void>()
  const source: BluetoothSource = {
    powered: () => state.powered,
    discovering: () => state.discovering,
    ready: () => state.ready,
    adapterAddress: () => state.adapterAddress,
    devices: () => state.devices,
    busy: () => state.busy,
    audioTarget: () => state.audioTarget,
    subscribe: (listener) => {
      listeners.add(listener)
      return () => {
        listeners.delete(listener)
      }
    },
  }
  return {
    source,
    change(next) {
      state = { ...state, ...next }
      for (const listener of [...listeners]) listener()
    },
  }
}

describe("bluetooth read model", () => {
  it("publishes the injected source's snapshot (injectable)", () => {
    const { source } = fakeSource()
    const reading = createBluetoothReadModel(source, fakeRuntime())
    assert.deepEqual(reading(), {
      powered: false,
      discovering: false,
      ready: false,
      adapterAddress: "",
      devices: [],
      busy: { address: null, action: null },
      audioTarget: null,
    })
  })

  it("republishes when the adapter powers on (reactive)", () => {
    const { source, change } = fakeSource()
    const reading = createBluetoothReadModel(source, fakeRuntime())

    change({ powered: true, ready: true, adapterAddress: "11:22:33:44:55:66" })

    assert.equal(reading().powered, true)
    assert.equal(reading().adapterAddress, "11:22:33:44:55:66")
  })

  it("republishes the device list", () => {
    const { source, change } = fakeSource()
    const reading = createBluetoothReadModel(source, fakeRuntime())

    change({ devices: [device({ connected: true })] })

    assert.equal(reading().devices.length, 1)
    assert.equal(reading().devices[0]?.alias, "Headphones")
    assert.equal(reading().devices[0]?.connected, true)
  })
})

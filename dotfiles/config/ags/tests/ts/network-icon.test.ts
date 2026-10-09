import { describe, it } from "node:test"
import assert from "node:assert/strict"
import {
  networkIconState,
  networkLabel,
  type NetworkReading,
} from "../../lib/network-icon.ts"

/**
 * The network state→key mapping, pinned.
 *
 * This logic used to live inline in `bar/widgets/network.tsx`, where it could
 * only be checked by rendering the widget. Extracted pure, it is checked here —
 * the point of the descriptor model: decisions move out of the view.
 */
function reading(overrides: Partial<NetworkReading> = {}): NetworkReading {
  return { wifi: null, wired: null, connectivity: 0, ...overrides }
}

describe("networkIconState — wifi", () => {
  it("maps an activated wifi reading to the strength bucket", () => {
    const on = (strength: number): NetworkReading =>
      reading({ wifi: { enabled: true, state: 100, strength } })
    assert.equal(networkIconState(on(90)), "wifi-full")
    assert.equal(networkIconState(on(50)), "wifi-high")
    assert.equal(networkIconState(on(25)), "wifi-medium")
    assert.equal(networkIconState(on(10)), "wifi-low")
  })

  it("is not-connected when the radio is off or the device is not activated", () => {
    assert.equal(networkIconState(reading({ wifi: { enabled: false, state: 100, strength: 90 } })), "wifi-not-connected")
    assert.equal(networkIconState(reading({ wifi: { enabled: true, state: 30, strength: 90 } })), "wifi-not-connected")
  })

  it("reports no-internet only for LIMITED(2)/PORTAL(1), never NONE(0)", () => {
    const connected = (connectivity: number): NetworkReading =>
      reading({ wifi: { enabled: true, state: 100, strength: 90 }, connectivity })
    assert.equal(networkIconState(connected(2)), "wifi-no-internet")
    assert.equal(networkIconState(connected(1)), "wifi-no-internet")
    // NONE means the check is disabled, not "no internet".
    assert.equal(networkIconState(connected(0)), "wifi-full")
    assert.equal(networkIconState(connected(3)), "wifi-full")
  })
})

describe("networkIconState — wired / none", () => {
  it("maps the wired device state", () => {
    assert.equal(networkIconState(reading({ wired: { state: 100 } })), "ethernet-connected")
    assert.equal(networkIconState(reading({ wired: { state: 100 }, connectivity: 2 })), "ethernet-no-internet")
    assert.equal(networkIconState(reading({ wired: { state: 30 } })), "ethernet-not-connected")
  })

  it("falls back to not-connected with no device", () => {
    assert.equal(networkIconState(reading()), "wifi-not-connected")
  })
})

describe("networkLabel", () => {
  it("is empty on wifi, names ethernet, and says none", () => {
    assert.equal(networkLabel(reading({ wifi: { enabled: true, state: 100, strength: 90 } })), "")
    assert.equal(networkLabel(reading({ wired: { state: 100 } })), "Ethernet")
    assert.equal(networkLabel(reading()), "No network")
  })
})

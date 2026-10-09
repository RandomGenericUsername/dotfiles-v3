import { describe, it } from "node:test"
import assert from "node:assert/strict"
import { projectBarIndicators } from "../../audio/presentation/bar-indicators.ts"
import type { AudioPanelViewModel } from "../../audio/presentation/audio-panel-view-model.ts"

/**
 * The bar indicators, pinned against the panel view model.
 *
 * The bar glyph and the panel it opens must read the same projection; these
 * cases assert the mapping from session state to glyph variant so a bar icon can
 * never disagree with the panel for the same reading.
 */
function model(overrides: Partial<AudioPanelViewModel> = {}): AudioPanelViewModel {
  return {
    preferredOutputId: null,
    preferredOutput: null,
    outputs: [],
    preferredInputId: null,
    input: null,
    inputs: [],
    inputConsumers: [],
    rows: [],
    appIntents: {},
    appVolumes: {},
    appLastIntents: {},
    appEndpoints: {},
    ...overrides,
  }
}

function endpoint(level: number, muted: boolean) {
  return { id: "e1", name: "Device", available: true, volume: { level, muted } }
}

describe("projectBarIndicators — output", () => {
  it("reads a missing preferred output as the muted glyph", () => {
    const state = projectBarIndicators(model())
    assert.equal(state.output.variant, "muted")
    assert.equal(state.output.level, 0)
    assert.equal(state.output.muted, false)
  })

  it("maps the preferred output's level to the shared variant table", () => {
    assert.equal(projectBarIndicators(model({ preferredOutput: endpoint(0.3, false) })).output.variant, "low")
    assert.equal(projectBarIndicators(model({ preferredOutput: endpoint(0.9, false) })).output.variant, "max")
  })

  it("lets mute win over a high level", () => {
    const state = projectBarIndicators(model({ preferredOutput: endpoint(0.8, true) }))
    assert.equal(state.output.variant, "muted")
    assert.equal(state.output.muted, true)
    assert.equal(state.output.level, 0.8)
  })
})

describe("projectBarIndicators — mic", () => {
  it("is mic-on with no live dot when there is no input and no consumer", () => {
    const state = projectBarIndicators(model())
    assert.equal(state.mic.variant, "mic-on")
    assert.equal(state.mic.live, false)
  })

  it("is mic-off when the preferred input is muted", () => {
    const state = projectBarIndicators(model({ input: endpoint(0.5, true) }))
    assert.equal(state.mic.variant, "mic-off")
  })

  it("shows the live dot only while an input consumer is present", () => {
    const consumer = { id: "s1", appId: "firefox", appName: "Firefox", iconName: "firefox" }
    const state = projectBarIndicators(model({ inputConsumers: [consumer] }))
    assert.equal(state.mic.live, true)
    assert.equal(state.mic.variant, "mic-on")
  })
})

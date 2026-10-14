import { describe, it } from "node:test"
import assert from "node:assert/strict"

import {
  createAudioReadModel,
  type AudioReadModelSource,
} from "../../domains/audio/read-model.ts"
import type { AudioPanelViewModel } from "../../audio/presentation/audio-panel-view-model.ts"
import type { EndpointState } from "../../audio/domain/audio-model.ts"
import { fakeRuntime } from "./fixtures/reactive-fixture.ts"

/**
 * The audio read model, driven by a FAKE source returning a fake view model and
 * a FAKE runtime. It reuses the hexagon's real `projectBarIndicators`, so the
 * suite proves the wiring without a live PipeWire/MPRIS session.
 */

function baseModel(overrides: Partial<AudioPanelViewModel> = {}): AudioPanelViewModel {
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

function endpoint(id: string, level: number, muted = false): EndpointState {
  return { id, name: id, available: true, volume: { level, muted } }
}

function fakeSource(initial: AudioPanelViewModel): {
  source: AudioReadModelSource
  set(next: AudioPanelViewModel): void
} {
  let model = initial
  const listeners = new Set<() => void>()
  return {
    source: {
      current: () => model,
      subscribe: (listener) => {
        listeners.add(listener)
        return () => {
          listeners.delete(listener)
        }
      },
    },
    set(next) {
      model = next
      for (const listener of [...listeners]) listener()
    },
  }
}

describe("audio read model", () => {
  it("publishes the hexagon projection's snapshot (injectable)", () => {
    const { source } = fakeSource(baseModel())
    const reading = createAudioReadModel(source, fakeRuntime())
    assert.deepEqual(reading(), {
      output: { variant: "muted", level: 0, muted: false },
      mic: { variant: "mic-on", live: false },
    })
  })

  it("republishes when the preferred output's level changes (reactive)", () => {
    const { source, set } = fakeSource(baseModel())
    const reading = createAudioReadModel(source, fakeRuntime())

    set(
      baseModel({
        preferredOutputId: "sink",
        preferredOutput: endpoint("sink", 0.8),
        outputs: [endpoint("sink", 0.8)],
      }),
    )

    assert.deepEqual(reading().output, { variant: "max", level: 0.8, muted: false })
  })

  it("lets mute win over a high level, through the shared variant table", () => {
    const { source, set } = fakeSource(baseModel())
    const reading = createAudioReadModel(source, fakeRuntime())

    set(
      baseModel({
        preferredOutputId: "sink",
        preferredOutput: endpoint("sink", 0.8, true),
        outputs: [endpoint("sink", 0.8, true)],
      }),
    )

    assert.equal(reading().output.variant, "muted")
    assert.equal(reading().output.muted, true)
  })

  it("shows the mic live dot only while an input consumer is present", () => {
    const { source, set } = fakeSource(baseModel())
    const reading = createAudioReadModel(source, fakeRuntime())
    assert.equal(reading().mic.live, false)

    set(
      baseModel({
        inputConsumers: [{ id: "stream", appId: "conference", appName: "Conference", iconName: "conference" }],
      }),
    )

    assert.equal(reading().mic.live, true)
  })
})

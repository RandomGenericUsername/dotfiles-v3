// ---------------------------------------------------------------------------
// Direct unit tests for `domain/ui-state.ts` (workstream A4, tasks 4.4–4.7).
//
// This module holds the two vocabularies the GUI and the backend disagree about,
// which is exactly why it was worth extracting and exactly why it needs direct
// tests:
//
//   * the UI says `microphone`, the config says `mic`, the CLI wants `mic`;
//   * the UI says `75%`, the CLI wants `75`.
//
// Both are silent failures: nothing throws, the panel just stops honouring the
// user's choice, or the backend argparse rejects the flag. `GIF_SIZE_ARG` below
// is the drift trap this workstream exists to kill — the bare numbers are
// asserted, not just the mapping.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"

import { defaultSettings, mergeSettings, type ConfigRecordingAudio } from "../../domain/settings.ts"
import {
  AUDIO_SOURCES,
  DEFAULT_RECORDING,
  DEFAULT_SCREENSHOT,
  GIF_SIZES,
  GIF_SIZE_ARG,
  audioToUi,
  configDefaults,
  durationSelection,
  isGif,
  mergeUiState,
  oneOf,
  type PersistedUiState,
  type UiState,
} from "../../domain/ui-state.ts"

// A settings object with every knob off its default, so a test that asserts a
// field came from the SETTINGS proves the precedence rule rather than agreeing
// with the hardcoded constant by coincidence.
const MAX_SETTINGS = mergeSettings({
  screenshot: { format: "jpeg", output: "save", cursor: true },
  recording: { fps: 24, quality: "low", audio: "mic", cursor: false },
})

// ---------------------------------------------------------------------------
// audioToUi — task 4.6
// ---------------------------------------------------------------------------

test("audioToUi: config mic becomes the UI word microphone", () => {
  assert.equal(audioToUi("mic"), "microphone")
})

test("audioToUi: none and system pass straight through", () => {
  assert.equal(audioToUi("none"), "none")
  assert.equal(audioToUi("system"), "system")
})

test("audioToUi: the two vocabularies are exactly these words", () => {
  // The mapping is total over the config union, and its image is the UI union.
  // Anything else is a typo the types would have caught but a config file on
  // disk would not.
  assert.deepEqual([...AUDIO_SOURCES].sort(), ["microphone", "none", "system"])
  // Typed at the union because these three words ARE the config union; the
  // mapping's totality is the property being asserted.
  const configVocabulary: ConfigRecordingAudio[] = ["none", "system", "mic"]
  assert.deepEqual(configVocabulary.map(audioToUi).sort(), ["microphone", "none", "system"])
})

// ---------------------------------------------------------------------------
// GIF_SIZE_ARG — task 4.7, THE DRIFT TRAP
// ---------------------------------------------------------------------------

test("GIF_SIZE_ARG: the UI percentages become bare numbers on the wire", () => {
  // bin/capture-tool's argparse accepts --size {original,75,50} and rejects
  // anything else. "75%" would not error in the GUI — it would fail in the
  // child process, after the user had already pressed record.
  assert.equal(GIF_SIZE_ARG["original"], "original")
  assert.equal(GIF_SIZE_ARG["75%"], "75")
  assert.equal(GIF_SIZE_ARG["50%"], "50")
})

test("GIF_SIZE_ARG: no emitted value carries a percent sign", () => {
  // Stated as a property over the whole table rather than per key, so ADDING a
  // scale later cannot smuggle "90%" past three hand-written assertions.
  for (const [ui, arg] of Object.entries(GIF_SIZE_ARG)) {
    assert.ok(!arg.includes("%"), `${JSON.stringify(ui)} -> ${arg} still contains %`)
  }
  assert.deepEqual(Object.values(GIF_SIZE_ARG), ["original", "75", "50"])
})

test("GIF_SIZE_ARG: the table is keyed by every UI scale and nothing else", () => {
  assert.deepEqual(Object.keys(GIF_SIZE_ARG).sort(), [...GIF_SIZES].sort())
  assert.deepEqual([...GIF_SIZES], ["original", "75%", "50%"])
})

// ---------------------------------------------------------------------------
// configDefaults — task 4.4, the precedence rule
// ---------------------------------------------------------------------------

test("configDefaults: with default settings it is exactly the hardcoded first-run state", () => {
  const ui = configDefaults(defaultSettings())
  assert.deepEqual(ui.screenshot, DEFAULT_SCREENSHOT)
  assert.deepEqual(ui.recording, DEFAULT_RECORDING)
})

test("configDefaults: settings beat the hardcoded constants per field", () => {
  const ui = configDefaults(MAX_SETTINGS)
  // From settings:
  assert.equal(ui.screenshot.format, "jpeg")
  assert.equal(ui.screenshot.save, true)
  assert.equal(ui.recording.fps, 24)
  assert.equal(ui.recording.quality, "low")
  // ...through audioToUi, which is where the second vocabulary lives.
  assert.equal(ui.recording.audio, "microphone")
  // Not in settings at all, so the hardcoded constants win:
  assert.equal(ui.screenshot.target, "region")
  assert.equal(ui.screenshot.delay, 0)
  assert.equal(ui.recording.target, "region")
  assert.equal(ui.recording.format, "mp4")
  assert.equal(ui.recording.duration, 0)
  assert.equal(ui.recording.gifFps, 15)
  assert.equal(ui.recording.size, "original")
  assert.equal(ui.recording.customDuration, 120)
})

test("configDefaults: output clipboard means do not save", () => {
  const ui = configDefaults(mergeSettings({ screenshot: { output: "clipboard" } }))
  assert.equal(ui.screenshot.save, false)
  const uiSave = configDefaults(mergeSettings({ screenshot: { output: "save" } }))
  assert.equal(uiSave.screenshot.save, true)
})

test("configDefaults: audio none and system pass through, mic does not", () => {
  assert.equal(configDefaults(mergeSettings({ recording: { audio: "none" } })).recording.audio, "none")
  assert.equal(
    configDefaults(mergeSettings({ recording: { audio: "system" } })).recording.audio,
    "system",
  )
  assert.equal(configDefaults(mergeSettings({ recording: { audio: "mic" } })).recording.audio, "microphone")
})

test("configDefaults: every settings fps and quality reaches the UI state", () => {
  for (const fps of [24, 30, 60] as const) {
    assert.equal(configDefaults(mergeSettings({ recording: { fps } })).recording.fps, fps)
  }
  for (const quality of ["low", "medium", "high"] as const) {
    assert.equal(configDefaults(mergeSettings({ recording: { quality } })).recording.quality, quality)
  }
  for (const format of ["png", "jpeg"] as const) {
    assert.equal(configDefaults(mergeSettings({ screenshot: { format } })).screenshot.format, format)
  }
})

test("configDefaults: returns fresh objects and mutates no constant", () => {
  const a = configDefaults(MAX_SETTINGS)
  const b = configDefaults(MAX_SETTINGS)
  assert.notEqual(a.screenshot, b.screenshot)
  assert.notEqual(a.recording, b.recording)
  a.screenshot.format = "png"
  a.recording.fps = 60
  assert.equal(b.screenshot.format, "jpeg")
  assert.equal(b.recording.fps, 24)
  assert.equal(DEFAULT_SCREENSHOT.format, "png")
  assert.equal(DEFAULT_RECORDING.fps, 60)
})

// ---------------------------------------------------------------------------
// mergeUiState — task 4.5, the loadUiState merge half
// ---------------------------------------------------------------------------

test("mergeUiState: an absent persisted file leaves the base untouched", () => {
  const base = configDefaults(MAX_SETTINGS)
  assert.deepEqual(mergeUiState(base, {}), base)
})

test("mergeUiState: last-used values override the base per field", () => {
  const base = configDefaults(MAX_SETTINGS)
  const merged = mergeUiState(base, {
    screenshot: { target: "window", delay: 10, format: "png", save: false },
    recording: {
      target: "screen",
      fps: 30,
      format: "gif",
      audio: "microphone",
      quality: "medium",
      duration: 60,
      gifFps: 20,
      size: "50%",
      customDuration: 300,
    },
  })
  assert.deepEqual(merged.screenshot, {
    target: "window",
    delay: 10,
    format: "png",
    save: false,
  })
  assert.deepEqual(merged.recording, {
    target: "screen",
    fps: 30,
    format: "gif",
    audio: "microphone",
    quality: "medium",
    duration: 60,
    gifFps: 20,
    size: "50%",
    customDuration: 300,
  })
  // ...and the base is not mutated: the merge is a pure function of its inputs,
  // so a second call from the same base gives the same answer.
  assert.deepEqual(mergeUiState(base, merged), merged)
  assert.equal(base.screenshot.format, "jpeg")
  assert.equal(base.recording.fps, 24)
})

test("mergeUiState: every accepted enum member round-trips", () => {
  const base = configDefaults(defaultSettings())
  for (const target of ["region", "screen", "window"] as const) {
    assert.equal(mergeUiState(base, { screenshot: { target } }).screenshot.target, target)
  }
  for (const delay of [0, 3, 5, 10] as const) {
    assert.equal(mergeUiState(base, { screenshot: { delay } }).screenshot.delay, delay)
  }
  for (const size of ["original", "75%", "50%"] as const) {
    assert.equal(mergeUiState(base, { recording: { size } }).recording.size, size)
  }
  for (const fps of [10, 15, 20, 30] as const) {
    assert.equal(mergeUiState(base, { recording: { gifFps: fps } }).recording.gifFps, fps)
  }
  for (const audio of ["none", "system", "microphone"] as const) {
    assert.equal(mergeUiState(base, { recording: { audio } }).recording.audio, audio)
  }
})

test("mergeUiState: an out-of-range enum falls back to the base value", () => {
  const base = configDefaults(MAX_SETTINGS) // jpeg/save, 24fps/low/microphone
  // The `as unknown as PersistedUiState` cast is the POINT of this test, not a
  // shortcut: the on-disk `capture-ui.json` is untrusted input, so the values
  // here are ones `PersistedUiState` forbids but a real file can contain (a
  // renamed enum member, a version-skewed field, a hand-edited file). The types
  // stop a caller writing them; nothing stops a JSON file. This is precisely the
  // gap the per-field fallback exists to cover, and a test that could not express
  // it would be testing nothing.
  const persisted = {
    screenshot: { target: "desktop", delay: 7, format: "webp", save: "true" },
    recording: {
      target: "monitor",
      fps: 120,
      format: "avi",
      // `mic` is the CONFIG vocabulary, not the UI one: the persisted UI state
      // is in UI words, so this must fall back rather than be half-understood.
      audio: "mic",
      quality: "perfect",
      gifFps: 25,
      size: "100%",
    },
  } as unknown as PersistedUiState
  const merged = mergeUiState(base, persisted)
  // `target`/`delay` are not in the settings at all, so their base value is the
  // hardcoded constant; `format`/`save`/`fps`/`quality`/`audio` come from the
  // settings, so falling back proves the BASE is honoured rather than a constant.
  assert.equal(merged.screenshot.target, "region") // base, not "desktop"
  assert.equal(merged.screenshot.delay, 0) // base, not 7
  assert.equal(merged.screenshot.format, "jpeg") // base, not "webp"
  assert.equal(merged.screenshot.save, true) // base, "true" is not a boolean
  assert.equal(merged.recording.target, "region") // base, not "monitor"
  assert.equal(merged.recording.fps, 24)
  assert.equal(merged.recording.format, "mp4")
  assert.equal(merged.recording.audio, "microphone") // base, "mic" is not a UI word
  assert.equal(merged.recording.quality, "low")
  assert.equal(merged.recording.gifFps, 15)
  assert.equal(merged.recording.size, "original")
})

test("mergeUiState: null and undefined field values fall back", () => {
  const base = configDefaults(MAX_SETTINGS)
  const merged = mergeUiState(base, {
    screenshot: { target: null, delay: undefined, format: null, save: null },
    recording: {
      target: null,
      fps: null,
      format: null,
      audio: null,
      quality: null,
      duration: null,
      gifFps: null,
      size: null,
      customDuration: null,
    },
  } as unknown as PersistedUiState)
  assert.deepEqual(merged, base)
})

test("mergeUiState: a null half is the same as an absent half", () => {
  // The adapter hands over whatever JSON.parse produced. `{"screenshot": null}`
  // must degrade to the base rather than throw on the spread.
  const base = configDefaults(MAX_SETTINGS)
  assert.deepEqual(mergeUiState(base, { screenshot: null } as unknown as PersistedUiState), base)
  assert.deepEqual(mergeUiState(base, { recording: null } as unknown as PersistedUiState), base)
  assert.deepEqual(
    mergeUiState(base, { screenshot: null, recording: null } as unknown as PersistedUiState),
    base,
  )
  // NOTE: a null/undefined `persisted` ITSELF is deliberately NOT asserted as
  // safe. `mergeUiState` dereferences `persisted.screenshot` directly, so it
  // throws on null. That is the correct division of labour: the adapter
  // (A5's `glib-ui-state-store`) owns "the file was missing / unparseable" and
  // substitutes `{}` before calling in. Making the merge null-tolerant too
  // would be redundant defensive code, not a fix. See domain/ui-state.ts:122.
  // A non-object half (corrupt JSON that parsed to something odd) is also safe:
  // reading `.screenshot` off a string yields undefined, which spreads to {}.
  assert.deepEqual(mergeUiState(base, "garbage" as unknown as PersistedUiState), base)
  assert.deepEqual(mergeUiState(base, 42 as unknown as PersistedUiState), base)
  assert.deepEqual(mergeUiState(base, [] as unknown as PersistedUiState), base)
})

test("mergeUiState: duration accepts 0 as infinite and rejects negatives", () => {
  const base = configDefaults(MAX_SETTINGS) // duration 0
  // 0 is falsy: the classic `|| base` fallback would silently drop the
  // "infinite" selection. It must survive.
  assert.equal(mergeUiState(base, { recording: { duration: 0 } }).recording.duration, 0)
  assert.equal(mergeUiState(base, { recording: { duration: 30 } }).recording.duration, 30)
  assert.equal(mergeUiState(base, { recording: { duration: -1 } }).recording.duration, 0)
  assert.equal(
    mergeUiState(base, { recording: { duration: "60" } } as unknown as PersistedUiState).recording
      .duration,
    0,
  )
  assert.equal(
    mergeUiState(base, { recording: { duration: NaN } }).recording.duration,
    0,
    "NaN fails the >= 0 comparison, so it falls back",
  )
})

test("mergeUiState: save accepts false as a value, not as absence", () => {
  const base = configDefaults(MAX_SETTINGS) // save: true
  assert.equal(mergeUiState(base, { screenshot: { save: false } }).screenshot.save, false)
  assert.equal(mergeUiState(base, { screenshot: { save: true } }).screenshot.save, true)
  assert.equal(
    mergeUiState(base, { screenshot: { save: 0 } } as unknown as PersistedUiState).screenshot.save,
    true,
  )
})

test("mergeUiState: customDuration below 5 falls back to the base", () => {
  // The spin editor's range starts at 5s; a persisted 1 or 0 (e.g. a value left
  // over from an older format, or a 0 meaning "not set") must not survive.
  const base = configDefaults(MAX_SETTINGS) // customDuration 120
  for (const tooSmall of [4, 1, 0, -1, 4.9]) {
    assert.equal(
      mergeUiState(base, { recording: { customDuration: tooSmall } }).recording.customDuration,
      120,
      `expected fallback for ${tooSmall}`,
    )
  }
})

test("mergeUiState: customDuration above 3600 clamps to 3600", () => {
  const base = configDefaults(MAX_SETTINGS)
  // The spec's scenario: 99999 clamps rather than falling back, so the user's
  // "as long as possible" survives instead of resetting to 120.
  assert.equal(
    mergeUiState(base, { recording: { customDuration: 99999 } }).recording.customDuration,
    3600,
  )
  assert.equal(mergeUiState(base, { recording: { customDuration: 3601 } }).recording.customDuration, 3600)
  assert.equal(mergeUiState(base, { recording: { customDuration: 3600 } }).recording.customDuration, 3600)
})

test("mergeUiState: customDuration in range is rounded to whole seconds", () => {
  const base = configDefaults(MAX_SETTINGS)
  const merged = (customDuration: number) =>
    mergeUiState(base, { recording: { customDuration } }).recording.customDuration
  assert.equal(merged(5), 5)
  assert.equal(merged(5.4), 5)
  assert.equal(merged(5.5), 6)
  assert.equal(merged(6.49), 6)
  assert.equal(merged(6.5), 7)
  assert.equal(merged(120.4), 120)
  assert.equal(merged(3599.6), 3600)
})

test("mergeUiState: a non-numeric customDuration falls back", () => {
  const base = configDefaults(MAX_SETTINGS)
  for (const notANumber of ["300", null, true, {}]) {
    assert.equal(
      mergeUiState(base, { recording: { customDuration: notANumber } } as unknown as PersistedUiState)
        .recording.customDuration,
      120,
    )
  }
})

test("mergeUiState: the whole precedence chain behaves as documented", () => {
  // last-used UI state > settings defaults > hardcoded constants, end to end,
  // for one field per layer.
  const chain = (
    persisted: PersistedUiState,
    settings: Parameters<typeof mergeSettings>[0],
  ): UiState => mergeUiState(configDefaults(mergeSettings(settings)), persisted)

  // 1. nothing anywhere -> the hardcoded constant
  assert.equal(chain({}, undefined).recording.fps, 60)
  // 2. settings beat the constant
  assert.equal(chain({}, { recording: { fps: 24 } }).recording.fps, 24)
  // 3. last-used beats settings
  assert.equal(chain({ recording: { fps: 30 } }, { recording: { fps: 24 } }).recording.fps, 30)
  // 4. ...but a nonsense last-used value falls back to SETTINGS, not to the
  //    constant — the base is the settings-sourced value, which is the whole
  //    reason the merge takes a base at all.
  assert.equal(chain({ recording: { fps: 120 } }, { recording: { fps: 24 } }).recording.fps, 24)
})

// ---------------------------------------------------------------------------
// oneOf — the primitive the merge is built from.
// ---------------------------------------------------------------------------

test("oneOf: membership decides, not coercion", () => {
  assert.equal(oneOf("png", ["png", "jpeg"], "png"), "png")
  assert.equal(oneOf("webp", ["png", "jpeg"], "png"), "png")
  assert.equal(oneOf(30, [24, 30, 60], 60), 30)
  assert.equal(oneOf("30", [24, 30, 60], 60), 60)
  assert.equal(oneOf(null, [24, 30, 60], 60), 60)
  assert.equal(oneOf(undefined, [24, 30, 60], 60), 60)
})

// ---------------------------------------------------------------------------
// The two predicates the recording view asks about (moved with the rest, task
// 3.4). They are pure now, which is why they can be tested at all.
// ---------------------------------------------------------------------------

test("isGif: only the gif format routes through the GIF pipeline", () => {
  assert.equal(isGif({ ...DEFAULT_RECORDING, format: "gif" }), true)
  for (const format of ["mp4", "webm"] as const) {
    assert.equal(isGif({ ...DEFAULT_RECORDING, format }), false)
  }
})

test("durationSelection: a preset duration echoes itself, anything else means custom", () => {
  for (const duration of [0, 10, 30, 60] as const) {
    assert.equal(durationSelection({ ...DEFAULT_RECORDING, duration }), duration)
  }
  // -1 is the sentinel the view uses to show the inline spin editor instead.
  for (const custom of [1, 5, 45, 120, 3600]) {
    assert.equal(durationSelection({ ...DEFAULT_RECORDING, duration: custom }), -1)
  }
})

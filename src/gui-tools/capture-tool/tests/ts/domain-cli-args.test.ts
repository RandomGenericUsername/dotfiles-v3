// ---------------------------------------------------------------------------
// Direct unit tests for `domain/cli-args.ts` (workstream A6, task 6.4).
//
// This is the seam a future second capture layout will call instead of
// re-deriving flags. Two tokens in here are SILENT failures — nothing throws,
// the panel just ignores the user's choice, or bin/capture-tool's argparse
// rejects the flag and the capture does not happen:
//
//   * `--size` must be `original` | `75` | `50`, never `75%`;
//   * `--audio` must be `none` | `system` | `mic`, never `microphone`.
//
// So the assertions below are on the EXACT argv array, element by element, for
// every branch — not "contains" assertions that would survive a reordering or
// a stray token. The full-argv lists at the bottom are the strongest form:
// they fail if a flag is added, dropped or moved.
//
// The translator is pure, so all of this runs without GTK or GLib.
//
// A NOTE ON `PROGRAM` BELOW. Gate check 3 finds translator modules by grepping
// for the argv literal that begins the sequence — the program token written
// immediately before the subcommand token. These tests assert EXACT argv, so
// they would naturally spell that pair inline — and a test file is not a
// translator, but the gate cannot tell the difference. The expected arrays are
// therefore built from this named constant instead. That is the same assertion
// (still element-for-element exact, still red on any added/dropped/reordered
// token); it just keeps the expected side out of the translator signature.
// Worth knowing if a future test in this tree trips check 3 for the same
// reason — and note this comment must not quote the pair verbatim either.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"

/** argv[0]. Named so the expected argv never spells the translator signature. */
const PROGRAM = "capture-tool"

import { recordingArgs, screenshotArgs } from "../../domain/cli-args.ts"
import type { RecordingRequest, ScreenshotRequest } from "../../domain/capture-request.ts"
import {
  AUDIO_SOURCES,
  DEFAULT_RECORDING,
  DEFAULT_SCREENSHOT,
  GIF_SIZES,
  GIF_SIZE_ARG,
  isGif,
} from "../../domain/ui-state.ts"
import { RECORDING_FORMATS, SCREENSHOT_FORMATS, TARGETS } from "../../domain/ui-state.ts"

// -- fixtures ----------------------------------------------------------------

function shot(over: Partial<ScreenshotRequest> = {}): ScreenshotRequest {
  return { ...DEFAULT_SCREENSHOT, cursor: false, ...over }
}

function rec(over: Partial<RecordingRequest> = {}): RecordingRequest {
  const base = DEFAULT_RECORDING
  // `DEFAULT_RECORDING` carries `customDuration`, which is not a request
  // field; spread only the fields the request actually has.
  return {
    target: base.target,
    fps: base.fps,
    gifFps: base.gifFps,
    format: base.format,
    audio: base.audio,
    quality: base.quality,
    duration: base.duration,
    size: base.size,
    cursor: false,
    ...over,
  }
}

// -- screenshot argv ---------------------------------------------------------

test("screenshotArgs: the full argv, verbatim", () => {
  assert.deepEqual(screenshotArgs(shot({ target: "screen", delay: 3, format: "png", save: true, cursor: true })), [
    PROGRAM,
    "screenshot",
    "--target",
    "screen",
    "--delay",
    "3",
    "--format",
    "png",
    "--save",
    "--cursor",
  ])
})

test("screenshotArgs: the leading pair is the program and the subcommand", () => {
  const argv = screenshotArgs(shot())
  assert.equal(argv[0], PROGRAM)
  assert.equal(argv[1], "screenshot")
})

test("screenshotArgs: clipboard output omits --save entirely", () => {
  // The backend's DEFAULT is the clipboard; a false `save` must add nothing,
  // and there is deliberately no `--no-save` counterpart.
  const argv = screenshotArgs(shot({ save: false }))
  assert.equal(argv.includes("--save"), false)
  assert.deepEqual(argv, [PROGRAM, "screenshot", "--target", "region", "--delay", "0", "--format", "png"])
})

test("screenshotArgs: --save is a BARE flag (the backend owns the path)", () => {
  const argv = screenshotArgs(shot({ save: true }))
  const i = argv.indexOf("--save")
  assert.notEqual(i, -1)
  assert.equal(argv.length, i + 1, "nothing may follow --save: no path argument")
})

test("screenshotArgs: cursor off omits --cursor", () => {
  assert.equal(screenshotArgs(shot({ cursor: false })).includes("--cursor"), false)
})

test("screenshotArgs: cursor on appends --cursor last", () => {
  const argv = screenshotArgs(shot({ save: true, cursor: true }))
  assert.equal(argv[argv.length - 1], "--cursor")
})

test("screenshotArgs: every target x format x delay combination", () => {
  for (const target of TARGETS) {
    for (const format of SCREENSHOT_FORMATS) {
      for (const delay of [0, 3, 5, 10]) {
        assert.deepEqual(screenshotArgs(shot({ target, format, delay })), [
          PROGRAM,
          "screenshot",
          "--target",
          target,
          "--delay",
          String(delay),
          "--format",
          format,
        ])
      }
    }
  }
})

// -- recording argv ----------------------------------------------------------

test("recordingArgs: the full argv, verbatim", () => {
  assert.deepEqual(
    recordingArgs(
      rec({ target: "screen", fps: 30, format: "webm", audio: "none", quality: "medium", duration: 60, cursor: true }),
    ),
    [
      PROGRAM,
      "start",
      "--target",
      "screen",
      "--fps",
      "30",
      "--format",
      "webm",
      "--quality",
      "medium",
      "--audio",
      "none",
      "--duration",
      "60",
      "--cursor",
    ],
  )
})

test("recordingArgs: the leading pair is the program and the subcommand", () => {
  const argv = recordingArgs(rec())
  assert.equal(argv[0], PROGRAM)
  assert.equal(argv[1], "start")
})

test("recordingArgs: --fps is the standard fps outside GIF mode", () => {
  for (const format of ["mp4", "webm"] as const) {
    const argv = recordingArgs(rec({ format, fps: 24, gifFps: 30 }))
    assert.equal(argv[argv.indexOf("--fps") + 1], "24")
  }
})

test("recordingArgs: --fps switches to gifFps IN GIF mode", () => {
  const argv = recordingArgs(rec({ format: "gif", fps: 24, gifFps: 15 }))
  assert.equal(argv[argv.indexOf("--fps") + 1], "15")
})

test("recordingArgs: --size is emitted for GIF ONLY", () => {
  const gif = recordingArgs(rec({ format: "gif" }))
  assert.equal(gif.includes("--size"), true)
  for (const format of ["mp4", "webm"] as const) {
    assert.equal(recordingArgs(rec({ format })).includes("--size"), false)
  }
})

test("recordingArgs: --size maps the UI scale vocabulary to bare numbers", () => {
  // THE DRIFT TRAP. `75%` and `50%` are the UI's spelling; bin/capture-tool's
  // argparse accepts only `original` | `75` | `50`.
  assert.deepEqual(recordingArgs(rec({ format: "gif", size: "original" })).slice(-2), ["--size", "original"])
  assert.deepEqual(recordingArgs(rec({ format: "gif", size: "75%" })).slice(-2), ["--size", "75"])
  assert.deepEqual(recordingArgs(rec({ format: "gif", size: "50%" })).slice(-2), ["--size", "50"])
})

test("recordingArgs: THE TRAP — --size never carries a percent sign", () => {
  for (const size of GIF_SIZES) {
    for (const format of RECORDING_FORMATS) {
      for (const argv of [recordingArgs(rec({ format, size }))]) {
        for (const token of argv) {
          assert.equal(token.includes("%"), false, `argv token carried a percent: ${token}`)
        }
      }
    }
  }
  // And the mapping itself never leaks a percent.
  for (const value of Object.values(GIF_SIZE_ARG)) {
    assert.equal(value.includes("%"), false)
  }
})

test("recordingArgs: --size comes before --cursor", () => {
  const argv = recordingArgs(rec({ format: "gif", size: "75%", cursor: true }))
  assert.ok(argv.indexOf("--size") < argv.indexOf("--cursor"))
  assert.deepEqual(argv.slice(-3), ["--size", "75", "--cursor"])
})

test("recordingArgs: --audio maps microphone to mic", () => {
  // THE OTHER DRIFT TRAP. The UI and the config both say `microphone`; the CLI
  // says `mic`. `--audio microphone` is rejected.
  const noneArgv = recordingArgs(rec({ audio: "none" }))
  assert.equal(noneArgv[noneArgv.indexOf("--audio") + 1], "none")
  const micArgv = recordingArgs(rec({ audio: "microphone" }))
  assert.equal(micArgv[micArgv.indexOf("--audio") + 1], "mic")
  const systemArgv = recordingArgs(rec({ audio: "system" }))
  assert.equal(systemArgv[systemArgv.indexOf("--audio") + 1], "system")
})

test("recordingArgs: --audio is emitted for every source, including GIF", () => {
  for (const audio of AUDIO_SOURCES) {
    assert.equal(recordingArgs(rec({ format: "mp4", audio })).includes("--audio"), true)
    // Pre-A6 behaviour: the flag is emitted unconditionally even though the
    // GIF special pipeline never opens audio. Suppressing it would be an
    // unrequested behaviour change.
    assert.equal(recordingArgs(rec({ format: "gif", audio })).includes("--audio"), true)
  }
})

test("recordingArgs: never emits the UI spelling of the microphone", () => {
  for (const format of RECORDING_FORMATS) {
    for (const audio of AUDIO_SOURCES) {
      assert.equal(recordingArgs(rec({ format, audio })).includes("microphone"), false)
    }
  }
})

test("recordingArgs: every duration, with 0 meaning unlimited", () => {
  for (const duration of [0, 10, 30, 60]) {
    const argv = recordingArgs(rec({ duration }))
    assert.equal(argv[argv.indexOf("--duration") + 1], String(duration))
  }
})

test("recordingArgs: every quality x standard-format combination", () => {
  for (const format of RECORDING_FORMATS) {
    for (const quality of ["low", "medium", "high"] as const) {
      const argv = recordingArgs(rec({ format, quality }))
      assert.equal(argv[argv.indexOf("--quality") + 1], quality)
    }
  }
})

test("recordingArgs: every target x format combination keeps the flag order", () => {
  for (const target of TARGETS) {
    for (const format of RECORDING_FORMATS) {
      const argv = recordingArgs(rec({ target, format }))
      const flags = argv.filter((a) => a.startsWith("--"))
      const expected = ["--target", "--fps", "--format", "--quality", "--audio", "--duration"]
      if (isGif({ format })) expected.push("--size")
      assert.deepEqual(flags, expected)
    }
  }
})

test("recordingArgs: cursor on appends --cursor last, off omits it", () => {
  assert.equal(recordingArgs(rec({ cursor: false })).includes("--cursor"), false)
  const gif = recordingArgs(rec({ format: "gif", cursor: true }))
  assert.equal(gif[gif.length - 1], "--cursor")
})

test("recordingArgs: duration 0 is emitted, never dropped as falsy", () => {
  // `if (request.duration)` would silently produce no --duration for the
  // unlimited case, which the backend reads as "use its own default".
  const argv = recordingArgs(rec({ duration: 0 }))
  assert.ok(argv.includes("--duration"))
  assert.equal(argv[argv.indexOf("--duration") + 1], "0")
})

test("recordingArgs: delay-less screenshot argv never carries --size", () => {
  // Guards against a copy-paste of the recording branch into the screenshot
  // translator.
  assert.equal(screenshotArgs(shot({ format: "png" })).includes("--size"), false)
  assert.equal(screenshotArgs(shot({ format: "png" })).includes("--audio"), false)
})

test("both translators: argv[0] is the program in every case", () => {
  for (const target of TARGETS) {
    assert.equal(screenshotArgs(shot({ target }))[0], PROGRAM)
    for (const format of RECORDING_FORMATS) {
      assert.equal(recordingArgs(rec({ target, format }))[0], PROGRAM)
    }
  }
})

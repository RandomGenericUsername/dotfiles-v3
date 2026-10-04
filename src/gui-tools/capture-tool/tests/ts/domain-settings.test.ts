// ---------------------------------------------------------------------------
// Direct unit tests for `domain/settings.ts` (workstream A4, tasks 4.2 + 4.3).
//
// WHY THIS FILE EXISTS: `mergeSettings`/`validateSettings` encode every
// tolerance rule the config contract depends on — missing is first-run, corrupt
// degrades to defaults, unknown enum values fall back, wrong types fall back,
// empty strings fall back. Before A3 that logic lived inside
// `ui/CaptureWindow.tsx` and had ZERO direct coverage: the only thing
// exercising it was the Python CLI suite, which reads the same config with a
// DIFFERENT reader. A move could silently break any one of those rules and
// nothing would go red.
//
// `domain/settings.ts` is pure (no `gi://`, no `ags/*`, no I/O), so it loads
// under plain Node with no GTK, no GJS and no browser. See the `capture-test`
// Makefile target for the runner.
//
// Test naming follows `node:test`: `*.test.ts`, discovered by `node --test`.
// ---------------------------------------------------------------------------

import { test } from "node:test"
import assert from "node:assert/strict"

import {
  DEFAULT_SETTINGS,
  configBool,
  configOneOf,
  configString,
  defaultSettings,
  expandDir,
  mergeSettings,
  validateSettings,
  type CaptureSettings,
} from "../../domain/settings.ts"

// ---------------------------------------------------------------------------
// mergeSettings — task 4.2
// ---------------------------------------------------------------------------

test("mergeSettings: first run (undefined) yields every default", () => {
  assert.deepEqual(mergeSettings(undefined), defaultSettings())
})

test("mergeSettings: non-object input yields every default", () => {
  // What JSON.parse hands back for `null`, `42`, `"nope"`, `true`. The spec's
  // "Corrupt config degrades to defaults" scenario.
  for (const garbage of [null, 42, "settings", true, false, Symbol.iterator]) {
    assert.deepEqual(
      mergeSettings(garbage),
      defaultSettings(),
      `expected defaults for ${String(garbage)}`,
    )
  }
})

test("mergeSettings: an array is an object, so it degrades field-by-field", () => {
  // typeof [] === "object", so the array is used as the record. No key on it is
  // a known field, so the result is still the defaults — asserted explicitly so
  // a future `Array.isArray` guard would be a *deliberate* change, not an
  // accident.
  assert.deepEqual(mergeSettings([]), defaultSettings())
  assert.deepEqual(mergeSettings(["nonsense"]), defaultSettings())
})

test("mergeSettings: an empty object yields every default", () => {
  assert.deepEqual(mergeSettings({}), defaultSettings())
})

test("mergeSettings: unknown extra keys are dropped, not merged through", () => {
  // The config file's key set is a BACKEND CONTRACT (bin/capture-tool reads it
  // on every invocation). A key the GUI invents would be written into a file the
  // backend parses, so the merged result must have exactly these fields.
  const merged = mergeSettings({
    screenshot_dir: "/tmp/shots",
    definitely_not_a_key: "surprise",
    recording: { fps: 30, nope: 1 },
  })
  assert.deepEqual(Object.keys(merged).sort(), [
    "bar_compact_controls",
    "filename_pattern",
    "notifications",
    "recording",
    "recording_dir",
    "screenshot",
    "screenshot_dir",
  ])
  assert.deepEqual(Object.keys(merged.screenshot).sort(), ["cursor", "format", "output"])
  assert.deepEqual(Object.keys(merged.recording).sort(), ["audio", "cursor", "fps", "quality"])
})

test("mergeSettings: a partial object keeps what it sets and defaults the rest", () => {
  const merged = mergeSettings({
    screenshot_dir: "/tmp/shots",
    recording: { fps: 30 },
  })
  assert.equal(merged.screenshot_dir, "/tmp/shots")
  assert.equal(merged.recording.fps, 30)
  // Everything else is the default, not undefined.
  assert.deepEqual(merged, {
    ...defaultSettings(),
    screenshot_dir: "/tmp/shots",
    recording: { ...defaultSettings().recording, fps: 30 },
  })
})

test("mergeSettings: the nested screenshot/recording halves absent yields their defaults", () => {
  const merged = mergeSettings({
    screenshot_dir: "/tmp/shots",
    recording_dir: "/tmp/vids",
    filename_pattern: "shot",
    notifications: false,
    bar_compact_controls: true,
  })
  assert.deepEqual(merged.screenshot, DEFAULT_SETTINGS.screenshot)
  assert.deepEqual(merged.recording, DEFAULT_SETTINGS.recording)
})

test("mergeSettings: a non-object nested half falls back instead of throwing", () => {
  // `typeof null === "object"` but null has no fields, and a string/array
  // screenshot half is corruption. Neither may throw at load time.
  for (const bad of [null, "png", 7, []]) {
    const merged = mergeSettings({ screenshot: bad, recording: bad })
    assert.deepEqual(merged.screenshot, DEFAULT_SETTINGS.screenshot)
    assert.deepEqual(merged.recording, DEFAULT_SETTINGS.recording)
  }
})

test("mergeSettings: unknown enum values fall back per field", () => {
  const merged = mergeSettings({
    screenshot: { format: "webp", output: "disk" },
    recording: { fps: 120, quality: "ultra", audio: "bluetooth" },
  })
  assert.equal(merged.screenshot.format, DEFAULT_SETTINGS.screenshot.format) // png
  assert.equal(merged.screenshot.output, DEFAULT_SETTINGS.screenshot.output) // clipboard
  assert.equal(merged.recording.fps, DEFAULT_SETTINGS.recording.fps) // 60
  assert.equal(merged.recording.quality, DEFAULT_SETTINGS.recording.quality) // high
  assert.equal(merged.recording.audio, DEFAULT_SETTINGS.recording.audio) // system
})

test("mergeSettings: a valid value in a partially corrupt half is still honoured", () => {
  // The fallback is per FIELD, not per half: one bad key must not poison its
  // siblings. This is the difference between tolerance and a silent reset.
  const merged = mergeSettings({
    screenshot: { format: "jpeg", output: 5, cursor: true },
    recording: { fps: "30", quality: "low", audio: "none", cursor: "yes" },
  })
  assert.equal(merged.screenshot.format, "jpeg") // valid, kept
  assert.equal(merged.screenshot.output, "clipboard") // wrong type, defaulted
  assert.equal(merged.screenshot.cursor, true) // valid, kept
  assert.equal(merged.recording.fps, 60) // "30" is a string, not the number
  assert.equal(merged.recording.quality, "low") // valid, kept
  assert.equal(merged.recording.audio, "none") // valid, kept
  assert.equal(merged.recording.cursor, true) // "yes" is not a boolean
})

test("mergeSettings: every accepted enum member round-trips", () => {
  // Not just the fallbacks: a value the GUI itself writes must survive the
  // merge, or saving a setting would silently not take effect.
  const merged = mergeSettings({
    screenshot: { format: "jpeg", output: "save", cursor: true },
    recording: { fps: 24, quality: "low", audio: "mic", cursor: false },
  })
  assert.deepEqual(merged.screenshot, { format: "jpeg", output: "save", cursor: true })
  assert.deepEqual(merged.recording, { fps: 24, quality: "low", audio: "mic", cursor: false })
})

test("mergeSettings: fps 30 and 60 survive alongside 24", () => {
  for (const fps of [24, 30, 60] as const) {
    assert.equal(mergeSettings({ recording: { fps } }).recording.fps, fps)
  }
})

test("mergeSettings: wrong types on the flat fields fall back", () => {
  const merged = mergeSettings({
    screenshot_dir: 42,
    recording_dir: ["/tmp"],
    filename_pattern: { fmt: "x" },
    notifications: "true",
    bar_compact_controls: 1,
  })
  assert.equal(merged.screenshot_dir, DEFAULT_SETTINGS.screenshot_dir)
  assert.equal(merged.recording_dir, DEFAULT_SETTINGS.recording_dir)
  assert.equal(merged.filename_pattern, DEFAULT_SETTINGS.filename_pattern)
  // "true" is a truthy STRING; honouring it as a boolean would be a type
  // confusion bug, so it falls back to the default (which is true).
  assert.equal(merged.notifications, DEFAULT_SETTINGS.notifications)
  // 1 is a truthy NUMBER and the default is false, so this is a visible flip.
  assert.equal(merged.bar_compact_controls, DEFAULT_SETTINGS.bar_compact_controls)
})

test("mergeSettings: an all-whitespace string is empty, so it falls back", () => {
  // configString trims before the emptiness test. A config written by a stray
  // editor with a space-only value must not produce a path of "   ".
  const merged = mergeSettings({ screenshot_dir: "   ", filename_pattern: "\t\n " })
  assert.equal(merged.screenshot_dir, DEFAULT_SETTINGS.screenshot_dir)
  assert.equal(merged.filename_pattern, DEFAULT_SETTINGS.filename_pattern)
})

test("mergeSettings: false booleans are values, not absence", () => {
  // The classic falsy-fallback bug: `notifications: false` and
  // `screenshot.cursor: false` must NOT be replaced by the (true/false)
  // defaults. DEFAULT_SETTINGS.notifications is true and
  // DEFAULT_SETTINGS.screenshot.cursor is false, so both directions are pinned
  // here — a fallback implementation fails one of them.
  const merged = mergeSettings({
    notifications: false,
    bar_compact_controls: false,
    screenshot: { cursor: true },
    recording: { cursor: false },
  })
  assert.equal(merged.notifications, false)
  assert.equal(merged.bar_compact_controls, false)
  assert.equal(merged.screenshot.cursor, true)
  assert.equal(merged.recording.cursor, false)
})

test("mergeSettings: does not mutate DEFAULT_SETTINGS or alias its nested objects", () => {
  const merged = mergeSettings({ screenshot: { format: "jpeg" } })
  merged.screenshot.format = "png"
  merged.recording.fps = 24
  assert.deepEqual(DEFAULT_SETTINGS, {
    screenshot_dir: "~/Pictures/Screenshots",
    recording_dir: "~/Videos/Recordings",
    filename_pattern: "{kind}_%Y-%m-%d_%H-%M-%S",
    notifications: true,
    bar_compact_controls: false,
    screenshot: { format: "png", output: "clipboard", cursor: false },
    recording: { fps: 60, quality: "high", audio: "system", cursor: true },
  })
  assert.notEqual(merged.screenshot, DEFAULT_SETTINGS.screenshot)
  assert.notEqual(merged.recording, DEFAULT_SETTINGS.recording)
})

test("mergeSettings: defaultSettings() hands out an independent deep copy each call", () => {
  // GJS has no structuredClone, so this is a hand-rolled deep copy; if it ever
  // regresses to a shallow one the next saved setting corrupts the defaults.
  const a = defaultSettings()
  const b = defaultSettings()
  assert.notEqual(a, b)
  assert.notEqual(a.screenshot, b.screenshot)
  assert.notEqual(a.recording, b.recording)
  a.screenshot.format = "jpeg"
  a.recording.audio = "none"
  assert.equal(b.screenshot.format, "png")
  assert.equal(b.recording.audio, "system")
})

// ---------------------------------------------------------------------------
// The field-level tolerance primitives, which carry the rules above.
// ---------------------------------------------------------------------------

test("configOneOf: membership decides, not coercion", () => {
  assert.equal(configOneOf("png", ["png", "jpeg"], "png"), "png")
  assert.equal(configOneOf("webp", ["png", "jpeg"], "png"), "png")
  // The fps tuple is numeric: the string "30" is NOT 30.
  assert.equal(configOneOf(30, [24, 30, 60], 60), 30)
  assert.equal(configOneOf("30", [24, 30, 60], 60), 60)
  assert.equal(configOneOf(null, [24, 30, 60], 60), 60)
  assert.equal(configOneOf(undefined, [24, 30, 60], 60), 60)
})

test("configBool: only a real boolean is accepted", () => {
  assert.equal(configBool(true, false), true)
  assert.equal(configBool(false, true), false)
  for (const notABool of ["true", 1, 0, null, undefined, {}, []]) {
    assert.equal(configBool(notABool, true), true)
    assert.equal(configBool(notABool, false), false)
  }
})

test("configString: a non-empty string is kept verbatim, whitespace-only is not", () => {
  assert.equal(configString("/tmp/x", "fallback"), "/tmp/x")
  // Not trimmed on the way through — the value is stored as the user typed it.
  assert.equal(configString("  /tmp/x  ", "fallback"), "  /tmp/x  ")
  for (const notAString of ["", "   ", "\t", 42, null, undefined, {}, []]) {
    assert.equal(configString(notAString, "fallback"), "fallback")
  }
})

// ---------------------------------------------------------------------------
// validateSettings — task 4.3
// ---------------------------------------------------------------------------

test("validateSettings: the defaults are valid", () => {
  assert.equal(validateSettings(defaultSettings()), null)
})

test("validateSettings: a populated settings object is valid", () => {
  const valid: CaptureSettings = {
    ...defaultSettings(),
    screenshot_dir: "/home/u/Pictures",
    recording_dir: "/home/u/Videos",
    filename_pattern: "{kind}_%Y%m%d-%H%M%S",
    notifications: false,
    bar_compact_controls: true,
    screenshot: { format: "jpeg", output: "save", cursor: true },
    recording: { fps: 24, quality: "low", audio: "mic", cursor: false },
  }
  assert.equal(validateSettings(valid), null)
})

test("validateSettings: a tilde path and a %-heavy strftime pattern are valid", () => {
  // `~` and `{kind}` are the defaults' own shape; a validator that expanded or
  // rejected them would break every first-run install.
  const s = defaultSettings()
  s.screenshot_dir = "~/Pictures/Screenshots"
  s.filename_pattern = "{kind}_%Y-%m-%d_%H-%M-%S"
  assert.equal(validateSettings(s), null)
})

test("validateSettings: an empty screenshot dir is rejected", () => {
  const s = defaultSettings()
  s.screenshot_dir = ""
  assert.equal(validateSettings(s), "Screenshot folder cannot be empty.")
  s.screenshot_dir = "    "
  assert.equal(validateSettings(s), "Screenshot folder cannot be empty.")
  s.screenshot_dir = "\t\n"
  assert.equal(validateSettings(s), "Screenshot folder cannot be empty.")
})

test("validateSettings: an empty recording dir is rejected", () => {
  const s = defaultSettings()
  s.recording_dir = ""
  assert.equal(validateSettings(s), "Recording folder cannot be empty.")
  s.recording_dir = "  "
  assert.equal(validateSettings(s), "Recording folder cannot be empty.")
})

test("validateSettings: an empty filename pattern is rejected", () => {
  const s = defaultSettings()
  s.filename_pattern = ""
  assert.equal(validateSettings(s), "Filename pattern cannot be empty.")
  s.filename_pattern = "   "
  assert.equal(validateSettings(s), "Filename pattern cannot be empty.")
})

test("validateSettings: a path separator in the pattern is rejected", () => {
  // The pattern is substituted into a filename, so a separator would let the
  // write escape the configured directory.
  const s = defaultSettings()
  for (const pattern of ["shots/shot", "/shot", "sub/shot", "//", "{kind}/%Y", "shot/"]) {
    s.filename_pattern = pattern
    assert.equal(
      validateSettings(s),
      "Filename pattern cannot contain a path separator.",
      `expected rejection for ${JSON.stringify(pattern)}`,
    )
  }
})

test("validateSettings: a NUL byte in the pattern is rejected", () => {
  // A NUL in a filename truncates the path at the syscall boundary.
  const s = defaultSettings()
  s.filename_pattern = "shot\0.png"
  assert.equal(validateSettings(s), "Filename pattern cannot contain a path separator.")
})

test("validateSettings: a backslash alone is NOT a separator here", () => {
  // Pinned because it is surprising: only "/" and NUL are rejected, so a
  // Windows-style pattern is accepted. If that is ever meant to change, this
  // test is the place it must change deliberately.
  const s = defaultSettings()
  s.filename_pattern = "sub\\shot"
  assert.equal(validateSettings(s), null)
})

test("validateSettings: surrounding whitespace is trimmed for the check only", () => {
  const s = defaultSettings()
  s.filename_pattern = "  {kind}  "
  assert.equal(validateSettings(s), null)
})

test("validateSettings: the checks run in a fixed order", () => {
  // The order is the user-visible one: the first broken field is the first
  // message shown, so the settings view can focus it.
  const s = defaultSettings()
  s.screenshot_dir = ""
  s.recording_dir = ""
  s.filename_pattern = ""
  assert.equal(validateSettings(s), "Screenshot folder cannot be empty.")
  s.screenshot_dir = "/tmp"
  assert.equal(validateSettings(s), "Recording folder cannot be empty.")
  s.recording_dir = "/tmp"
  assert.equal(validateSettings(s), "Filename pattern cannot be empty.")
})

// ---------------------------------------------------------------------------
// expandDir — the injected environment seam (task 3.3). Pure string work, and
// the reason domain/ needs no gi://GLib.
// ---------------------------------------------------------------------------

test("expandDir: expands ~ and $VAR/${VAR} through the injected environment", () => {
  const env = {
    getenv: (name: string) => ({ HOME: "/home/u", SHOTSDIR: "/data/shots" })[name] ?? null,
    home: () => "/home/u",
  }
  assert.equal(expandDir("~/Pictures", env), "/home/u/Pictures")
  assert.equal(expandDir("~", env), "/home/u")
  assert.equal(expandDir("$SHOTSDIR/x", env), "/data/shots/x")
  assert.equal(expandDir("${SHOTSDIR}/x", env), "/data/shots/x")
  // An unset variable is left verbatim rather than becoming "undefined/" or "".
  assert.equal(expandDir("$NOPE/x", env), "$NOPE/x")
  assert.equal(expandDir("/absolute/path", env), "/absolute/path")
  // A ~ that is not the home prefix is not ours to expand.
  assert.equal(expandDir("~user/x", env), "~user/x")
})

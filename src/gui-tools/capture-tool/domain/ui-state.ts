// ---------------------------------------------------------------------------
// Persisted UI state (GUI-local JSON; no provisioning surface).
//
// PURE LAYER (design.md §2/§3.1/§3.4, tasks 3.2 + 3.4): the interfaces, the
// first-run constants, the option vocabularies, the settings→defaults
// precedence rule, and the MERGE half of `loadUiState` — which is pure once the
// read is lifted. The read and the write (`loadUiState`'s I/O half and
// `saveUiState`) own the GLib file reads/writes and the recursive directory
// creation, and move to `adapters/glib-ui-state-store.ts` at A5.
// ---------------------------------------------------------------------------

import type {
  AudioSource,
  CaptureTarget,
  GifScale,
  RecordingFormat,
  RecordingQuality,
  ScreenshotFormat,
} from "../types"
import type { CaptureSettings, ConfigRecordingAudio } from "./settings"

export interface ScreenshotUiState {
  target: CaptureTarget
  delay: number
  format: ScreenshotFormat
  save: boolean
}

export interface RecordingUiState {
  target: CaptureTarget
  fps: number
  format: RecordingFormat
  audio: AudioSource
  quality: RecordingQuality
  duration: number
  gifFps: number
  size: GifScale
  customDuration: number
}

// First-run defaults per spec: Region/PNG/Clipboard and
// Region/60fps/MP4/System/High/∞ (GIF extras: 15fps, Original, 120s custom).
export const DEFAULT_SCREENSHOT: ScreenshotUiState = {
  target: "region",
  delay: 0,
  format: "png",
  save: false,
}

export const DEFAULT_RECORDING: RecordingUiState = {
  target: "region",
  fps: 60,
  format: "mp4",
  audio: "system",
  quality: "high",
  duration: 0,
  gifFps: 15,
  size: "original",
  customDuration: 120,
}

/**
 * The ONE live UI state the whole app shares (fix-capture-per-monitor-state).
 *
 * The composition root calls this ONCE and hands the result to every window it
 * builds, because the state is per-APPLICATION, not per-window: there is one
 * `capture-ui.json`, one settings config and one precedence chain, so two
 * windows each allocating their own copy would mean two owners of one logical
 * value writing the same file — last writer wins, and the loser's selection is
 * silently destroyed (reproduced: two windows, one file, `screen` overwritten
 * by `window`).
 *
 * Two properties are load-bearing, and both are asserted in
 * `tests/ts/ui-state-ownership.test.ts`:
 *
 *   * FRESH OBJECTS, not the constants. Every caller gets objects it may
 *     mutate; `DEFAULT_SCREENSHOT` / `DEFAULT_RECORDING` stay pristine so the
 *     next first run is not seeded from another window's leftovers.
 *   * A REAL FACTORY, not a memoised singleton. Sharing is the composition
 *     root's decision, made once, visibly — not a hidden module-level global
 *     that a second window would silently inherit.
 *
 * Mutated IN PLACE from then on: `ClassicWindow`'s `applyStateToUi()` assigns
 * into these objects rather than rebinding, because the three pages hold the
 * exact objects they were constructed with.
 */
export function createUiState(): UiState {
  return {
    screenshot: { ...DEFAULT_SCREENSHOT },
    recording: { ...DEFAULT_RECORDING },
  }
}

export function oneOf<T>(value: unknown, allowed: readonly T[], fallback: T): T {
  return allowed.includes(value as T) ? (value as T) : fallback
}

export const TARGETS = ["region", "screen", "window"] as const
export const SCREENSHOT_DELAYS = [0, 3, 5, 10] as const
export const SCREENSHOT_FORMATS = ["png", "jpeg"] as const
export const RECORDING_FPS = [24, 30, 60] as const
export const GIF_FPS = [10, 15, 20, 30] as const
export const RECORDING_FORMATS = ["mp4", "webm", "gif"] as const
export const AUDIO_SOURCES = ["system", "microphone", "none"] as const
export const QUALITIES = ["low", "medium", "high"] as const
export const DURATIONS = [0, 10, 30, 60] as const
export const GIF_SIZES = ["original", "75%", "50%"] as const

/** Config `mic` ↔ UI `microphone` (the two vocabularies in play). */
export function audioToUi(audio: ConfigRecordingAudio): AudioSource {
  return audio === "mic" ? "microphone" : audio
}

/** The pair of mode views `configDefaults` and `mergeUiState` both speak in. */
export interface UiState {
  screenshot: ScreenshotUiState
  recording: RecordingUiState
}

/**
 * Initial-selection defaults sourced from the settings config (precedence:
 * last-used UI state > settings defaults > hardcoded constants).
 */
export function configDefaults(config: CaptureSettings): UiState {
  return {
    screenshot: {
      ...DEFAULT_SCREENSHOT,
      format: config.screenshot.format as ScreenshotFormat,
      save: config.screenshot.output === "save",
    },
    recording: {
      ...DEFAULT_RECORDING,
      fps: config.recording.fps,
      quality: config.recording.quality as RecordingQuality,
      audio: audioToUi(config.recording.audio),
    },
  }
}

/** The on-disk shape `mergeUiState` accepts: every field optional. */
export interface PersistedUiState {
  screenshot?: Partial<ScreenshotUiState>
  recording?: Partial<RecordingUiState>
}

/**
 * The MERGE half of `loadUiState` (design.md §3.1, task 3.2): overlay the
 * last-used values on the settings defaults, falling back per field.
 *
 * Pure — the existence probe, the read, the JSON parse, and the
 * missing-is-silent / corrupt-is-loud degradation stay with the caller until
 * A5 lifts them into `adapters/glib-ui-state-store.ts`.
 */
export function mergeUiState(base: UiState, persisted: PersistedUiState): UiState {
  const screenshot = { ...base.screenshot, ...persisted.screenshot }
  const recording = { ...base.recording, ...persisted.recording }
  return {
    screenshot: {
      target: oneOf(screenshot.target, TARGETS, base.screenshot.target),
      delay: oneOf(screenshot.delay, SCREENSHOT_DELAYS, base.screenshot.delay),
      format: oneOf(screenshot.format, SCREENSHOT_FORMATS, base.screenshot.format),
      save: typeof screenshot.save === "boolean" ? screenshot.save : base.screenshot.save,
    },
    recording: {
      target: oneOf(recording.target, TARGETS, base.recording.target),
      fps: oneOf(recording.fps, RECORDING_FPS, base.recording.fps),
      format: oneOf(recording.format, RECORDING_FORMATS, base.recording.format),
      audio: oneOf(recording.audio, AUDIO_SOURCES, base.recording.audio),
      quality: oneOf(recording.quality, QUALITIES, base.recording.quality),
      duration:
        typeof recording.duration === "number" && recording.duration >= 0
          ? recording.duration
          : base.recording.duration,
      gifFps: oneOf(recording.gifFps, GIF_FPS, base.recording.gifFps),
      size: oneOf(recording.size, GIF_SIZES, base.recording.size),
      customDuration:
        typeof recording.customDuration === "number" && recording.customDuration >= 5
          ? Math.min(3600, Math.round(recording.customDuration))
          : base.recording.customDuration,
    },
  }
}

// CLI contract (design.md §4): --audio {none,system,mic}, --duration <seconds>
// (0 = infinite). GIF additionally takes --size {original,75,50} (backend
// contract — NOT percents; the backend argparse rejects anything else).
export const GIF_SIZE_ARG: Record<GifScale, string> = {
  original: "original",
  "75%": "75",
  "50%": "50",
}

// ---------------------------------------------------------------------------
// The two GIF/duration predicates the recording view asks about. They were
// closures over the component's `recording` variable; the state they read is
// now an argument, because `domain/` has no window to close over (design.md
// §3.1 line map, tasks 3.4). Same predicates, same values — the call sites pass
// the same `recording` they used to capture.
// ---------------------------------------------------------------------------

/**
 * GIF mode, i.e. the format that routes through the GIF special pipeline.
 *
 * Takes the structural minimum ({ format }) rather than the whole state, so the
 * request→argv translator (`domain/cli-args.ts`, A6) asks the SAME predicate the
 * view does instead of re-deriving `format === "gif"`. Two copies of the GIF
 * branch is precisely the drift this layer exists to prevent.
 */
export function isGif(recording: { format: RecordingFormat }): boolean {
  return recording.format === "gif"
}

/**
 * The selected duration button's value: one of `DURATIONS`, or -1 when the
 * value is custom (the inline spin editor's value is then in
 * `recording.customDuration`).
 */
export function durationSelection(recording: RecordingUiState): number {
  return DURATIONS.includes(recording.duration as (typeof DURATIONS)[number])
    ? recording.duration
    : -1
}
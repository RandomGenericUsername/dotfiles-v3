// ---------------------------------------------------------------------------
// Capture REQUESTS: what the user asked for, as values (design.md §2/§3.3,
// task 6.1).
//
// A request is the GUI's intent, in the GUI's vocabulary — `microphone`, not
// `mic`; `75%`, not `75`. It is deliberately NOT argv: argv is the BACKEND's
// vocabulary, and turning one into the other is a pure function that lives one
// module over in `domain/cli-args.ts`.
//
// Why the split matters (spec requirement "Exactly one request→argv
// translator SHALL exist, in domain/"): a second layout can hold its own
// request objects, its own widget tree and its own state — but it calls the
// same translator. There is exactly one place that knows the backend wants
// `--size 75` and `--audio mic`, so there is exactly one place to get wrong.
//
// The fields mirror exactly what `takeScreenshot()` / `startRecording()` passed
// at the argv call sites before A6 (CaptureWindow.tsx:264–308 at HEAD). Nothing
// is added and nothing is dropped; `cursor` is the settings-derived flag that
// both call sites read out of `config.{screenshot,recording}.cursor`.
//
// `AudioSource` (UI vocabulary) and `GifScale` (UI vocabulary) are re-exported
// here so a layout that builds a request needs one import, and so the
// vocabulary boundary is stated in one place.
//
// Types only: no imports from `ags/*` or `gi://*` (gate check 1).
// ---------------------------------------------------------------------------

import type {
  AudioSource,
  CaptureTarget,
  GifScale,
  RecordingFormat,
  RecordingQuality,
  ScreenshotFormat,
} from "../types"

export type { AudioSource, GifScale }

/** Everything needed to spawn one `capture-tool screenshot`. */
export interface ScreenshotRequest {
  /** `region` | `screen` | `window`. */
  target: CaptureTarget
  /** Countdown in seconds before the shutter fires. */
  delay: number
  /** `png` | `jpeg`. */
  format: ScreenshotFormat
  /**
   * False → clipboard (the backend's default, no flag). True → the backend's
   * own default save path (config dir + filename pattern), hence a bare
   * `--save` with no path argument.
   */
  save: boolean
  /** Settings-derived: whether the pointer is captured too. */
  cursor: boolean
}

/** Everything needed to spawn one `capture-tool start`. */
export interface RecordingRequest {
  /** `region` | `screen` | `window`. */
  target: CaptureTarget
  /** Frames per second for the standard (`mp4`/`webm`) pipeline. */
  fps: number
  /**
   * Frames per second for the GIF pipeline. The two are separate knobs in the
   * UI (different rows, one shown per mode) and only the relevant one is
   * emitted as `--fps`.
   */
  gifFps: number
  /** `mp4` | `webm` | `gif`. */
  format: RecordingFormat
  /** UI audio vocabulary: `none` | `system` | `microphone`. */
  audio: AudioSource
  quality: RecordingQuality
  /** Seconds; 0 means unlimited (the backend's own convention). */
  duration: number
  /** UI scale vocabulary: `original` | `75%` | `50%`. GIF only. */
  size: GifScale
  /** Settings-derived: whether the pointer is captured too. */
  cursor: boolean
}

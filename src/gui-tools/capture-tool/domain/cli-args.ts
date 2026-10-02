// ---------------------------------------------------------------------------
// THE request→argv translator (design.md §3.3, task 6.2) — the single pure
// seam between the GUI and the capture engine.
//
// This module is the ONLY place in the whole tool that writes an argv literal
// for `capture-tool screenshot` / `capture-tool start`. That is not tidiness,
// it is correctness: this is what makes "two layouts, one engine" true rather
// than aspirational. A future alternate capture layout builds its own request
// objects and calls these two functions; it does not re-derive the flags. If it
// could, the GIF size token and the audio vocabulary would drift the moment the
// second layout was written, and BOTH drifts fail silently at the worst
// possible moment — the backend's argparse rejects the flag and the capture
// simply does not happen.
//
// THE TWO VOCABULARY TRAPS (spec requirement "The translator SHALL emit the
// backend's exact token vocabulary"), stated here because this is where they
// are enforced:
//
//   * `--size` takes `original` | `75` | `50` — BARE NUMBERS. The UI's scale
//     vocabulary is `original` | `75%` | `50%`. The `%` must be dropped, or
//     bin/capture-tool's argparse rejects `--size 75%`.
//   * `--audio` takes `none` | `system` | `mic`. The UI's vocabulary is `none`
//     | `system` | `microphone`. `--audio microphone` is rejected.
//     (`audioToUi()` in ./ui-state.ts is the OTHER direction of the same
//     mapping, for config `mic` → UI `microphone`.)
//
// Both conversions go through the existing, already-tested lookups —
// `GIF_SIZE_ARG` for the scale, and a local expression for the audio source —
// rather than re-spelling the literals here.
//
// PURE: no GTK, no GLib, no process spawn, no `ags/*`, no `gi://*` (gate checks
// 1 and 3 — and note the gate greps this file for the spawning symbol's name
// too, so this comment must not spell it out). Inputs in, argv array out. The
// spawn — and the hide-then-wait-150ms that belongs to the compositor rather
// than to this translation — is the adapter's
// (`adapters/exec-capture-launcher.ts`, reached through
// `ports/capture-launcher.ts`).
//
// Ordering is part of the contract, not an accident of how the array literal
// was typed: flag order is reproduced exactly as the pre-A6 call sites built
// it, so a diff against a recorded capture run is meaningful.
// ---------------------------------------------------------------------------

import type { RecordingRequest, ScreenshotRequest } from "./capture-request"
import { GIF_SIZE_ARG, isGif } from "./ui-state"

/**
 * UI audio vocabulary → CLI audio vocabulary.
 *
 * The ONLY asymmetry is the microphone: the UI and the config both say
 * `microphone`, the CLI says `mic`. `none` and `system` are spelled the same
 * everywhere, so they pass through untouched.
 */
function audioArg(audio: RecordingRequest["audio"]): string {
  return audio === "microphone" ? "mic" : audio
}

/**
 * `capture-tool screenshot` argv (pre-A6: CaptureWindow.tsx:264–281).
 *
 * `--save` is a bare flag: the backend owns the destination (its config dir +
 * filename pattern), so the GUI never composes a path. Its absence means
 * clipboard, which is why there is no `--no-save` counterpart.
 */
export function screenshotArgs(request: ScreenshotRequest): string[] {
  const args = [
    "capture-tool",
    "screenshot",
    "--target",
    request.target,
    "--delay",
    String(request.delay),
    "--format",
    request.format,
  ]
  if (request.save) args.push("--save")
  if (request.cursor) args.push("--cursor")
  return args
}

/**
 * `capture-tool start` argv (pre-A6: CaptureWindow.tsx:287–307).
 *
 * Three branches carry the traps:
 *
 *   * `--fps` is `gifFps` in GIF mode and `fps` otherwise — the two knobs are
 *     separate rows in the UI and only the visible one is meaningful.
 *   * `--size` is emitted for GIF ONLY. The standard pipeline has no scale
 *     flag; passing one is rejected.
 *   * `--audio` is emitted unconditionally, even for GIF (where the special
 *     pipeline never opens audio anyway). That matches the pre-A6 behaviour
 *     byte for byte; the flag is harmlessly ignored, and suppressing it here
 *     would be an unrequested behaviour change.
 */
export function recordingArgs(request: RecordingRequest): string[] {
  const gif = isGif(request)
  const args = [
    "capture-tool",
    "start",
    "--target",
    request.target,
    "--fps",
    String(gif ? request.gifFps : request.fps),
    "--format",
    request.format,
    "--quality",
    request.quality,
    "--audio",
    audioArg(request.audio),
    "--duration",
    String(request.duration),
  ]
  // `75%` -> `75`, `50%` -> `50`: bare numbers or argparse rejects the flag.
  if (gif) args.push("--size", GIF_SIZE_ARG[request.size])
  if (request.cursor) args.push("--cursor")
  return args
}

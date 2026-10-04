// ---------------------------------------------------------------------------
// ADAPTER: `execAsync`-backed capture launching (design.md §3.4, task 5.7).
//
// Owns the two things about spawning that are NOT argv: the spawn itself, and
// the 150ms delay after the window is hidden.
//
// THE 150ms IS NOT A POLITE PAUSE. The window must be off screen BEFORE the
// backend reads the display, or the capture includes the panel that asked for
// it. The compositor's unmap is not synchronous with `visible = false`, so the
// hide is given a turn of the event loop plus margin before the process starts.
// This belongs to the adapter rather than to the view because it is a fact
// about the compositor, not about any one layout: a second layout inherits it
// by construction instead of re-deriving (possibly wrongly) the number.
//
// Rejections are logged, not propagated: the launcher is fire-and-forget, and
// the caller has already hidden the window, so there is nothing left to undo.
// ---------------------------------------------------------------------------

import { execAsync } from "ags/process"
import type { CaptureLauncher } from "../ports/capture-launcher"

/** The composition root's `CaptureLauncher`. */
export function execCaptureLauncher(): CaptureLauncher {
  return {
    launch(argv: string[]): void {
      setTimeout(() => execAsync(argv).catch(console.error), 150)
    },
  }
}
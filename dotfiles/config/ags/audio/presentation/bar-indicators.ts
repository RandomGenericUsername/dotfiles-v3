import { levelVariant, clampVolume } from "./levels.ts"
import type { AudioPanelViewModel } from "./audio-panel-view-model.ts"

/**
 * The status bar's audio indicators, projected from the panel view model.
 * PURE — no `ags`, no GTK, no Gio, no I/O, so `make ags-test` exercises it.
 *
 * WHY THIS IS ITS OWN MODULE rather than living in `bar/widgets/audio.tsx`. The
 * bar's two glyphs are DECISIONS (which `volume` variant a reading maps to, when
 * the mic live dot shows), and the widget must only render them. Kept here, the
 * decisions are checked by a table of cases; kept in the widget, they can only
 * be checked by rendering GObject state. Same argument as
 * `components/battery/presentation.ts` and `battery-icon.ts`.
 *
 * The two indicators mirror the panel's own projections so the bar glyph and the
 * panel it opens can never disagree: `output` reads the same
 * `preferredOutput.volume` the panel's output section reads, and `mic` reads the
 * same `input`/`inputConsumers` the panel's Input section reads.
 */

export interface BarIndicatorState {
  /** The `volume` icon-group variant for the preferred output. */
  output: {
    variant: string
    /** 0..1, clamped. */
    level: number
    muted: boolean
  }
  /** The `microphone` icon-group variant plus live-recording state. */
  mic: {
    variant: "mic-on" | "mic-off"
    /** True while any input-direction consumer is present. */
    live: boolean
  }
}

export function projectBarIndicators(model: AudioPanelViewModel): BarIndicatorState {
  // A null preferredOutput (before hydration, or no sink) reads as unmuted/0 —
  // levelVariant then yields "muted", the same glyph a real zero/muted sink
  // shows. This is the bar's boot state, unchanged from before the migration.
  const outputVolume = model.preferredOutput?.volume
  const muted = outputVolume?.muted ?? false
  const level = clampVolume(outputVolume?.level ?? 0)

  // The mic glyph is discrete (on/off); the live dot is separate and reflects
  // any current input-direction stream (the hexagon equivalent of the legacy
  // `micInUse`).
  const micMuted = model.input?.volume.muted ?? false

  return {
    output: { variant: levelVariant(muted, level), level, muted },
    mic: {
      variant: micMuted ? "mic-off" : "mic-on",
      live: model.inputConsumers.length > 0,
    },
  }
}

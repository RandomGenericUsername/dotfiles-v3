import type { ReadAccessor, ReactiveRuntime } from "../../platform/ports/reactive"
import {
  projectBarIndicators,
  type BarIndicatorState,
} from "../../audio/presentation/bar-indicators.ts"
import type { AudioPanelViewModel } from "../../audio/presentation/audio-panel-view-model.ts"

/**
 * The audio domain's read model: the audio hexagon's view model → a reactive
 * bar-indicator reading. PURE — no `ags`, no `gi://*` (spine AD-2/AD-3).
 *
 * WHY THIS EXISTS. The audio hexagon already owns the domain, the ports, the
 * adapters and the composition root; what it did not have was an injectable
 * read model with the same shape as the other domains. The bar widget projected
 * `binding.model()` inline, so the "what the bar shows" decision lived in the
 * widget. This module is that projection, injectable and testable.
 *
 * The hexagon is NOT rewritten. This read model wraps the existing
 * `AudioPanelViewModel` and reuses `projectBarIndicators` verbatim, so the bar
 * glyph and the panel it opens still cannot disagree.
 */

/** The bar-indicator reading the audio surfaces consume. */
export type AudioReading = BarIndicatorState

/**
 * The read-model source: the hexagon's current view model plus a subscription
 * that fires when it changes. `audio/composition.ts`'s binding satisfies both.
 */
export interface AudioReadModelSource {
  current(): AudioPanelViewModel
  subscribe(listener: () => void): () => void
}

/**
 * Observe the audio hexagon as a reactive `AudioReading`.
 *
 * A source change republishes a fresh projection, so a `createComputed` that
 * calls the accessor re-runs whenever the session moves.
 */
export function createAudioReadModel(
  source: AudioReadModelSource,
  runtime: ReactiveRuntime,
): ReadAccessor<AudioReading> {
  const [reading, setReading] = runtime.createState<AudioReading>(projectBarIndicators(source.current()))
  source.subscribe(() => setReading(projectBarIndicators(source.current())))
  return reading
}

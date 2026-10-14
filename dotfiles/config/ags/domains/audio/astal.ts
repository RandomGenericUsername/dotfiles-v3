import { agsRuntime } from "../astal"
import type { ReadAccessor } from "../reactive"
import { audioPanelBinding } from "../../audio/composition"
import {
  createAudioReadModel as createReadModel,
  type AudioReadModelSource,
  type AudioReading,
} from "./read-model"

/**
 * The audio read model's binding to the existing hexagon (spine AD-2).
 *
 * The composition root (`audio/composition.ts`) is the app-level audio service:
 * it is assembled once and shared. This adapter closes over that binding and
 * exposes only the bar-indicator reading, so the hexagon is consumed — never
 * rewritten and never carried in `BarContext`.
 */
export function createAudioReadModel(): ReadAccessor<AudioReading> {
  const binding = audioPanelBinding()
  const source: AudioReadModelSource = {
    current: () => binding.model(),
    subscribe: (listener) => binding.model.subscribe(listener),
  }
  return createReadModel(source, agsRuntime)
}

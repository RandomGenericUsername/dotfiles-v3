import { Accessor, createEffect, createState, onCleanup } from "ags"
import { execAsync } from "ags/process"
import { interval } from "ags/time"
import { registry } from "../../lib/icon-registry"
import { LevelSlider } from "../primitives/LevelSlider"

/**
 * Display brightness.
 *
 * No Astal brightness binding is assumed: reads/writes go through the
 * provisioned `brightnessctl`. The value is optimistic on change and refreshed
 * by an interval that only runs while `visible` is true — the host owns
 * polling policy, so any embedder (panel, popover) can drive it.
 */

const [brightness, setBrightness] = createState(0)

let timer: { cancel: () => void } | null = null

function parseBrightness(out: string): number {
  const parts = out.trim().split(",")
  const percent = parts.find((part) => part.endsWith("%"))
  if (percent) {
    const value = parseInt(percent, 10)
    if (!Number.isNaN(value)) return value
  }
  const current = Number(parts[2])
  const max = Number(parts[4])
  if (current > 0 && max > 0) return Math.round((current / max) * 100)
  return 0
}

function refreshBrightness() {
  execAsync(["brightnessctl", "-m"])
    .then((out) => setBrightness(parseBrightness(out)))
    .catch(() => {
      /* no backlight / permission — leave the last value */
    })
}

function writeBrightness(value: number) {
  const next = Math.max(1, Math.min(100, Math.round(value)))
  if (next === Math.round(brightness())) return
  setBrightness(next)
  execAsync(["brightnessctl", "set", `${next}%`]).catch(() => {
    /* swallow; the next refresh reconciles */
  })
}

export function BrightnessSlider({ visible }: { visible: Accessor<boolean> }) {
  createEffect(() => {
    const shown = visible()
    if (timer) {
      timer.cancel()
      timer = null
    }
    if (!shown) return
    refreshBrightness()
    timer = interval(2000, refreshBrightness)
  })

  onCleanup(() => {
    if (timer) {
      timer.cancel()
      timer = null
    }
  })

  return (
    <LevelSlider
      leading={
        <image
          class="settings-slider-icon"
          pixel_size={16}
          $={(self) =>
            self.set_from_file(registry.resolve("brightness", "default") ?? "")
          }
        />
      }
      value={brightness}
      min={1}
      max={100}
      step={1}
      onChange={writeBrightness}
    />
  )
}

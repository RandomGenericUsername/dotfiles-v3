import Wp from "gi://AstalWp?version=0.1"
import { createBinding, createComputed, createEffect } from "ags"
import { registry } from "../../lib/icon-registry"
import { LevelSlider } from "../primitives/LevelSlider"

/**
 * Sound volume.
 *
 * Self-contained: reads/writes via the AstalWp (require 0.1) default speaker.
 * The slider writes `volume`; clicking the leading speaker glyph toggles
 * `mute`. The glyph is level-aware and resolved through the shared icon
 * registry; the initial assignment happens inside `createEffect` so the first
 * render is correct.
 *
 * Version pinning uses the ESM equivalent `gi://AstalWp?version=0.1`: gjs ESM
 * has no global `require_version`.
 */

const wp = Wp.get_default()
const rawVolume = wp
  ? createBinding(wp, "default-speaker", "volume")
  : createComputed(() => 0)
const rawMute = wp
  ? createBinding(wp, "default-speaker", "mute")
  : createComputed(() => true)

const volume = createComputed(() =>
  Math.max(0, Math.min(1, Number(rawVolume() ?? 0))),
)
const muted = createComputed(() => rawMute() === true)

function levelVariant(isMuted: boolean, value: number): string {
  if (isMuted || value <= 0) return "muted"
  const percent = Math.min(100, value * 100)
  if (percent <= 25) return "lowest"
  if (percent <= 50) return "low"
  if (percent <= 75) return "medium"
  return "max"
}

function toggleMute() {
  const speaker = wp?.default_speaker
  if (speaker) speaker.mute = !speaker.mute
}

function writeVolume(percent: number) {
  const value = Math.max(0, Math.min(100, Math.round(percent))) / 100
  const speaker = wp?.default_speaker
  if (speaker) speaker.volume = value
}

function SpeakerGlyph() {
  const variant = createComputed(() => levelVariant(muted(), volume()))
  return (
    <button
      class="settings-slider-glyph"
      onClicked={toggleMute}
      canFocus={false}
      tooltipText="Toggle mute"
    >
      <image
        class="settings-slider-icon"
        pixel_size={17}
        $={(self) => {
          createEffect(() => {
            self.set_from_file(registry.resolve("volume", "system-" + variant()) ?? "")
          })
        }}
      />
    </button>
  )
}

export function VolumeSlider() {
  return (
    <LevelSlider
      leading={<SpeakerGlyph />}
      value={createComputed(() => Math.round(volume() * 100))}
      min={0}
      max={100}
      step={1}
      onChange={writeVolume}
    />
  )
}

import { PanelCard } from "../primitives"
import { VolumeSlider } from "../../components/sliders/VolumeSlider"

/**
 * Sound section — panel chrome around the shared `VolumeSlider`.
 */

export function SoundCard() {
  return (
    <PanelCard title="Sound">
      <VolumeSlider />
    </PanelCard>
  )
}

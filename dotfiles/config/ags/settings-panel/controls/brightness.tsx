import { panelVisible } from "../state"
import { PanelCard } from "../primitives"
import { BrightnessSlider } from "../../components/sliders/BrightnessSlider"

/**
 * Display section — panel chrome around the shared `BrightnessSlider`. The
 * panel owns polling policy here, gating the slider's interval on visibility.
 */

export function DisplayCard() {
  return (
    <PanelCard title="Display">
      <BrightnessSlider visible={panelVisible} />
    </PanelCard>
  )
}

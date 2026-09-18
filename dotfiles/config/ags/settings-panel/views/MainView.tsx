import { WifiTile } from "../controls/wifi"
import { BluetoothTile } from "../controls/bluetooth"
import { HyprmodTile } from "../controls/hyprmod"
import { DisplayCard } from "../controls/brightness"
import { SoundCard } from "../controls/volume"

/**
 * Section extensibility.
 *
 * The main view is a stable list: to add a capability card, append a descriptor
 * to SECTION_ORDER and add its control component. No existing section needs to
 * change and the panel layout (a single card stack) is unchanged.
 */
interface SectionDescriptor {
  id: string
  render: () => unknown
}

export const SECTION_ORDER: SectionDescriptor[] = [
  { id: "wifi", render: () => <WifiTile /> },
  { id: "bluetooth", render: () => <BluetoothTile /> },
  { id: "hyprmod", render: () => <HyprmodTile /> },
  { id: "display", render: () => <DisplayCard /> },
  { id: "sound", render: () => <SoundCard /> },
]

export function MainView() {
  return (
    <box orientation={1} spacing={8}>
      {SECTION_ORDER.map((section) => section.render()) as never}
    </box>
  )
}

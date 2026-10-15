import { iconByStateKey } from "../../kit/icon"
import { overlays } from "../../kit/overlay"
import type { DescriptorSpec } from "../../kit/widget"
import { createBluetoothReadModel } from "../../domains/bluetooth/astal"
import type { BluetoothReading } from "../../domains/bluetooth/read-model"

/**
 * The status-bar Bluetooth indicator (design §3, the `bluetooth` bar group), as
 * a `DescriptorSpec` (spine AD-8; doc 101 §5): one glyph + a tooltip.
 *
 * The read model is the `domains/bluetooth` adapter (AD-2/AD-3), the glyph is a
 * state-key ref resolved through the one chain (AD-7), and the shared shell owns
 * the button, the tooltip, the anchor record and the click. There is deliberately
 * NO right-click gesture and NO scroll gesture: Bluetooth is discrete, so there
 * is no continuous value to nudge and no secondary action to invent.
 *
 * Two states only, per the owner's artwork: `off` is distinguished from `on` by
 * the slash in the glyph's SHAPE, never by opacity or tint.
 */

function bluetoothStateKey(powered: boolean): string {
  // NOTE the keys: `bluetooth-on` / `bluetooth-off`, NOT bare `on` / `off`.
  // YAML 1.1 resolves a bare `on:`/`off:` key to a boolean, so the manifest
  // comes out of the parser with `True`/`False` keys and every lookup would
  // miss silently. Do not "simplify" these to match the variant names.
  return powered ? "bluetooth-on" : "bluetooth-off"
}

export function createBluetoothWidget(): DescriptorSpec<BluetoothReading> {
  const reading = createBluetoothReadModel()

  return {
    id: "bluetooth",
    read: () => reading(),
    tooltip: () => "Bluetooth",
    icon: iconByStateKey("bluetooth", (s: BluetoothReading) =>
      bluetoothStateKey(s.powered),
    ),
    // Mutual exclusion is the coordinator's job: it closes the settings panel
    // and every other surface before opening Bluetooth, so one connectivity
    // surface is up at a time.
    primary: (_s, anchorX) => overlays.toggle("bluetooth", anchorX),
  }
}

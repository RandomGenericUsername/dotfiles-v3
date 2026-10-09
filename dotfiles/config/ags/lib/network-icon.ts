/**
 * Network → `network` icon-group state key, and the bar label. PURE.
 *
 * Extracted from `bar/widgets/network.tsx`, where the mapping lived inline in
 * the view. Kept pure so it is testable without a desktop (`make ags-test`) and
 * shared by the descriptor and any future surface — the same argument as
 * `battery-icon.ts`. The Astal objects are typed structurally, so this module
 * imports no GJS.
 */

/** NMConnectivityState: NONE=0, PORTAL=1, LIMITED=2, FULL=3. */
const CONNECTIVITY_PORTAL = 1
const CONNECTIVITY_LIMITED = 2

/** NMDeviceState: ACTIVATED=100; anything below means not associated/unplugged. */
const DEVICE_STATE_ACTIVATED = 100

/** The Astal fields this mapping reads, as a plain shape (no GJS import). */
export interface WifiReading {
  enabled?: boolean
  state?: number
  strength: number
}
export interface WiredReading {
  state?: number
}
export interface NetworkReading {
  wifi: WifiReading | null
  wired: WiredReading | null
  connectivity: number
}

// NONE (0) means the connectivity check is disabled, not "no internet", so only
// LIMITED/PORTAL count as no-internet.
function hasNoInternet(connectivity: number): boolean {
  return connectivity === CONNECTIVITY_LIMITED || connectivity === CONNECTIVITY_PORTAL
}

function wifiStrengthKey(strength: number): string {
  if (strength >= 80) return "wifi-full"
  if (strength >= 50) return "wifi-high"
  if (strength >= 25) return "wifi-medium"
  return "wifi-low"
}

/** The `bar_mappings.states` key for a network reading. */
export function networkIconState(reading: NetworkReading): string {
  const { wifi, wired, connectivity } = reading
  if (wifi) {
    const radioOn = wifi.enabled !== false
    const activated = (wifi.state ?? 0) === DEVICE_STATE_ACTIVATED
    if (!radioOn || !activated) return "wifi-not-connected"
    if (hasNoInternet(connectivity)) return "wifi-no-internet"
    return wifiStrengthKey(wifi.strength)
  }
  if (wired) {
    if ((wired.state ?? 0) === DEVICE_STATE_ACTIVATED) {
      return hasNoInternet(connectivity) ? "ethernet-no-internet" : "ethernet-connected"
    }
    return "ethernet-not-connected"
  }
  return "wifi-not-connected"
}

/** The bar label: empty on Wi-Fi (the glyph carries it), "Ethernet" on wired. */
export function networkLabel(reading: NetworkReading): string {
  if (reading.wifi) return ""
  if (reading.wired) return "Ethernet"
  return "No network"
}

/**
 * Shared Wi-Fi signal-strength → icon-key thresholds.
 *
 * Single home for the ≥75/≥50/≥25 step table so the settings-panel tile
 * (`settings-panel/controls/wifi.tsx`) and popup rows stay in step.
 */
export function wifiSignalIconKey(strength: number): string {
  if (strength >= 75) return "wifi-signal-full"
  if (strength >= 50) return "wifi-signal-good"
  if (strength >= 25) return "wifi-signal-medium"
  return "wifi-signal-low"
}

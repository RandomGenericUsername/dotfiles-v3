/**
 * The bar manifest (spine AD-14; ags-bar-validation).
 *
 * The bar's capabilities, params, and icon groups as PURE DATA: no GJS, no
 * GTK, no AGS, no JSX. Both the bar (lenient, at startup) and the
 * `ags-bar-validate` install gate (strict, in provisioning) consume these
 * same declarations through `validateLayout` + `validateIcons` — one rule
 * set, two enforcements (AD-15).
 *
 * This module has ZERO imports on purpose: importing it must succeed on a
 * stock runner with no desktop runtime (`node --test` import). Keep it that
 * way — a value import of even one `gi://` or `ags` module would silently
 * move this file out of the pure set the tests pin.
 */

/**
 * One bar capability: a layout-entry id the registry can render (AD-8).
 *
 * `params` is the CLOSED set of layout-entry param names the capability
 * accepts. A `BarEntry` naming any other param is `unknown-param`. No widget
 * takes params today, so every entry is empty — the empty list IS the
 * declaration, not an omission, and the validator rejects any param outright.
 *
 * `multi` allows the id to appear more than once in a layout. Every
 * capability is single-instance today (the repo default names each widget
 * exactly once), so a repeated id is `duplicate-widget`.
 *
 * `iconGroup` is the `icons.json` group the widget resolves glyphs from, if
 * any. Glyph-less widgets (workspaces, clock) carry none.
 */
export interface CapabilityDecl {
  readonly id: string
  readonly params: readonly string[]
  readonly multi: boolean
  readonly iconGroup?: string
}

/**
 * An `icons.json` group the bar draws glyphs from.
 *
 * `states` is the CLOSED set of `bar_mappings.states` keys the bar depends
 * on for this group. A group with a non-empty list declares states, so every
 * listed key must map to a variant that exists — otherwise `missing-icon-key`
 * (AD-15). Groups the bar addresses by variant directly (launchers, the tray
 * override, the recording controls) carry an empty list and are exempt.
 */
export interface IconGroupDecl {
  readonly name: string
  readonly states: readonly string[]
}

/** The whole declaration surface the validators run over. */
export interface BarManifest {
  readonly capabilities: readonly CapabilityDecl[]
  readonly iconGroups: readonly IconGroupDecl[]
}

/**
 * The bar's declared capabilities, in registry order (`bar/registry.ts`).
 * The ids here and the registry keys must agree — the validator enforces
 * layout ids against THIS list, so a widget added to the registry without a
 * declaration here fails install rather than rendering.
 */
const CAPABILITIES: readonly CapabilityDecl[] = [
  { id: "workspaces", params: [], multi: false },
  { id: "clock", params: [], multi: false },
  { id: "tray", params: [], multi: false, iconGroup: "tray" },
  { id: "recording", params: [], multi: false, iconGroup: "capture-tool" },
  { id: "audio-output", params: [], multi: false, iconGroup: "volume" },
  { id: "audio-mic", params: [], multi: false, iconGroup: "microphone" },
  { id: "battery", params: [], multi: false, iconGroup: "battery" },
  { id: "bluetooth", params: [], multi: false, iconGroup: "bluetooth" },
  { id: "network", params: [], multi: false, iconGroup: "network" },
  { id: "btop", params: [], multi: false, iconGroup: "btop" },
  { id: "thunderbird", params: [], multi: false, iconGroup: "thunderbird" },
  { id: "settings", params: [], multi: false, iconGroup: "settings" },
  { id: "power-menu", params: [], multi: false, iconGroup: "power-menu" },
]

/**
 * The `icons.json` groups the bar consumes. `states` mirrors the code-emitted
 * keys per group (the `bar_mappings.states` vocabulary): the validator pins
 * each against the artifact's table and its variants.
 *
 * `power-mode` is deliberately ABSENT: it declares states in the artifact but
 * no bar widget draws from it (panel-only), so the bar validator has no scope
 * over it.
 */
const ICON_GROUPS: readonly IconGroupDecl[] = [
  {
    name: "battery",
    states: [
      "charging-0",
      "charging-100",
      "charging-25",
      "charging-50",
      "charging-75",
      "discharging-0",
      "discharging-100",
      "discharging-25",
      "discharging-50",
      "discharging-75",
      "plugged",
    ],
  },
  { name: "bluetooth", states: ["bluetooth-off", "bluetooth-on"] },
  { name: "btop", states: [] },
  { name: "capture-tool", states: [] },
  { name: "microphone", states: ["microphone-mic-off", "microphone-mic-on"] },
  {
    name: "network",
    states: [
      "ethernet-connected",
      "ethernet-no-internet",
      "ethernet-not-connected",
      "wifi-full",
      "wifi-high",
      "wifi-low",
      "wifi-medium",
      "wifi-no-internet",
      "wifi-not-connected",
    ],
  },
  { name: "power-menu", states: ["default"] },
  { name: "settings", states: ["default"] },
  { name: "thunderbird", states: [] },
  { name: "tray", states: [] },
  {
    name: "volume",
    states: [
      "volume-low",
      "volume-lowest",
      "volume-max",
      "volume-medium",
      "volume-muted",
    ],
  },
]

export const BAR_MANIFEST: BarManifest = {
  capabilities: CAPABILITIES,
  iconGroups: ICON_GROUPS,
}

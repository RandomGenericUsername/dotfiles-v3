import Gtk from "gi://Gtk?version=4.0"
import Pango from "gi://Pango?version=1.0"
import Battery from "gi://AstalBattery"
import { createBinding, createComputed, createEffect, For } from "ags"
import { execAsync } from "ags/process"
import { iconByStateKey, resolveIcon } from "../../kit/icon"
import type { IconSource } from "../../kit/icon-source"
import { applyIconSource } from "../../kit/widget"
import {
  POWER_MODES,
  UNLISTED_MODE,
  activeProfileOf,
  formatBatteryTime,
  formatPercentage,
  isDeclaredTier,
  modeTooltip,
  powerModeStateKey,
  profilesForMode,
  railMeta,
  resolveMode,
  variantTooltip,
  variantToSelect,
  type IndexedProfile,
  type PowerMode,
} from "./presentation"
import { batteryStateKey } from "./battery-icon"
import {
  activeProfileIndex,
  powerProfiles,
  powerReady,
  setPowerProfile,
} from "../../services/power-service"

/**
 * The battery panel body.
 *
 * Every DECISION about what to write comes from `presentation.ts` and is called
 * here; everything else is an EFFECT — the bindings, the icon lookups, the
 * click handlers. No formatting, no rounding and no "which mode is active"
 * logic is written in this file, because anything written here is untestable
 * without a live desktop.
 *
 * THE SELECTOR IS TWO-LEVEL. A MODE owns a glyph; a VARIANT is a selectable
 * profile on a tier that mode declares. The rail draws one cell per declared
 * mode (three), the selected mode's variants render as a second-level control
 * ONLY when there is more than one, and the selected profile's name + mode +
 * tier are stated once beneath it.
 */

const device = Battery.get_default()
const percentage = createBinding(device, "percentage")
const charging = createBinding(device, "charging")
const timeToFull = createBinding(device, "timeToFull")
const timeToEmpty = createBinding(device, "timeToEmpty")

/** Fallback word when the daemon reports no capacity at all. */
const NO_PERCENTAGE = "—"

/**
 * The panel's two glyphs, as state-key refs (spine AD-7). Code emits a state
 * key — `charging-75` for the header, `power-mode-powersave` for a mode cell —
 * the manifest's `bar_mappings.states` maps it to a variant, and the registry
 * maps the variant to art. A key with no table entry blanks rather than
 * throwing: a deferred manifest leaves the mode cell's label without a glyph
 * (the `unlisted` tier's `power-mode-unknown` key is deliberately absent).
 */
const batteryIcon = iconByStateKey(
  "battery",
  (s: { percentage: number; charging: boolean }) =>
    batteryStateKey(s.percentage, s.charging),
)
const modeIcon = iconByStateKey("power-mode", (s: PowerMode) =>
  powerModeStateKey(s),
)

/**
 * The `power-mode` glyph for a mode. The glyph hangs on the MODE, not the
 * profile: `powerModeStateKey` keys off `mode.glyph`, so every tier a mode
 * declares shares the one glyph. Resolved through the uniform chain (AD-7).
 */
function modeIconPath(mode: PowerMode): IconSource | null {
  return resolveIcon(modeIcon, mode)
}

/**
 * The seconds the time estimate applies to, for the direction the clock runs.
 *
 * Picking the BINDING here rather than in the render keeps `formatBatteryTime`
 * on its pure `(seconds, charging)` contract: it still decides how to render,
 * but which number it is stays an effect.
 */
const relevantSeconds = createComputed(() =>
  charging() ? timeToFull() : timeToEmpty(),
)

const timePresentation = createComputed(() =>
  formatBatteryTime(relevantSeconds(), charging()),
)

/**
 * The header percentage, or the fallback word.
 *
 * `formatPercentage` already rounds and clamps and returns `null` for a missing
 * reading; this only chooses the word for that `null`, which is a display
 * decision rather than a formatting one.
 */
const headerPercentage = createComputed(
  () => formatPercentage(percentage() * 100) ?? NO_PERCENTAGE,
)

/**
 * The declared modes, as an accessor for `For`.
 *
 * `POWER_MODES` is the declaration itself (leaf / scales / engine); the rail is
 * daemon-independent, so these three cells render before the first reply and
 * keep their positions as profiles come and go.
 */
const declaredModes = createComputed(() => POWER_MODES)

/** The active profile, resolved by the daemon's `active_profile` INDEX. */
const selectedProfile = createComputed(
  () => activeProfileOf(powerProfiles(), activeProfileIndex())?.profile ?? null,
)

/**
 * The mode the active profile resolves into, or `null` before the daemon
 * answers. Undeclared tiers fold into the neutral `Unlisted` pseudo-mode, so a
 * new tier shows up visibly instead of vanishing.
 */
const selectedModeName = createComputed(() => {
  const profile = selectedProfile()
  return profile === null ? null : resolveMode(profile.tier).mode
})

/** The active mode's variants, in daemon order, each with its daemon index. */
const activeVariants = createComputed<IndexedProfile[]>(() => {
  const profile = selectedProfile()
  if (profile === null) return []
  return profilesForMode(resolveMode(profile.tier), powerProfiles())
})

/** The control renders only when the selected mode actually offers a choice. */
const showVariantControl = createComputed(() => activeVariants().length > 1)

/** The Unlisted cell exists ONLY when an undeclared tier is present. */
const hasUnlistedTier = createComputed(() =>
  powerProfiles().some((profile) => !isDeclaredTier(profile.tier)),
)

const railMetaName = createComputed(() => railMeta(selectedProfile()).name)
const railMetaLine = createComputed(() => railMeta(selectedProfile()).line)

/**
 * The deep-link row's launcher.
 *
 * The panel can set the profiles the daemon offers, but the daemon's own
 * GTK frontend exposes settings this panel does not model (per-policy CPU
 * scaling, thresholds). Rather than duplicate a settings surface, the last row
 * hands off to the real one — so the panel is a fast path, not a dead end.
 */
function openPowerOptionsGtk(): void {
  execAsync(["power-options-gtk"]).catch((e) => {
    console.error("battery panel: power-options-gtk launch failed:", e)
  })
}

/** One mode cell: the mode's glyph over its label. The whole cell is the target. */
function ModeCell(props: { mode: PowerMode }) {
  const { mode } = props
  const selected = createComputed(() => selectedModeName() === mode.mode)
  return (
    <button
      class={createComputed(() =>
        selected() ? "battery-mode-cell sel" : "battery-mode-cell",
      )}
      sensitive={powerReady}
      tooltipText={createComputed(() => modeTooltip(mode, powerProfiles()))}
      onClicked={() => {
        const name = variantToSelect(mode, powerProfiles(), activeProfileIndex())
        // A mode with no variant has nothing to select; the click is a no-op
        // rather than a write of an empty name.
        if (name !== null) setPowerProfile(name)
      }}
    >
      <box
        orientation={1}
        spacing={3}
        halign={Gtk.Align.CENTER}
        valign={Gtk.Align.CENTER}
      >
        <image
          class="battery-profile-icon"
          pixel_size={24}
          $={(self) => {
            createEffect(() => {
              // A deferred manifest may leave `unknown` unresolved; the cell
              // still renders its label, and the meta line spells out
              // "unmapped tier" rather than implying a mapping.
              applyIconSource(self, modeIconPath(mode))
            })
          }}
        />
        <label class="battery-mode-label" xalign={0.5} label={mode.mode} />
      </box>
    </button>
  )
}

/** The mode rail: the declared modes, plus the Unlisted cell only when needed. */
function ModeRail() {
  return (
    <box
      class="battery-mode-rail"
      orientation={1}
      spacing={8}
      halign={Gtk.Align.CENTER}
    >
      <box orientation={0} spacing={8} halign={Gtk.Align.CENTER}>
        <For each={declaredModes} id={(mode: PowerMode) => mode.mode}>
          {(mode: PowerMode) => <ModeCell mode={mode} />}
        </For>
      </box>
      {/* A fourth cell wraps to its own centred row, so the rail never grows
          the 312px surface horizontally. */}
      <box
        orientation={0}
        halign={Gtk.Align.CENTER}
        visible={hasUnlistedTier}
      >
        <ModeCell mode={UNLISTED_MODE} />
      </box>
    </box>
  )
}

/** One variant pill. The active one is marked by DAEMON INDEX, not by name. */
function VariantOption(props: { entry: IndexedProfile }) {
  const { entry } = props
  const selected = createComputed(() => entry.index === activeProfileIndex())
  return (
    <button
      class={createComputed(() =>
        selected() ? "battery-variant-opt sel" : "battery-variant-opt",
      )}
      sensitive={powerReady}
      tooltipText={variantTooltip(entry.profile)}
      onClicked={() => setPowerProfile(entry.profile.name)}
    >
      <label
        xalign={0.5}
        maxWidthChars={22}
        ellipsize={Pango.EllipsizeMode.END}
        label={entry.profile.name}
      />
    </button>
  )
}

/** The second level: rendered ONLY when the selected mode offers > 1 variant. */
function VariantControl() {
  return (
    <box orientation={1} visible={showVariantControl}>
      <label class="settings-section-label" xalign={0} label="VARIANT" />
      <box class="battery-variant" orientation={0} spacing={6}>
        <For each={activeVariants} id={(entry: IndexedProfile) => entry.index}>
          {(entry: IndexedProfile) => <VariantOption entry={entry} />}
        </For>
      </box>
    </box>
  )
}

export function BatteryContent(_props: { visible: unknown }) {
  return (
    <box orientation={1}>
      {/* Nav header — glyph, title, reading. */}
      <box class="settings-nav-header" spacing={9}>
        <image
          class="battery-header-icon"
          pixel_size={18}
          $={(self) => {
            createEffect(() => {
              applyIconSource(
                self,
                resolveIcon(batteryIcon, {
                  percentage: percentage(),
                  charging: charging(),
                }),
              )
            })
          }}
        />
        <label class="settings-nav-title" xalign={0} hexpand label="Battery" />
        <label
          class="battery-header-pct"
          xalign={1}
          label={headerPercentage}
        />
      </box>

      {/* Hero — the one number the panel exists to answer. Both labels declare
          `xalign={0}`: GTK's default is 0.5, which would centre them against a
          panel where every other label is left-aligned. */}
      <box class="battery-hero" orientation={1} spacing={0}>
        <label
          class="battery-hero-primary"
          xalign={0}
          label={createComputed(() => timePresentation().primary)}
        />
        <label
          class="battery-hero-sub"
          xalign={0}
          label={createComputed(() => timePresentation().sub)}
        />
      </box>

      <box class="settings-divider" />
      <label class="settings-section-label" xalign={0} label="POWER MODE" />

      {/* The mode rail, then the selected mode's variants when it has more
          than one. The selected profile is named once, under the selector. */}
      <ModeRail />
      <VariantControl />
      <box
        class="battery-rail-meta"
        orientation={1}
        spacing={1}
      >
        <label
          class="settings-net-name"
          xalign={0}
          maxWidthChars={26}
          ellipsize={Pango.EllipsizeMode.END}
          label={railMetaName}
        />
        <label
          class="settings-net-sub"
          xalign={0}
          maxWidthChars={30}
          ellipsize={Pango.EllipsizeMode.END}
          label={railMetaLine}
        />
      </box>

      {/* Deep link to the daemon's own frontend. The whole row is the hit
          target, not just the trailing chevron — a footer row whose only
          clickable pixel is a 10px glyph is a miss most of the time. A
          `button` gives the row focus-on-click and hover styling for free;
          the chevron is decorative and says so with its own class. */}
      <button class="battery-deeplink" onClicked={openPowerOptionsGtk}>
        {/* No `xalign` on the box: GtkBox has no such property (GTK4 dropped it;
            the equivalent is `halign`/`valign`). The labels inside carry
            `xalign={0}` instead, which is what actually left-aligns the text. */}
        <box orientation={1} spacing={1} hexpand valign={Gtk.Align.CENTER}>
          <label class="settings-wifi-settings-label" xalign={0} label="Power Options" />
          <label class="settings-wifi-settings-note" xalign={0} label="opens power-options-gtk" />
        </box>
        <label class="settings-wifi-settings-arrow" xalign={1} label="›" />
      </button>
    </box>
  )
}

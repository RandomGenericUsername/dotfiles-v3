import Gtk from "gi://Gtk?version=4.0"
import Battery from "gi://AstalBattery"
import { createBinding, createComputed, createEffect, For } from "ags"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"
import {
  POWER_PROFILE_ORDER,
  formatBatteryTime,
  formatPercentage,
  isActiveProfile,
  profileIconVariant,
  type PowerProfileId,
} from "./presentation"
import { batteryStateKey } from "./battery-icon"
import {
  activeProfile,
  powerReady,
  setPowerProfile,
} from "../../services/power-service"

/**
 * The battery panel body.
 *
 * Every DECISION about what to write comes from `presentation.ts` and is called
 * here; everything else is an EFFECT — the bindings, the icon lookups, the
 * click handlers. No formatting, no rounding and no "which row is active" logic
 * is written in this file, because anything written here is untestable without
 * a live desktop.
 */

const device = Battery.get_default()
const percentage = createBinding(device, "percentage")
const charging = createBinding(device, "charging")
const timeToFull = createBinding(device, "time-to-full")
const timeToEmpty = createBinding(device, "time-to-empty")

/** Fallback word when the daemon reports no capacity at all. */
const NO_PERCENTAGE = "—"

/**
 * The battery glyph for the header, at the CURRENT state.
 *
 * Resolved rather than hard-coded so the header tracks charging and level the
 * way the status-bar icon does, instead of being a static decoration that
 * contradicts it.
 */
function batteryIconPath(): string | null {
  const mappings = registry.getBarMappings("battery")
  if (!mappings) return null
  const variant = mappings.states[batteryStateKey(percentage(), charging())]
  if (!variant) return null
  return registry.resolve("battery", variant)
}

/** The `power-mode` glyph for a profile row. Three variants, five profiles. */
function profileIconPath(id: PowerProfileId): string | null {
  return registry.resolve("power-mode", profileIconVariant(id))
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
 * The profile rows, as an accessor for `For`.
 *
 * `POWER_PROFILE_ORDER` is a frozen readonly tuple. `For` takes an
 * `Accessor<Iterable<T>>` rather than a bare array, so the constant is spread
 * into a plain array here ONCE at module scope and never re-derived — the
 * ORDER (cheapest first, hottest last) is a product decision recorded in
 * `presentation.ts`, and this does not touch it.
 */
const profileRows = createComputed(
  () => [...POWER_PROFILE_ORDER] as PowerProfileId[],
)

/**
 * The deep-link row's launcher.
 *
 * The panel can set the five profiles the daemon offers, but the daemon's own
 * GTK frontend exposes settings this panel does not model (per-policy CPU
 * scaling, thresholds). Rather than duplicate a settings surface, the last row
 * hands off to the real one — so the panel is a fast path, not a dead end.
 */
function openPowerOptionsGtk(): void {
  execAsync(["power-options-gtk"]).catch((e) => {
    console.error("battery panel: power-options-gtk launch failed:", e)
  })
}

/**
 * A profile's label, with the `++` TIER rendered typographically.
 *
 * WHY TEXT AND NOT A BADGE. `presentation.ts` deliberately maps both `++` tiers
 * onto the base profile's glyph, because they are the same mode pushed further
 * rather than different modes. Drawing the tier graphically — a corner badge,
 * a distinct icon — would contradict that: it would spend visual weight on a
 * distinction the icon vocabulary has already declined to make, and a badge is
 * the shape a reader scans for FIRST. As type, `++` reads as a qualifier of
 * the word before it, which is exactly what it is.
 *
 * The suffix is tinted `@color_13` — the same accent the `.active` treatment
 * uses — so "pushed further" is visibly *more* rather than merely different.
 * Split into two labels rather than one Pango-markup string because the split
 * is then styleable by CSS (`.battery-profile-tier`) instead of hard-coding a
 * colour into a template, which `style.css`'s tokens-only rule forbids.
 *
 * For the four base profiles there is no suffix, so no second label is created.
 */
function ProfileLabel(props: { id: PowerProfileId }) {
  const { id } = props
  const tier = /\+\+$/.exec(id)?.[0] ?? ""
  const base = tier === "" ? id : id.slice(0, -tier.length)
  return (
    <box class="battery-profile-label" spacing={0}>
      <label class="settings-net-name" xalign={0} label={base} />
      {tier === "" ? null : (
        <label class="battery-profile-tier" xalign={0} label={tier} />
      )}
    </box>
  )
}

/** One power-profile row. */
function PowerProfileRow(props: { id: PowerProfileId }) {
  const { id } = props
  const active = createComputed(() =>
    isActiveProfile(activeProfile() ?? "", id),
  )
  return (
    <button
      class={createComputed(() =>
        active() ? "settings-net battery-profile sel" : "settings-net battery-profile"
      )}
      sensitive={powerReady}
      onClicked={() => setPowerProfile(id)}
    >
      <image
        class="battery-profile-icon"
        pixel_size={18}
        $={(self) => {
          createEffect(() => {
            self.set_from_file(profileIconPath(id) ?? "")
          })
        }}
      />
      <ProfileLabel id={id} />
    </button>
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
              self.set_from_file(batteryIconPath() ?? "")
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

      {/* Hero — the one number the panel exists to answer. */}
      <box class="battery-hero" orientation={1} spacing={0}>
        <label class="battery-hero-primary" label={createComputed(() => timePresentation().primary)} />
        <label class="battery-hero-sub" label={createComputed(() => timePresentation().sub)} />
      </box>

      <box class="settings-divider" />
      <label class="settings-section-label" xalign={0} label="POWER MODE" />

      {/* Five rows, cheapest first, hottest last (presentation.ts §4.1). */}
      <box class="battery-profile-list" orientation={1} spacing={2}>
        <For each={profileRows}>
          {(id: PowerProfileId) => <PowerProfileRow id={id} />}
        </For>
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

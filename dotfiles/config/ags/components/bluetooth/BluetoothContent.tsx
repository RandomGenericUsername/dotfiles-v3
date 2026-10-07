import { Accessor, createComputed, createEffect, createState, For } from "ags"
import { Gtk } from "ags/gtk4"
import Pango from "gi://Pango?version=1.0"
import { execAsync } from "ags/process"
import { registry } from "../../lib/icon-registry"
import {
  bluetoothAdapterAddress,
  bluetoothBusy,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothPowered,
  connectDevice,
  disconnectDevice,
  pairDevice,
  postBluetoothNotification,
  refreshBluetoothDevices,
  routeAudioToDevice,
  startBluetoothDiscovery,
  stopBluetoothDiscovery,
  unpairDevice,
  type BluetoothDevice,
} from "../../services/bluetooth-service"

/**
 * Bluetooth capability body (design §4, mock `mockups/panel.html`).
 *
 * State is owned by BlueZ D-Bus and exposed through the service's accessors;
 * this component only reads them and forwards user intent (`pairDevice`,
 * `connectDevice`, `disconnectDevice`, `unpairDevice`). There is no subprocess,
 * no bus call, no agent plumbing and no timer here — the ONE subprocess is the
 * footer row's `execAsync(["blueman-manager"])`, the same single escape hatch
 * `WifiContent`'s `nm-connection-editor` row uses.
 */

export {
  bluetoothBusy,
  bluetoothDevices,
  bluetoothDiscovering,
  bluetoothPowered,
}
export type { BluetoothDevice }

/**
 * The one open unpair-confirm, for the whole module.
 *
 * A single slot, not one flag per row: "exactly one confirm open at a time" is
 * then structural rather than enforced by each row politely closing its
 * neighbours. Both mounted surfaces (bar popup and settings subview) share this
 * state because they share this module, so a confirm opened in one is closed by
 * opening one in the other.
 */
const [confirmingAddress, setConfirmingAddress] = createState<string | null>(null)

/**
 * Close any open unpair confirm.
 *
 * Exported for the dismissal paths that live outside this file — the popup's
 * catcher (`BluetoothPopup.tsx`) and `app.tsx`'s `popup-close` handler — which
 * should dismiss a confirm BEFORE the surface closes rather than after.
 */
export function dismissUnpairConfirm(): void {
  setConfirmingAddress(null)
}



/**
 * Battery level (BlueZ integer 0-100) → the panel's guard-exempt glyph
 * variant. Bucket boundaries mirror the bar's `getBatteryStateKey`
 * (`<25 / <50 / <75 / <100`, which takes a 0-1 fraction): one threshold
 * set serves both surfaces. The panel must never resolve bare `battery-*`
 * — those are guard-subject (status bar only).
 */
function batteryVariant(level: number): string {
  if (level < 25) return "system-battery-0"
  if (level < 50) return "system-battery-25"
  if (level < 75) return "system-battery-50"
  if (level < 100) return "system-battery-75"
  return "system-battery-100"
}

/**
 * RSSI (dBm, negative = present) → `settings-panel` signal level.
 * Fixed contract thresholds (design D5): ≥−60 full, ≥−70 good, ≥−80 medium,
 * else low. `high` was renamed `full` so the ladder reads the same as
 * `wifi-signal-*` (`lib/wifi-signal.ts`); the boundaries did not move.
 */
function signalVariant(rssi: number): string {
  if (rssi >= -60) return "full"
  if (rssi >= -70) return "good"
  if (rssi >= -80) return "medium"
  return "low"
}

/**
 * Leading circle-badged signal glyph, at the Wi-Fi row's size: `.settings-net-signal`
 * is `min-width/min-height: 30px` and `WifiContent` draws `<image pixel_size={30}>`.
 *
 * NOTHING is rendered when `rssi >= 0` — BlueZ reports 0 for "not seen"
 * (asleep / out of range), so there is no level to draw. The variant is not
 * resolved either: `signalVariant(0)` would answer "full", which is a lie about
 * a device nobody has heard from. No glyph means no tooltip, which is precisely
 * why the row's WORD subtitle is load-bearing — see `subtitle` below.
 */
function BluetoothSignalIcon({ rssi }: { rssi: Accessor<number> }) {
  const seen = createComputed(() => rssi() < 0)
  const src = createComputed(() =>
    seen()
      ? registry.resolve("settings-panel", "bluetooth-signal-" + signalVariant(rssi()))
      : null,
  )
  return (
    <image
      class="settings-net-signal"
      pixel_size={30}
      valign={Gtk.Align.CENTER}
      visible={seen}
      // The exact reading lives HERE and only here. `""` when unseen, so an
      // out-of-range row carries no tooltip at all.
      tooltipText={createComputed(() =>
        seen() ? `Signal: −${Math.abs(rssi())} dBm` : "",
      )}
      $={(self) => {
        createEffect(() => {
          self.set_from_file(src() ?? "")
        })
      }}
    />
  )
}

export function BluetoothRow({ device: item }: { device: BluetoothDevice }) {
  // The service re-emits the list and a row widget may be reused for the same
  // address; read the live entry so status/battery stay correct.
  const live = createComputed(
    () =>
      bluetoothDevices().find((device) => device.address === item.address) ??
      item,
  )

  const name = createComputed(
    () => live().alias || live().name || "Unknown device",
  )
  const connected = createComputed(() => live().connected)
  const paired = createComputed(() => live().paired)
  const rssi = createComputed(() => live().rssi)
  const battery = createComputed(() => live().battery)

  const busy = createComputed(() => {
    const pending = bluetoothBusy()
    return pending.address === item.address && pending.action !== null
  })
  const anyBusy = createComputed(() => bluetoothBusy().address !== null)

  // BlueZ reports RSSI 0 when the device has not been seen (asleep / out of
  // range); a negative value means it is currently present. A paired device
  // that is not present is shown dimmed with Connect disabled.
  const inRange = createComputed(() => connected() || rssi() < 0)
  const absent = createComputed(() => paired() && !connected() && !inRange())

  const confirming = createComputed(() => confirmingAddress() === item.address)

  // `.sel` on the connected row is the mock's contract and matches `WifiRow`,
  // which also fills its connected row. `.confirming` wins over `.sel` because
  // an open confirm is the row's whole story right now.
  const rowClass = createComputed(() => {
    if (confirming()) return "settings-net confirming"
    if (connected()) return "settings-net sel"
    return absent() ? "settings-net out-of-range" : "settings-net"
  })

  /**
   * The row's WORD layer — `Not in range` / `Paired` / `Ready to pair`,
   * mirroring `WifiRow`'s `Saved` / `Secured` / `Open network`. No strength
   * figure ever appears here; the number moved to the glyph tooltip.
   *
   * LOAD-BEARING, not decorative: an `rssi >= 0` row has no glyph and therefore
   * no tooltip, so this word is the ONLY channel carrying the state, alongside
   * `.settings-net.out-of-range`'s opacity and the unavailable primary action.
   * Do not "simplify" this away when the subtitle looks redundant on rows that
   * do have a glyph.
   */
  const subtitle = createComputed(() => {
    if (confirming()) return "Remove from paired devices"
    if (!paired()) return "Ready to pair"
    if (!inRange()) return "Not in range"
    return "Paired"
  })

  const actionLabel = createComputed(() =>
    connected() ? "Disconnect" : paired() ? "Connect" : "Pair",
  )
  // `<Action>ing…` — Pairing… / Connecting… / Disconnecting… / Unpairing…
  const busyLabel = createComputed(() => {
    const pending = bluetoothBusy()
    if (pending.address !== item.address || pending.action === null) return ""
    const action = pending.action
    return `${action.charAt(0).toUpperCase()}${action.slice(1)}ing…`
  })
  // BlueZ is single-flight (`runAction` returns early while any address is
  // busy), so every other row's primary action goes unavailable too.
  const primaryAvailable = createComputed(() => inRange() && !anyBusy())

  function act() {
    // Clicking a confirming row's background is click-OUTSIDE for that row: it
    // dismisses rather than, say, disconnecting a device mid-unpair.
    if (confirming()) {
      setConfirmingAddress(null)
      return
    }
    // `!inRange()` IS a refusal. OWNER DECISION 2026-10-05: out of range means
    // you cannot click Connect, full stop.
    //
    // History, because this guard and the reachability rule are load-bearing on
    // each other and both have been changed twice:
    // - The guard was once lifted so a press would surface BlueZ's real reason
    //   instead of silence. Rejected: unreachable hardware looked actionable.
    // - The reachability rule once had a 20s staleness clock (`rssiAt`), so a
    //   row reached "Not in range" unprompted. Removed 2026-10-07: a stationary
    //   device holds one RSSI for minutes and the clock manufactured dead ends
    //   for hardware sitting right there (MEASURED: `-55` stable 30s+).
    // What remains is the honest pair: the rule errs toward in-range (a present
    // reading counts however old; only absence clears it), and a press on a
    // stale-but-present reading reaches BlueZ and explains itself through the
    // notification card. Do not tighten either half without re-reading the
    // note above `BluetoothDevice` in the service.
    if (busy() || !inRange()) return
    if (connected()) disconnectDevice(item.address)
    else if (paired()) connectDevice(item.address)
    else pairDevice(item.address)
  }

  function openConfirm() {
    console.error(`BluetoothContent: openConfirm(${item.address}) busy=${anyBusy()}`)
    if (anyBusy()) return
    setConfirmingAddress(item.address)
  }

  function confirmUnpair() {
    console.error(`BluetoothContent: confirmUnpair(${item.address}) busy=${anyBusy()}`)
    if (anyBusy()) return
    setConfirmingAddress(null)
    unpairDevice(item.address)
  }

  return (
    <box
      class={rowClass}
      orientation={1}
      spacing={3}
      $={(self) => {
        // The WHOLE ROW is the primary action (6.3), wired exactly like
        // `WifiRow`. The action controls are real `Gtk.Button`s, and a
        // `Gtk.Button` claims the click sequence in the gesture arena on press —
        // so this row-level gesture only ever fires for a click that MISSED
        // them. That is the "the action button claims its own click first" rule;
        // it is why the actions must be buttons and not the bare boxes
        // `WifiRow` uses for its single Connect affordance.
        const click = new Gtk.GestureClick({ button: 1 })
        click.connect("released", () => act())
        self.add_controller(click)
      }}
    >
      <box spacing={8}>
        <BluetoothSignalIcon rssi={rssi} />
        <label
          class="settings-net-name"
          xalign={0}
          label={name}
          hexpand
          maxWidthChars={26}
          ellipsize={Pango.EllipsizeMode.END}
          tooltipText={name}
        />
        <label
          class="settings-badge conn"
          label="Connected"
          valign={Gtk.Align.CENTER}
          visible={connected}
        />
      </box>
      {/* Line 2 — the row's second line. "Two-line geometry" in the no-reflow
          requirement means THIS line 1 / line 2 split, not two sub-lines inside
          the meta stack: the confirm swaps the meta stack's CONTENT in place and
          both lines stay. Below, the confirm branch keeps the battery slot
          occupied exactly as the idle branch does, so a connected row's meta
          stack is the same two sub-lines before and after and its height is
          identical — that is what makes "the row above it has not moved" true.

          Note the busy branch DOES grow the meta stack by one sub-line, and that
          is deliberate: the mock's own pairing state draws the busy row with
          `spin + Pairing…` AND `Can take up to 30 s` beside a one-line idle row.
          Only the confirm is held to zero reflow. */}
      <box class="settings-row-meta" spacing={8}>
        <box orientation={1} spacing={2} hexpand>
          {/* Slot 1: the in-flight line, else the connected-device battery. A
              paired-but-idle `Battery1` reading is stale, so battery shows only
              while connected — showing it would be a lie. Note it stays visible
              while confirming: dropping it would remove a sub-line from a
              connected row and reflow the list, which is the one thing the
              confirm must never do. */}
          <box class="settings-meta-stat" spacing={6} visible={busy}>
            <Gtk.Spinner class="settings-spinner" spinning={busy} />
            <label label={busyLabel} />
          </box>
          <box
            class="settings-meta-stat"
            spacing={6}
            visible={createComputed(() => connected() && battery() > 0 && !busy())}
          >
            <image
              class="settings-meta-icon"
              pixel_size={14}
              $={(self) => {
                createEffect(() => {
                  self.set_from_file(
                    registry.resolve("battery", batteryVariant(battery())) ??
                      "",
                  )
                })
              }}
            />
            <label label={createComputed(() => `${battery()}%`)} />
          </box>
          {/* Slot 2: the watchdog note while busy, else the word layer. The
              note is STATIC on purpose — a countdown needs a timer in the view,
              which the architecture forbids. The watchdog itself stays in
              `bluetooth-service`, bounded and self-cancelling; its failure
              surfaces as a notification card (`postBluetoothNotification`),
              never as panel text — there is deliberately no failure row. */}
          <label
            class="settings-net-sub"
            xalign={0}
            label="Can take up to 30 s"
            visible={busy}
          />
          <label
            class="settings-net-sub"
            xalign={0}
            label={subtitle}
            visible={createComputed(() => !busy())}
          />
        </box>
        <box
          spacing={8}
          valign={Gtk.Align.CENTER}
          visible={createComputed(() => !busy())}
        >
          {/* WHY ALL FOUR ARE ALWAYS MOUNTED AND ONLY `visible` TOGGLES.
              This was a structural `{cond ? <A/> : <B/>}` pair, which is the
              bug this comment exists to prevent repeating: AGS builds a STATIC
              widget tree, so a JSX ternary is evaluated once, at construction.
              Nothing subscribes to `confirming()`, so whichever branch was
              chosen when the row was built was chosen forever. MEASURED
              consequence: clicking `Unpair` called `openConfirm` (logged nine
              times) but `confirmUnpair` was NEVER reached -- the confirm
              buttons did not exist, so unpairing was impossible and nothing on
              screen or in the log said why.

              The fix is the idiom this file already uses 22 times: mount both
              branches and drive `visible` from a computed. That subscribes, so
              the swap actually happens. Kept as four explicit buttons rather
              than a computed-wrapped fragment because `visible` is reactive
              here and JSX shape is not. */}
          <button
            class="settings-rowact"
            onClicked={() => setConfirmingAddress(null)}
            canFocus={false}
            valign={Gtk.Align.CENTER}
            visible={createComputed(() => confirming())}
          >
            <label label="Keep" />
          </button>
          {/* `disabled` is the visual; `sensitive` is the guard. BOTH are required and
              they must agree -- this has now been got wrong three times, so:
                64078268  class + sensitive={inRange() && !anyBusy()}   correct
                rework    class only, sensitive deleted                 wrong: a CSS
                          class does not disable a GTK button, so the button
                          stayed activatable and focusable while looking dead
                6ec8202d  sensitive narrowed to !anyBusy()              wrong: made
                          unreachable hardware look clickable. OWNER REJECTED.
              FINAL: class for looks, sensitive for truth, both driven by the
              same `primaryAvailable`. Never "simplify" one into the other.

              The load-bearing dependency, updated 2026-10-07: there is no
              staleness clock anymore (see the service note), so a present
              reading counts however old it is and only absence reads "Not in
              range". A disabled Connect is therefore self-explanatory only in
              the absent case; in the stale-but-present case the press is what
              corrects the record, via the notification card. That is the
              intended pair — do not re-add a clock without re-reading the
              service note. */}
          <button
            class={createComputed(() =>
              primaryAvailable() ? "settings-rowact" : "settings-rowact disabled",
            )}
            sensitive={primaryAvailable}
            onClicked={act}
            canFocus={false}
            valign={Gtk.Align.CENTER}
            visible={createComputed(() => !confirming())}
          >
            <label label={actionLabel} />
          </button>
          {/* The ONE new class this change introduces (design §2/§7).
              `confirmUnpair` re-checks `anyBusy()` rather than trusting the
              button's visibility: a confirm can already be open when a
              different row's action starts, and BlueZ's single-flight
              `runAction` would drop the unpair silently. Better to refuse
              loudly than to look like it worked. */}
          <button
            class="settings-rowact danger"
            onClicked={confirmUnpair}
            canFocus={false}
            valign={Gtk.Align.CENTER}
            visible={createComputed(() => confirming())}
          >
            <label label="Unpair device" />
          </button>
          {/* Hidden entirely while busy: `runAction` is single-flight, so an
              Unpair issued during another row's action would be dropped. */}
          <button
            class="settings-rowact subtle"
            onClicked={openConfirm}
            canFocus={false}
            valign={Gtk.Align.CENTER}
            visible={createComputed(() =>
              !confirming() && paired() && !anyBusy(),
            )}
          >
            <label label="Unpair" />
          </button>
        </box>
      </box>
    </box>
  )
}

/**
 * `Bluetooth Settings ›` footer row.
 *
 * Launches `blueman-manager`, NOT `bluetoothctl`: bluetoothctl is a terminal
 * TUI, which a click from a panel is the worst possible way to open. Blueman is
 * also what makes a PIN/passkey pairing completable at all — the panel's own
 * agent registers `NoInputNoOutput` and cannot answer `RequestPinCode`.
 */
function BluetoothSettingsFooter({
  visible,
}: {
  visible: Accessor<boolean>
}) {
  return (
    <box
      class="settings-wifi-settings-row"
      spacing={8}
      visible={visible}
      $={(self) => {
        const click = new Gtk.GestureClick({ button: 1 })
        click.connect("released", () => {
          execAsync(["blueman-manager"]).catch((error) => {
            console.error(
              `BluetoothContent: could not launch blueman-manager: ${error}`,
            )
            postBluetoothNotification(
              "Bluetooth",
              "blueman-manager is unavailable — run provisioning to install it.",
            )
          })
        })
        self.add_controller(click)
      }}
    >
      {/* WHY maxWidthChars IS REQUIRED HERE, copied from WifiContent's
          `nm-connection-editor` row: an unwrapped Gtk.Label reports its FULL
          text width as natural width, which is what grew that surface off the
          right edge of the monitor. Ellipsize is kept ONLY on the short row
          label, where losing the tail is acceptable. */}
      <label
        class="settings-wifi-settings-label"
        hexpand
        xalign={0}
        maxWidthChars={14}
        ellipsize={Pango.EllipsizeMode.END}
        label="Bluetooth Settings"
      />
      {/* wrap, NOT ellipsize, for the same reason as the Wi-Fi row: this note is
          the actionable part of the row and truncating it destroys the only
          information it carries. Wrapping costs one extra line instead. */}
      <label
        class="settings-wifi-settings-note"
        valign={Gtk.Align.CENTER}
        xalign={1}
        wrap
        maxWidthChars={22}
        label="opens Blueman"
      />
      <label class="settings-wifi-settings-arrow" label="›" />
    </box>
  )
}

/** The embeddable body: off/scanning states + the device sections. */
export function BluetoothContent({ visible }: { visible: Accessor<boolean> }) {
  // WHY THIS IS A TRI-STATE (`boolean | null`) AND NOT A PLAIN BOOLEAN.
// With `createState(false)` the expansion rule was
// `manuallyToggled() || nearbyDevices().length > 0`, which is
// unconditionally TRUE whenever any device is in range. MEASURED
// consequence: the chevron was inert. Clicking it set the flag to `true`
// (still expanded, no visible change) and clicking again set it to `false`
// (still expanded, because `nearbyCount > 0` won) -- so the section could
// never be collapsed and the arrow was a control that did nothing.
//
// `null` means "the user has not expressed an intent yet", so the section
// still auto-opens when devices are found. A real boolean means the user has
// decided and wins from then on. That is what an arrow is supposed to do.
const [manuallyToggled, setManuallyToggled] = createState<boolean | null>(
  null,
)

  const powered = createComputed(() => bluetoothPowered())
  const pairedDevices = createComputed(() =>
    bluetoothDevices().filter((device) => device.paired),
  )
  // "Available" is everything discovery found that is not already paired: the
  // `Ready to pair` rows.
  const nearbyDevices = createComputed(() =>
    bluetoothDevices().filter((device) => !device.paired),
  )
  const hasDevices = createComputed(() => bluetoothDevices().length > 0)
  const hasPaired = createComputed(() => pairedDevices().length > 0)

  // WHY the section AUTO-OPENS on discovery: a discovery run starts the moment
  // the surface becomes visible, so a section that only opened on a click
  // would show an empty popup and then silently populate a section the user
  // never opened. So with no manual decision recorded, it opens as soon as
  // devices are found, and closes again when they go away.
  //
  // What it does NOT do any more: refuse to collapse while devices are
  // present. That was the previous rule and it made the chevron inert -- see
  // the tri-state note above. The user can now always collapse what they are
  // looking at, which is the whole point of an arrow.
  const expanded = createComputed(() => {
    const manual = manuallyToggled()
    if (manual !== null) return manual
    return nearbyDevices().length > 0
  })

  // Discovery runs while this content is visible and the adapter is powered;
  // hiding it (or powering off) stops it so BlueZ does not scan forever. The
  // service reference-counts start/stop, so a popup close racing a subview
  // open cannot stop a scan the other surface just started.
  createEffect(() => {
    if (!visible()) return
    if (!bluetoothPowered()) return
    startBluetoothDiscovery()
    return () => stopBluetoothDiscovery()
  })

  // Devices that connected outside the panel (auto-connect) still need the audio
  // sink defaulted.
  //
  // Transition-triggered, NOT on every device-list change. `bluetoothDevices()`
  // is re-published on every RSSI update, and an active scan produces those
  // constantly, so an effect that routed on each run would re-route the same
  // headset over and over. Each re-route calls `setAudioTarget(null)` before it
  // finds the endpoint again, so the default sink would flicker between "unset"
  // and the headset on every advertisement frame.
  //
  // The old comment here said "routing is idempotent". It was not — see the
  // routeInFlight guard in bluetooth-service.ts.
  const routedAddresses = new Set<string>()
  createEffect(() => {
    if (!visible()) return
    if (!bluetoothPowered()) return
    const connected = bluetoothDevices().filter((device) => device.connected)
    const stillConnected = new Set(connected.map((device) => device.address))
    for (const device of connected) {
      if (routedAddresses.has(device.address)) continue
      routedAddresses.add(device.address)
      void routeAudioToDevice(device.alias || device.name)
    }
    // Forget devices that dropped, so reconnecting routes again.
    for (const address of [...routedAddresses]) {
      if (!stillConnected.has(address)) routedAddresses.delete(address)
    }
  })

  // Click-outside / Escape dismissal, as far as THIS file can own it. The
  // popup's catcher and `app.tsx`'s `popup-close` handler live elsewhere (tasks
  // 5.3/5.4) and both do nothing but flip `visible`; resetting here means an
  // open confirm can never outlive its surface, so you are never returned to a
  // stale "Remove from paired devices". For the literal before-the-surface
  // ordering, those two files call `dismissUnpairConfirm()` first.
  createEffect(() => {
    if (visible()) return
    setConfirmingAddress(null)
  })

  // The scanning indicator. `Gtk.Spinner`, deliberately NOT a bespoke loader:
  // the supplied spinner pack's artwork cannot be animated smoothly here (GTK
  // 4.22.5 exposes no widget rotation, and this stylesheet records that GTK
  // honours @keyframes only best-effort), and the native widget is one boolean
  // with no timer and no assets. It is the same widget and the same class as
  // the in-flight action spinner on each row, and as WifiContent.tsx:366.
  // Findings, measurements and the bespoke-loader cost:
  // docs/Animated_Icon_Loader_Findings.md
  //
  // ONE indicator, TWO positions (owner rulings, 2026-10-05), keyed on whether
  // the Available Devices section is OPEN and whether its list has items:
  //
  //   open,   empty -> spinner + "Scanning..." as the list's empty state, in the
  //                     rows' place. There is nothing else on screen saying a
  //                     scan is running.
  //   open,   items -> spinner in the section header. The list already shows the
  //                     scan by growing, so a centred line between two populated
  //                     lists is noise.
  //   CLOSED, any  -> spinner in the section header. The list is not on screen,
  //                     so the header is the only visible part of the section and
  //                     the only place the indicator can live.
  //
  // The `CLOSED` case is why the header is not simply "the list has items" case:
  // collapsing the section used to leave BOTH wrong -- the placeholder stayed
  // visible below a collapsed header, and the header spinner went away, so a
  // collapsed list during a scan showed nothing at all.
  //
  // The two are exhaustive and mutually exclusive: exactly one shows while
  // scanning, and neither shows when not scanning.
  const scanning = createComputed(() => powered() && bluetoothDiscovering())
  const scanningPlaceholder = createComputed(
    () => scanning() && expanded() && nearbyDevices().length === 0,
  )
  const scanningInHeader = createComputed(
    () =>
      scanning() &&
      (!expanded() || nearbyDevices().length > 0),
  )

  // Re-read reachability whenever the panel becomes visible.
  //
  // BlueZ emits no event when a paired device merely stops advertising — it
  // just stops reporting RSSI — so the cached value can be minutes or hours
  // old. A fresh read costs one GetAll per cached device and only happens
  // while someone is looking, which is the only time the answer is read.
  // There is deliberately no timer here at all: a staleness clock was built
  // and removed 2026-10-07, because a stationary device holds one RSSI for
  // minutes and any timeout manufactures "Not in range" dead ends for
  // hardware that is sitting right there. See the note above
  // `BluetoothDevice` in the service.
  createEffect(() => {
    if (!visible()) return
    void refreshBluetoothDevices()
  })

  return (
    <box
      orientation={1}
      spacing={8}
      $={(self) => {
        // Click-outside for an open confirm, at the body level. A click on a
        // row's action BUTTON is claimed by that button and cancels this
        // gesture, so clicking `Keep` dismisses through its own handler rather
        // than through here.
        const click = new Gtk.GestureClick({ button: 1 })
        click.connect("released", () => setConfirmingAddress(null))
        self.add_controller(click)
      }}
    >
      <label
        class="settings-empty"
        xalign={0}
        label="Bluetooth is off"
        visible={createComputed(() => !powered())}
      />

      {/* Adapter detail row — the LOCAL CONTROLLER's own address
          (`Adapter1.Address`), never a device's. Hidden entirely while powered
          off, `—` when BlueZ has not published one.

          THERE IS DELIBERATELY NO AUDIO-OUTPUT ROW HERE. `bluetoothAudioTarget`
          exists so a failed routing attempt is recorded in state instead of
          vanishing — a device can read `Connected` while the sound stayed on
          the speakers with nothing to indicate which half of the chain failed.
          It is a record, not a readout: PipeWire routing state inside a
          Bluetooth surface mixes concerns (owner ruling), so do not
          "helpfully" add the row back. */}
      <box class="settings-conn-details" visible={powered}>
        <box class="settings-detail-row" spacing={8}>
          <label class="settings-detail" xalign={0} label="Adapter" />
          <label
            class="settings-detail"
            xalign={1}
            hexpand
            label={createComputed(() => bluetoothAdapterAddress() || "—")}
          />
        </box>
      </box>

      <box class="settings-divider" visible={powered} />

      <label
        class="settings-section-label"
        xalign={0}
        label="Paired"
        visible={createComputed(() => powered() && hasPaired())}
      />
      <box
        orientation={1}
        spacing={4}
        visible={createComputed(() => powered() && hasPaired())}
      >
        <For
          each={pairedDevices}
          id={(device: BluetoothDevice) => device.address}
        >
          {(device: BluetoothDevice) => <BluetoothRow device={device} />}
        </For>
      </box>

      <button
        class="settings-chevron-row"
        onClicked={() => setManuallyToggled(!expanded())}
        canFocus={false}
        visible={powered}
      >
        {/* ONE child, always: a Gtk.Button takes a single child. An earlier version
            put the label and a spinner here as siblings; the label was dropped
            and the spinner was left alone in the row, which rendered as a large
            empty box. Both contents go inside one box instead.

            `hexpand` on the label pushes the spinner to the right edge, which
            is what the mock's `.chev` does with `justify-content:space-between`.

            This is the SECOND position of the one indicator: it is visible only
            while the Available Devices list is non-empty, in which case the
            centred placeholder is hidden (see `scanningPlaceholder`). */}
        <box>
          <label
            class="settings-chevron-label"
            xalign={0}
            hexpand
            label={createComputed(() =>
              expanded() ? "Available Devices ▾" : "Available Devices ▸",
            )}
          />
          <Gtk.Spinner
            class="settings-spinner"
            spinning={scanningInHeader}
            visible={scanningInHeader}
          />
        </box>
      </button>

      <box
        class="settings-other-networks"
        orientation={1}
        spacing={4}
        visible={createComputed(() => powered() && expanded())}
      >
        <For
          each={nearbyDevices}
          id={(device: BluetoothDevice) => device.address}
        >
          {(device: BluetoothDevice) => <BluetoothRow device={device} />}
        </For>
      </box>

      {/* The Available Devices EMPTY STATE, directly under the list it belongs
          to, replacing "No devices found" (owner ruling, 2026-10-05). It is the
          list's placeholder, so it lives where the list's rows would be -- not
          up between the paired section and the section header, which is where it
          used to sit and where it read as a stray status line between two lists.

          One indicator, two positions: while the list is empty this is the only
          one showing; once the list has items, `scanningInHeader` puts the
          spinner in the section header instead and this row is hidden.

          The mock centres this row (`justify-content:center`). The OUTER box
          must be vertical for that to work: `halign` positions a child on its
          parent's CROSS axis, so in a horizontal box -- which is AGS's default
          -- it is main-axis packing and is ignored and the row sits at the start
          with its natural width. MEASURED, see
          prototypes/halign-centring-probe.js. */}
      <box orientation={1} class="settings-empty" hexpand visible={scanningPlaceholder}>
        <box spacing={7} halign={Gtk.Align.CENTER}>
          <Gtk.Spinner
            class="settings-spinner"
            spinning={scanningPlaceholder}
          />
          <label label="Scanning…" />
        </box>
      </box>

      <label
        class="settings-empty"
        xalign={0}
        label="No devices found"
        visible={createComputed(
          // Also gated on `expanded()`: this is the same slot as the scanning
          // placeholder, so it must not appear under a collapsed header either.
          () =>
            powered() &&
            expanded() &&
            !bluetoothDiscovering() &&
            !hasDevices(),
        )}
      />

      <BluetoothSettingsFooter
        visible={powered}
      />
    </box>
  )
}
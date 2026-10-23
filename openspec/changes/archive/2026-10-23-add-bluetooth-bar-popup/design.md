# Design — Bluetooth bar indicator + popup

Mock as contract: `mockups/panel.html` (owner-approved 2026-10-03). Every
dimension in the mock is authored at 312px and scaled by `--s`, so ×1 is the
real geometry and ×2 is a legible review size. The mock's captions are the
requirement list; `specs/bluetooth-bar-popup/spec.md` restates them as
verifiable SHALLs.

## 1. Parity is the whole design

`WifiPopup.tsx` / `WifiContent.tsx` are the reference. Where BlueZ and
NetworkManager genuinely differ, the divergence is named rather than smuggled
in. The mapping is enforced by `scripts/bluetooth-mock-parity.py`, not by
review.

| Wi-Fi | Bluetooth counterpart | Shared class |
|---|---|---|
| `WifiPopupCatcher` | `BluetoothPopupCatcher` | `settings-catcher`, `settings-catcher-fill` |
| `WifiPopup` window | `BluetoothPopup` | `settings-panel`, `settings-surface` |
| `WifiPopup` header | `BluetoothPopup` header | `settings-nav-header`, `settings-nav-title` |
| `WifiSwitch` | `WifiSwitch` | `settings-switch` |
| `components/wifi/state.ts` | `components/bluetooth/state.ts` | — |
| `WifiContent` body | `BluetoothContent` body | — |
| `WifiRow` | `BluetoothRow` | `settings-net`, `settings-net-name`, `settings-badge.conn`, `settings-rowact` |
| `SignalIcon` (30px) | `BluetoothSignalIcon` (30px) | `settings-net-signal` |
| `ConnectionDetails` | adapter detail block | `settings-conn-details`, `settings-detail-row` |
| `settings-chevron-row` | `Available Devices` section | `settings-chevron-row`, `settings-chevron-label` |
| `nm-connection-editor` row | `blueman-manager` row | `settings-wifi-settings-row`, `-label`, `-note`, `-arrow` |

## 2. Row geometry

`BluetoothContent.tsx` already renders a two-line row
(`box orientation={1}` → line 1, then `box class="settings-row-meta"`). The mock
keeps that and changes three things:

1. **Leading circle-badged glyph.** The shipped row has *no* leading glyph; the
   bars appear in the meta line. The mock leads with
   `settings-panel/bluetooth-signal-{full,good,medium,low}` at **30px** — the
   real `.settings-net-signal` size (`style.css:821-824` `min-width/min-height:
   30px`, `WifiContent.tsx:215` `pixel_size={30}`). Threshold table is the
   existing `signalVariant()`: `≥−60 high, ≥−70 good, ≥−80 medium, else low`,
   renamed `high → full` to match the wifi-signal ladder.
2. **Word-only subtitle.** The `−N dBm` string leaves the meta line and moves to
   the signal glyph's tooltip. `WifiRow` prints `Saved` / `Secured` / `Open
   network` and never a strength number, because the leading glyph already *is*
   the strength. Bluetooth printed it twice — bars and digits.
3. **No signal glyph when `rssi >= 0`.** BlueZ reports `0` for "not seen". There
   is no signal to draw, therefore no tooltip, therefore the number is in no
   channel at all — which is exactly why the **word** layer is load-bearing and
   cannot be deleted. `Not in range` is the sole carrier, reinforced by the
   `.settings-net.out-of-range` opacity and the insensitive `Connect` button:
   three independent channels, never opacity alone.

## 3. Icons

Two groups, different jobs, different mechanisms — deliberately.

### `settings-panel` — circle badges for rows (guard-exempt)

`bluetooth-signal-{full,good,medium,low}`, converted from the owner's
Downloads artwork: literal `#D9D9D9` → `{{COLOR_BACKGROUND}}`, `black` →
`{{COLOR_FOREGROUND}}`. Tint contract mirrors `wifi-signal-*` exactly: badge
`color12` on the top step, `color13` below, bars `color0`. The four steps are a
progressive `fill-opacity` ladder.

The bare `signal-*` variants stay in the manifest. `BluetoothContent.tsx:194`
resolves them today, and removing them is a behaviour change outside this
change's icon scope.

### `bluetooth` — bar glyph (guard-MANAGED)

`bluetooth-on` / `bluetooth-off` from the owner's artwork
(`stroke="black"` → `{{COLOR_FOREGROUND}}`; these are stroke-drawn, not
fill-drawn). Declares `COLOR_FOREGROUND` at **group level only** and is added
to `BAR_GROUPS` in `runtime/domain/icon_contrast.py`.

The guard rewrites only group-level placeholders (`icon_contrast.py:40-42`;
variant-level overrides and `bar_mappings` are structurally unreachable). So a
variant-level pin would *exempt* the glyph from retargeting — the `system-battery-*`
mechanism, which is right for a glyph on opaque glass and wrong for a glyph
floating over the wallpaper. Hence: panel carries ON/OFF in the rendered tint
(never retargeted); bar carries state in the glyph's **art** (always retargeted).

### YAML trap

`bar_mappings.states` keys must not be bare `on:` / `off:`. YAML 1.1 resolves
those to booleans, so the map comes out of the parser with `True` / `False`
keys and every bar lookup misses silently. Keys are `bluetooth-on` /
`bluetooth-off`. `network` dodges the same trap by using `wifi-not-connected`
rather than `off`.

## 4. Popup window

Property-for-property with `WifiPopup.tsx`:

```
name="bluetooth-popup"  class="settings-panel"  gdkmonitor={monitor}
anchor={TOP|LEFT}  exclusivity={Exclusivity.IGNORE}  layer={Layer.OVERLAY}
marginTop={52}  marginLeft={clamp(iconX - 156, 8, monitorWidth - 320)}
keymode={Keymode.NONE}
  <box class="settings-surface" widthRequest={312}>
    <box class="settings-nav-header">  ← PINNED, sibling of the scrolledwindow
    <scrolledwindow class="settings-scroll"
        propagateNaturalWidth={false} maxContentHeight={420}>
      <BluetoothContent visible={bluetoothPopupVisible} />
```

`propagateNaturalWidth={false}` is the settings panel's rule, not the Wi-Fi
popup's: Bluetooth rows carry a 26-char name plus two action buttons, and an
unwrapped `Gtk.Label` reports its full text as natural width, so an unclamped
row grows the surface past the 312px the `marginLeft` math assumes and runs it
off the right of the monitor.

`exclusivity` MUST be `IGNORE`: `NORMAL` makes Hyprland offset the overlay below
the bar's reserved zone and *then* applies `marginTop`, pushing the popup ~48px
too low. This is the Wi-Fi popup's hard-won lesson.

### Header is a sibling, never a child

A header inside the scrolledwindow scrolls away. `SubviewHeader.tsx` exists
because the settings panel learned this the hard way. Both Bluetooth surfaces
put the header outside the scroll area, and the mock shows it pinned.

### Keymode

`Keymode.NONE`, permanently. Bluetooth has **no typed-input surface** — the
shipped agent is `NoInputNoOutput` (Just Works), so unlike Wi-Fi there is no
password prompt, no reveal eye, and no `Gtk.Entry`. That is a deliberate
asymmetry with the reference, not an omission.

An `EventControllerKey` Esc handler is registered anyway, mirroring
`WifiPopup`: currently unreachable, live the instant a PIN field exists. The
future rule is already fixed by the Wi-Fi precedent — `ON_DEMAND` only while a
field needing typed input is on screen, never unconditionally (an
unconditional `ON_DEMAND` grabs the keyboard, the bar swallows the first click,
and same-spot collapse stops working).

Dismissal rides on the catcher and on `ags request popup-close`, which
`app.tsx`'s request handler must extend to call `closeBluetoothPopup()`.

## 5. Service additions

`bluetooth-service.ts` keeps owning every byte of Bluetooth state. The view
gains nothing: it reads accessors and forwards intent. Three accessors added,
all plain reads of data BlueZ or WirePlumber already hold:

1. **`bluetoothAdapterAddress: Accessor<string>`** — the adapter's own address,
   set in `updateAdapterProps`. Feeds the `Adapter` detail row. This is the
   machine's controller hardware address, not a device's.
2. **`bluetoothAudioTarget: Accessor<string | null>`** — the endpoint
   `routeAudioToDevice` actually defaulted, `null` when the 16-attempt window
   expired. **Closes the silent failure**: today headphones read `Connected`
   while sound stays on the speakers. Kept in the service as a recorded result,
   not surfaced as a panel row — PipeWire state inside a Bluetooth surface mixes
   concerns (owner ruling, 2026-10-03).
3. **`setBluetoothPowered(enabled: boolean)`** — the mirror of
   `setWifiEnabled(enabled)`. Both surfaces now mount a power control, and a
   blind `toggleBluetooth()` read-modify-write is how a stale read writes the
   wrong value. Every call site forwards an explicit value.

### Reference-counted discovery

`startBluetoothDiscovery` / `stopBluetoothDiscovery` become reference-counted:
`start` increments, `stop` decrements, `StopDiscovery` is issued only at zero.
Without this the panel's always-mounted views make the race real — a popup
close racing a panel open runs the popup's cleanup against a scan the subview
just started. The current early-return in `runStartDiscovery`
(`if (bluetoothDiscovering()) return`) makes the leak half-invisible and the
double-stop half-real.

The count lives in the service because *when* BlueZ should scan is a state
concern — the same reason the audio graph snapshot was moved out of
`AudioPopup.tsx` into `audio/state.ts`.

## 6. Hub — the decision not to add a topic

**Stay purely BlueZ D-Bus. No `bluetooth.state`.** `contracts/event-contract.
{json,xml}`, `hub.KNOWN_TOPICS`, `emit_validation.SCHEMAS`,
`lib/event-bus-core.ts` and `lib/event-bus.ts` are all **unchanged**.

The case for is real: two consumers now want the same state, and the hub is the
repo's "one source of truth, many subscribers" shape; `speedtest.state` proves
it works; the bar already has a hub consumer.

It loses on four counts:

- **No lossy boundary to protect.** The hub's `(epoch, seq)` ordering, hydration
  and restart handling exist to survive a *lossy* transport. An in-process
  GObject binding with per-property `PropertiesChanged` watches is neither lossy
  nor un-hydratable. The hub buys no reliability here.
- **A second source of truth.** Either the daemon observes BlueZ and
  re-broadcasts what AGS already holds (two holders that can disagree), or the
  AGS service publishes to the hub (a relay wrapped around a variable it could
  just read). Both are worse than not having it.
- **The frequency does not fit.** `KNOWN_TOPICS` is a closed set and the
  contract carries `publish_rate`. RSSI updates on **every received
  advertisement frame**; staying truthful means a per-frame flood on the
  session bus for a subscriber that already has the value synchronously. Every
  existing topic is transition-shaped; a signal ladder is not.
- **It would break the parity this change exists to create.** Two connectivity
  panels on two state transports, two hydration paths, two `JobsCleared`
  behaviours, two different things that happen when `bluetoothd` is missing.

**The trigger that reverses it:** a consumer *outside* the AGS bar process — a
lock screen, a `dotfiles-*` CLI, a script, a second GUI instance. Then the
producer is a BlueZ observer **inside the runtime daemon** (AGS must not become
a hub producer for state it already owns), the payload is a state bag with
transition-only cadence, and RSSI rides the payload rather than being published
as its own event. A different change, in a different process.

## 7. Blueman

`blueman` is the `Bluetooth Settings` row's target and the only agent on the
system able to answer `RequestPinCode` / `RequestPasskey`. Validated on the
target machine: 2.4.6-2 already present, `bluetooth.service` active, `hci0`
unblocked, controller `A0:E7:0B:8B:36:7E`; `blueman-manager` launched cleanly
against the live adapter and was torn down, leaving `bluetooth`, `pipewire` and
`wireplumber` verified unaffected.

Not autostarted. Its tray applet would sit in the bar owning a second agent role
for a GUI the user only opens deliberately.

## 8. Anti-drift harnesses

`scripts/bluetooth-mock-parity.py`, wired into `make gates` beside
`wifi-mock-parity` / `speedtest-mock-parity`. Same contract as the Wi-Fi gate:
every `class="…"` token in each anchored mock state must resolve to
`style.css`, to the state's mapped TSX file, to an explicit allowlist entry
(with a reason), or to a tracked known gap (warning, with its owning change).

**RED until this change lands** — same posture as
`capture-hexagonal-gate.py`. A red run before implementation is the expected
state, not a regression; read the per-check lines and the uncovered-token list
rather than the exit code. The known gaps named in the script are exactly the
classes this change ships, so the gate goes green as the tasks land.

Stdlib-only Python, no desktop stack, ~0.1s.

---
name: AGS Bluetooth Control
description: Behavioral contract for the Bluetooth bar indicator, the follower-anchored Bluetooth popup, and the reworked settings-panel Bluetooth subview — information architecture, interaction and state patterns, lifecycle rules, accessibility floor, and the hub judgement call.
status: draft
updated: 2026-10-02
design: DESIGN.md
sources:
  - dotfiles/config/ags/components/wifi/WifiPopup.tsx
  - dotfiles/config/ags/components/wifi/WifiContent.tsx
  - dotfiles/config/ags/components/wifi/state.ts
  - dotfiles/config/ags/components/bluetooth/BluetoothContent.tsx
  - dotfiles/config/ags/services/bluetooth-service.ts
  - dotfiles/config/ags/settings-panel/{SettingsPanel.tsx,state.ts,views/SubviewHeader.tsx,controls/bluetooth.tsx}
  - dotfiles/config/ags/audio/AudioPopup.tsx
  - dotfiles/config/ags/app.tsx
  - dotfiles/config/ags/lib/event-bus-core.ts
  - contracts/event-contract.json
  - src/runtime/src/runtime/domain/{hub.py,icon_contrast.py}
  - _bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-bluetooth-2026-10-02/mockups/
---

# AGS Bluetooth Control — Experience Spine

## Foundation

Desktop surface of the Hyprland dotfiles environment, rendered by AGS (GTK4) on Wayland. Three surfaces: a **bar indicator** in the always-on status bar, a **follower-anchored Bluetooth popup** under that indicator, and the **settings-panel Bluetooth subview**. Data comes exclusively from **BlueZ over D-Bus** through `services/bluetooth-service.ts` (ObjectManager `InterfacesAdded`/`InterfacesRemoved`, per-device `Device1` property watches, per-device `Battery1` property watches), plus one bounded 30 s watchdog per action. No polling, no `bluetoothctl`, no hub topic.

The architectural rule this surface must never violate:

> **Services own all state; the UI is a strictly thin reader that only forwards user intent.** No subprocesses, no bus calls, no timers in the view.

The design is at **full parity with the Wi-Fi panel**, which is the mandated reference. Where BlueZ and NetworkManager genuinely differ, the divergence is named here rather than papered over.

## Information Architecture

| Surface | Reached from | Purpose |
|---|---|---|
| Bluetooth bar indicator | Always in the bar, `end` box, left of `NetworkStatus` (`bluetooth` group) | Adapter power + whether anything is connected + whether audio is routed. Left-click opens the popup. |
| Bluetooth popup — Adapter | Popup header switch | Power toggle. `Gtk.Switch` in the pinned header, `active = bluetoothPowered`. |
| Bluetooth popup — Adapter details | Popup | `Adapter` (hci address) and `Audio output` (the PipeWire endpoint `routeAudioToDevice` landed on). |
| Bluetooth popup — Paired | Popup | Every device BlueZ reports `paired = true`, sorted connected-first then strongest RSSI. One row per device. |
| Bluetooth popup — Available Devices | Popup, `▸`/`▾` chevron row | Every device BlueZ reports `paired = false` (discovered neighbours). Collapsed by default. |
| Bluetooth popup — footer | Popup | `Bluetooth Settings ›` — launches `bluetoothctl` (the Bluetooth analogue of `nm-connection-editor`). |
| Settings panel — tile | `MainView` | `Bluetooth` capability tile: glyph is the power toggle, row opens the subview. Subtitle is the state word. |
| Settings panel — Bluetooth subview | Tile | The same `BluetoothContent` body under a pinned `SubviewHeader` (`‹` back + title + `Gtk.Switch`). |

Two sections (`Paired`, `Available Devices`) derived from the **one flat `bluetoothDevices()` accessor** by the view's `createComputed` — exactly the `connected` / `knownSaved` / `otherNetworks` split `WifiContent` derives from `wifiNetworks()`. No new state is introduced to hold the split.

Sections with zero rows collapse, except `Available Devices`, whose chevron row is always present while powered on (so the "scan" affordance is never invisible).

→ Composition reference: `mockups/index.html`, `mockups/key-bar-indicator.html`, `mockups/key-popup-states.html`, `mockups/key-actions.html`, `mockups/key-settings-panel.html`, `mockups/key-parity.html`. **Spine wins on conflict.**

## Voice and Tone

Microcopy only. Brand voice lives in `DESIGN.md`.

| Do | Don't |
|---|---|
| "Bluetooth" · "Paired" · "Available Devices" · "Scanning…" · "No devices found" | "Wireless Devices", "Bluetooth Settings", "Device Manager" |
| "Bluetooth is off" | "Adapter disabled" |
| "Connect" · "Disconnect" · "Pair" · "Unpair" · "Keep" · "Unpair device" | "OK", "Yes", "Remove" |
| "Connecting…" · "Pairing…" · "Disconnecting…" (spinner + label) | a bare spinner, or "Please wait" |
| "Not in range" | "Signal lost", "Unavailable" |
| Service failure strings **verbatim** (`Pairing timed out`, `Could not turn Bluetooth on (adapter may be soft-blocked)`, `No Bluetooth adapter available`) | reworded, or prefixed `Error:` |
| Device alias verbatim from BlueZ (`TOZO NC9`, `LG OM7560(07)`) | humanised guesses ("Your headphones") |

Tone is terse and factual. The popup reports BlueZ; it does not congratulate, apologise, or explain that Bluetooth is a radio.

Note the deliberate asymmetry with Wi-Fi: Wi-Fi can ask for a **typed** password and therefore owns a prompt, a reveal eye and a `Keymode.ON_DEMAND` window. **Bluetooth has no typed-input surface** — the shipped pairing agent is `NoInputNoOutput` (Just Works, auto-accepting). So Bluetooth ships **no prompt, no entry, and no keyboard grab**. If a PIN/passkey entry is ever added, the ON_DEMAND rule below activates unchanged, gated on that new field's visibility.

## Header control — the parity fix

Both Bluetooth surfaces put a **`Gtk.Switch` (`WifiSwitch`)** in the header's trailing slot, replacing the subview's current bare `BluetoothToggle` glyph.

*Why this is a change and not a detail.* `WifiPopup` and `SettingsPanel` both put `WifiSwitch` there; the same slot in `BluetoothView` holds a 22px bare glyph. A user who has learned "the pill on the right of this header is the radio" gets a bare glyph in one Bluetooth surface and the pill in the other, at identical screen positions. Parity is not about looking alike, it is about *doing* alike.

*Why the capability glyph is not lost.* `BluetoothToggle` is not deleted — `CapabilityTile` keeps using `IconToggle` on the **main-view tile**, where the glyph has 34px of room and no header to share. The glyph's job is to say *which capability this is*; the switch's job is to say *is it on*. Splitting them by slot is the point.

*Safety.* `IconToggle` is a `Gtk.Button`: its `clicked` signal fires only on genuine user activation, so it does **not** carry the `notify::active` self-oscillation hazard `WifiSwitch` was written to defeat. Both stay. But both now forward an **explicit** value via the new `setBluetoothPowered(enabled)` instead of a blind `toggleBluetooth()` read-modify-write, because two surfaces can now both mount a toggle and a stale read is a real (if rare) way to write the wrong value.

## Component Patterns

Behavioral rules. Visual specs live in `DESIGN.md.Components`.

| Component | Use | Behavioral rules |
|---|---|---|
| Bluetooth bar indicator | Bar | Variant resolves through `registry.getBarMappings("bluetooth").states[stateKey]` → `registry.resolve("bluetooth", variant)` — the exact `bar/widgets/network.tsx` path. `off` when `!bluetoothPowered()`; `active` when the routed device is connected; `connected` when some device is connected; `idle` otherwise. Left-click records the pointer x and toggles the popup. No right-click, no scroll (there is no continuous value to nudge — Bluetooth is discrete, unlike volume). |
| Follower anchoring | Bar widget | A `Gtk.EventControllerMotion` records `get_position()[1]` on every hover and does **not** claim clicks, so the button's own `onClicked` still fires. The click stores the x into `bluetoothIconX` *before* toggling. `null` x (programmatic open) falls back to the right edge, exactly as `WifiPopup` does. |
| Popup window | `BluetoothPopup` | `class="settings-panel"`, `anchor={TOP\|LEFT}`, `exclusivity=IGNORE`, `layer=OVERLAY`, `marginTop={52}`, `keymode=Astal.Keymode.NONE` (constant — see §Keyboard). Body is `<box class="settings-surface" widthRequest={312}>` → `<box class="settings-nav-header">` + `<scrolledwindow class="settings-scroll">`, in that order. |
| Bluetooth catcher | `BluetoothPopupCatcher` | Full-screen `settings-catcher` / `settings-catcher-fill`, `keymode=NONE`, `visible=bluetoothPopupVisible`, `GestureClick(BUTTON_PRIMARY)` on `released` → `closeBluetoothPopup()`. Registered in `app.tsx` **immediately before** the popup so the popup stacks above it on the overlay layer. |
| Header switch | Both surfaces | `WifiSwitch active={bluetoothPowered} onToggled={(v) => void setBluetoothPowered(v)}`. Must honour the `WifiSwitch` contract — pass the explicit value, never a blind toggle; the switch already suppresses backend echoes. |
| Device row | Both surfaces | Row-level `Gtk.GestureClick(BUTTON_PRIMARY)` on `released` → `act()`; the action button claims its own click first. `act()`: no-op if `busy()` or `!inRange()`; `disconnectDevice` if connected; `connectDevice` if paired; `pairDevice` otherwise. |
| Leading signal glyph | Device row | `settings-panel/signal-{low,medium,good,high}` via the existing thresholds (`≥−60 high`, `≥−70 good`, `≥−80 medium`, else `low`). Rendered **only when `rssi < 0`**; absent otherwise (BlueZ's "not seen"). Tooltip carries `−N dBm`. |
| Row subtitle | Device row | Words only, on `.settings-net-sub`, mirroring `WifiRow`'s `Saved` / `Secured` / `Open network`: `Not in range` (paired + `rssi ≥ 0` + not connected) · `Paired` (paired, in range, not connected) · `Ready to pair` (not paired). No numbers. |
| Battery stat | Device row | `battery/system-battery-{level<25?0:<50?25:<75?50:<100?75:100}` + `N%`. Visible **only when `connected && battery > 0`**, mirroring the shipped gate. Never a bare `battery-*`. |
| Row action | Device row | Primary `settings-rowact`, label `Disconnect` / `Connect` / `Pair`, `sensitive = inRange() && !anyBusy()`. While `bluetoothBusy().address === this address && action !== null` the button is replaced by `Gtk.Spinner class="settings-spinner"` + the label `Pairing…` / `Connecting…` / `Disconnecting…` / `Unpairing…`, and a static `.settings-meta-stat` line reads `Can take up to 30 s`. **The 30 s is a fixed string, never a countdown** — a countdown would require a timer in the view. |
| Unpair | Device row | `settings-rowact subtle`, visible only when `paired && !anyBusy()`, no-op when `anyBusy()` (the service is single-flight: `runAction` returns early if `bluetoothBusy().address !== null`). |
| Unpair confirm | Device row | First click swaps the row's meta stack for `Remove from paired devices` and the action pair for `Keep` (`settings-rowact`) / `Unpair device` (`settings-rowact danger`). **The row does not resize and does not reflow** — same two-line geometry, so a confirm never moves anything. `Keep` dismisses; `Unpair device` calls `unpairDevice`. Opening the confirm on one row closes any other open confirm. The popup's `Esc` / click-outside dismisses an open confirm *before* the surface closes. |
| Adapter details | Popup + subview | `.settings-detail-row` × 2: `Adapter` (adapter address, `—` if unavailable) and `Audio output` (`bluetoothAudioTarget()`, `—` when nothing is routed). Visible only while powered on. |
| Available Devices chevron | Popup + subview | `settings-chevron-row` with the label `Available Devices ▸` / `▾`. Expansion is `manuallyToggled || nearbyCount > 0` — see §Discover-then-reveal. |
| Footer row | Popup + subview | `Bluetooth Settings` + note `opens bluetoothctl` + `›`. Launches `bluetoothctl` on click; if the spawn fails, the failure surfaces in the existing `.settings-message` line, never a dialog. Mirrors `WifiContent`'s `nm-connection-editor` row including the wrap-not-ellipsize rule on the note. |
| Settings tile | Main view | `CapabilityTile` unchanged in shape. Subtitle: `Off` / `Pairing…` (while busy) / `<alias> · <battery>%` (connected, battery > 0) / `<alias>` (connected, no battery) / `Not connected`. Glyph stays `bluetooth` / `bluetooth-off` — the tile glyph is the **capability**, the subtitle is the **state**. |
| Discovery | Both surfaces | `visible`-scoped `createEffect`: `if (!visible()) return; if (!bluetoothPowered()) return; startBluetoothDiscovery(); return () => stopBluetoothDiscovery()`. Unchanged in shape from the shipped effect. |
| Audio routing | Service | `routeAudioToDevice(alias)` runs after a successful `pair`/`connect` and from the visible-scoped effect for devices that connected outside the panel. It polls the **PipeWire** speaker collection for up to 16 × 500 ms (an 8 s ceiling) — this is service-side, in a service-owned promise, and is *not* view polling. Its result is now recorded into `bluetoothAudioTarget`. |

## State Patterns

The state machine BlueZ actually produces, and what each one looks like. All eleven are in `mockups/key-popup-states.html` and `mockups/key-actions.html`.

| State | BlueZ signal | Treatment |
|---|---|---|
| **Powered off** | `Adapter1.Powered = false` | Header switch OFF. Body is exactly one line: `Bluetooth is off` (`.settings-empty`). Adapter details, sections and footer are all hidden — this mirrors `WifiContent`, whose `OtherNetworksExpand` is `visible={wifiEnabled && …}` so the Wi-Fi popup's off state is also one line. Discovery is stopped by the effect. |
| **Adapter absent** | no `Adapter1` object on the bus | Header switch insensitive (`sensitive={false}`), body shows `No Bluetooth adapter available` with the `info-caution` glyph. Never a crash, never a disabled-looking-but-clickable switch. |
| **Soft-blocked** | `Set(Powered)` rejects | Switch returns to its previous value; `.settings-message` reads `Could not turn Bluetooth on (adapter may be soft-blocked)`. The user learns the truth is outside the panel. |
| **Powered on, nothing paired** | `Powered = true`, empty list | `Scanning…` (spinner) while `bluetoothDiscovering`, `No devices found` once discovery settles empty. Both `.settings-empty`. The `Available Devices ▾` chevron row is present regardless, so the user can re-open the section and read what the surface is doing. |
| **Connected** | `Device1.Connected = true` | The flagship state. Row gets `.settings-net.sel` (solid `@color_10`) **and** the `Connected` badge **and** the `Disconnect` action. `Audio output` in the details block names the endpoint. Bar indicator reads `active` (or `connected` if routing has not landed). |
| **Paired, not connected, in range** | `Paired = true`, `RSSI < 0` | `.settings-net` (no fill), `Paired` subtitle, `Connect` action enabled, `signal-*` glyph + `Unpair` shown. Battery stat is **hidden** — the shipped gate requires `connected`, and that stays: a paired-but-idle device reports a stale `Battery1` percentage that would be a lie. |
| **Out of range** | `Paired = true`, `RSSI ≥ 0` (BlueZ's "not seen"), not connected | `.settings-net.out-of-range` (opacity 0.45), subtitle `Not in range`, `Connect` **insensitive** (`.settings-rowact.disabled`), **no signal glyph** (there is no signal to show), `Unpair` still available. The dimming plus the disabled button plus the word are three independent signals, so the state never rests on colour or opacity alone. |
| **Discovering** | `Adapter1.Discovering = true` | Spinner + `Scanning…` when the list is empty; once anything is found the `Available Devices` section reveals itself (see §Discover-then-reveal). A `Scanning…` line **coexists** with a populated list rather than replacing it. |
| **Pairing in progress** | `bluetoothBusy() = { address, action: "pair" }` | The row's action is replaced by spinner + `Pairing…`; a static `Can take up to 30 s` meta line appears. Every other row's primary action goes **insensitive** (`anyBusy()`), because `runAction` is single-flight — one BlueZ call at a time. `Unpair` is hidden entirely while busy. |
| **Pairing failed** | `bluetoothFailure()` set by `failAction` | The `.settings-message` line at the top of the body carries `Pairing failed: <bus error>` verbatim; the row's action returns to `Pair`. No toast, no modal, no retry button — retry *is* the restored action. |
| **Pairing timed out** | the 30 s watchdog fires | Same surface, message reads `Pairing timed out`. The watchdog exists precisely so a hung BlueZ call cannot leave the row spinning forever; the view's only obligation is to stop rendering the spinner when `busy` clears, which it does by construction. |
| **Unpairing** | `action: "unpair"` | Spinner + `Unpairing…`, and the row **disappears** the instant `RemoveDevice` completes (the device is gone from the cache → `InterfacesRemoved` → row destroyed). No farewell animation, no undo, no toast. |
| **Disconnected externally** | `Device1.Connected = false` | The row survives; it demotes from `.sel` to plain, the badge goes, the action becomes `Connect`. BlueZ auto-reconnect can flip it back on its own — the row simply follows, because it reads the live entry by address on every access. |
| **Device leaves range while connected** | `Connected = true` but `RSSI → 0` | The row **keeps** `.sel` and the `Connected` badge. `inRange()` is `connected || rssi < 0`, so a connected device is by definition in range; it is not dimmed out from under a live connection. |
| **Device disappears from the bus** | `InterfacesRemoved` | Row destroyed, its `Device1`/`Battery1` watches removed. No placeholder, no "reconnecting" row. |
| **Battery watch disappears** | `InterfacesRemoved` on `Battery1` | Battery stat hidden (`battery` reset to `0`); the rest of the row is untouched. |
| **Long device name** | alias > 26 chars | `maxWidthChars={26}` + `Pango.EllipsizeMode.END` on the name, `tooltipText` = full name. With `propagateNaturalWidth={false}` on the scrolledwindow the row clips rather than growing the surface past 312px. |
| **A device connects outside the panel** | auto-connect | The visible-scoped routing effect picks it up; `bluetoothAudioTarget` updates; the bar indicator flips to `active` with no interaction. |

### Discover-then-reveal

`Available Devices` expansion is `manuallyToggled || nearbyCount > 0`.

*Why.* A discovery run starts the moment the surface becomes visible, so a collapsed section fills with rows within a second or two of opening. A purely manual toggle would therefore show the user an empty popup and then quietly populate a section they had not opened. Collapsing it only while it is genuinely empty gives the Wi-Fi popup's "quiet when nothing is happening, dense when the graph is busy" behaviour **and** guarantees the section is never a trap. Toggling it closed while rows exist is allowed (the user's choice wins) and the count is not re-forced until the section empties again.

### Scroll reset

The popup resets its scroll to 0 on every open, via a `bluetoothViewEpoch` bumped in `openBluetoothPopup()` and an effect reading `viewEpoch(); visible();`. This follows the **audio** popup rather than the Wi-Fi popup, because Bluetooth's `Available Devices` section is derived state that survives a close/reopen — without the reset, reopening a scrolled popup drops the user into the middle of a neighbour list they had already seen. The Wi-Fi popup can skip it only because its scroll position is dominated by a section (`Other Networks`) that is also user-controlled and short.

### Keyboard

`keymode` is `Astal.Keymode.NONE` and **stays** `NONE`. There is no Bluetooth field that accepts typed input, so there is nothing to widen it for. The popup registers an `EventControllerKey` `Esc` handler anyway, mirroring `WifiPopup` — it is currently unreachable, and it becomes live the instant a PIN/passkey entry exists.

The rule for that future day is already fixed by the Wi-Fi precedent: **`ON_DEMAND` only while a field needing typed input is on screen**, i.e. `self.keymode = bluetoothPinPromptVisible() ? ON_DEMAND : NONE`. Never unconditionally — an unconditional `ON_DEMAND` grabs the keyboard, the bar swallows the first click, and the same-spot collapse stops working.

Dismissal therefore rides on two paths only: the catcher's click-outside, and `ags request popup-close` (the Hyprland keybind), which `app.tsx` must extend to call `closeBluetoothPopup()` alongside `closeSettings()` and `closeAudio()`.

### Mutual exclusion

Coordinated by **callers**, not by the state module — the existing `components/wifi/state.ts` comment states this rule and Bluetooth inherits it verbatim:

- `settings-panel/state.open()` calls `closeWifiPopup()` **and** `closeBluetoothPopup()`.
- The Bluetooth bar widget calls `close()` (settings) then `toggleBluetoothPopup()` — the `bar/widgets/network.tsx` order.

`components/bluetooth/state.ts` therefore imports **nothing** from `settings-panel/**`. The one-way dependency rule is preserved.

### Discovery reference counting

`startBluetoothDiscovery` / `stopBluetoothDiscovery` are reference-counted in the service; `StopDiscovery` is issued only when the count reaches zero. The panel keeps all three views mounted and toggles `visible`, so a popup close racing a panel open can otherwise run the popup's cleanup against a scan the subview has just started. The count lives in the service because scheduling *when* BlueZ should scan is a state concern — the same reason the audio graph snapshot was moved out of `AudioPopup` into `audio/state.ts`.

## Interaction Primitives

**Mouse-first, keyboard-supported.**

- Left-click the bar indicator — open the popup under the indicator (same-spot second click closes it).
- Click the header switch — set adapter power (explicit value, never a toggle).
- Click anywhere on a device row — the row's primary action (`Pair` / `Connect` / `Disconnect`).
- Click the row's action button — the same action (it claims its own click first).
- Click `Unpair` — enter the inline confirm; click `Unpair device` to confirm; click `Keep` to dismiss.
- Click `Available Devices ▸ / ▾` — toggle the section (suppressed while it is empty).
- Click `Bluetooth Settings ›` — launch `bluetoothctl`.
- Click-outside anywhere, or the global Escape keybind (`ags request popup-close`) — dismiss.
- `‹` in the settings subview — return to `MainView`.

**Banned:** opening the popup on hover; auto-hiding it on a timer; running discovery while the surface is hidden; a countdown timer on the pairing watchdog; any subprocess, `bluetoothctl` parse, or bus call from the view; rebuilding the whole popup on every BlueZ property change (only the affected row updates — each row re-reads its own live entry by address).

## Accessibility Floor

- Every interactive element has a tooltip naming its action and target ("Toggle Bluetooth", "Disconnect TOZO NC9", "Show signal −52 dBm", "Unpair TOZO NC9").
- State is conveyed by **at least two** independent channels. Out-of-range: dimmed row **and** the word `Not in range` **and** an insensitive button. Connected: fill **and** the `Connected` badge **and** the `Disconnect` label. Never colour alone, never opacity alone.
- The destructive confirm is not colour-alone either: the button says `Unpair device`, and `Keep` sits beside it.
- The bar indicator's four states are distinguished by **shape**, not tint, so they survive on any wallpaper and for any colour-vision profile.
- `Esc` always closes the popup; an open unpair confirm is dismissed before the surface is.
- The popup does not trap focus and holds no keyboard by default, so bar click activation and same-spot collapse keep working.
- Every device name is reachable in full via tooltip even when ellipsized.

## Key Flows

### Flow 1 — Connect the headphones from the bar (juan david, 09:12, headphones on the desk)

1. He clicks the Bluetooth glyph in the bar. The popup drops under the icon, the header switch reads ON, and the details block shows the adapter address. `Scanning…` shows for a moment.
2. `Available Devices` reveals itself as soon as `TOZO NC9` is found — he does not have to go looking for it.
3. He clicks the row. It spins: `Pairing…`, with `Can take up to 30 s` beneath so the wait is legible without a countdown, and every other row's action goes insensitive because BlueZ is single-flight.
4. **Climax:** the row fills with the selected tint, the `Connected` badge appears, the action flips to `Disconnect`, and `Audio output` in the details block names `TOZO NC9`. The bar indicator flips to the `active` glyph. **One click took him from the bar to a paired, connected, audio-routed headset**, and the last line of the popup tells him the part that is usually a lie — that the sound actually moved.

Failure: pairing times out at 30 s → the message line reads `Pairing timed out`, the action returns to `Pair`, and nothing else in the popup moves.

### Flow 2 — The headphones are connected but the sound is on the speakers (juan david, 11:40, the bug this design exists for)

1. He auto-connected by walking out of range and back. The row says `Connected`. He presses play and hears nothing change.
2. He opens the popup. The row is filled and badged, and the `Audio output` row in the adapter details reads `—`.
3. **Climax:** the surface has told him the truth — BlueZ connected, PipeWire did not route — and `Disconnected`/`Connect` is one click away if he wants to force a fresh connect. He does not have to open a terminal to find out which half failed.

Failure: `routeAudioToDevice` finds the endpoint but `stream.target_endpoint` throws for a vanished stream — the endpoint is still recorded, so `Audio output` is honest about the sink even though one stream did not move.

### Flow 3 — Two devices, one of them gone (juan david, 16:05)

1. The popup shows `TOZO NC9` connected, `LG OM7560(07)` paired and dimmed, and `HONOR 400 Smart` available.
2. `LG OM7560(07)` reads `Not in range` with an insensitive `Connect`. He knows it is not a bug — the device is asleep, not broken.
3. He clicks `Unpair` on it. The row's second line swaps in place to `Remove from paired devices` with `Keep` / `Unpair device`; **nothing above it moves**.
4. **Climax:** he confirms and the row is simply gone — no toast, no undo, no empty-state message. `Keep` would have cost him the same two clicks to change his mind, so the destructive path is one click longer than the safe one, which is the only asymmetry that matters.

Failure: he opens a confirm and then clicks outside the popup — the confirm closes and the popup closes, and on reopen nothing is pending.

### Flow 4 — Power off and on (juan david, 22:15, battery)

1. He clicks the header switch off. The body collapses to one line, `Bluetooth is off`, discovery stops, and the bar glyph becomes the slashed `off` variant.
2. He clicks it back on. The body returns to `Scanning…`, `Available Devices` re-reveals as soon as anything is found.
3. **Climax:** the paired device is already back, paired and ready, because pairing lives in BlueZ and not in the panel. Nothing had to be re-taught and nothing was remembered on his behalf.

Failure: BlueZ rejects `Set(Powered)` — the switch springs back and the message line explains that the adapter may be soft-blocked, which is the one thing he cannot fix from here.

## The hub question — judgement call

**Question.** Should this design introduce a `bluetooth.state` topic published through `org.dotfiles.Events1`, or stay purely BlueZ-D-Bus like Wi-Fi?

**Recommendation: stay purely BlueZ D-Bus. No new hub topic. No change to `contracts/event-contract.json` / `.xml`, no change to `hub.KNOWN_TOPICS`, no new entry in `emit_validation.py`, no new constant in `event-bus-core.ts`.**

### The case for a topic

It is a real argument and it deserves a hearing.

- **The hub exists to move domain state across a process boundary, and this change creates a second surface that wants the same state.** Two Bluetooth consumers (bar indicator and popup) now read the same five accessors. The hub's `GetTopicState` + `DomainEvent` is precisely the "one source of truth, many subscribers" shape, and the repo has already built the machinery — subscribe-before-read hydration, `(epoch, seq)` ordering, `JobsCleared` restart.
- **`speedtest.state` proves the pattern works for exactly this shape of problem** — a service that also has a D-Bus-backed sibling (`wifi-service`) chose to publish its terminal state through the hub *and* keep its own state. So there is precedent for a BlueZ-adjacent service also emitting.
- **The bar already has a hub consumer** (`bar/widgets/recording.tsx` subscribes to `capture.state`), so a Bluetooth bar indicator would not be introducing a new dependency; it would be reusing an existing one.
- **Discoverability.** A `bluetooth.state` topic is the natural home for a later lock screen, CLI, or script consumer. Not building it now means building it twice later.

### The case against — and why it wins

- **There is no process boundary to cross.** BlueZ is a separate *service*, but it is not a separate *consumer-facing* process from the UI's point of view: AGS already talks to it directly, synchronously, over the system bus. The hub's reason for existing — hydrate-or-miss ordering, at-most-once delivery, epoch bumps on restart — exists to survive a **lossy** transport. An in-process GObject binding with per-property `PropertiesChanged` watches is neither lossy nor un-hydratable. Using the hub here buys no reliability.
- **It would create a second source of truth for the same fact.** To publish `bluetooth.state`, *something* must own the BlueZ watch. Either the runtime daemon becomes a BlueZ observer and re-broadcasts what AGS already holds — in which case AGS and the daemon both hold the state and can disagree — or the AGS service publishes to the hub, in which case the hub is a relay wrapped around a variable it could just read. The second form is worse than useless: it puts `(epoch, seq)` ordering in front of a state source that has its own, correct, native ordering (BlueZ property watches).
- **The frequency does not fit.** `validation.structural` in the contract includes `publish_rate`, and `hub.py`'s `KNOWN_TOPICS` is a closed set. A naive `bluetooth.state` would have to publish on `RSSI` changes to stay truthful — and RSSI updates on **every received advertisement frame**. That is a per-frame event flood onto the session bus for a subscriber that already has the value synchronously. The existing topics are all transition-shaped (`capture.state` is explicitly "on every transition **and at least once per second while recording**"); a signal ladder is not transition-shaped.
- **It would break the parity this change is chartered to create.** Wi-Fi reads NM live. A Bluetooth panel that rides the hub while its twin does not means two connectivity panels with two state transports, two hydration paths, two `JobsCleared` restart behaviours, and two different things that happen when `bluetoothd` is missing. The mandate is full parity; this is full divergence.
- **It puts a bus call in the view, or it puts state in two places.** The architectural rule is *services own state; the view is a thin reader*. A view that hydrates from `GetTopicState` is making a synchronous bus call with a 2 s timeout in the render path — precisely the shape the Wi-Fi popup's comments warn against. And if the view keeps reading the service instead, the topic has no reader and is pure cost.
- **`Control` is the wrong tool too.** The hub's control path addresses `org.dotfiles.Job1` leases and needs a `CONTROL_ALLOWLIST` entry. Pairing is not a job; it is a BlueZ method call with a 30 s watchdog. Routing `pair` through the hub would mean the daemon, not AGS, calling BlueZ — a second control path and a re-implementation of the watchdog.
- **It expands a pinned contract for no consumer.** `contracts/event-contract.json` and `.xml` are pinned by an executed drift test, and `KNOWN_TOPICS` is a deliberate frozen set ("AD-44: the hub never advertises a topic absent from the contract"). Adding a topic the repo does not need is contract debt bought with a diff.

### The concrete contract surface this implies

**None.** Stated explicitly so the decision is auditable:

| Artifact | Change |
|---|---|
| `contracts/event-contract.json` / `.xml` | **unchanged** — no new topic, no new payload schema, no new enum |
| `src/runtime/src/runtime/domain/hub.py` `KNOWN_TOPICS` | **unchanged** |
| `src/runtime/src/runtime/adapters/emit_validation.py` `SCHEMAS` | **unchanged** |
| `dotfiles/config/ags/lib/event-bus-core.ts` | **unchanged** — no `BLUETOOTH_STATE_TOPIC` constant |
| `dotfiles/config/ags/lib/event-bus.ts` | **unchanged** — no subscription, no hydration |
| `bar/widgets/bluetooth.tsx` | reads `bluetooth-service` accessors directly, exactly as `bar/widgets/battery.tsx` reads its binding |

The bar indicator is a **direct reader** of `bluetoothPowered` / `bluetoothDevices` / `bluetoothAudioTarget` — same process, same service, same pattern as every other bar widget except the recorder.

### The trigger that would reverse this

Recorded so the door is not closed blindly. Introduce `bluetooth.state` **only** when a consumer appears **outside the AGS bar process** — a lock screen, a `dotfiles-*` CLI, a script, or a second GUI instance. At that point the design is:

```
topic:    bluetooth.state
producer: a BlueZ observer inside the runtime daemon (NOT the AGS service —
          AGS must not become a hub producer for a state it already owns locally)
payload:  { powered: b, adapter: s, discovering: b,
            connected: as, paired: as, failure: s }
          # connected / paired are arrays of { address, alias, battery, rssi }
cadence:  on TRANSITION only. RSSI rides the transition payload and is never
          published as its own event; a pure RSSI delta with no change to the
          connected/paired membership sets is dropped by the producer.
enum:     none (a state bag, not a lifecycle — unlike capture.state/speedtest.state)
```

That is a different change, in a different process, with a different producer. It is explicitly **out of scope here**.

## Inspirations & Anti-patterns

- **Lifted from the Wi-Fi popup (the reference):** the 312px surface, the pinned `settings-nav-header` as a sibling of the scrolledwindow, the `settings-scroll` + `maxContentHeight={420}` growth rule, follower anchoring from a recorded pointer x, `marginTop={52}`, `exclusivity: IGNORE`, `Keymode.NONE`, the catcher-before-popup window ordering, the `›` footer row with a wrap-not-ellipsize note, the whole-row-is-the-action hit target, and the derived-section split of one flat accessor.
- **Lifted from the Wi-Fi popup's naming discipline:** `settings-icon-toggle` keeps the main view, `settings-switch` keeps the header. Same component vocabulary, different slots, no new primitives.
- **Lifted from the audio popup:** the `viewEpoch` scroll reset, and the "quiet when nothing is happening, dense when the graph is busy" body philosophy that Discover-then-reveal implements.
- **Lifted from the 2026-09-25 Bluetooth row change:** the two-line row geometry, the `maxWidthChars 26` + ellipsize truncation, the RSSI and battery bucket tables, and the `system-battery-*` guard exemption. This design **keeps** that row and fixes its parity gaps rather than replacing it.
- **Lifted from `icon_contrast.py`:** the art-carries-state discipline for bar glyphs, which is the same insight `settings-panel/wifi` vs `wifi-off` already encodes for panel glyphs.
- **Rejected — a hub topic.** See §The hub question. The failure mode is a second source of truth for a state that already has a lossless in-process binding, plus a per-advertisement event flood.
- **Rejected — a device-type icon per row** (headphones / keyboard / phone). BlueZ reports an `Icon` string, but there is no icon group for those glyphs, they would need a per-device art taxonomy nobody maintains, and the connection state is the only thing the row is for. Rejected as decoration.
- **Rejected — a modal unpair dialog.** The popup is a surface with no modal stack, and a modal would grab a keyboard the surface otherwise does not hold. An inline confirm in the existing action slot is one row, no new window, no reflow.
- **Rejected — a countdown on the pairing watchdog.** It would require a timer in the view. A static `Can take up to 30 s` says the same thing at a fraction of the architectural cost.
- **Rejected — a "Reconnect all" / "Forget all" bulk action.** BlueZ pairing is per-device and deliberate; a bulk forget is unrecoverable from the panel and has no counterpart in the Wi-Fi reference.

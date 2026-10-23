# Add a Bluetooth bar indicator + follower-anchored popup (Wi-Fi parity)

## Why

Wi-Fi is reachable from **two** places: a status-bar icon that opens a
follower-anchored 312px popup, and a tile in the settings panel. Bluetooth is
reachable from **one**: the settings-panel tile only. The asymmetry is the whole
problem.

The consequences are concrete, not cosmetic:

- **Bluetooth is two clicks and a scroll away.** A user with Bluetooth
  headphones must open the settings gear at the far right of the bar, find the
  tile, and open the subview — while the Wi-Fi icon for the same class of
  action sits two icons away.
- **The panel cannot tell you pairing failed usefully.** `BluetoothContent`
  today shows a bare bar-glyph signal, a literal `−N dBm` string in the meta
  line, and no word for the state. The subview header carries a bare
  `BluetoothToggle` glyph where every other subview header carries a
  `Gtk.Switch`, so "the pill on the right of this header is the radio" — a
  rule the user learns once from Wi-Fi — is false in exactly one place.
- **A silent failure is invisible.** `routeAudioToDevice` in
  `bluetooth-service.ts` polls WirePlumber for up to 16 × 500ms and then
  simply gives up. When it fails, the row still reads `Connected` while the
  sound stays on the speakers, and the user has no way to learn which half of
  the chain broke short of opening a terminal.
- **A discovery race exists today.** The settings panel keeps all three views
  mounted and toggles `visible` (`SettingsPanel.tsx:171-181`), so a popup
  closing while the panel opens can run the first surface's cleanup against a
  scan the second surface just started. `startBluetoothDiscovery` /
  `stopBluetoothDiscovery` are not reference-counted.

## What Changes

- **A new bar indicator** (`bar/widgets/bluetooth.tsx`) reading
  `bluetoothPowered` directly, resolving its glyph through
  `registry.getBarMappings("bluetooth").states[...]` →
  `registry.resolve("bluetooth", variant)` — the exact path
  `bar/widgets/network.tsx` uses. Left-click opens the popup; a
  `Gtk.EventControllerMotion` records the pointer x so the popup anchors under
  the icon.
- **A new `bluetooth` icon group** with `bluetooth-on` / `bluetooth-off`
  variants from the owner's artwork and `bar_mappings` — added to `BAR_GROUPS`
  in `runtime/domain/icon_contrast.py` so the contrast guard retargets the
  glyph on light wallpapers. Group-level `COLOR_FOREGROUND` only: a
  variant-level pin would structurally exempt the glyph from the guard, which
  is the opposite of what a bar glyph needs. `off` reads as **shape** (a
  slash), never as dimness.
- **A new popup** (`components/bluetooth/BluetoothPopup.tsx` +
  `BluetoothPopupCatcher`), mirroring `WifiPopup.tsx` property for property:
  312px `settings-surface`, `exclusivity=IGNORE`, `layer=OVERLAY`,
  `marginTop=52`, follower `marginLeft` clamped to the monitor, pinned
  `settings-nav-header` as a **sibling** of the scrolledwindow,
  `propagateNaturalWidth={false}`, `Keymode.NONE`, catcher registered before
  the popup in `app.tsx`.
- **`components/bluetooth/state.ts`** — panel-agnostic popup visibility and
  icon x, importing nothing from `settings-panel/**` (the one-way dependency
  rule `components/wifi/state.ts` documents).
- **Reworked `BluetoothRow`** to the owner-approved mock: circle-badged
  `bluetooth-signal-*` glyph at 30px (matching `.settings-net-signal` and
  `WifiContent`'s `pixel_size={30}`), word-only subtitles, the `−N dBm` number
  removed from the meta line and carried on the glyph tooltip, whole-row as the
  primary action, and an inline unpair confirm that does not reflow the row.
- **Header parity fix** — `BluetoothView`'s header gains the same `WifiSwitch`
  the Wi-Fi subview uses. `BluetoothToggle` is retained on the main-view tile
  only, where `IconToggle` is safe (it is a `Gtk.Button`, so `clicked` fires
  only on real user activation and it carries none of the
  `notify::active` self-oscillation hazard `WifiSwitch` exists to defeat).
- **Three service accessors** — `bluetoothAdapterAddress`,
  `bluetoothAudioTarget` (the reported routing result that closes the silent
  failure), and `setBluetoothPowered(enabled)` so both surfaces forward an
  explicit value instead of a blind read-modify-write toggle.
- **Reference-counted discovery** in `bluetooth-service.ts`.
- **`blueman` in provisioning** (`packages.yaml` + both `group_vars`), mapped
  and validated. It is the only agent on the system able to answer a PIN or
  passkey request; the panel's own agent is `NoInputNoOutput` (Just Works).
  Not autostarted — its tray applet would own a second agent role for a GUI
  the user only opens deliberately.
- **`bluetooth-mock-parity.py`**, the anti-drift harness, wired into `make
  gates`. The approved mock is the contract; every `class="…"` token in each
  anchored state must resolve to `style.css`, to the state's mapped TSX, to an
  explicit allowlist entry, or to a tracked known gap.

The mock in `mockups/panel.html` is the **owner-approved acceptance contract**,
not an illustration. Its states are the requirement list.

## Capabilities

### New Capabilities
- `bluetooth-bar-popup` — the bar indicator, the follower-anchored popup, the
  reworked device row, the header parity fix, the service accessors, the
  discovery lifecycle, and the `blueman` provisioning contract.

### Modified Capabilities
- None. No existing requirement changes: the Wi-Fi panel, the settings panel's
  Wi-Fi path, the audio popup and the hub contract are untouched.

## Non-goals

- **No hub topic.** `bluetooth.state` was considered and rejected
  (`design.md` §Hub). BlueZ is already bound losslessly in-process; a topic
  would add a second source of truth for the same fact and, to stay truthful on
  RSSI, would publish on every received advertisement frame. `contracts/
  event-contract.{json,xml}` and `hub.KNOWN_TOPICS` stay unchanged.
- **No `bluetoothctl` row target.** It is a terminal TUI; the row opens
  `blueman-manager`.
- **No modal unpair dialog.** The popup has no modal stack and no keyboard.
- **No PIN/passkey entry in the panel.** The pairing agent is Just Works. Blueman
  covers PIN pairing when the user opens it deliberately.
- **No `connected` / `active` bar states.** The owner's artwork ships two
  variants; adding more is a separate decision.
- **No per-device-type row icons.** BlueZ reports an `Icon` string, but there is
  no icon group for those glyphs and connection state is what the row is for.

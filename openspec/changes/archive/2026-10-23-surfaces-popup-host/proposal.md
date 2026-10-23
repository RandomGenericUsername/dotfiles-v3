# surfaces-popup-host

## Why

Spine **AD-10** makes a surface body a **factory** and ships **`PopupHost`** as
the one popup primitive: *"a `SurfaceSpec.body` is a **factory**; hosts mount it
only while visible and tear it down when hidden, so at most one overlay is live.
Durable state lives in an app-level service. `PopupHost` is the shipped primitive
(window + click-catcher + anchor margin + keymode) absorbing all five current
popups (AudioPopup, WifiPopup, BatteryPopup, **BluetoothPopup**, SettingsPanel)."*
Doc 101 §4.4 defines `SurfaceSpec`/`SurfaceHostContext`/`SurfaceRegistry`; §13
step 5 ("Surfaces") is this step.

Today the five popups repeat the same chrome **five times**: a full-screen
`settings-catcher` window with a `settings-catcher-fill` click box, a
`settings-surface`/`audio-surface` body box, the identical `marginLeft` clamp
math, a `marginTop={52}`, and a `$` setup that pins `Astal.Keymode` and installs
the Escape controller. There is no `SurfaceSpec`, `SurfaceRegistry` or
`PopupHost` in the tree.

Evidence:

- `grep -rln 'settings-catcher' dotfiles/config/ags --include='*.tsx'` →
  `audio/AudioPopup.tsx`, `components/battery/BatteryPopup.tsx`,
  `components/bluetooth/BluetoothPopup.tsx`, `components/wifi/WifiPopup.tsx`,
  `settings-panel/SettingsPanel.tsx` (5 files).
- `grep -rln 'marginLeft = createComputed' dotfiles/config/ags --include='*.tsx'`
  → the same 5 files.
- `grep -rln 'Astal.Keymode' dotfiles/config/ags --include='*.tsx'` → the same
  5 files.
- `grep -rln 'settings-catcher-fill' dotfiles/config/ags --include='*.tsx'` →
  the same 5 files.
- `grep -rn 'SurfaceSpec\|PopupHost\|SurfaceRegistry' dotfiles/config/ags` → no
  matches (the port does not exist yet; it is only described in doc 101 §4.4).
- `ls dotfiles/config/ags/kit/` → `icon-source.ts icon.ts overlay.ts shapes.ts
  widget.tsx` (no surface/popup-host).

Verify:

- `grep -rln 'settings-catcher' dotfiles/config/ags --include='*.tsx'`
- `grep -rln 'marginLeft = createComputed' dotfiles/config/ags --include='*.tsx'`
- `grep -rln 'Astal.Keymode' dotfiles/config/ags --include='*.tsx'`
- `grep -rn 'SurfaceSpec\|PopupHost\|SurfaceRegistry' dotfiles/config/ags`
- `ls dotfiles/config/ags/kit/`

## What Changes

### A pure surface contract in the kit (AD-10)

- New `dotfiles/config/ags/kit/surface.ts` (**pure**: no `gi://`, no `ags`):
  `SurfaceHostContext`, `SurfaceSpec<E>` (`body(host)` is a **factory**,
  `width?`, `height?`, `keyboard?`), `SurfaceRegistry<E>` +
  `createSurfaceRegistry`, and the pure mount policy `SurfaceMount<E>` +
  `createSurfaceMount` that builds the body only while visible and drops it when
  hidden.

### `PopupHost`, the shipped popup primitive (AD-10)

- New `dotfiles/config/ags/kit/popup-host.tsx`: `PopupHost` (the anchored panel
  window: `marginTop` + the clamped `marginLeft` + the `keymode` flip + the
  Escape controller) and `PopupCatcher` (the full-screen
  `settings-catcher`/`settings-catcher-fill` click box that closes the surface).
  `PopupHost` consumes a `SurfaceSpec`, wraps `spec.body(host)` in the surface
  box, and mounts it through gnim `With` (build only while visible; dispose the
  body scope when hidden) driven by the pure `createSurfaceMount` policy.

### All five popups render through `PopupHost`

- `audio/AudioPopup.tsx`, `components/wifi/WifiPopup.tsx`,
  `components/battery/BatteryPopup.tsx`, `components/bluetooth/BluetoothPopup.tsx`
  and `settings-panel/SettingsPanel.tsx` each keep their own body/header/state
  but delegate the window, catcher, anchor math and keymode to `PopupHost` /
  `PopupCatcher`. The duplicated catcher markup, `marginLeft` clamp and keymode
  `$` block are deleted from all five.
- Behaviour is preserved: the windows keep their names/classes/anchors, the
  catcher still closes the surface (Bluetooth still dismisses an open unpair
  confirm first), and the keymode still flips to `ON_DEMAND` only while typed
  input (Wi-Fi password prompt / speed-test interval) is on screen.

### Content stays host-agnostic (doc 101 §4.4)

- `WifiContent`/`BluetoothContent` remain mountable in **both** their popup
  (`WifiPopup`/`BluetoothPopup`) and the settings panel
  (`WifiView`/`BluetoothView`). The refactor does not move them.

### One new test proves the mount policy

- New `dotfiles/config/ags/tests/ts/surface-mount.test.ts` proves the body is
  **mounted lazily** (factory not called while hidden; built once on show;
  dropped on hide; rebuilt on re-show) and that, wired to the real overlay
  coordinator, **at most one surface body is live** at a time.

### Deploy manifest (hard constraint)

- `kit/surface.ts` and `kit/popup-host.tsx` are registered in
  `compositor_configs_skeleton_files` and mirrored in the verify role, so a fresh
  provision deploys them and `make deploy-coverage` stays green.

## Out of scope

- **No `BarContext` injection.** Doc 101 §4.7's `ctx.surfaces` (the registry as
  an injected port) and the `ctx.overlays` conversion are the platform-extraction
  step (AD-20 step 8); `SurfaceHostContext` carries the reactive `visible` today
  and the registry stays a shipped, tested primitive that is not yet injected.
- **No settings-embeds-panels rework.** The panel's subviews are unchanged; this
  step only removes the duplicated popup chrome.
- **No visual restyle.** Window names/classes, anchors, widths, margins, surface
  classes and CSS classes are byte-for-byte the same values as before.
- **No overlay-coordinator change.** `kit/overlay.ts` is unchanged; the host
  consumes it as-is.
- **No app-local (`src/gui-tools/**`) popup migration** — those apps have their
  own windows and belong to the `ags-apps` epic.

## Impact

- New: `dotfiles/config/ags/kit/surface.ts`,
  `dotfiles/config/ags/kit/popup-host.tsx`,
  `dotfiles/config/ags/tests/ts/surface-mount.test.ts`.
- Edited: `dotfiles/config/ags/audio/AudioPopup.tsx`,
  `dotfiles/config/ags/components/wifi/WifiPopup.tsx`,
  `dotfiles/config/ags/components/battery/BatteryPopup.tsx`,
  `dotfiles/config/ags/components/bluetooth/BluetoothPopup.tsx`,
  `dotfiles/config/ags/settings-panel/SettingsPanel.tsx`,
  `dotfiles/config/ags/tests/tsconfig.tests.json`,
  `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`,
  `src/provisioning/ansible/roles/verify/vars/main.yml`,
  `src/provisioning/tests/unit/test_compositor_configs_role.py`,
  `src/provisioning/tests/unit/test_verify_role.py`.
- No behaviour change on a provisioned host beyond the deleted duplication: the
  five surfaces open, anchor, close and flip keymode exactly as before.

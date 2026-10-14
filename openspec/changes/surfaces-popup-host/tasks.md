# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-surfaces/spec.md` with ADDED Requirements + Scenarios citing AD-10
  and doc 101 §4.4/§13 step 5.
  Verify: `openspec validate surfaces-popup-host --type change` → valid.
  - `openspec validate surfaces-popup-host --type change` →
    `Change 'surfaces-popup-host' is valid`.

## 2. The pure surface contract (AD-10)

- [x] 2.1 Add `dotfiles/config/ags/kit/surface.ts`: `SurfaceHostContext`,
  `SurfaceSpec<E>` (factory `body`), `SurfaceRegistry<E>` +
  `createSurfaceRegistry`, and the pure mount policy `SurfaceMount<E>` +
  `createSurfaceMount`. No `gi://`, no `ags`.
  Verify: `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/kit/surface.ts` → no matches.
  - `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/kit/surface.ts`
    → no matches (exit 1). The module has no imports at all.

- [x] 2.2 Register `../kit/surface.ts` (and `../kit/overlay.ts`) in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
  - `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.

## 3. `PopupHost`, the shipped primitive (AD-10)

- [x] 3.1 Add `dotfiles/config/ags/kit/popup-host.tsx`: `PopupHost` (anchored
  panel window: `marginTop`, clamped `marginLeft`, keymode flip, Escape
  controller) and `PopupCatcher` (the `settings-catcher` /
  `settings-catcher-fill` click box), mounting `spec.body(host)` through gnim
  `With` + `createSurfaceMount`.
  Verify: `grep -n "export function PopupHost\|export function PopupCatcher\|createSurfaceMount" dotfiles/config/ags/kit/popup-host.tsx`.
  - `grep -n ...` → `50:export function PopupCatcher(...)`,
    `98:export function PopupHost(...)`, `4:import { createSurfaceMount ... }`,
    `127:const mount = createSurfaceMount(() => (`. `PopupHost` wraps the
    factory output and mounts it with `<With value={visible}>{(v) =>
    mount.render(v)}</With>`.

## 4. All five popups render through `PopupHost`

- [x] 4.1 Refactor `components/wifi/WifiPopup.tsx`: export a `wifiSurface` spec
  (header + scrolledwindow + `WifiContent`); `WifiPopup`/`WifiPopupCatcher` become
  thin `PopupHost`/`PopupCatcher` calls; delete the catcher window, the
  `marginLeft` clamp and the keymode `$` block.
  Verify: `grep -cE 'settings-catcher-fill|marginLeft = createComputed|Astal\.Keymode' dotfiles/config/ags/components/wifi/WifiPopup.tsx` → 0.
  - `0` (only `kit/popup-host.tsx` still contains the chrome).

- [x] 4.2 Refactor `components/bluetooth/BluetoothPopup.tsx` (catcher still
  dismisses an open unpair confirm before closing; keymode stays `NONE`).
  Verify: `grep -cE 'settings-catcher-fill|marginLeft = createComputed|Astal\.Keymode' dotfiles/config/ags/components/bluetooth/BluetoothPopup.tsx` → 0.
  - `0`; `onClose` runs `dismissUnpairConfirm()` before `closeBluetoothPopup()`.

- [x] 4.3 Refactor `components/battery/BatteryPopup.tsx` (keep the
  wifi-opens-so-battery-stands-down effect).
  Verify: `grep -cE 'settings-catcher-fill|marginLeft = createComputed|Astal\.Keymode' dotfiles/config/ags/components/battery/BatteryPopup.tsx` → 0.
  - `0`; `createEffect(() => { if (wifiPopupVisible()) closeBatteryPopup() })`
    is kept.

- [x] 4.4 Refactor `settings-panel/SettingsPanel.tsx` (keymode flips on the Wi-Fi
  prompt / speed-test interval; keep the scroll reset).
  Verify: `grep -cE 'settings-catcher-fill|marginLeft = createComputed|Astal\.Keymode' dotfiles/config/ags/settings-panel/SettingsPanel.tsx` → 0.
  - `0`; the `keyboard` accessor and the `viewEpoch` scroll-reset effect moved
    into the body factory.

- [x] 4.5 Refactor `audio/AudioPopup.tsx` (keep the required `binding` parameter
  and the monitor-derived width/drawer height).
  Verify: `grep -cE 'settings-catcher-fill|marginLeft = createComputed|Astal\.Keymode' dotfiles/config/ags/audio/AudioPopup.tsx` → 0; `node openspec/changes/redesign-ags-audio-panel/validation/audio-panel-render.test.mjs` → 6/6.
  - `0`; `node ...audio-panel-render.test.mjs` → `6/6 render checks passed`
    (binding still required, app.tsx still passes it, layers reachable).

- [x] 4.6 Confirm the content bodies still mount in both hosts.
  Verify: `grep -l "WifiContent" dotfiles/config/ags/components/wifi/WifiPopup.tsx dotfiles/config/ags/settings-panel/views/WifiView.tsx` → both; `grep -l "BluetoothContent" dotfiles/config/ags/components/bluetooth/BluetoothPopup.tsx dotfiles/config/ags/settings-panel/views/BluetoothView.tsx` → both.
  - Both commands list both files: `WifiContent` is mounted by
    `WifiPopup.tsx` and `WifiView.tsx`; `BluetoothContent` by
    `BluetoothPopup.tsx` and `BluetoothView.tsx`.

## 5. Test the mount policy (pure, no GTK)

- [x] 5.1 Add `tests/ts/surface-mount.test.ts`: lazy mount (factory not called
  while hidden; built once on show; dropped on hide; rebuilt on re-show) and
  at-most-one-live wired to the real overlay coordinator.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/surface-mount.test.ts` → `fail 0`.
  - `tests 3, pass 3, fail 0` — lazy mount, at-most-one-live, registry lookup.

## 6. Deploy registration (hard constraint)

- [x] 6.1 Register `kit/surface.ts` and `kit/popup-host.tsx` in
  `compositor_configs_skeleton_files`; mirror both in the verify role.
  Verify: `make deploy-coverage` → `PASS`.
  - `make deploy-coverage` → `reachable AGS modules from
    dotfiles/config/ags/app.tsx: 80`, `deployed AGS sources in the manifest: 93`,
    `PASS`.

- [x] 6.2 Update the provisioning structural tests that pin the skeleton list
  (`test_compositor_configs_role.py`, `test_verify_role.py`), including the
  `_build_provisioned_layout` fixture.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.
  - `test_compositor_configs_role.py` → `27 passed` (count pinned at 108).
  - `test_verify_role.py` → `72 passed` (fixture writes the two new kit files).

## 7. Verify

- [x] 7.1 All gates green: `make ags-test` (fail 0, 0 type errors),
  `make ags-typecheck` (PASS), `make bar-typecheck` (OK), `make gates-ci`
  (exit 0), `make deploy-coverage` (PASS).
  - `make ags-test` → `tests 111, pass 111, fail 0`, `0 type errors`.
  - `make ags-typecheck` → `PASS (with GIR typings, 0 errors in the extracted
    bar tree ..., 29 third-party, 36 in tests/, 0 exempt)`.
  - `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - `make gates-ci` → `EXIT=0`.
  - `make deploy-coverage` → `PASS`.

- [x] 7.2 The change validates and the tree is clean.
  Verify: `openspec validate surfaces-popup-host --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
  - `openspec validate surfaces-popup-host --type change` → valid;
    `git status --porcelain` → empty after the implementation commit.

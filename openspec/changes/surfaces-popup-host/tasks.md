# Tasks

## 1. Plan (commit 1)

- [ ] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-surfaces/spec.md` with ADDED Requirements + Scenarios citing AD-10
  and doc 101 §4.4/§13 step 5.
  Verify: `openspec validate surfaces-popup-host --type change` → valid.

## 2. The pure surface contract (AD-10)

- [ ] 2.1 Add `dotfiles/config/ags/kit/surface.ts`: `SurfaceHostContext`,
  `SurfaceSpec<E>` (factory `body`), `SurfaceRegistry<E>` +
  `createSurfaceRegistry`, and the pure mount policy `SurfaceMount<E>` +
  `createSurfaceMount`. No `gi://`, no `ags`.
  Verify: `grep -nE "^import .*(gi://|\"ags\")" dotfiles/config/ags/kit/surface.ts` → no matches.

- [ ] 2.2 Register `../kit/surface.ts` (and `../kit/overlay.ts`) in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.

## 3. `PopupHost`, the shipped primitive (AD-10)

- [ ] 3.1 Add `dotfiles/config/ags/kit/popup-host.tsx`: `PopupHost` (anchored
  panel window: `marginTop`, clamped `marginLeft`, keymode flip, Escape
  controller) and `PopupCatcher` (the `settings-catcher` /
  `settings-catcher-fill` click box), mounting `spec.body(host)` through gnim
  `With` + `createSurfaceMount`.
  Verify: `grep -n "export function PopupHost\|export function PopupCatcher\|createSurfaceMount" dotfiles/config/ags/kit/popup-host.tsx`.

## 4. All five popups render through `PopupHost`

- [ ] 4.1 Refactor `components/wifi/WifiPopup.tsx`: export a `wifiSurface` spec
  (header + scrolledwindow + `WifiContent`); `WifiPopup`/`WifiPopupCatcher` become
  thin `PopupHost`/`PopupCatcher` calls; delete the catcher window, the
  `marginLeft` clamp and the keymode `$` block.
  Verify: `grep -c "settings-catcher\|marginLeft = createComputed\|Astal.Keymode" dotfiles/config/ags/components/wifi/WifiPopup.tsx` → 0.

- [ ] 4.2 Refactor `components/bluetooth/BluetoothPopup.tsx` (catcher still
  dismisses an open unpair confirm before closing; keymode stays `NONE`).
  Verify: `grep -c "settings-catcher\|marginLeft = createComputed\|Astal.Keymode" dotfiles/config/ags/components/bluetooth/BluetoothPopup.tsx` → 0.

- [ ] 4.3 Refactor `components/battery/BatteryPopup.tsx` (keep the
  wifi-opens-so-battery-stands-down effect).
  Verify: `grep -c "settings-catcher\|marginLeft = createComputed\|Astal.Keymode" dotfiles/config/ags/components/battery/BatteryPopup.tsx` → 0.

- [ ] 4.4 Refactor `settings-panel/SettingsPanel.tsx` (keymode flips on the Wi-Fi
  prompt / speed-test interval; keep the scroll reset).
  Verify: `grep -c "settings-catcher\|marginLeft = createComputed\|Astal.Keymode" dotfiles/config/ags/settings-panel/SettingsPanel.tsx` → 0.

- [ ] 4.5 Refactor `audio/AudioPopup.tsx` (keep the required `binding` parameter
  and the monitor-derived width/drawer height).
  Verify: `grep -c "settings-catcher\|marginLeft = createComputed\|Astal.Keymode" dotfiles/config/ags/audio/AudioPopup.tsx` → 0; `node openspec/changes/redesign-ags-audio-panel/validation/audio-panel-render.test.mjs` → 6/6.

- [ ] 4.6 Confirm the content bodies still mount in both hosts.
  Verify: `grep -l "WifiContent" dotfiles/config/ags/components/wifi/WifiPopup.tsx dotfiles/config/ags/settings-panel/views/WifiView.tsx` → both; `grep -l "BluetoothContent" dotfiles/config/ags/components/bluetooth/BluetoothPopup.tsx dotfiles/config/ags/settings-panel/views/BluetoothView.tsx` → both.

## 5. Test the mount policy (pure, no GTK)

- [ ] 5.1 Add `tests/ts/surface-mount.test.ts`: lazy mount (factory not called
  while hidden; built once on show; dropped on hide; rebuilt on re-show) and
  at-most-one-live wired to the real overlay coordinator.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/surface-mount.test.ts` → `fail 0`.

## 6. Deploy registration (hard constraint)

- [ ] 6.1 Register `kit/surface.ts` and `kit/popup-host.tsx` in
  `compositor_configs_skeleton_files`; mirror both in the verify role.
  Verify: `make deploy-coverage` → `PASS`.

- [ ] 6.2 Update the provisioning structural tests that pin the skeleton list
  (`test_compositor_configs_role.py`, `test_verify_role.py`), including the
  `_build_provisioned_layout` fixture.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.

## 7. Verify

- [ ] 7.1 All gates green: `make ags-test` (fail 0, 0 type errors),
  `make ags-typecheck` (PASS), `make bar-typecheck` (OK), `make gates-ci`
  (exit 0), `make deploy-coverage` (PASS).
  Verify: run each target; record the observed result.

- [ ] 7.2 The change validates and the tree is clean.
  Verify: `openspec validate surfaces-popup-host --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.

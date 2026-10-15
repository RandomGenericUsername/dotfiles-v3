# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-preferences-notifier-theme/spec.md` with ADDED Requirements +
  Scenarios citing AD-11/AD-12/AD-13 and doc 101 §4.5/§4.6/§4.7/§13 step 7.
  Verify: `openspec validate preferences-notifier-theme --type change` → valid.
  - `openspec validate preferences-notifier-theme --type change` →
    `Change 'preferences-notifier-theme' is valid`.

## 2. The pure platform ports (AD-11, AD-12, AD-13)

- [ ] 2.1 Add `dotfiles/config/ags/platform/preferences.ts`: the `Preferences`
  port (`get<T>(namespace, key, fallback): ReadAccessor<T>`), the injected
  `PreferencesSource` seam, and the pure `createPreferences` core (fallback on
  an absent file, one watch per namespace, re-read on change). No `gi://`, no
  `ags`.
  Verify: `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/platform/preferences.ts` → no matches.
- [ ] 2.2 Add `dotfiles/config/ags/platform/notifier.ts`: `NotificationIntent`,
  the `Notifier` port (`post`/`dismiss`), the injected `NotifierSinks` seam, and
  the pure `createNotifier` router (transient → notify; keyed/progress → card).
  No `gi://`, no `ags`.
  Verify: `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/platform/notifier.ts` → no matches.
- [ ] 2.3 Add `dotfiles/config/ags/platform/theme.ts`: the `Theme` port
  (`apply()`), the injected `CssSink` seam, and the pure `createTheme` core. No
  `gi://`, no `ags`.
  Verify: `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/platform/theme.ts` → no matches.
- [ ] 2.4 Register all three port modules in `tests/tsconfig.tests.json`'s
  explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.

## 3. The adapters (file + monitor lifecycle; the wire; the CSS)

- [ ] 3.1 Add `dotfiles/config/ags/lib/preferences.ts`: the Gio
  `PreferencesSource` (`GLib.file_get_contents` + a per-namespace
  `Gio.FileMonitor` held in an adapter-owned map, never module scope) and the
  bound `preferences` instance on the injected `agsRuntime`.
  Verify: `grep -n "monitors.set\|monitor_file\|agsRuntime" dotfiles/config/ags/lib/preferences.ts`.
- [ ] 3.2 Add `dotfiles/config/ags/lib/notifier.ts`: the freedesktop `Notify`
  transient sink (the call moved out of `bluetooth-service.ts`), the card sink
  seam, and the bound `notifier` instance.
  Verify: `grep -n '"Notify"\|org.freedesktop.Notifications' dotfiles/config/ags/lib/notifier.ts`.
- [ ] 3.3 Add `dotfiles/config/ags/lib/theme.ts`: the `app.apply_css` `CssSink`
  applying the stable `colors.css` pointer, and the bound `theme` instance.
  Verify: `grep -n "colors.css\|apply_css" dotfiles/config/ags/lib/theme.ts`.

## 4. The bar consumes the ports (no behaviour change)

- [ ] 4.1 Repoint `bar/widgets/recording.tsx` at
  `preferences.get("capture-tool", "bar_compact_controls", false)`; delete
  `CAPTURE_CONFIG`, `loadCompactControls`, and the module-scope monitor; add a
  `createEffect` that closes the popup when compact mode turns off.
  Verify: `grep -cE 'captureConfigMonitor|monitor_file|loadCompactControls' dotfiles/config/ags/bar/widgets/recording.tsx` → `0`;
  `grep -c 'preferences.get' dotfiles/config/ags/bar/widgets/recording.tsx` → `1`.
- [ ] 4.2 Repoint `services/bluetooth-service.ts`'s `postBluetoothNotification`
  at `notifier.post({...})` (transient); the freedesktop call leaves the sender.
  Verify: `grep -c 'Gio.bus_get_sync' dotfiles/config/ags/services/bluetooth-service.ts` → `0`;
  `grep -c 'notifier.post' dotfiles/config/ags/services/bluetooth-service.ts` → `1`.
- [ ] 4.3 Repoint `app.tsx`'s palette apply at `theme.apply()`; leave the
  component stylesheet (`audio/audio-panel.css`) as a direct apply.
  Verify: `grep -n "theme.apply\|apply_css" dotfiles/config/ags/app.tsx`.

## 5. Tests prove the pure cores (pure, no GTK)

- [ ] 5.1 Add `tests/ts/preferences.test.ts`: a fake `PreferencesSource` (fake
  file + fake monitor) drives the real core — fallback on an absent file, a
  reactive update on a monitor change, one watch per namespace.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/preferences.test.ts` → `fail 0`.
- [ ] 5.2 Add `tests/ts/notifier.test.ts`: fake sinks capture intents —
  transient → notify, keyed/progress → card, dismiss → the dismiss seam.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/notifier.test.ts` → `fail 0`.
- [ ] 5.3 Add `tests/ts/theme.test.ts`: a fake `CssSink` receives the stable
  palette path from `theme.apply()`.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/theme.test.ts` → `fail 0`.

## 6. Deploy registration (hard constraint)

- [ ] 6.1 Register `platform/{preferences,notifier,theme}.ts` and
  `lib/{preferences,notifier,theme}.ts` in `compositor_configs_skeleton_files`;
  mirror all six in the verify role.
  Verify: `make deploy-coverage` → `PASS`.
- [ ] 6.2 Update the provisioning structural tests that pin the skeleton list
  (`test_compositor_configs_role.py`, `test_verify_role.py`), including the
  `_build_provisioned_layout` fixture.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.

## 7. Verify

- [ ] 7.1 All gates green: `make ags-test` (fail 0, 0 type errors),
  `make ags-typecheck` (PASS), `make bar-typecheck` (OK), `make gates-ci`
  (exit 0), `make deploy-coverage` (PASS).
- [ ] 7.2 The change validates and the tree is clean.
  Verify: `openspec validate preferences-notifier-theme --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.

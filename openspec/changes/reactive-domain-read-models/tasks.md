# Tasks

## 1. Plan (this commit)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-domain-read-models/spec.md` with ADDED Requirements + Scenarios
  citing AD-2/AD-3 and doc 101 §13 step 2.
  Verify: `openspec validate reactive-domain-read-models --type change` → valid.
  - `openspec validate reactive-domain-read-models --type change` →
    `Change 'reactive-domain-read-models' is valid`.

## 2. One injectable reactive port (AD-2)

- [ ] 2.1 Add the pure `domains/reactive.ts`: `ReadAccessor<T>`, `Setter<T>`,
  `ReactiveRuntime` (the `createState` port). No `ags`, no `gi://`, no I/O.
  Verify: `grep -n "interface ReadAccessor\|interface ReactiveRuntime" dotfiles/config/ags/domains/reactive.ts`.
- [ ] 2.2 Add the adapter `domains/astal.ts`: `agsRuntime` binding the port to
  gnim's `createState`.
  Verify: `grep -n "agsRuntime\|createState" dotfiles/config/ags/domains/astal.ts`.

## 3. Network read model (pure core + Astal adapter)

- [ ] 3.1 Make `domains/network/read-model.ts` pure: keep `NetworkService` /
  `WifiDevice` / `WiredDevice` and `snapshot`, drop the `gi://`/`ags` imports,
  and take `(service, runtime)`; return `ReadAccessor<NetworkReading>`.
  Verify: `grep -n "gi://\|from \"ags\"" dotfiles/config/ags/domains/network/read-model.ts` → no matches.
- [ ] 3.2 Add `domains/network/astal.ts`: `createNetworkReadModel(network =
  Network.get_default())` closing over the injected service and `agsRuntime`.
  Verify: `grep -n "Network.get_default\|agsRuntime" dotfiles/config/ags/domains/network/astal.ts`.
- [ ] 3.3 Re-point the existing consumer
  `bar/widgets/network-descriptor.tsx` at the Astal adapter.
  Verify: `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.

## 4. Battery read model

- [ ] 4.1 Add pure `domains/battery/read-model.ts`: `BatteryService`,
  `BatteryReading`, `snapshot`, `createBatteryReadModel(service, runtime)`
  subscribing to `notify::{percentage,charging,isPresent,timeToFull,timeToEmpty}`.
  Verify: `grep -n "createBatteryReadModel\|notify::" dotfiles/config/ags/domains/battery/read-model.ts`.
- [ ] 4.2 Add `domains/battery/astal.ts`: `createBatteryReadModel(battery =
  Battery.get_default())`.
  Verify: `grep -n "Battery.get_default\|agsRuntime" dotfiles/config/ags/domains/battery/astal.ts`.

## 5. Bluetooth read model

- [ ] 5.1 Add pure `domains/bluetooth/read-model.ts`: `BluetoothSource`,
  `BluetoothReading` (+ device/busy readings), `snapshot`,
  `createBluetoothReadModel(source, runtime)` subscribing to the source.
  Verify: `grep -n "createBluetoothReadModel\|interface BluetoothSource" dotfiles/config/ags/domains/bluetooth/read-model.ts`.
- [ ] 5.2 Add `domains/bluetooth/astal.ts`: adapt
  `services/bluetooth-service.ts`'s accessors into the source and bind it.
  Verify: `grep -n "bluetoothPowered\|agsRuntime" dotfiles/config/ags/domains/bluetooth/astal.ts`.

## 6. Audio read model

- [ ] 6.1 Add pure `domains/audio/read-model.ts`: `AudioReadModelSource`,
  `AudioReading` (= the bar-indicator projection), `createAudioReadModel(source,
  runtime)` projecting the existing hexagon's `AudioPanelViewModel`.
  Verify: `grep -n "createAudioReadModel\|projectBarIndicators" dotfiles/config/ags/domains/audio/read-model.ts`.
- [ ] 6.2 Add `domains/audio/astal.ts`: wrap `audio/composition.ts`'s binding as
  the source and bind it. Do NOT rewrite the hexagon.
  Verify: `grep -n "audioPanelBinding\|agsRuntime" dotfiles/config/ags/domains/audio/astal.ts`.

## 7. Unit tests — fake device, no live Astal

- [ ] 7.1 Add `tests/ts/fixtures/reactive-fixture.ts`: a minimal pure
  `ReactiveRuntime` (a `createState` signal) so a read model can be driven
  without `ags`.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/*.test.ts` → `fail 0`.
- [ ] 7.2 Add four read-model suites, each with a fake device/source: prove the
  initial snapshot is published (injectable) and a device/source change
  republishes (reactive).
  Verify: `make ags-test` → `fail 0` and the four new suites pass.
- [ ] 7.3 Register the new pure modules in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.

## 8. Verify

- [ ] 8.1 All gates green.
  Verify: `make ags-test` → `fail 0`, 0 type errors; `make ags-typecheck` →
  PASS; `make bar-typecheck` → OK; `make gates-ci` → exit 0.
- [ ] 8.2 The change validates and the tree is clean.
  Verify: `openspec validate reactive-domain-read-models --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.

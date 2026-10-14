# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-domain-read-models/spec.md` with ADDED Requirements + Scenarios
  citing AD-2/AD-3 and doc 101 §13 step 2.
  Verify: `openspec validate reactive-domain-read-models --type change` → valid.
  - `openspec validate reactive-domain-read-models --type change` →
    `Change 'reactive-domain-read-models' is valid`.

## 2. One injectable reactive port (AD-2)

- [x] 2.1 Add the pure `domains/reactive.ts`: `ReadAccessor<T>`, `Setter<T>`,
  `ReactiveRuntime` (the `createState` port). No `ags`, no `gi://`, no I/O.
  Verify: `grep -n "interface ReadAccessor\|interface ReactiveRuntime" dotfiles/config/ags/domains/reactive.ts`.
  - `22:export interface ReadAccessor<T> {`, `32:export interface ReactiveRuntime {`.
    `grep -rnE "^import .*(gi://|\"ags\")" dotfiles/config/ags/domains/reactive.ts`
    → no matches.
- [x] 2.2 Add the adapter `domains/astal.ts`: `agsRuntime` binding the port to
  gnim's `createState`.
  Verify: `grep -n "agsRuntime\|createState" dotfiles/config/ags/domains/astal.ts`.
  - `1:import { createState } from "ags"`, `15:export const agsRuntime: ReactiveRuntime = {`.

## 3. Network read model (pure core + Astal adapter)

- [x] 3.1 Make `domains/network/read-model.ts` pure: keep `NetworkService` /
  `WifiDevice` / `WiredDevice` and `snapshot`, drop the `gi://`/`ags` imports,
  and take `(service, runtime)`; return `ReadAccessor<NetworkReading>`.
  Verify: `grep -nE "^import .*(gi://|\"ags\")" dotfiles/config/ags/domains/network/read-model.ts` → no matches.
  - No matches. The file imports only `../reactive` and `../../lib/network-icon.ts`
    (both pure), and `createNetworkReadModel(network, runtime)` returns
    `ReadAccessor<NetworkReading>`.
- [x] 3.2 Add `domains/network/astal.ts`: `createNetworkReadModel(network =
  Network.get_default())` closing over the injected service and `agsRuntime`.
  Verify: `grep -n "Network.get_default\|agsRuntime" dotfiles/config/ags/domains/network/astal.ts`.
  - `17:  network: NetworkService = Network.get_default() as unknown as NetworkService,`,
    `19:  return createReadModel(network, agsRuntime)`.
- [x] 3.3 Re-point the existing consumer
  `bar/widgets/network-descriptor.tsx` at the Astal adapter.
  Verify: `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - Import is now `from "../../domains/network/astal"`; `make bar-typecheck` →
    `OK: 0 errors in dotfiles/config/ags`.

## 4. Battery read model

- [x] 4.1 Add pure `domains/battery/read-model.ts`: `BatteryService`,
  `BatteryReading`, `snapshot`, `createBatteryReadModel(service, runtime)`
  subscribing to `notify::{percentage,charging,isPresent,timeToFull,timeToEmpty}`.
  Verify: `grep -n "createBatteryReadModel\|notify::" dotfiles/config/ags/domains/battery/read-model.ts`.
  - `68:export function createBatteryReadModel(`,
    `74:    service.connect(\`notify::${prop}\`, () => setReading(snapshot(service)))`.
- [x] 4.2 Add `domains/battery/astal.ts`: `createBatteryReadModel(battery =
  Battery.get_default())`.
  Verify: `grep -n "Battery.get_default\|agsRuntime" dotfiles/config/ags/domains/battery/astal.ts`.
  - `18:  battery: BatteryService = Battery.get_default() as unknown as BatteryService,`,
    `20:  return createReadModel(battery, agsRuntime)`.

## 5. Bluetooth read model

- [x] 5.1 Add pure `domains/bluetooth/read-model.ts`: `BluetoothSource`,
  `BluetoothReading` (+ device/busy readings), `snapshot`,
  `createBluetoothReadModel(source, runtime)` subscribing to the source.
  Verify: `grep -n "createBluetoothReadModel\|interface BluetoothSource" dotfiles/config/ags/domains/bluetooth/read-model.ts`.
  - `64:export interface BluetoothSource {`,
    `94:export function createBluetoothReadModel(`.
- [x] 5.2 Add `domains/bluetooth/astal.ts`: adapt
  `services/bluetooth-service.ts`'s accessors into the source and bind it.
  Verify: `grep -n "bluetoothPowered\|agsRuntime" dotfiles/config/ags/domains/bluetooth/astal.ts`.
  - `41:    powered: () => bluetoothPowered(),`, `56:  return createReadModel(source, agsRuntime)`.
    The service's BlueZ logic is untouched; only its public accessors are wrapped.

## 6. Audio read model

- [x] 6.1 Add pure `domains/audio/read-model.ts`: `AudioReadModelSource`,
  `AudioReading` (= the bar-indicator projection), `createAudioReadModel(source,
  runtime)` projecting the existing hexagon's `AudioPanelViewModel`.
  Verify: `grep -n "createAudioReadModel\|projectBarIndicators" dotfiles/config/ags/domains/audio/read-model.ts`.
  - `41:export function createAudioReadModel(`, `45:  const [reading, setReading] =
    runtime.createState<AudioReading>(projectBarIndicators(source.current()))`.
- [x] 6.2 Add `domains/audio/astal.ts`: wrap `audio/composition.ts`'s binding as
  the source and bind it. Do NOT rewrite the hexagon.
  Verify: `grep -n "audioPanelBinding\|agsRuntime" dotfiles/config/ags/domains/audio/astal.ts`.
  - `3:import { audioPanelBinding } from "../../audio/composition"`,
    `19:  const binding = audioPanelBinding()`, `24:  return createReadModel(source, agsRuntime)`.
    No hexagon file was modified.

## 7. Unit tests — fake device, no live Astal

- [x] 7.1 Add `tests/ts/fixtures/reactive-fixture.ts`: a minimal pure
  `ReactiveRuntime` (a `createState` signal) so a read model can be driven
  without `ags`.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/*.test.ts` → `fail 0`.
  - `fakeRuntime()` + `makeEmitter()` added; the suite runs with no `ags` import
    on any tested path.
- [x] 7.2 Add four read-model suites, each with a fake device/source: prove the
  initial snapshot is published (injectable) and a device/source change
  republishes (reactive).
  Verify: `make ags-test` → `fail 0` and the four new suites pass.
  - `make ags-test` → `tests 90, suites 13, pass 90, fail 0`. The four new suites
    (`network read model`, `battery read model`, `bluetooth read model`,
    `audio read model`) all pass; +15 tests over the 75 baseline.
- [x] 7.3 Register the new pure modules in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
  - The include list gained `../domains/reactive.ts` and the four
    `../domains/*/read-model.ts`; `make ags-test` →
    `OK: 0 type errors in the ags pure-module unit tests`.

## 8. Verify

- [x] 8.1 All gates green.
  Verify: `make ags-test` → `fail 0`, 0 type errors; `make ags-typecheck` →
  PASS; `make bar-typecheck` → OK; `make gates-ci` → exit 0.
  - `make ags-test` → `tests 90, pass 90, fail 0`, `0 type errors`.
  - `make ags-typecheck` → `PASS (with GIR typings, 0 errors in the extracted bar
    tree …, 29 third-party, 24 in tests/, 0 exempt)`.
  - `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - `make gates-ci` → `EXIT=0`.
- [x] 8.2 The change validates and the tree is clean.
  Verify: `openspec validate reactive-domain-read-models --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
  - `openspec validate reactive-domain-read-models --type change` → valid;
    `git status --porcelain` → empty after the implementation commit.

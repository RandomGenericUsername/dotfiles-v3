# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-bar-shapes/spec.md` with ADDED Requirements + Scenarios citing AD-8
  and AD-9 (and doc 101 §5, §13 step 6).
  Verify: `openspec validate migrate-widgets-to-shapes --type change` → valid.
  - `openspec validate migrate-widgets-to-shapes --type change` →
    `Change 'migrate-widgets-to-shapes' is valid`.

## 2. The layout vocabulary + the repo default (AD-9)

- [x] 2.1 Add the pure `dotfiles/config/ags/kit/layout.ts`: `BarEntry`,
  `BarLayout` (sections, **no version field**), `LayoutProvider`, and
  `resolveLayout(providers, repoDefault)` (first non-null wins; never null).
  Verify: `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/kit/layout.ts` → no matches.
  - `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/kit/layout.ts`
    → no matches (exit 1). The module has no imports at all.
- [x] 2.2 Add `dotfiles/config/ags/bar/layout.default.ts`: the repo-default
  provider (always non-null) and the default `BarLayout` in today's order.
  Verify: `grep -n "repoDefaultLayout\|sections" dotfiles/config/ags/bar/layout.default.ts`.
  - `grep -n ...` → `22:export const DEFAULT_LAYOUT: BarLayout = {`,
    `23:  sections: {`, `47:export const repoDefaultLayout: LayoutProvider = {`.
- [x] 2.3 Register `kit/layout.ts` and `bar/layout.default.ts` in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
  - `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.

## 3. The shape renderers (AD-8)

- [x] 3.1 In `kit/widget.tsx`, add one shared `useShell` and a `BarWidget`
  dispatcher plus `RichWidget` (`content`), `Collection` (`items`/`key`/`item`)
  and `ForeignCollection` (`items`/`render`); re-point `BarWidgetButton` at
  `useShell` so the shell is implemented once.
  Verify: `grep -n "export function BarWidget\|export function RichWidget\|export function Collection\|export function ForeignCollection\|function useShell" dotfiles/config/ags/kit/widget.tsx`.
  - `grep -n ...` → `71:function useShell<S>(...`, `175:export function BarWidgetButton<S>`,
    `216:export function RichWidget<S>`, `248:export function Collection<I, S>`,
    `273:export function ForeignCollection<I, S>`, `305:export function BarWidget(`.
- [x] 3.2 Add the optional `spacing` presentation hint to `CollectionSpec` /
  `ForeignCollectionSpec` in `kit/shapes.ts` (the shared `Shell` is unchanged).
  Verify: `make ags-test` → the `kit-shapes` suite still passes.
  - `make ags-test` → `tests 132, pass 132, fail 0`, 0 type errors (the
    `kit-shapes` typing test is included and passes).

## 4. The widgets move onto the shapes (AD-8)

- [x] 4.1 `clock.tsx` → `RichWidgetSpec` (two labels; timer unchanged).
  Verify: `grep -n "clockWidget: RichWidgetSpec" dotfiles/config/ags/bar/widgets/clock.tsx`.
  - `grep -n ...` → `31:export const clockWidget: RichWidgetSpec<ClockState> = {`.
- [x] 4.2 `recording.tsx` → `RichWidgetSpec` (dot + timer + buttons; hub
  `control` through the injected context).
  Verify: `grep -n "createRecordingWidget\|RichWidgetSpec" dotfiles/config/ags/bar/widgets/recording.tsx`.
  - `grep -n ...` → `50:export function createRecordingWidget(): RichWidgetSpec<RecordingState> {`;
    `ctx.hub.control(jobId, action)` drives pause/resume/stop.
- [x] 4.3 `workspaces.tsx` → `CollectionSpec` (items/key/item; the active class
  stays reactive).
  Verify: `grep -n "workspacesWidget: CollectionSpec" dotfiles/config/ags/bar/widgets/workspaces.tsx`.
  - `grep -n ...` → `18:export const workspacesWidget: CollectionSpec<number, undefined> = {`.
- [x] 4.4 `tray.tsx` → `ForeignCollectionSpec` (items/render); the recording
  indicator is no longer rendered by the tray.
  Verify: `grep -c "RecordingIndicator" dotfiles/config/ags/bar/widgets/tray.tsx` → `0`.
  - `grep -c ...` → `0`.
- [x] 4.5 `network-descriptor.tsx` is wired; `network.tsx` is retired
  (deleted) and its two manifest entries removed.
  Verify: `test ! -e dotfiles/config/ags/bar/widgets/network.tsx` and
  `grep -rn "widgets/network\"" dotfiles/config/ags/bar`.
  - `test ! -e ...` → exit 0 (the file is gone); `grep -rn "widgets/network\"" ...`
    → no matches; `registry.ts` imports `networkWidget` from
    `./widgets/network-descriptor`.
- [x] 4.6 `battery.tsx` / `bluetooth.tsx` / `audio.tsx` become
  `DescriptorSpec`s (audio-output) with the audio **microphone** as a
  `RichWidgetSpec` (the live-dot badge is not expressible as a descriptor).
  Verify: `grep -n "DescriptorSpec" dotfiles/config/ags/bar/widgets/battery.tsx dotfiles/config/ags/bar/widgets/bluetooth.tsx dotfiles/config/ags/bar/widgets/audio.tsx`.
  - `battery.tsx:34:export function createBatteryWidget(): DescriptorSpec<BatteryReading> {`,
    `bluetooth.tsx:29:export function createBluetoothWidget(): DescriptorSpec<BluetoothReading> {`,
    `audio.tsx:53:export function createAudioOutputWidget(...): DescriptorSpec<BarIndicatorState> {`;
    `audio.tsx:86:createAudioMicWidget(...): RichWidgetSpec<BarIndicatorState>`.
- [x] 4.7 Add `bar/registry.ts` (entry id → spec) and re-point `Bar.tsx` at
  `resolveLayout([], repoDefaultLayout)` + `BarWidget`, removing the hardcoded
  composition.
  Verify: `grep -c "Workspaces\|Clock\|BatteryIndicator\|NetworkStatus" dotfiles/config/ags/bar/Bar.tsx` → `0`;
  `grep -n "repoDefaultLayout\|BarWidget" dotfiles/config/ags/bar/Bar.tsx`.
  - `grep -c ...` → `0`; `grep -n ...` → `21:import { BarWidget } from "../kit/widget"`,
    `24:import { repoDefaultLayout } from "./layout.default"`, `39: const layout = resolveLayout([], repoDefaultLayout)`,
    `47: return spec ? [<BarWidget spec={spec} ctx={ctx} />] : []`.

## 5. Tests prove the pure layout chain

- [x] 5.1 Add `tests/ts/layout.test.ts`: whole-replacement chain (user ›
  runtime › repo-default), null providers skipped, repo default non-null, and
  the default layout's ids are unique.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/layout.test.ts` → `fail 0`.
  - `node ... --test .../layout.test.ts` → `tests 6, pass 6, fail 0`.

## 6. Deploy registration (hard constraint)

- [x] 6.1 Register `kit/layout.ts`, `bar/layout.default.ts` and
  `bar/registry.ts` in `compositor_configs_skeleton_files`; mirror all three in
  the verify role; remove the `bar/widgets/network.tsx` entry from both.
  Verify: `make deploy-coverage` → `PASS`.
  - `make deploy-coverage` → `reachable AGS modules from dotfiles/config/ags/app.tsx: 95`,
    `deployed AGS sources in the manifest: 101`, `PASS`.
- [x] 6.2 Update the provisioning structural tests that pin the skeleton list
  (`test_compositor_configs_role.py`, `test_verify_role.py`), including the
  `_build_provisioned_layout` fixture.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.
  - `99 passed in 400.12s` (the compositor count is pinned at 116; the fixture
    writes the three new files and drops `network.tsx`).

## 7. Verify

- [x] 7.1 All gates green: `make ags-test` (fail 0, 0 type errors),
  `make ags-typecheck` (PASS), `make bar-typecheck` (OK), `make gates-ci`
  (exit 0), `make deploy-coverage` (PASS).
  - `make ags-test` → `tests 132, pass 132, fail 0`, `0 type errors`.
  - `make ags-typecheck` → `PASS (with GIR typings, 0 errors in the extracted
    bar tree …, 29 third-party, 44 in tests/, 0 exempt)`.
  - `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - `make gates-ci` → `GATES_CI_EXIT=0`.
  - `make deploy-coverage` → `PASS`.
  - Note: `wifi-mock-parity` (inside `gates-ci`) mapped the retired
    `bar/widgets/network.tsx`; the mapping was re-pointed at
    `bar/widgets/network-descriptor.tsx` (`PASS`, 103 tokens).
- [x] 7.2 The bundle resolves and the tree is clean.
  Verify: `ags bundle dotfiles/config/ags/app.tsx /tmp/w.js --gtk 4` → exit 0;
  `openspec validate migrate-widgets-to-shapes --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
  - `ags bundle dotfiles/config/ags/app.tsx /tmp/w.js --gtk 4` → exit 0.
  - `openspec validate migrate-widgets-to-shapes --type change` → valid.
  - `git status --porcelain` → empty after the implementation commit.

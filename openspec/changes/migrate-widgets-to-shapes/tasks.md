# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-bar-shapes/spec.md` with ADDED Requirements + Scenarios citing AD-8
  and AD-9 (and doc 101 §5, §13 step 6).
  Verify: `openspec validate migrate-widgets-to-shapes --type change` → valid.
  - `openspec validate migrate-widgets-to-shapes --type change` →
    `Change 'migrate-widgets-to-shapes' is valid`.

## 2. The layout vocabulary + the repo default (AD-9)

- [ ] 2.1 Add the pure `dotfiles/config/ags/kit/layout.ts`: `BarEntry`,
  `BarLayout` (sections, **no version field**), `LayoutProvider`, and
  `resolveLayout(providers, repoDefault)` (first non-null wins; never null).
  Verify: `grep -nE '^import .*(gi://|"ags")' dotfiles/config/ags/kit/layout.ts` → no matches.
  - `<fill in>`
- [ ] 2.2 Add `dotfiles/config/ags/bar/layout.default.ts`: the repo-default
  provider (always non-null) and the default `BarLayout` in today's order.
  Verify: `grep -n "repoDefaultLayout\|sections" dotfiles/config/ags/bar/layout.default.ts`.
  - `<fill in>`
- [ ] 2.3 Register `kit/layout.ts` and `bar/layout.default.ts` in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
  - `<fill in>`

## 3. The shape renderers (AD-8)

- [ ] 3.1 In `kit/widget.tsx`, add one shared `useShell` and a `BarWidget`
  dispatcher plus `RichWidget` (`content`), `Collection` (`items`/`key`/`item`)
  and `ForeignCollection` (`items`/`render`); re-point `BarWidgetButton` at
  `useShell` so the shell is implemented once.
  Verify: `grep -n "export function BarWidget\|export function RichWidget\|export function Collection\|export function ForeignCollection\|function useShell" dotfiles/config/ags/kit/widget.tsx`.
  - `<fill in>`
- [ ] 3.2 Add the optional `spacing` presentation hint to `CollectionSpec` /
  `ForeignCollectionSpec` in `kit/shapes.ts` (the shared `Shell` is unchanged).
  Verify: `make ags-test` → the `kit-shapes` suite still passes.
  - `<fill in>`

## 4. The widgets move onto the shapes (AD-8)

- [ ] 4.1 `clock.tsx` → `RichWidgetSpec` (two labels; timer unchanged).
  Verify: `grep -n "clockWidget: RichWidgetSpec" dotfiles/config/ags/bar/widgets/clock.tsx`.
  - `<fill in>`
- [ ] 4.2 `recording.tsx` → `RichWidgetSpec` (dot + timer + buttons; hub
  `control` through the injected context).
  Verify: `grep -n "createRecordingWidget\|RichWidgetSpec" dotfiles/config/ags/bar/widgets/recording.tsx`.
  - `<fill in>`
- [ ] 4.3 `workspaces.tsx` → `CollectionSpec` (items/key/item; the active class
  stays reactive).
  Verify: `grep -n "workspacesWidget: CollectionSpec" dotfiles/config/ags/bar/widgets/workspaces.tsx`.
  - `<fill in>`
- [ ] 4.4 `tray.tsx` → `ForeignCollectionSpec` (items/render); the recording
  indicator is no longer rendered by the tray.
  Verify: `grep -c "RecordingIndicator" dotfiles/config/ags/bar/widgets/tray.tsx` → `0`.
  - `<fill in>`
- [ ] 4.5 `network-descriptor.tsx` is wired; `network.tsx` is retired
  (deleted) and its two manifest entries removed.
  Verify: `test ! -e dotfiles/config/ags/bar/widgets/network.tsx` and
  `grep -rn "widgets/network\"" dotfiles/config/ags/bar`.
  - `<fill in>`
- [ ] 4.6 `battery.tsx` / `bluetooth.tsx` / `audio.tsx` become
  `DescriptorSpec`s (audio-output) with the audio **microphone** as a
  `RichWidgetSpec` (the live-dot badge is not expressible as a descriptor).
  Verify: `grep -n "DescriptorSpec" dotfiles/config/ags/bar/widgets/battery.tsx dotfiles/config/ags/bar/widgets/bluetooth.tsx dotfiles/config/ags/bar/widgets/audio.tsx`.
  - `<fill in>`
- [ ] 4.7 Add `bar/registry.ts` (entry id → spec) and re-point `Bar.tsx` at
  `resolveLayout([], repoDefaultLayout)` + `BarWidget`, removing the hardcoded
  composition.
  Verify: `grep -c "Workspaces\|Clock\|BatteryIndicator\|NetworkStatus" dotfiles/config/ags/bar/Bar.tsx` → `0`;
  `grep -n "repoDefaultLayout\|BarWidget" dotfiles/config/ags/bar/Bar.tsx`.
  - `<fill in>`

## 5. Tests prove the pure layout chain

- [ ] 5.1 Add `tests/ts/layout.test.ts`: whole-replacement chain (user ›
  runtime › repo-default), null providers skipped, repo default non-null, and
  the default layout's ids are unique.
  Verify: `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test dotfiles/config/ags/tests/ts/layout.test.ts` → `fail 0`.
  - `<fill in>`

## 6. Deploy registration (hard constraint)

- [ ] 6.1 Register `kit/layout.ts`, `bar/layout.default.ts` and
  `bar/registry.ts` in `compositor_configs_skeleton_files`; mirror all three in
  the verify role; remove the `bar/widgets/network.tsx` entry from both.
  Verify: `make deploy-coverage` → `PASS`.
  - `<fill in>`
- [ ] 6.2 Update the provisioning structural tests that pin the skeleton list
  (`test_compositor_configs_role.py`, `test_verify_role.py`), including the
  `_build_provisioned_layout` fixture.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.
  - `<fill in>`

## 7. Verify

- [ ] 7.1 All gates green: `make ags-test` (fail 0, 0 type errors),
  `make ags-typecheck` (PASS), `make bar-typecheck` (OK), `make gates-ci`
  (exit 0), `make deploy-coverage` (PASS).
  - `<fill in>`
- [ ] 7.2 The bundle resolves and the tree is clean.
  Verify: `ags bundle dotfiles/config/ags/app.tsx /tmp/w.js --gtk 4` → exit 0;
  `openspec validate migrate-widgets-to-shapes --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
  - `<fill in>`

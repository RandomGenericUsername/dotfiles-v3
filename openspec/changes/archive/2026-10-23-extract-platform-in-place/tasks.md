# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-platform-package/spec.md` with ADDED Requirements + Scenarios citing
  AD-1, AD-2, AD-17, AD-19 and AD-20 (and doc 101 §3, §13 step 8).
  Verify: `openspec validate extract-platform-in-place --type change` → valid.
  - `openspec validate extract-platform-in-place --type change` →
    `Change 'extract-platform-in-place' is valid`.

## 2. The package root + identity (AD-17, AD-20)

- [x] 2.1 Create the in-place package root `dotfiles/config/ags/platform/` with a
  `package.json` (name `ags-platform`, `exports` for the entry point and the
  port/adapter subpaths) and an `index.ts` public surface.
  Verify: `cat dotfiles/config/ags/platform/package.json` shows `"name": "ags-platform"` and an `exports` map.
  - `cat dotfiles/config/ags/platform/package.json` → `"name": "ags-platform"`,
    `"exports": { ".": "./index.ts", "./ports/*": "./ports/*.ts",
    "./adapters/*": "./adapters/*.ts" }`.
- [x] 2.2 Create the `ports/` and `adapters/` subdirectories.
  Verify: `test -d dotfiles/config/ags/platform/ports && test -d dotfiles/config/ags/platform/adapters`.
  - exit 0.

## 3. Move the ports (AD-4, AD-5, AD-11, AD-12, AD-13)

- [x] 3.1 `git mv` `platform/{event-client,preferences,notifier,theme}.ts` into
  `platform/ports/`; `kit/icon-source.ts` → `platform/ports/`; `domains/reactive.ts`
  → `platform/ports/`.
  Verify: `ls dotfiles/config/ags/platform/ports`.
  - `ls` → `event-client.ts icon-source.ts notifier.ts preferences.ts
    reactive.ts theme.ts` (6).
- [x] 3.2 Repoint the intra-package port imports
  (`../domains/reactive` → `./reactive`, `../kit/icon-source` → `./icon-source`).
  Verify: `grep -nE "gi://|\"ags" dotfiles/config/ags/platform/ports/*.ts` → no matches.
  - Only prose in `PURE:` comments matches; no port imports `gi://` or `ags`
    (verified by `grep -nE '^import'` on the six port files).

## 4. Move the adapters (AD-4, AD-5, AD-11, AD-12, AD-13)

- [x] 4.1 `git mv` `lib/{event-bus,preferences,notifier,theme,icon-registry}.ts`,
  `kit/icon.ts` and `domains/astal.ts` into `platform/adapters/`.
  Verify: `ls dotfiles/config/ags/platform/adapters`.
  - `ls` → `astal.ts event-bus.ts icon-registry.ts icon.ts notifier.ts
    preferences.ts theme.ts` (7).
- [x] 4.2 Repoint the intra-package adapter imports
  (`../domains/astal` → `./astal`, `../platform/<port>` → `../ports/<port>`,
  `../icons.json` → `../../icons.json`, `./icon-source` → `../ports/icon-source`).
  Verify: `grep -rn "\.\./platform/\|\.\./domains/\|\.\./lib/\|\.\./kit/" dotfiles/config/ags/platform` → no matches.
  - no matches.

## 5. Repoint the bar importers (AD-1, AD-20)

- [x] 5.1 Repoint every bar import of a moved seam at the package
  (`app.tsx`, `bar/registry.ts`, `bar/widgets/*`, `components/*`,
  `settings-panel/controls/*`, `services/*`, `kit/widget.tsx`, `kit/shapes.ts`,
  `domains/<domain>/*`).
  Verify: `grep -rn "lib/event-bus\|lib/theme\|lib/preferences\|lib/notifier\|lib/icon-registry\|kit/icon\b\|domains/reactive\|domains/astal" dotfiles/config/ags --include=*.ts --include=*.tsx` → no matches.
  - no matches (exit 1).
- [x] 5.2 Prove the direction: the package imports no bar/app module and the bar
  does not import another app.
  Verify: `grep -rnE "\.\./(bar|components|settings-panel|services|audio|domains)/" dotfiles/config/ags/platform` → no matches;
  `grep -rn "gui-tools" dotfiles/config/ags/platform` → no matches.
  - both → no import matches (`gui-tools` appears only in two explanatory
    comments in `ports/event-client.ts`).

## 6. Repoint the pure test project (AD-2, AD-19)

- [x] 6.1 Update the test imports and the `tests/tsconfig.tests.json` explicit
  purity list to the new port paths.
  Verify: `grep -n "platform/ports" dotfiles/config/ags/tests/tsconfig.tests.json`.
  - `platform/ports/{icon-source,event-client,preferences,notifier,theme,reactive}.ts`
    are listed; `domains/reactive.ts` and `kit/icon-source.ts` are removed.
- [x] 6.2 `make ags-test` → `fail 0` and `OK: 0 type errors`.
  Verify: `make ags-test`.
  - `tests 132, pass 132, fail 0`; `OK: 0 type errors in the ags pure-module
    unit tests`.

## 7. Deploy registration (AD-17, AD-19)

- [x] 7.1 Register every new/relocated package file in
  `compositor_configs_skeleton_files`; declare `ags/platform/ports` and
  `ags/platform/adapters` as destination dirs; remove the stale entries for the
  moved sources.
  Verify: `make deploy-coverage` → `PASS`.
  - `deploy-coverage: reachable AGS modules from dotfiles/config/ags/app.tsx: 95`,
    `deployed AGS sources in the manifest: 103`, `PASS`. The manifest has 118
    sources and no entry points at a missing file.
- [x] 7.2 Mirror the changes in the verify role
  (`verify_compositor_skeleton_files`) and update the provisioning structural
  tests (`test_compositor_configs_role.py`, `test_verify_role.py`).
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.
  - `99 passed in 448.92s` (the count is pinned at 118; the
    `_build_provisioned_layout` fixture places every new package file and drops
    the moved sources).

## 8. Verify (AD-19)

- [x] 8.1 All gates green: `make ags-test`, `make ags-typecheck`,
  `make bar-typecheck`, `make gates-ci`, `make deploy-coverage`.
  - `make ags-test` → `tests 132, pass 132, fail 0`, `0 type errors`.
  - `make ags-typecheck` → `PASS (… 0 errors in the extracted bar tree …,
    29 third-party, 44 in tests/, 0 exempt)`.
  - `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - `make gates-ci` → `GATES_CI_EXIT=0`.
  - `make deploy-coverage` → `PASS`.
- [x] 8.2 The bar bundles; the change is valid; the tree is clean.
  Verify: `ags bundle dotfiles/config/ags/app.tsx /tmp/extract.js --gtk 4` → exit 0;
  `openspec validate extract-platform-in-place --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
  - `ags bundle dotfiles/config/ags/app.tsx /tmp/extract.js --gtk 4` →
    `BUNDLE_EXIT=0` (2 478 580 bytes emitted).
  - `openspec validate extract-platform-in-place --type change` → valid.
  - `git status --porcelain` → empty after the implementation commit.

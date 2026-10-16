# Tasks — ags-remove-bar-bridge

Planning only. Every tick names the command run and the observed result; nothing
is ticked from reading a diff. Slices are ordered so the repo is green after each
one and the tree is deleted only after every gate that reads it is retired or
repointed.

Preconditions for the whole change: `ags-apps/bar` exists and is the pinned unit
(`git -C /home/inumaki/Development/ags-apps tag | grep bar-v0.1.0`), and
`cd /home/inumaki/Development/ags-apps && make gates-ci` is green.

## 0. Freeze the duplicate (no code)

- [ ] 0.1 Prove the two trees are the same tree, so deletion loses nothing.
  Verify: `git ls-files dotfiles/config/ags | wc -l` → 115;
  `git -C /home/inumaki/Development/ags-apps ls-files bar | wc -l` → 115;
  `diff -rq dotfiles/config/ags /home/inumaki/Development/ags-apps/bar --exclude=node_modules --exclude=@girs --exclude=tsconfig.json` → no differences.
- [ ] 0.2 Record the ags-apps gate baseline the retirement leans on.
  Verify: `cd /home/inumaki/Development/ags-apps && make gates-ci` → exit 0
  (`bar-typecheck`/`ags-test` live at `ags-apps/Makefile:88,143`).

## 1. Rewrite `deploy-coverage` so it no longer requires the in-repo entry

This is the **only** gate that cannot simply be deleted: it hard-requires
`dotfiles/config/ags/app.tsx` (`scripts/deploy-coverage.py:452,459`). It must be
made to assert the provisioning shape without the tree, while keeping the
assertions that are still meaningful here.

- [ ] 1.1 Drop the `relative_import_closure` / entry-existence requirement from
  `scripts/deploy-coverage.py` (`:92-94,183-199,452,459`). Keep, unchanged:
  `assert_no_per_file_bar_skeletons` (`:316-332`), the retired-`platform/`-dir
  check (`:463-468`), `assert_platform_provisioning` (`:231-313`),
  `assert_bar_provisioning` (`:335-440`). The closure report becomes a note, not
  a precondition.
  Verify (tree still present): `make deploy-coverage` → exit 0, output still
  contains `PASS -- the retired bar bridge carries no per-file deploy source`.
  Verify (tree absent, simulate): `mv dotfiles/config/ags /tmp/ags-bak &&
  make deploy-coverage; mv /tmp/ags-bak dotfiles/config/ags` → exit 0.
- [ ] 1.2 Update `TestDeployCoverageGate`
  (`src/provisioning/tests/unit/test_compositor_configs_role.py:1001-1091`):
  `test_gate_passes_on_the_real_tree` must pass with no in-repo `app.tsx`; the
  two hermetic negative tests keep their synthetic trees and their `_AGS`
  symlink input (`:1015`).
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py -q` → pass.

## 2. Retire the bar dev gates that already exist in `ags-apps`

- [ ] 2.1 Delete `bar-typecheck` (`Makefile:448-501`), `ags-typecheck`
  (`Makefile:663-675`), `ags-test` / `ags-test-deps` (`Makefile:263-334`), the
  `BAR_DIR` var (`Makefile:388`), `AGS_TESTS`/`AGS_TS_TESTS`/`AGS_TSCONFIG_TESTS`
  (`Makefile:275-277`), and `tsconfig.ags.json` + `scripts/ags-typecheck.py`.
  Verify: `rg -n 'bar-typecheck|ags-typecheck|ags-test|dotfiles/config/ags' Makefile scripts/ags-typecheck.py tsconfig.ags.json` → no matches.
- [ ] 2.2 Drop them from `GATES` (`Makefile:46-55`) and from the `gates-ci`
  filter (`Makefile:78`, leaving `capture-typecheck`), and delete the
  `ags-test`/`ags-typecheck`/`bar-typecheck` jobs
  (`.github/workflows/gates.yml:221,381,403`).
  Verify: `rg -n 'bar-typecheck|ags-typecheck|ags-test' .github/workflows/gates.yml Makefile` → no matches.
- [ ] 2.3 Update `scripts/ci-gates-parity.py:121-141`: delete the
  `bar-typecheck`/`ags-typecheck` `CI_SELF_HOSTED_GATES` entries (the gates no
  longer exist here); keep `CI_EXCLUDED_GATES = {capture-typecheck}`.
  Verify: `make ci-gates-parity` → exit 0; `make gates-ci` → exit 0.

## 3. Retire the bar-only parity / audio / symbol gates

Each of these reads `dotfiles/config/ags/**` and belongs to the bar's repo.

- [ ] 3.1 Delete `icons-json-drift` (`Makefile:531-550`) + `scripts/icons-json-drift.py`.
- [ ] 3.2 Delete the five `*-mock-parity` targets
  (`Makefile:503-504,515-516,525-526,528-529,660-661`) + their scripts.
- [ ] 3.3 Delete the seven `audio-*-test` targets, `audio-panel-gates`, and
  `AUDIO_VALIDATION` (`Makefile:683-711`), and the
  `openspec/changes/redesign-ags-audio-panel/validation/*.mjs` inputs.
- [ ] 3.4 Delete `speedtest-no-new-architecture` (`Makefile:603-604`) +
  `scripts/speedtest-no-new-architecture.py` (or rewrite it to assert only the
  `notifications` consumer; decide at implementation).
- [ ] 3.5 Remove `ags-symbol-check.mjs` from `PER_APP_SUITES`
  (`Makefile:358-362`) and delete `src/gui-tools/icon-color-mapping-editor/tests/ags-symbol-check.mjs`
  + `mpris-core.test.mjs` (the latter imports `dotfiles/config/ags/services/mpris-core.ts`).
- [ ] 3.6 Remove the corresponding CI jobs (`.github/workflows/gates.yml`:
  `75,83,93,111,173,181,275,292,303,314,325,336,347,358`) and reconcile
  `ci-gates-parity` (`make ci-gates-parity` names any drift).
  Verify: `make gates-ci` → exit 0; `make ci-gates-parity` → exit 0;
  `rg -n 'config/ags' scripts/*.py` → only `sync-icons-manifest.py:46` (deployed
  spine path, stays) and `contract-pin-check.py:62` (handled in §5).

## 4. Delete the in-repo bar source

- [ ] 4.1 `git rm -r dotfiles/config/ags` (115 tracked files).
  Verify: `test ! -e dotfiles/config/ags` → exit 0;
  `git ls-files dotfiles/config/ags | wc -l` → 0.
- [ ] 4.2 Confirm nothing left in the repo requires the tree.
  Verify: `rg -n 'dotfiles/config/ags' -g '!openspec/changes/**' -g '!_bmad-output/**' -g '!docs/**' .`
  → only references scheduled for §5/§6.

## 5. Repoint the remaining references

- [ ] 5.1 `scripts/contract-pin-check.py:62`: drop the `TS_VENDORED` half (the
  bar's `lib/generated/contract.ts` moves to `ags-apps`); the Python/JSON-schema
  halves stay.
  Verify: `python3 scripts/contract-pin-check.py` → exit 0 (skip message where the
  `contracts` sibling is absent, as today).
- [ ] 5.2 `Makefile` `ags-platform-dev` (`:419-439`): delete the
  `$(BAR_DIR)/node_modules/ags-platform` link (`:431-432`); keep the repo-root
  shortcut (`:437-438`) that `per-app-drift-symbol-suites` needs.
  Verify: `make per-app-drift-symbol-suites` → exit 0.
- [ ] 5.3 `.gitignore:22-23,59-60`: delete the `dotfiles/config/ags` artifact
  entries.
  Verify: `rg -n 'dotfiles/config/ags' .gitignore` → no matches.

## 6. Update the provisioning tests, `AGENTS.md`, and docs

- [ ] 6.1 `src/provisioning/tests/unit/test_compositor_skeleton_configs.py`:
  delete `TestAgsSkeleton` (`:132-149`) and the `_AGS_APP`/`_AGS_CSS` uses in
  `TestSkeletonsAreStatic` (`:206-224`), including the `(_CONFIG_DIR/"ags").is_dir()`
  assertion (`:223`). Keep hypr/hyprpaper/rofi.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_skeleton_configs.py -q` → pass.
- [ ] 6.2 `src/provisioning/tests/unit/test_gui_tools_role.py:810-812`: drop the
  `dotfiles/config/ags/app.tsx` read (the bar-manifest assertion is owned by
  `ags-apps`); keep the autostart + keybind assertions.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_gui_tools_role.py -q` → pass.
- [ ] 6.3 `AGENTS.md` §2: rewrite the bar clause — the bar deploys **whole** via
  the pinned `ags_apps` unit, so there are no per-file bar sources to register;
  keep the registration rule for the non-bar skeletons and `gui_tools_*_app_files`;
  state that `deploy-coverage` asserts the **absence** of a stale per-file bar
  entry. Update the gate list to the post-removal set.
  Verify: `rg -n 'register every new bar source|New bar source files' AGENTS.md`
  → no stale claim.
- [ ] 6.4 Update the docs (group I in the proposal) to say the bar source lives
  in `ags-apps`, not `dotfiles/config/ags`. The runtime consumer path
  `<install>/config/ags/colors.css` is unchanged.
  Verify: `rg -n 'dotfiles/config/ags' docs/` → only historical/point-in-time
  mentions, each annotated.
- [ ] 6.5 Full green.
  Verify: `make deploy-coverage` → exit 0; `make gates-ci` → exit 0;
  `uv run --directory src/provisioning pytest tests/unit -q` → pass.

## 7. Required companions in `ags-apps` (NOT this repo)

These are recorded so the retirement does not silently lose coverage; they are
out of scope here.

- [ ] 7.1 Re-home `icons-json-drift` in `ags-apps` (its committed
  `bar/icons.json` is now the only committed manifest).
- [ ] 7.2 Re-home the five `*-mock-parity` gates and the seven audio validation
  suites in `ags-apps`.
- [ ] 7.3 Re-home `ags-symbol-check.mjs` (its `ROOT` was `dotfiles/config/ags`)
  and the `contract.ts` pin check.
- [ ] 7.4 `ags-apps` runs `bar-typecheck` + `ags-test` + the re-homed gates on
  its own CI before the `bar-v0.1.0` pin can move.

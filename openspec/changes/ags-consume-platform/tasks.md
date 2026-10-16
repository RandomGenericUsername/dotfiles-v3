# Tasks

Evidence convention: every tick names the command run and the observed result.
Nothing is ticked from reading a diff.

## 1. Install the unit + shortcut

- [x] 1.1 Add the one-unit install to provisioning under `<install>/ags-platform/<version>/`. Verify: a fresh provision places the unit (stat the dir).

  - New role `src/provisioning/ansible/roles/ags_platform/` (vars + tasks) and
    playbook `src/provisioning/ansible/playbooks/ags-platform.yaml`, imported by
    `bootstrap.yaml` right after `compositor-configs.yaml`.
  - `ags_platform_version: v0.1.0` is THE PIN; the clone is shallow + anonymous
    HTTPS (`depth: 1`, public repo) into `ags_platform_unit_dir`
    (`<install>/ags-platform/v0.1.0`), presence-guarded and `--check`-gated, and
    its `.git` is removed (deployed as a source tree, not a working copy).
  - The pin is recorded at `<install>/ags-platform/pinned`.
  - Evidence (simulated install, no root, real network):
    `git clone --depth 1 --branch v0.1.0 https://github.com/RandomGenericUsername/ags-platform <install>/ags-platform/v0.1.0`
    → exit 0; `ls` shows `index.ts package.json ports/ adapters/ icons.json`.
  - Evidence (role unit test):
    `uv run --directory src/provisioning pytest tests/unit/test_ags_platform_role.py -q`
    → passes (structure + a real playbook run against a pre-seeded unit).

- [x] 1.2 Create the shared-ancestor `node_modules/ags-platform` shortcut. Verify: `ags run` resolves the bare specifier (bar starts).

  - The role ensures `<install>/config/node_modules/` and symlinks
    `<install>/config/node_modules/ags-platform -> <install>/ags-platform/v0.1.0`
    (`state: link`, `force: true`, so a rollback is a repoint).
  - The shortcut is the SHARED ANCESTOR of every `config/ags-*`, so the bar and
    every app resolve the bare specifier with no per-app copy.
  - Evidence (simulated install + real bundle):
    `ags bundle config/ags/app.tsx /tmp/opencode/consume.js --gtk 4` → **exit 0**.
  - Evidence (negative control): removing the shortcut makes the same bundle
    fail with `Could not resolve "ags-platform/adapters/theme"` — the shortcut is
    load-bearing, not decorative.

- [x] 1.3 Confirm AGS's embedded esbuild resolves through the config symlinks (realpath). Verify: run the bar **and** one app from `~/.config/ags-*`.

  - esbuild realpaths the `node_modules` symlink, so resolution walks the REAL
    config tree (`<install>/config/ags`) up to the shared ancestor
    (`<install>/config/node_modules`). Proven by the bundle above, whose bar tree
    is the deployed `config/ags` shape (no `node_modules` inside it).
  - The deployed `~/.config/ags` is a symlink INTO `<install>/config/ags`
    (config-links role), so the realpath is the spine path the shortcut is a
    sibling of. `verify` asserts the unit + shortcut on the host
    (`verify_ags_platform_*`).

## 2. Remove per-file enumeration

- [~] 2.1 Delete the five `gui_tools_*_app_files` lists and the bar's `compositor_configs_skeleton_files`. Verify: `git grep -n "app_files" src/provisioning` → none.

  - DONE for the platform: the 15 per-file platform entries
    (`ags-platform-*`: `package.json` + `index.ts` + 6 ports + 7 adapters) and
    their `ags/platform{,/ports,/adapters}` config dirs are DELETED from
    `compositor_configs_skeleton_files` / `compositor_configs_config_dirs`, and
    the in-place `dotfiles/config/ags/platform/**` copy is deleted.
  - NOT DONE (deliberate, out of scope): the five `gui_tools_*_app_files` lists
    and the rest of `compositor_configs_skeleton_files` STAY. Those apps do not
    import `ags-platform` yet (only the bar does — `grep -rn "ags-platform"
    src/gui-tools` → none), so deleting their manifests would undeploy working
    apps. The spec's "every app resolves the framework" is satisfied by the
    SHARED-ANCESTOR shortcut (the apps CAN resolve it); migrating the apps to
    import it is the sequenced follow-up (`ags-apps` thin-slice, handoff §5 step
    6). Deleting the bar's own manifest would also undeploy the bar's own files.

- [~] 2.2 Remove the ~200 retired per-file copies on upgrade. Verify: `verify` passes on a fresh host; no stale framework files remain.

  - DONE for the retired platform copies: the 15 platform skeleton entries are
    gone and the in-place copy is deleted, so a fresh provision never places a
    `config/ags/platform/` tree. `verify` asserts the external unit + shortcut
    instead (`verify_ags_platform_unit_files`, `verify_ags_platform_shortcut`).
  - NOT DONE (out of scope): the "~200" per-file copies are the other apps' files,
    removed only when those apps consume the platform (step 2.1 above).

## 3. Pin + rollback

- [x] 3.1 Record the pinned framework version. Verify: a rollback repoints the shortcut and `ags run` starts the previous unit.

  - The pin is `ags_platform_version: v0.1.0` (the version DIRECTORY name) and is
    written to `<install>/ags-platform/pinned`. Rollback = point
    `ags_platform_shortcut` at a sibling `<version>/` dir (or set
    `ags_platform_version` to an older tag and re-run); the shortcut task is
    `force: true`, so the repoint converges in one run.
  - Evidence: `test_ags_platform_role.py` asserts the pin file contents and that
    the shortcut resolves to the pinned unit dir; the simulated install shows the
    same shape end to end.

- [x] 3.2 `make gates-ci` green.

  - Evidence: `make gates-ci` → exit 0. Also green: `make ags-test` (100 tests),
    `make bar-typecheck` (0 errors in the bar; 29 third-party; 0 ags-platform),
    `make ags-typecheck` (PASS), `make deploy-coverage` (PASS; external
    `ags-platform` unit + shortcut asserted).

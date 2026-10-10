# Tasks

## 1. Install the unit + shortcut

- [ ] 1.1 Add the one-unit install to provisioning under `<install>/ags-platform/<version>/`. Verify: a fresh provision places the unit (stat the dir).
- [ ] 1.2 Create the shared-ancestor `node_modules/ags-platform` shortcut. Verify: `ags run` resolves the bare specifier (bar starts).
- [ ] 1.3 Confirm AGS's embedded esbuild resolves through the config symlinks (realpath). Verify: run the bar **and** one app from `~/.config/ags-*`.

## 2. Remove per-file enumeration

- [ ] 2.1 Delete the five `gui_tools_*_app_files` lists and the bar's `compositor_configs_skeleton_files`. Verify: `git grep -n "app_files" src/provisioning` → none.
- [ ] 2.2 Remove the ~200 retired per-file copies on upgrade. Verify: `verify` passes on a fresh host; no stale framework files remain.

## 3. Pin + rollback

- [ ] 3.1 Record the pinned framework version. Verify: a rollback repoints the shortcut and `ags run` starts the previous unit.
- [ ] 3.2 `make gates-ci` green.

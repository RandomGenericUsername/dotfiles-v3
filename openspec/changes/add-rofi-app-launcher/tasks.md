## 1. Runtime: `colors.rasi` becomes the sixth palette artifact

- [ ] 1.1 `src/runtime/src/runtime/adapters/csg_adapter.py` — add `--format rasi` to the args list (after `sequences`, ~L292); add `"colors.rasi"` to the post-run artifact verify set (~L348); hash it: `colors_rasi=hash_file(output_dir / "colors.rasi")` (~L363)
- [ ] 1.2 `src/runtime/src/runtime/domain/models.py` — `PaletteArtifacts` TypedDict gains `colors_rasi: str  # key: "colors.rasi"` (models.py:49-56)
- [ ] 1.3 `src/runtime/src/runtime/application/derive.py` — `PALETTE_ARTIFACT_NAMES` tuple gains `"colors.rasi"` (derive.py:247); the meta `artifact_hashes` dict gains `"colors.rasi": generated.artifact_hashes["colors_rasi"]` (~L382)
- [ ] 1.4 `src/runtime/src/runtime/adapters/seeder.py` — `write_palette_meta_in` parse gains `colors_rasi=artifact_hashes["colors.rasi"]` (seeder.py:430-434); `repoint_current_symlinks` palette tuple gains `"colors.rasi"` (seeder.py:557-563) so `current/colors.rasi` is repointed
- [ ] 1.5 `src/runtime/src/runtime/application/reconcile.py` — the three pinned tuples each gain `"colors.rasi"`: `_derive_skipped` (~L451), `_cleanup_stale_symlinks` (~L492), `_build_expected_targets` (~L551)
- [ ] 1.5a `src/runtime/src/runtime/application/inspect.py` — the palette `targets` tuple (L323-329) gains `"colors.rasi"` so inspect reports the artifact in the current layer
- [ ] 1.5b Docstring-only artifact lists (no behavior): `ports/color_scheme_generator.py:19` and `adapters/cache.py:128` list the five names — update to six for accuracy (no logic change)
- [ ] 1.6 `src/runtime/src/runtime/adapters/json_state_repository.py` — sentinel-shape dict gains `"colors_rasi": SENTINEL_HASH` (~L359)
- [ ] 1.7 Update runtime tests for the six-artifact set: every `PaletteEntry`/`PaletteArtifacts` constructor across `src/runtime/tests/unit/` (test_seed_cache, test_json_state_repository, test_reconcile, test_cli_reconcile, test_crash_recovery, test_apply_wallpaper, test_inspect, test_ags_reloader, test_hyprland_reloader, test_hyprpaper_reloader) and `src/runtime/tests/integration/` fixtures; add rasi to csg-adapter, seeder, reconcile, inspect, seed_cache expectations
- [ ] 1.8 Verify migration: `ensure_palette_entry_complete` (derive.py) evicts a five-artifact legacy entry and regenerates — existing test covers the mechanism; add an explicit five→six regression case if absent

## 2. Runtime: consumer pointer at the rofi root

- [ ] 2.1 `src/runtime/src/runtime/adapters/consumer_path_spec.py` — `consumer_pointers()` gains `ConsumerPointer(path="config/rofi/colors.rasi", target="colors.rasi")` (after gtk-4.0, consumer_path_spec.py:28-30); update the module docstring table
- [ ] 2.2 `src/runtime/tests/unit/test_seed_cache.py` — extend the consumer-pointer assertions to include the rofi pointer (the existing `test_custom_spec_is_consumed_generically` already proves the loop consumes any spec; add rofi to the real-spec test and assert the target is `colors.rasi`)
- [ ] 2.3 `src/runtime/tests/unit/test_inspect.py` + integration — `inspect` status surfaces the new pointer healthy (create-parent rule: present only once the spine dir exists)

## 3. Launcher config (authored skeleton — measured-fidelity theme)

- [ ] 3.1 Create `dotfiles/config/rofi/launcher/config.rasi` — static, NO `.j2`/`.tpl` suffix (template-suffix guard in `test_compositor_skeleton_configs.py`); contains `@import "../colors.rasi"` + `configuration { modes: "drun"; font: "JetBrainsMono Nerd Font 12"; show-icons: true; display-drun: …; drun-display-format: "{name}" }` + theme block
- [ ] 3.2 Theme per the measured reference (design.md D6): `window { transparency: "real"; location: center; width: 548px; border: 4px; border-color: @color04; background-color: @color01; padding: 2px; border-radius: 12px; }` — `transparency: "real"` makes the area outside the border transparent (no dim, wallpaper shows through); the 2px `window` padding zone shows `@color01` as the ring between border and body; `mainbox { background-color: @background; border-radius: 8px; padding: 18px 18px 14px; spacing: 21px; }`; `inputbar { background-color: @color01; border-radius: 5px; padding: …; }` 38px tall with magnifier prompt + `entry` placeholder; `listview { lines: 8; spacing: 0; scrollbar: false; }`; `element { height: 36px; border-radius: 5px; padding-left: 25px; }`; `element-icon { size: 24px; }`; `element selected.normal { background-color: @color10; text-color: @background; }`; `element normal.normal { text-color: @foreground; }`; placeholder `@color07` (G5-tunable)
- [ ] 3.3 Host sanity check: `rofi -config ~/.config/rofi/launcher/config.rasi -dump-theme` exit 0 with a live palette present (parse-only; no window); verify the transparent-window + border/ring realization parses (`window { transparency: "real"; border: 4px @color04; background-color: @color01; padding: 2px; }` + `mainbox` `@background`) — probe already validated at plan time
- [ ] 3.4 Guard test: skeleton has no `{{ }}` Jinja collisions (file is plain rasi; `@import`/rasi `@var` syntax is not Jinja)
- [ ] 3.5 Layer-overlay verification (D7): launch the launcher on the live session, confirm `hyprctl layers` shows a rofi overlay surface and `window-rules.lua` needs no rofi entry; confirm no `-normal-window` flag anywhere

## 4. Provisioning: packages manifest + group_vars

- [ ] 4.1 `dotfiles/provisioning/packages.yaml` — replace the `wofi` entry with `rofi` (keep the `# Application launcher` comment)
- [ ] 4.2 `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` — update the expected package set: `"wofi"` → `"rofi"` (line ~358)
- [ ] 4.3 `src/provisioning/ansible/group_vars/arch.yml` — add `rofi: rofi` to the `packages` map (near `wlogout` / launcher-adjacent entries)
- [ ] 4.4 `src/provisioning/ansible/group_vars/debian-family.yml` — add `rofi: rofi` to the `packages` map (same logical name; symmetry per NFR-3)
- [ ] 4.5 `src/provisioning/tests/unit/test_packages_role.py` — confirm value-shape tests still pass with the new entry; add explicit arch assertion `arch["packages"]["rofi"] == "rofi"` if the test suite pattern calls for it

## 5. Provisioning: compositor_configs + config-links + verify

- [ ] 5.1 `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` — `compositor_configs_config_dirs` gains `config/rofi` and `config/rofi/launcher`; `compositor_configs_skeleton_files` gains `{ name: rofi-launcher-config-rasi, source: dotfiles/config/rofi/launcher/config.rasi, dest: {{ spine }}/rofi/launcher/config.rasi }`
- [ ] 5.2 `src/provisioning/tests/unit/test_compositor_configs_role.py` — skeleton count 26 → 27 and the `expected` source list gains `dotfiles/config/rofi/launcher/config.rasi`; config-dirs list updated
- [ ] 5.3 `src/provisioning/ansible/roles/config_links/vars/main.yml` — `config_links_managed_dirs` gains `rofi` (NOT in `config_links_gtk_dirs`)
- [ ] 5.4 `src/provisioning/ansible/roles/verify/vars/main.yml` — `verify_managed_link_dirs` gains `rofi` (parity-EXACT with config_links, enforced by `test_managed_dirs_parity_with_verify`)
- [ ] 5.5 `src/provisioning/tests/unit/test_config_links_role.py` + `test_verify_role.py` — parity + membership updated for `rofi`
- [ ] 5.6 `src/provisioning/tests/unit/test_compositor_skeleton_configs.py` — `_EXISTING_DIRS_KNOWN_FILES` gains `"rofi": ("launcher/config.rasi",)`; the no-template-suffix guard covers the new file
- [ ] 5.7 Docs coordination: `docs/99-dotfiles-hexagonal-architecture.md` launcher row (`wofi` → `rofi`, line ~1228); `_bmad-output/planning-artifacts/architecture/…/shared-data-contract.md` — palette artifact set line (~75/~141/~171) gains `colors.rasi`, consumer table (~160-163) gains the rofi pointer row

## 6. Keybinding

- [ ] 6.1 `dotfiles/config/hypr/keybindings.lua:29` — `hl.dsp.exec_cmd("wofi --show drun")` → `hl.dsp.exec_cmd("rofi -config ~/.config/rofi/launcher/config.rasi -show drun")`; comment updated to `Open application launcher (rofi)`
- [ ] 6.2 Update any keybinding-locking test/fixture that asserts the command string
- [ ] 6.3 NO window rule added (D7): confirm `window-rules.lua` is untouched by this change. Note in a comment/commit message that if `-normal-window` is ever adopted later, a float + center + size rule becomes necessary — deferred, not built

## 7. Verification & acceptance gates (G1–G6)

- [ ] 7.1 **G1**: `pytest src/runtime/tests` green (ruff/mypy on edited runtime files)
- [ ] 7.2 **G2**: `pytest src/provisioning/tests` green (ruff/mypy on edited provisioning files)
- [ ] 7.3 **G3** real-machine provisioning: `assets` + `compositor-configs` playbooks against `install_dir=$HOME/.local/share/dotfiles`; re-run idempotent; assert `~/.config/rofi/launcher/config.rasi` resolves through the spine and `~/.config/rofi` is a spine symlink
- [ ] 7.4 **G4** runtime on host (session env): reconcile/`wallpaper set` → `current/colors.rasi` exists (symlink to six-artifact cache entry), `<install>/config/rofi/colors.rasi` → `current/colors.rasi`; `dotfiles-runtime inspect` shows the pointer healthy
- [ ] 7.5 **G5** live launch + palette pickup: `SUPER+D` opens the themed launcher; `wallpaper set <other>` then relaunch → colors follow; **fidelity pass** against the reference geometry at 1x (panel-sized 548px centered window over the live wallpaper, no dim; 4px border + 2px ring; searchbar 38px; rows 36px; 24px icons; radius 12/5px; no Hyprland rule needed — `hyprctl layers` shows the overlay) — correct any deviation in `launcher/config.rasi`
- [ ] 7.6 **G6** future-tool extensibility review: confirm adding a second rofi tool = new subdir + one skeleton entry, no runtime edits
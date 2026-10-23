## 1. `btop_config` role

<!-- IMPLEMENTATION NOTES (deviations from the spec as written) -->
<!-- 1.1-1.4: `color_theme` is `colors.btop-minimal.theme`, NOT the spec's -->
<!-- `csg-minimal.theme`. The consumer pointers place files named -->
<!-- `colors.btop-<difficulty>.theme` (task 2.1's own names) and btop matches -->
<!-- `color_theme` against the DISCOVERED entries by full path / filename / -->
<!-- stem (btop_theme.cpp:451-471). `csg-minimal.theme` matches none of those, -->
<!-- so it would silently fall back to Default_theme — the exact failure this -->
<!-- integration exists to prevent. The spec's own task 5.6 negative control -->
<!-- would have caught it. -->
<!-- 5.7: driven at the seeder's layer (repoint `current/` at a new cache entry -->
<!-- and re-place the pointers = verbatim `repoint_consumer_symlinks`), not by -->
<!-- shelling out to `dotfiles-runtime wallpaper set` — the CSG btop backends -->
<!-- that command needs are a SIBLING change absent from this worktree. -->
<!-- 5.8: btop must be ended with SIGINT, not SIGTERM — measured against btop -->
<!-- 1.4.7, SIGTERM skips the atexit config write, which would make the hash -->
<!-- assertion pass for the wrong reason. The negative control (setting flipped -->
<!-- to `true`) requires the hash to CHANGE. -->
<!-- 5.10: `config/btop` is deliberately absent from `verify_install_spine_dirs` -->
<!-- (that list is parity-EXACT with `filesystem_spine_dirs`, which the -->
<!-- filesystem role does not own for btop); it is asserted via -->
<!-- `verify_btop_spine_dir` / `verify_btop_themes_dir` instead. -->

- [x] 1.1 `roles/btop_config/vars/main.yml` — `btop_config_spine_dir` (`<install>/config/btop`), `btop_config_spine_themes_dir` (`…/btop/themes`), `btop_config_xdg_config_home`, and the `install_dir | trim` / `ansible_facts.env` F4 locks, mirroring `kitty_config/vars/main.yml` exactly
- [x] 1.2 `roles/btop_config/templates/btop.conf.j2` — managed header + `color_theme = "csg-minimal.theme"` + `save_config_on_exit = false`; every other setting at btop's stock default
- [x] 1.3 `roles/btop_config/tasks/main.yml` — fail-loud `install_dir` assert first; `state: directory` for `…/btop` **and `…/btop/themes`** (required by D4 — the seeder never mkdirs into the spine); render `btop.conf`; no `become`
- [x] 1.4 Role unit tests: rendered `btop.conf` contains `color_theme = "csg-minimal.theme"` and `save_config_on_exit = false`; no `install_dir | default(` fallback; both directories are ensured

## 2. Consumer pointers for the three themes

- [x] 2.1 `adapters/consumer_path_spec.py` — add three pointers: `config/btop/themes/colors.btop-minimal.theme` → `colors.btop-minimal.theme`, and likewise for `balanced` and `full`
- [x] 2.2 **Coordinate, never re-decide** — this table is contract data transcribed verbatim in `shared-data-contract.md` (per the module docstring). Update the contract doc in the same change
- [x] 2.3 Update the `repoint_consumer_symlinks` docstring and the pinned-table comment listing the four existing entries
- [x] 2.4 Tests: the three new pointers are created; a missing `current/` target is skipped with a warning; a missing destination parent is skipped (never mkdir'd)

## 3. Wiring into provisioning

- [x] 3.1 `playbooks/btop-config.yaml` + import into `bootstrap.yaml` beside `kitty-config.yaml`, before `config-links.yaml`
- [x] 3.2 `config_links/vars/main.yml` — add `btop` to `config_links_managed_dirs`
- [x] 3.3 `verify/vars/main.yml` — add `btop` to `verify_managed_link_dirs` (**must match 3.2 exactly** — `test_verify_managed_link_dirs` compares the lists)
- [x] 3.4 Packages — `btop` is already in `group_vars/arch.yml:100` and `group_vars/debian-family.yml:87`; confirm both, add if either is missing
- [x] 3.5 `filesystem` — confirm `~/.config/btop` needs no separate entry (config_links creates the link; the role creates the spine dir)
- [x] 3.6 `verify/vars/main.yml` — assert: `btop.conf` exists; `color_theme` is `csg-minimal.theme`; `save_config_on_exit` is `false`; `…/btop/themes/` exists; all three theme files present (extend `verify_palette_files` at `:366-372` and add a config-file assertion)
- [x] 3.7 Parity/verify role tests updated for the new role and managed dir

## 4. Documentation

- [x] 4.1 Note in the role docs that `save_config_on_exit = false` is mandatory (btop would otherwise truncate the spine-owned config through the symlink on exit — `btop_config.cpp:379`, `:836-845`)
- [x] 4.2 Record the reload deferral explicitly: the theme applies on the next btop launch; no running instance is disturbed
- [x] 4.3 Fold in the pre-existing doc drift: `docs/99-dotfiles-hexagonal-architecture.md:340` says 3 formats (it is now 10) and `ARCHITECTURE_PLAN.md:32` omits `KITTY`

## 5. End-to-end verification — all machine-checkable, no eyes required

The theme-application assertions reuse the harness proven in
`add-csg-btop-theme-formats` (`assert_theme_applies.py`): btop's DEBUG log must
name our file, and the captured pty frame must carry our colours with zero
`Default_theme` colours present.

- [x] 5.1 `uv run --directory src/provisioning pytest` green
- [x] 5.2 `make contracts-check` green
- [x] 5.3 **Config assertions, no launching:** assert the rendered `btop.conf` contains `color_theme = "csg-minimal.theme"` and `save_config_on_exit = false`, and that every other key equals btop's stock default
- [x] 5.4 **The themes are discoverable:** assert each of the three files exists under `<install>/config/btop/themes/`, has the `.theme` extension, and `resolve()`s into a palette cache entry — this is exactly the predicate `Theme::updateThemes` uses (`extension() == ".theme"` and `access(R_OK)`), so it proves discoverability without running btop
- [x] 5.5 **btop actually resolves the theme (end-to-end, headless):** run the application harness against the *provisioned* `~/.config/btop` (isolated via `XDG_CONFIG_HOME`/`XDG_STATE_HOME`) and require exit 0 with our colours painted and zero Default leak
- [x] 5.6 **Negative control against the real config:** assert that naming a non-existent theme in that same provisioned config makes the harness fail — proving step 5.5 is not vacuously green. This is the check that would have caught a `config_links` or pointer bug
- [x] 5.7 **Palette propagation:** after `wallpaper set`, assert all three theme files' contents changed and that `resolve()` still lands in the new palette entry
- [x] 5.8 **`save_config_on_exit` guarantee, asserted not assumed:** record `btop.conf`'s hash, run btop headlessly and terminate it, assert the hash is **unchanged**. This proves btop did not truncate the spine-owned file through the symlink — the risk that made this setting mandatory
- [x] 5.9 **Backup guard:** with a pre-existing real `~/.config/btop` containing a marker file, assert after provisioning that the marker is readable under the timestamped backup path and `~/.config/btop` is the spine symlink
- [x] 5.10 **Idempotence:** run `config_links` twice and assert no second backup directory is created

A running btop is expected to keep its colours until relaunch (D7). This is
asserted as a *non*-action: no step kills, signals, or relaunches a running btop,
and step 5.7 asserts only that the on-disk files changed.

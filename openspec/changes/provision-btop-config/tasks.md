## 1. `btop_config` role

- [ ] 1.1 `roles/btop_config/vars/main.yml` — `btop_config_spine_dir` (`<install>/config/btop`), `btop_config_spine_themes_dir` (`…/btop/themes`), `btop_config_xdg_config_home`, and the `install_dir | trim` / `ansible_facts.env` F4 locks, mirroring `kitty_config/vars/main.yml` exactly
- [ ] 1.2 `roles/btop_config/templates/btop.conf.j2` — managed header + `color_theme = "csg-minimal.theme"` + `save_config_on_exit = false`; every other setting at btop's stock default
- [ ] 1.3 `roles/btop_config/tasks/main.yml` — fail-loud `install_dir` assert first; `state: directory` for `…/btop` **and `…/btop/themes`** (required by D4 — the seeder never mkdirs into the spine); render `btop.conf`; no `become`
- [ ] 1.4 Role unit tests: rendered `btop.conf` contains `color_theme = "csg-minimal.theme"` and `save_config_on_exit = false`; no `install_dir | default(` fallback; both directories are ensured

## 2. Consumer pointers for the three themes

- [ ] 2.1 `adapters/consumer_path_spec.py` — add three pointers: `config/btop/themes/colors.btop-minimal.theme` → `colors.btop-minimal.theme`, and likewise for `balanced` and `full`
- [ ] 2.2 **Coordinate, never re-decide** — this table is contract data transcribed verbatim in `shared-data-contract.md` (per the module docstring). Update the contract doc in the same change
- [ ] 2.3 Update the `repoint_consumer_symlinks` docstring and the pinned-table comment listing the four existing entries
- [ ] 2.4 Tests: the three new pointers are created; a missing `current/` target is skipped with a warning; a missing destination parent is skipped (never mkdir'd)

## 3. Wiring into provisioning

- [ ] 3.1 `playbooks/btop-config.yaml` + import into `bootstrap.yaml` beside `kitty-config.yaml`, before `config-links.yaml`
- [ ] 3.2 `config_links/vars/main.yml` — add `btop` to `config_links_managed_dirs`
- [ ] 3.3 `verify/vars/main.yml` — add `btop` to `verify_managed_link_dirs` (**must match 3.2 exactly** — `test_verify_managed_link_dirs` compares the lists)
- [ ] 3.4 Packages — `btop` is already in `group_vars/arch.yml:100` and `group_vars/debian-family.yml:87`; confirm both, add if either is missing
- [ ] 3.5 `filesystem` — confirm `~/.config/btop` needs no separate entry (config_links creates the link; the role creates the spine dir)
- [ ] 3.6 `verify/vars/main.yml` — assert: `btop.conf` exists; `color_theme` is `csg-minimal.theme`; `save_config_on_exit` is `false`; `…/btop/themes/` exists; all three theme files present (extend `verify_palette_files` at `:366-372` and add a config-file assertion)
- [ ] 3.7 Parity/verify role tests updated for the new role and managed dir

## 4. Documentation

- [ ] 4.1 Note in the role docs that `save_config_on_exit = false` is mandatory (btop would otherwise truncate the spine-owned config through the symlink on exit — `btop_config.cpp:379`, `:836-845`)
- [ ] 4.2 Record the reload deferral explicitly: the theme applies on the next btop launch; no running instance is disturbed
- [ ] 4.3 Fold in the pre-existing doc drift: `docs/99-dotfiles-hexagonal-architecture.md:340` says 3 formats (it is now 10) and `ARCHITECTURE_PLAN.md:32` omits `KITTY`

## 5. End-to-end verification

- [ ] 5.1 `uv run --directory src/provisioning pytest` green
- [ ] 5.2 `make contracts-check` green
- [ ] 5.3 Provision; confirm `~/.config/btop/btop.conf` selects `csg-minimal.theme`
- [ ] 5.4 Confirm `~/.config/btop/themes/` lists all three themes and each resolves into a palette cache entry
- [ ] 5.5 Launch btop from the ags bar widget and confirm the theme applies and the menu lists all three
- [ ] 5.6 Change the wallpaper; confirm the three files update and the **next** btop launch is re-themed (a running instance is expected to keep the old colours — D7)
- [ ] 5.7 Quit btop and confirm `btop.conf` was not rewritten (the `save_config_on_exit` guarantee)

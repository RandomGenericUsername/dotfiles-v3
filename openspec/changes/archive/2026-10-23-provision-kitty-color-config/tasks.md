## 1. `kitty_config` role

- [ ] 1.1 `roles/kitty_config/vars/main.yml` — `kitty_config_xdg_config_home`, `kitty_config_xdg_state_home`, `kitty_config_state_current_dir` (`<state>/dotfiles/current`), `kitty_config_spine_config_dir` (`<install>/config/kitty`), all with the `ansible_facts.env` F4 lock and `install_dir | trim` seam
- [ ] 1.2 `roles/kitty_config/templates/kitty.conf.j2` — managed header + `include {{ kitty_config_state_current_dir }}/colors.kitty` + `include local.conf` + `auto_reload_config -1`
- [ ] 1.3 `roles/kitty_config/tasks/main.yml` — fail-loud `install_dir` + facts asserts; ensure spine dir; render `kitty.conf`; touch `local.conf` only if absent (`force: false`); no `become`
- [ ] 1.4 Role unit tests: rendered `kitty.conf` contains the absolute include and `auto_reload_config -1`; no `install_dir | default(` fallback; `local.conf` not clobbered

## 2. Wiring into provisioning

- [ ] 2.1 `playbooks/kitty-config.yaml` + import it in `bootstrap.yaml` after `zsh-config` (or beside `wlogout-config`)
- [ ] 2.2 `filesystem` — ensure the kitty config-home dir path is part of the created set
- [ ] 2.3 `config-links` (`config_links`) — link `~/.config/kitty -> <install>/config/kitty`
- [ ] 2.4 Packages — ensure `kitty` is in the manifest/group_vars maps (add if missing)
- [ ] 2.5 `verify` — assert the linked `~/.config/kitty`, `kitty.conf`, and the include line; add `colors.kitty` to the expected palette artifacts list
- [ ] 2.6 Parity/verify tests updated for the new role + config

## 3. End-to-end verification

- [ ] 3.1 Provision; confirm `~/.config/kitty/kitty.conf` includes `…/current/colors.kitty`
- [ ] 3.2 Change the wallpaper; confirm all open kitty windows re-theme (runtime `KittyReloader` SIGUSR1) and new kitty windows start themed
- [ ] 3.3 `uv run --directory src/provisioning pytest` green; runtime `daemon run` converge no longer logs a `/dev/tty` failure

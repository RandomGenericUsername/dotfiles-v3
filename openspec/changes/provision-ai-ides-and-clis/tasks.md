## 1. Manifest + AUR channel (Arch-only)

- [ ] 1.1 `dotfiles/provisioning/packages.yaml` — add five logical entries with a comment block: `antigravity-ide`, `windsurf`, `vscode`, `copilot-cli`, `codex-cli`
- [ ] 1.2 `src/provisioning/ansible/group_vars/arch.yml` — add to the `packages` map: `antigravity-ide: antigravity-ide`, `windsurf: devin-desktop`, `vscode: visual-studio-code-bin`, `copilot-cli: github-copilot-cli`, `codex-cli: openai-codex-bin`
- [ ] 1.3 `src/provisioning/ansible/roles/packages/vars/arch.yml` — append `antigravity-ide, devin-desktop, visual-studio-code-bin, github-copilot-cli, openai-codex-bin` to `aur_packages`
- [ ] 1.4 `src/provisioning/tests/unit/test_ansible_scaffold.py` — add the five logical keys to `_ARCH_EXTRA_KEYS`
- [ ] 1.5 `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` — add the five names to the expected package set

## 2. rofi-launchable desktop entries

- [ ] 2.1 Author `dotfiles/applications/antigravity-ide.desktop` (Wayland/Ozone flags, `StartupWMClass=antigravity-ide`)
- [ ] 2.2 Author `dotfiles/applications/code.desktop` (Wayland/Ozone flags, `StartupWMClass=code`)
- [ ] 2.3 Author `dotfiles/applications/devin-desktop.desktop` (Wayland/Ozone flags, `StartupWMClass=Devin`)
- [ ] 2.4 Author `dotfiles/applications/copilot.desktop` (`Exec=kitty --title … copilot`, `Terminal=false`)
- [ ] 2.5 Author `dotfiles/applications/codex.desktop` (`Exec=kitty --title … codex`, `Terminal=false`)
- [ ] 2.6 `src/provisioning/ansible/roles/compositor_configs/vars/main.yml` — add the five entries to `compositor_configs_desktop_entries`

## 3. Legacy standalone Codex shadow

- [ ] 3.1 `src/provisioning/ansible/roles/cli_tools/tasks/main.yml` — stat `{{ cli_tools_bin_dir }}/codex`; remove it only when `stat.islnk` and `stat.lnk_target` contains `.codex/packages/standalone`; remove `{{ ansible_facts.env.HOME }}/.codex/packages` when present (both check-gated)
- [ ] 3.2 `src/provisioning/tests/unit/test_cli_tools_role.py` — assert the cleanup is guarded (islnk + standalone target) and check-gated

## 4. Verify gate

- [ ] 4.1 `src/provisioning/ansible/roles/verify/vars/main.yml` — add `antigravity-ide`, `code`, `devin-desktop`, `copilot`, `codex` to `verify_system_binaries`
- [ ] 4.2 `src/provisioning/tests/unit/test_verify_role.py` — extend `test_system_binaries_are_compositors` with the five names

## 5. Acceptance gates

- [ ] 5.1 **G1** `pytest src/provisioning/tests` green
- [ ] 5.2 **G2** `ansible-playbook --syntax-check` for both `os_family` values green (via the role test)
- [ ] 5.3 **G4** real provisioning (manual, scripted): `packages` → `cli_tools` → `compositor-configs`; re-run idempotent; five binaries resolve; five `.desktop` files in `~/.local/share/applications/`; `~/.local/bin/codex` gone
- [ ] 5.4 **G3** rofi lists the five entries (`rofi -show drun`)
- [ ] 5.5 **G5** `make gates` (or the CI subset) green

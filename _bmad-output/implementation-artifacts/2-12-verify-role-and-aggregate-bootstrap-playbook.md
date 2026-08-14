---
baseline_commit: 555eafe
---

# Story 2.12: Verify Role and Aggregate Bootstrap Playbook

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-13: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-22, FR-4, FR-3).

## Story

As an operator,
I want a `verify` role plus the aggregate `bootstrap.yaml`,
So that all preconditions and done-criteria are assertable in one run.

## Acceptance Criteria

1. `roles/verify/` role exists with `tasks/main.yml` and `vars/main.yml` (AC 1, FR-22, plan §6)
2. `verify.yaml` asserts the ten done-criteria against **provisioned locations** (`~/.config/...`, install dir), NOT the repo checkout (AC 2, hardening: machine, not repo — plan §8):
   - install-dir subtree (criterion 1)
   - system binaries on PATH — Hyprland, Hyprpaper, Waybar (criterion 2)
   - `csg`/`weg`/icon-renderer on PATH (criterion 3)
   - assets deployed — `default.png` + `icon-templates/` + `icon-mappings/` + `csg-templates/` + `weg-effects.yaml` (criterion 4)
   - per-tool settings parse — the three rendered `settings.toml` files exist AND their spine-path targets resolve to existing directories (criterion 5, hardening: parse ≠ works)
   - default palette files present — `generated/palettes/{colors.conf, colors.yaml, colors.gtk.css}` (criterion 6)
   - compositor configs + fragments placed — skeletons + `colors.conf` + `colors.css` (criterion 7)
   - filesystem structure — XDG config/state/cache dirs + install subtree (criterion 8)
   - config copies present as REAL directories, not symlinks (criterion 9)
   - §12 capability preconditions — the four runtime assumptions assertable via `VerifyCapabilityUseCase` (criterion 10)
3. The ITR settings-parse gate uses `itr list <install>/icon-mappings/icons.yaml --config ~/.config/itr/settings.toml` (not `defaults.yaml`) (AC 3, SPEC.md#51)
4. `bootstrap.yaml` aggregates all role playbooks in dependency order: `packages` → `cli_tools` → `filesystem` → `assets` → `default_palette` → `compositor_configs` → `config_copies` → `settings` → `verify` (AC 4, plan §11 step 7)
5. `bootstrap.yaml --check` completes cleanly without mutation (AC 5, FR-22, FR-3, hardening: dry-run must be dry)

## Tasks / Subtasks

- [ ] Create `src/provisioning/ansible/roles/verify/vars/main.yml` (AC: 1, 2)
  - [ ] Open with the standard header comment: `# Verify role vars (Story 2.12).` + role-description + `# Mirror-and-adapt discipline (Epic 1 retro action item)` block itemizing what differs from each mirror
  - [ ] `verify_xdg_config_home`: the EXACT derivation used by filesystem/compositor_configs/config_copies/settings — `{{ ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.config', true) }}` (honors `$XDG_CONFIG_HOME`, defaults to `~/.config`; uses `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact — F4 lock)
  - [ ] `verify_install_spine_dirs`: mirror `filesystem_spine_dirs` EXACTLY — the nine install-spine dirs under `install_dir`: `wallpapers`, `icon-templates`, `icon-mappings`, `csg-templates`, `generated`, `generated/palettes`, `generated/effects`, `generated/icons`, `generated/.weg-tmp` (parity-lock with `filesystem/vars/main.yml` in the test — if the spine changes, verify must change)
  - [ ] `verify_install_spine_files`: the file node(s) that must exist IN the spine root: `weg-effects.yaml` (mirror `filesystem_file_nodes`; emitted by the assets role 2.6)
  - [ ] `verify_system_binaries`: the compositor/OS binaries on PATH — `[hyprland, hyprpaper, waybar]` (criterion 2; do NOT attempt to check fonts "on PATH" — fonts are files, not binaries; the fonts decision is documented in Dev Notes "Fonts in done-criterion 2")
  - [ ] `verify_cli_tools`: the uv-tool-installed CLIs on PATH — `[csg, weg, itr]` (criterion 3; `itr` IS the icon-renderer console script)
  - [ ] `verify_cli_bin_dir`: the uv bin dir to prepend to PATH — mirror `cli_tools_bin_dir` exactly: `{{ ansible_facts.env.HOME }}/.local/bin` (the CLIs land here via `uv tool install`; without the prepend the bootstrap chain would FALSE-FAIL right after cli_tools installed them — mirror of the default_palette/assets PATH-prepend pattern)
  - [ ] `verify_settings_files`: the three rendered settings DEST paths — mirror `settings_files` dests exactly: `{{ verify_xdg_config_home }}/color-scheme-generator/settings.toml`, `{{ verify_xdg_config_home }}/weg/settings.toml`, `{{ verify_xdg_config_home }}/itr/settings.toml` (parity-lock with `settings/vars/main.yml` in the test)
  - [ ] `verify_settings_spine_targets`: the spine-path TARGETS the rendered settings must resolve to (the parse ≠ works hardening — criterion 5 checks the target of each path, not just parseability): `<install>/generated/palettes` (CSG output.directory), `<install>/generated/effects` (WEG output.directory), `<install>/generated/.weg-tmp` (WEG processing.temp_dir), `<install>/generated/icons` (ITR output.output_dir), `<install>/icon-templates` (ITR templates.dir), `<install>/generated/palettes/colors.yaml` (ITR color_scheme.path). Each as `{{ install_dir | trim }}/...` — trim lock, NO hardcoded absolute paths
  - [ ] `verify_palette_files`: the default-palette outputs that must be present under `{{ install_dir | trim }}/generated/palettes/` — `[colors.conf, colors.yaml, colors.gtk.css]` (mirror `default_palette_formats` — conf/gtk.css/yaml; NOT json/sh)
  - [ ] `verify_compositor_config_dirs`: the three compositor config dirs under the XDG config home: `{{ verify_xdg_config_home }}/hypr`, `{{ verify_xdg_config_home }}/hyprpaper`, `{{ verify_xdg_config_home }}/waybar` (mirror `filesystem_compositor_dirs` / `compositor_configs_config_dirs`)
  - [ ] `verify_compositor_skeleton_files`: the skeleton files that must be present — `{{ verify_xdg_config_home }}/hypr/hyprland.conf`, `{{ verify_xdg_config_home }}/hyprpaper/hyprpaper.conf`, `{{ verify_xdg_config_home }}/waybar/config`, `{{ verify_xdg_config_home }}/waybar/style.css` (mirror `compositor_configs_skeleton_files` dests)
  - [ ] `verify_compositor_fragments`: the palette fragments copied into the config dirs — `{{ verify_xdg_config_home }}/hypr/colors.conf` and `{{ verify_xdg_config_home }}/waybar/colors.css` (mirror `compositor_configs_fragment_copies` dests; note the Waybar source is `colors.gtk.css` renamed to `colors.css` on copy)
  - [ ] `verify_xdg_dirs`: the XDG base dirs that must exist — mirror `filesystem_xdg_{config,state,cache}_home` derivations verbatim (three separate vars, or a list with the three derivations; the test must assert NO hardcoded absolute path and F4 lock)
  - [ ] `verify_config_copies_targets`: mirror the config-copies.yaml entries EXACTLY — `[nvim, starship, wlogout, zsh]` (parity-lock with `dotfiles/provisioning/config-copies.yaml`; each must be a REAL directory at `{{ verify_xdg_config_home }}/<target>`, not a symlink — runtime independence)
  - [ ] `verify_itr_list_target`: `{{ install_dir | trim }}/icon-mappings/icons.yaml` (the pinned ITR list gate arg — NOT `defaults.yaml`; the deployed icon-mappings dir contains `icons.yaml`, verified)
  - [ ] NO hardcoded absolute paths anywhere (every path derives from `{{ install_dir | trim }}` and `{{ verify_xdg_config_home }}` — trim lock; the test scans vars)

- [ ] Create `src/provisioning/ansible/roles/verify/tasks/main.yml` (AC: 1-3)
  - [ ] FIRST task: fail-loud fact-gathering assert — mirror config_copies verbatim: `ansible_facts.env.HOME is defined and ansible_facts.env.HOME | trim | length > 0` (the vars derive from `ansible_facts.env`; a bootstrap aggregator that forgets `gather_facts: true` must die with a friendly message, not an opaque undefined-var traceback — resolves the 2.11 deferred-work flag) [config_copies/tasks/main.yml:54-60]
  - [ ] SECOND task: fail-loud install_dir seam assert — use the HARDENED five-condition form from settings 2.11 (this role gates rendered files, so it inherits the hardened assert): `install_dir is defined`, `install_dir is not none`, `install_dir is string`, `install_dir | trim | length > 0`, `install_dir | trim | regex_search('^/') is not none` — reject `None`/relative/trailing-slash values before any stat evaluates [settings/tasks/main.yml:42-54]
  - [ ] Check system binaries on PATH: for each of `{{ verify_system_binaries }}`, `ansible.builtin.shell: command -v <name>` registered, `changed_when: false`, `failed_when: false` (NO `become`), followed by an assert that every rc == 0 with non-empty stdout — the assert gated `when: not ansible_check_mode` (command/shell tasks are skipped under --check in ansible-core 2.20.3; the gate keeps `bootstrap.yaml --check` clean — mirror of the default_palette/assets "Check for weg/Ensure csg available" pair) [default_palette/tasks/main.yml:77-95]
  - [ ] Check CLI tools on PATH: same shell+assert pair for `{{ verify_cli_tools }}`, with `environment: PATH: "{{ verify_cli_bin_dir }}:{{ ansible_facts.env.PATH }}"` so uv-installed tools are found (mirror default_palette_bin_dir) — assert gated `when: not ansible_check_mode`
  - [ ] Assert install-dir subtree: `ansible.builtin.stat` loop over `{{ verify_install_spine_dirs }}` under `{{ install_dir | trim }}` and the file node(s) `{{ verify_install_spine_files }}`, then assert every stat `.exists` (gated `when: not ansible_check_mode` — stats run, but the assert must not fail a `bootstrap.yaml --check` on a partially-provisioned host)
  - [ ] Assert assets deployed: stat+assert pair for `{{ install_dir | trim }}/wallpapers/default.png`, `{{ install_dir | trim }}/icon-templates/`, `{{ install_dir | trim }}/icon-mappings/`, `{{ install_dir | trim }}/csg-templates/`, `{{ install_dir | trim }}/weg-effects.yaml` (criterion 4) — assert gated `when: not ansible_check_mode`
  - [ ] Assert default palette files: stat+assert pair for each `{{ verify_palette_files }}` under `{{ install_dir | trim }}/generated/palettes/` (criterion 6) — assert gated `when: not ansible_check_mode`
  - [ ] Assert settings files exist: stat+assert pair for each `{{ verify_settings_files }}` (criterion 5 part 1) — assert gated `when: not ansible_check_mode`
  - [ ] Assert settings spine targets resolve: stat+assert pair for each `{{ verify_settings_spine_targets }}` (criterion 5 part 2 — parse ≠ works: the rendered file pointing at a MISSING directory must fail verify even if the file itself parses) — assert gated `when: not ansible_check_mode`
  - [ ] Settings parse gate (AC 3): three command tasks + asserts, all gated `when: not ansible_check_mode`, with `verify_cli_bin_dir` on PATH:
    - `csg info --config <csg settings.toml>` — NOTE the deferred-work finding: csg's `info` swallows ConfigResolutionError and exits 0 even on a parse-broken file, so this task is a documented WEAK gate; the authoritative CSG parse proof is the spine-target resolution assert above + Story 3.3's schema-parity. Keep the task (it exercises the CLI + is the done-criterion wording) but document the vacuity in a comment
    - `weg info --config <weg settings.toml>` — this half CAN actually fail (per the 2.11 review finding); keep it as a real gate
    - `itr list {{ verify_itr_list_target }} --config <itr settings.toml>` — the pinned icons.yaml gate (SPEC.md#51, done-criterion 5)
    - After the three command tasks, assert each registered rc == 0 (gated `when: not ansible_check_mode`)
  - [ ] Assert compositor configs + fragments: stat+assert pairs for `{{ verify_compositor_config_dirs }}`, `{{ verify_compositor_skeleton_files }}`, `{{ verify_compositor_fragments }}` (criterion 7) — asserts gated `when: not ansible_check_mode`
  - [ ] Assert filesystem structure: stat+assert pairs for `{{ verify_xdg_dirs }}` (criterion 8) — assert gated `when: not ansible_check_mode`
  - [ ] Assert config copies are real directories (criterion 9): stat loop over `{{ verify_xdg_config_home }}/{{ item }}` for each `{{ verify_config_copies_targets }}` with `follow: false`, then assert every stat `.isdir` (a symlink back into the repo reports islnk: true / isdir: false — the runtime-independence guarantee) — mirror config_copies dest-check exactly [config_copies/tasks/main.yml:104-120]; both stat and assert gated `when: not ansible_check_mode`
  - [ ] Header comment documenting: scope (ten done-criteria), the machine-not-repo invariant (asserts against provisioned locations only), the check-mode gating rationale (a real `verify` is check=False via `VerifyCapabilityUseCase`; under `bootstrap.yaml --check` all state-asserts are skipped so the dry run stays clean and mutation-free — the authoritative gate is the real `dotfiles-provision verify`), the csg-info vacuity note, the config-copies real-dir check, NO become/become_user, no hardcoded absolute paths
  - [ ] NO become/become_user anywhere (user-scoped role — everything checked lives under the user's config home and install dir; mirror 2.5-2.11)
  - [ ] NO hardcoded absolute paths (everything via `{{ install_dir | trim }}` and `{{ verify_xdg_config_home }}`)

- [ ] Create `src/provisioning/ansible/playbooks/verify.yaml` (AC: 1-3)
  - [ ] Open with the standard explanatory comment block (mirror `settings.yaml`/`config-copies.yaml`): one-per-role playbook; user-scoped (NO become); distro-agnostic (NO group_by — the role consumes no group_vars); why `gather_facts: true` is REQUIRED (vars derive from `ansible_facts.env.XDG_CONFIG_HOME`/`HOME`); the install_dir seam contract; the real-verify vs `--check` gating semantics
  - [ ] `hosts: localhost`, `gather_facts: true`, `roles: [verify]`, NO become, NO group_by

- [ ] Create `src/provisioning/ansible/playbooks/bootstrap.yaml` (AC: 4, 5)
  - [ ] AGGREGATE via `import_playbook` statements in the EXACT dependency order (plan §11 step 7, story 2.12 AC 4):
    ```
    - import_playbook: packages.yaml
    - import_playbook: cli-tools.yaml
    - import_playbook: filesystem.yaml
    - import_playbook: assets.yaml
    - import_playbook: default-palette.yaml
    - import_playbook: compositor-configs.yaml
    - import_playbook: config-copies.yaml
    - import_playbook: settings.yaml
    - import_playbook: verify.yaml
    ```
    (Each per-role playbook keeps its OWN hosts/become/gather_facts/group_by — importing preserves the packages.yaml distro `group_by` mechanism and the become:true packages play, so the single bootstrap aggregate runs the whole chain correctly. Do NOT flatten into one play — mixing become (packages) with user-scoped roles in one play breaks the privilege contract.)
  - [ ] Leading comment block documenting: what bootstrap.yaml is (the aggregate run — FR-4); the dependency order rationale (`packages` first, `verify` last); that it is `--check`-clean (dry-run must be dry — every command/shell task in the chain is check-gated or auto-skipped); the seam extra-vars a direct run must pass (`-e install_dir=...` and `-e os_family=arch|debian-family` — the orchestrator provides them via `--extra-vars`, per use_cases `_seam_extra_vars`; `os_family` is REQUIRED because packages.yaml group_by's on it)
  - [ ] NO `hosts:`/`roles:`/`tasks:` at the top level — only the nine `import_playbook` entries (Ansible top-level list of imports)

- [ ] Add structural real-file tests `src/provisioning/tests/unit/test_verify_role.py` (AC: 1-3)
  - [ ] Copy the FULL helper suite verbatim from `test_settings_role.py` / `test_config_copies_role.py` (`_find_ansible_dir()` walk-up resolver, `_TASK_KEYWORDS`, `_module_key`/`_module`/`_module_text`/`_creates_value`, `_vars()`, `_tasks_with_module()`) — the duplicated-helper pattern is the accepted repo convention (no shared conftest)
  - [ ] `TestVerifyRoleTree`: role tree exists (`tasks/main.yml`, `vars/main.yml`); tasks parse to a list of named tasks
  - [ ] `TestVerifyTasks`:
    - first task is the fail-loud fact-gathering assert (`ansible_facts.env.HOME is defined`)
    - second task is the hardened install_dir seam assert (five conditions: `is defined`, `is not none`, `is string`, `| trim | length > 0`, `regex_search('^/')`)
    - system-binary + cli-tool shell checks: `shell` module with `command -v`, `changed_when: false`, `failed_when: false`, and their asserts gated `when: not ansible_check_mode`; cli-tool tasks set `environment.PATH` containing `verify_cli_bin_dir`
    - every state-assert task is gated `when: not ansible_check_mode` (stat loops are ungated or gated — either is fine — but the ASSERTS on existence/isdir MUST be check-gated so `bootstrap.yaml --check` completes cleanly)
    - the settings parse-gate command tasks (csg info / weg info / itr list) exist and are check-gated
    - `itr list` target contains `icon-mappings/icons.yaml` and the `--config` flag references the ITR settings dest (NOT `defaults.yaml`)
    - config-copies dest check uses `stat` with `follow: false` and asserts `.isdir` (real dirs, not symlinks)
    - NO become/become_user anywhere
  - [ ] `TestVerifyVars`: required keys present; `verify_xdg_config_home` honors + F4 lock (no `{{ ansible_env.`); `verify_install_spine_dirs` parity-EXACT with `filesystem_spine_dirs`; `verify_settings_files` parity-EXACT with `settings_files` dests; `verify_config_copies_targets` parity-EXACT with `dotfiles/provisioning/config-copies.yaml` entries; `verify_palette_files` == `[colors.conf, colors.yaml, colors.gtk.css]`; `verify_cli_tools` == `[csg, weg, itr]`; `verify_system_binaries` == `[hyprland, hyprpaper, waybar]`; NO hardcoded absolute paths (trim lock — scan vars with the `_hardcoded_absolute_path()` regex helper from test_settings_role.py)
  - [ ] `TestVerifyPlaybook`: verify.yaml parses, `hosts: localhost`, `gather_facts: true`, `roles: [verify]`, no become, no group_by; `--syntax-check` exits 0 (skip if ansible-playbook absent)
  - [ ] **Runtime execution test** `test_verify_passes_on_a_provisioned_machine`: build a minimal provisioned "machine" in a `tempfile.TemporaryDirectory()`:
    - `home`, `xdg` (= `home/.config`), `install` roots; `env["HOME"]`, `env["XDG_CONFIG_HOME"]`, `env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")`
    - create the install spine dirs + `weg-effects.yaml`; place `wallpapers/default.png`, `icon-templates/`, `icon-mappings/icons.yaml`, `csg-templates/`, `generated/palettes/{colors.conf, colors.yaml, colors.gtk.css}`
    - create the three config dirs + the three rendered `settings.toml` files pointing at the spine targets (valid TOML with the spine paths)
    - create the compositor dirs + skeleton files + fragments (`hypr/colors.conf`, `waybar/colors.css`)
    - create the four config-copy targets as REAL dirs under `xdg/`
    - stub binaries `hyprland`/`hyprpaper`/`waybar`/`csg`/`weg`/`itr` as executable `#!/bin/sh` scripts in `home/.local/bin/` that `exit 0` (so `command -v` + the parse gates pass without real CLIs)
    - run the real `ansible-playbook playbooks/verify.yaml -e install_dir=<install>` and assert `failed` is absent / the run completes with zero failed tasks
    - then DELETE one criterion element (e.g. remove `generated/palettes/colors.conf`) and assert the re-run FAILS loudly (negative lock: verify is not vacuous)
  - [ ] **Negative runtime test** `test_verify_fails_when_not_provisioned`: run `verify.yaml` against a bare temp HOME/XDG/install (no spine, no configs, no binaries) and assert the run FAILS (the gate cannot go green on an unprovisioned machine — hardening: machine, not repo)
  - [ ] Optional: skip the runtime tests if `ansible-playbook` is absent (mirror the settings test gate pattern — the suite must not hard-depend on the CLI)
  - [ ] A structural test asserting `verify.yaml` runs the FULL chain in order (a regression check that the aggregate actually contains verify LAST)

- [ ] Add structural test `src/provisioning/tests/unit/test_bootstrap_playbook.py` (AC: 4, 5)
  - [ ] Copy the helper suite (or a minimal subset) for playbook parsing: bootstrap.yaml parses as a list of `import_playbook` entries
  - [ ] Assert the NINE imports in the EXACT dependency order: packages → cli-tools → filesystem → assets → default-palette → compositor-configs → config-copies → settings → verify (use `import_playbook` keys; assert each referenced playbook file exists under `playbooks/`)
  - [ ] Assert NO top-level `hosts:`/`roles:`/`tasks:` keys (the aggregate is imports-only)
  - [ ] `--syntax-check` exits 0 (skip if ansible-playbook absent)
  - [ ] NOTE: do NOT run a full `bootstrap.yaml --check` in this story — the end-to-end dry-run integration tests (every playbook under `--check`) are Story 3.2 (`test_ansible_dryrun.py`); here we lock structure + syntax only

- [ ] Verify full suite + lint + layering guard (AC: 1-5)
  - [ ] `uv run pytest` — full suite green, no regressions from the 396-pass baseline (Story 2.11 + review fixes — see Git Intelligence)
  - [ ] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean (mypy baseline: 10 pre-existing errors in test_default_palette_role.py + test_cli_tools_role.py — new files must be clean)
  - [ ] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)
  - [ ] `git status --short` shows ONLY the new role dir, the two playbooks, the two test files, and the story/status artifacts

### Review Findings

(none yet — populated by the code-review pass)

## Dev Notes

### Scope — what Story 2.12 is and is not

**IS:** the `verify` Ansible role (FR-22) that asserts the ten done-criteria (plan §8) against provisioned locations — install spine, system binaries, CLI tools, assets, settings files + their spine-target resolution, default palette, compositor configs, XDG structure, real-dir config copies — plus the `verify.yaml` one-per-role playbook and the aggregate `bootstrap.yaml` (FR-4) that runs the whole chain in dependency order.

**IS NOT:** the fresh-machine `scripts/bootstrap.sh` (Story 3.1), the playbook dry-run integration tests (Story 3.2 — `test_ansible_dryrun.py` runs every playbook under `--check`), or the settings-parity/default-palette integration tests (Story 3.3). Do NOT create `tests/integration/` in this story. Do NOT add any `.py` under `ansible/`. Do NOT modify any existing role/playbook/manifest/test. Do NOT touch `dotfiles/provisioning/*.yaml` (the five manifests are LOCKED). Do NOT modify `dotfiles/config/`. Do NOT modify any Python hexagon file (`src/provisioning/src/**`). The Python `VerifyCapabilityUseCase`/`BootstrapUseCase` ALREADY wire `verify.yaml`/`bootstrap.yaml` (cli/main.py:80-86) — nothing to add there.

### The ten done-criteria (the verify contract — plan §8, SPEC.md CAP-3)

| # | Criterion | Verify asserts |
|---|---|---|
| 1 | Install dir established | full install-spine subtree (nine dirs + `weg-effects.yaml`) |
| 2 | System binaries on PATH | `hyprland`, `hyprpaper`, `waybar` via `command -v` |
| 3 | CLI tools on PATH | `csg`, `weg`, `itr` via `command -v` (with `verify_cli_bin_dir` on PATH) |
| 4 | Assets deployed | `default.png` + `icon-templates/` + `icon-mappings/` + `csg-templates/` + `weg-effects.yaml` |
| 5 | Settings render and parse | the three `settings.toml` exist AND their spine-path targets resolve to existing dirs; csg/weg info + `itr list icons.yaml` gates exit 0 |
| 6 | Default palette generated | `generated/palettes/{colors.conf, colors.yaml, colors.gtk.css}` present |
| 7 | Compositor configs placed | skeletons + `hypr/colors.conf` + `waybar/colors.css` present |
| 8 | Filesystem structure exists | XDG config/state/cache dirs present |
| 9 | Config copies present | `nvim/starship/wlogout/zsh` REAL dirs (not symlinks) |
| 10 | §12 preconditions | the four runtime assumptions (binaries, assets, filesystem, settings parseable) — which IS criteria 2/3+4+8+5, i.e. the whole role |

Criterion 10 is not a separate task — it is the §12 precondition package that `VerifyCapabilityUseCase` exposes (use_cases.py:75-96 runs `verify.yaml` with a REAL check, never `--check`). The role is that package.

### Fonts in done-criterion 2

Done-criterion 2 says "Hyprland, Hyprpaper, Waybar, fonts on PATH" — but fonts are fontconfig files, not PATH binaries. **Decision (documented, do not implement font presence):** verify asserts the three compositor BINARIES on PATH. Font presence is the packages role's idempotent install concern (it installs the group_vars font list) and is NOT a PATH check. If you want an extra font sanity signal, note it as a comment — do NOT build an `fc-list` grep into the role (fragile, distro-specific, out of the ACs).

### Machine, not repo (the core invariant)

Every assert target is a PROVISIONED location: `~/.config/...` (via `verify_xdg_config_home`) and the install dir (via `{{ install_dir | trim }}`). NOTHING in the role references the repo checkout (`{{ playbook_dir }}` repo roots are NOT used — this role has no repo-root var, unlike assets/compositor_configs/config_copies). This is the "machine, not repo" hardening from the epics file: the gate must never go green because the repo still exists while the machine is unprovisioned. The runtime tests prove this by provisioning a temp machine and asserting verify passes, then un-provisioning a piece and asserting it fails.

### Check-mode gating (why every state-assert is `when: not ansible_check_mode`)

`dotfiles-provision verify` runs `verify.yaml` with `check=False` — that is the authoritative gate. But `verify` is ALSO the last import of `bootstrap.yaml`, and `bootstrap.yaml --check` must "complete cleanly without mutation" (AC 5). Under `--check`:
- `stat` tasks run and report honestly (no mutation) — fine ungated;
- `command`/`shell` tasks are SKIPPED by ansible-core 2.20.3 (verified 2.7);
- the ASSERTS on state existence would therefore FAIL on any partially-provisioned host under `bootstrap.yaml --check` — so every existence/isdir/rc assert is gated `when: not ansible_check_mode`.

The gate means a `bootstrap.yaml --check` reports the plan without failing on absent state; the real `dotfiles-provision verify` (check=False) is where the ten criteria are enforced. This is the identical discipline the default_palette (2.7), compositor_configs (2.9), and config_copies (2.10) roles use for their state asserts. Do NOT remove the gates "to make verify stricter" — that breaks `bootstrap.yaml --check`.

### The install_dir seam + hardened assert

`install_dir` is never defaulted (group_vars/all.yml). The verify role's install_dir assert uses the HARDENED five-condition form from settings 2.11 (rejects `None`, non-strings, relative paths, trailing slashes) — this role gates rendered files and is the natural owner of the hardened seam contract. The fact-gathering assert (first task) is the config_copies mirror — it resolves the 2.11 deferred-work flag (an aggregator that forgets `gather_facts: true` dies with a friendly message, not an opaque traceback). Do NOT alias install_dir into a var (lazy evaluation could surface a raw undefined-var error).

### Parse ≠ works (criterion 5 hardening)

Story 2.11's review deferred a flag: `csg info --config` is a VACUOUS gate — csg's `info` swallows `ConfigResolutionError` and exits 0 even on a parse-broken file (info_cmd.py:43-44). The WEG half can actually fail. So criterion 5 is enforced TWO ways:
1. **Path resolution (the real gate):** assert each spine-path TARGET referenced by the rendered settings resolves to an EXISTING directory. A rendered file pointing at `<install>/generated/palettes` where that dir was deleted FAILS verify even though the file itself parses.
2. **The three CLI gates** (`csg info`, `weg info`, `itr list icons.yaml`) exit 0 — exercised as documented done-criterion wording; csg's vacuity is documented in a comment so a future reader doesn't trust it.

### The ITR list gate pins icons.yaml

`itr list <install>/icon-mappings/icons.yaml --config ~/.config/itr/settings.toml` — NOT `defaults.yaml` (which lacks a `variants` field and is not listable). The deployed `icon-mappings/` dir contains `icons.yaml` (verified in the repo). SPEC.md#51 pins this; the test asserts the task references `icons.yaml`.

### config-copies real-dir check

Criterion 9 (runtime independence) needs REAL directories, not symlinks. Mirror config_copies' dest-check exactly: `stat` with `follow: false` then assert `.isdir` — a symlink back into the repo reports `islnk: true` / `isdir: false`. Both stat and assert gated `when: not ansible_check_mode`. [Source: config_copies/tasks/main.yml:104-120]

### bootstrap.yaml aggregation semantics

- `import_playbook` is a top-level statement; `bootstrap.yaml` is a list of nine imports. Each imported playbook keeps its own `hosts`/`become`/`gather_facts`/`group_by` — this is what makes the aggregate correct: packages.yaml's two-play structure (group_by on the `os_family` seam, then a become:true packages play) works unmodified when imported.
- Direct runs need `-e install_dir=...` AND `-e os_family=arch|debian-family` (packages.yaml group_by's on os_family and its guard asserts `os_family` matches the host fact). The orchestrator always passes both via `--extra-vars` (use_cases `_seam_extra_vars`).
- `--check` cleanliness: packages' `package` module reports would-change (no mutation); cli_tools/assets use command/creates tasks skipped under check; default_palette/compositor_configs/config_copies gate their state-touching tasks; settings template has full check-mode; verify's asserts are check-gated. The aggregate is therefore dry-run-safe.
- Do NOT flatten roles into a single play: packages needs `become: true` and the group_by distro mechanism; the other roles are strictly user-scoped (NO become). A flattened play would either run packages unprivileged or run user-scoped roles as root — both break the locked privilege contract.

### Mirror-and-adapt discipline (Epic 1 retro action item)

"What differs from each mirror":
- **config_copies (2.10)** — fact-gathering assert + real-dir `follow: false` isdir dest check + check-gated state asserts: 2.10 COPIES and verifies its own copies; verify re-checks the same targets read-only. verify inherits the fact assert verbatim and the isdir check verbatim; it does NOT copy anything.
- **default_palette (2.7)** — shell `command -v` + assert pair with bin-dir PATH prepend: verify reuses the pattern for BOTH system binaries and CLI tools; unlike 2.7 it has no csg presence REQUIREMENT per se — the whole point is asserting what provisioning placed.
- **settings (2.11)** — hardened install_dir assert + spine-target contract: verify consumes the SAME spine targets the settings role renders and the hardened assert form; verify does NOT render anything.
- **filesystem (2.5)** — XDG derivation + spine dirs: verify mirrors `filesystem_spine_dirs` and the XDG derivations EXACTLY (a divergence would make verify check the wrong layout); the parity tests lock them.
- **assets (2.6)** — the asset kind→spine-segment mapping: verify re-checks the five deployed asset outcomes (default.png, three dirs, weg-effects.yaml) read-only.
- **compositor_configs (2.9)** — skeleton/fragment target map: verify re-checks the placed skeletons + fragments read-only; note the Waybar fragment is `colors.css` (renamed from `colors.gtk.css` on copy).

### The runtime execution test

The 2.10/2.11 discipline: structural tests alone cannot prove verify isn't vacuous. The runtime test builds a minimal provisioned "machine" in a temp dir (spine, assets, settings, palette, compositor, config-copies, stub binaries) and asserts the real `verify.yaml` run passes; then it removes ONE element and asserts the re-run FAILS. The negative test (bare temp env) proves the gate cannot go green on an unprovisioned machine — the hardening: machine, not repo. Stub binaries in `home/.local/bin` make `command -v` + the csg/weg/itr gates pass without installing real CLIs. `--syntax-check` on both new playbooks, skip-if-ansible-absent.

## Project Structure Notes

- `src/provisioning/ansible/roles/verify/tasks/main.yml` — NEW role tasks (fact assert, install_dir assert, binary/cli checks, spine/assets/palette/settings/compositor/filesystem/config-copy stat+assert pairs, settings parse gates).
- `src/provisioning/ansible/roles/verify/vars/main.yml` — NEW role vars (XDG homes, spine dirs/files, system binaries, CLI tools + bin dir, settings files + spine targets, palette files, compositor dirs/skeletons/fragments, config-copy targets, itr list target).
- `src/provisioning/ansible/playbooks/verify.yaml` — NEW one-per-role playbook (localhost, gather_facts, roles: [verify], no become, no group_by).
- `src/provisioning/ansible/playbooks/bootstrap.yaml` — NEW aggregate (nine `import_playbook` entries in dependency order; imports-only, no top-level play keys).
- `src/provisioning/tests/unit/test_verify_role.py` — NEW structural + runtime tests (mirror test_settings_role.py helper suite).
- `src/provisioning/tests/unit/test_bootstrap_playbook.py` — NEW structural test (import order, file existence, syntax-check).
- Consumed, NOT modified: `src/provisioning/cli/main.py` (already wires both playbooks), `application/use_cases.py`, all existing roles/playbooks/manifests, `dotfiles/provisioning/*.yaml`, `dotfiles/config/**`.
- No new dependencies. No Python outside the two test files.

## Testing Requirements

- Full gates: `uv run pytest` (396-pass baseline from Story 2.11 + review fixes), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` (new files must be mypy-clean; 10 pre-existing baseline errors in test_default_palette_role.py/test_cli_tools_role.py — do NOT chase them), `python tests/architecture/test_layering.py` (standalone nicety).
- New `src/provisioning/tests/unit/test_verify_role.py` (see Tasks/Subtasks): copy the FULL helper suite verbatim from `test_settings_role.py` (incl. `_hardcoded_absolute_path()` regex helper). Classes: `TestVerifyRoleTree`, `TestVerifyTasks`, `TestVerifyVars`, `TestVerifyPlaybook`, plus the runtime exec tests. Assert the parity locks (spine dirs ↔ filesystem, settings files ↔ settings role, config-copy targets ↔ config-copies.yaml), the check-gated state asserts, the hardened install_dir assert, the `follow: false` real-dir check, and the icons.yaml ITR gate.
- New `src/provisioning/tests/unit/test_bootstrap_playbook.py`: the nine imports in EXACT order + file-exists check + no top-level play keys + `--syntax-check` exit 0 (skip-if-absent). Do NOT attempt a full `bootstrap --check` here (Story 3.2 owns it).
- Do NOT re-use a shared conftest for role tests — the duplicated-helper pattern is the accepted repo convention.

## Previous Story Intelligence

### Story 2.11 — Settings Role (DONE 2026-08-12, the immediate predecessor)
- The rendered files' contract is the spine-path map this role re-checks: CSG `output.directory` → `<install>/generated/palettes`; WEG `output.directory` → `<install>/generated/effects` + `processing.temp_dir` → `<install>/generated/.weg-tmp`; ITR `output.output_dir` → `<install>/generated/icons` + `templates.dir` → `<install>/icon-templates` + `color_scheme.path` → `<install>/generated/palettes/colors.yaml`. Verify's `verify_settings_spine_targets` mirrors these six targets. [Source: 2-11-settings-role.md Dev Notes "The three rendered files"]
- The hardened install_dir assert (five conditions) landed in settings 2.11's review; verify inherits it. [Source: 2-11-settings-role.md Review Findings]
- Deferred-work flags for 2.12: (a) no fail-loud fact-gathering guard for `ansible_facts.env` → verify LEADS with the config_copies fact assert; (b) `csg info --config` gate is vacuous → verify's real gate is spine-target resolution, csg info documented weak; (c) `HOME=""` → `/.config` — chain-wide fix deferred, NOT this story; (d) schema-parity → 3.3's settings-parity tests. [Source: deferred-work.md#3-8, 2-11-settings-role.md Review Findings]

### Story 2.10 — Config Copies Role (DONE 2026-08-12)
- The real-dir `follow: false` isdir dest check + the fact-gathering first-task assert — both inherited verbatim by verify for criterion 9. [Source: 2-10-config-copies-role.md, config_copies/tasks/main.yml]
- Established the runtime-execution-test discipline (structural tests alone missed a silent no-op). Verify's runtime tests extend this to prove the gate is not vacuous.

### Story 2.7 — Default Palette Role (DONE 2026-08-12)
- `default_palette_formats` = `[conf, gtk.css, yaml]` → the palette files verify checks are `colors.conf` (Hyprland), `colors.yaml` (ITR chain), `colors.gtk.css` (→ Waybar `colors.css`). NOT json/sh. [Source: default_palette/vars/main.yml#75-91]
- The `command -v` + bin-dir PATH-prepend + check-gated assert pattern for finding uv-installed CLIs. [Source: default_palette/tasks/main.yml#77-95]
- Palette generation reported success but output files could be missing (silent render failure) — verify's palette-file asserts close that loop for the bootstrap chain. [Source: 2.7 review finding]

### Story 2.5 — Filesystem Role (the layout creator)
- `filesystem_spine_dirs` (the nine install-spine dirs) + the three XDG home derivations — verify mirrors these EXACTLY (parity-locked). [Source: filesystem/vars/main.yml]

### Story 2.4 — CLI Tools Role
- `cli_tools_bin_dir` = `{{ ansible_facts.env.HOME }}/.local/bin` — the uv bin dir verify prepends to PATH; `itr` IS the icon-renderer console script. [Source: cli_tools/vars/main.yml#14]

### Story 2.2 — Ansible Scaffold
- The aggregate `bootstrap.yaml` was planned in §6/§11 but never built — the per-role playbooks already carry "aggregation into bootstrap.yaml is Story 2.12" comments. The distro mechanism (group_by on `os_family`) lives in packages.yaml and is preserved by import_playbook.

## Git Intelligence

- Baseline: `555eafe` (`feat: auto-commit story implementation`, 2026-08-12 — the Story 2.11 implementation commit). **The working tree is DIRTY with the uncommitted 2.11 review-fix changes** (`settings/tasks/main.yml`, `csg-settings.toml.j2`, `test_settings_role.py`, plus the 2.11 story/status artifacts). Build on the CURRENT working tree (it contains the review fixes); do NOT stash/revert them. The `git status --short` before this story shows those 6 modified files — after this story it must show ONLY those + the new role dir, two playbooks, two test files, and story/status artifacts.
- 396 tests pass at baseline (374 baseline + 22 new from 2.11).
- Recent work pattern (2.8→2.11): each story is one role + one playbook + one structural test file + story/status artifacts; role tests duplicate the shared helper suite (no shared conftest). Commit titles follow `chore: create story X.Y ...` → `feat: implement story X.Y ...` → `fix: apply code review findings ...`.
- This story adds ONLY: `src/provisioning/ansible/roles/verify/**` (tasks, vars), `src/provisioning/ansible/playbooks/verify.yaml`, `src/provisioning/ansible/playbooks/bootstrap.yaml`, `src/provisioning/tests/unit/test_verify_role.py`, `src/provisioning/tests/unit/test_bootstrap_playbook.py`, and the story/status artifacts. It must NOT modify any existing role/playbook/test/manifest/Python file.

## Latest Tech Information

- ansible-core **2.20.3** installed (verified 2026-08-12); pyproject requires `ansible-core>=2.16`. Collections: community.general, ansible.posix, kewlfft.aur. `import_playbook`, `stat`, `assert`, `shell`, `command` are core — no new collections.
- `import_playbook`: top-level statement; imports are statically read at parse time; each imported playbook keeps its own play keys (hosts/become/gather_facts). Paths resolve relative to the importing playbook's directory. This is the correct aggregation primitive for bootstrap.yaml.
- `ansible.builtin.stat` `follow: false`: reports `islnk`/`isdir` for the symlink itself, not its target — the real-dir check relies on it.
- Check-mode semantics (verified 2.7, ansible-core 2.20.3): `command`/`shell` tasks are SKIPPED under `--check`; `stat`/`assert`/`file` run safely. Hence every state-assert in verify is gated `when: not ansible_check_mode`.
- `tomllib` available (`requires-python = ">=3.12"`) for the runtime test's settings parse.
- The repo currently has NO `tests/integration/` directory — Story 3.2 creates it. Do NOT create it here.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#465-479] — Story 2.12 ACs (verify role, ten done-criteria, ITR icons.yaml gate, bootstrap aggregate order, --check clean)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#43] — FR-22 Verify Role
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#25] — FR-4 Bootstrap Command (aggregate bootstrap.yaml)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#49-58] — NFR-7 Verify-Gate Contract, NFR-2 No Persisted State, NFR-9 Bootstrap Reproducibility
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#140-142] — hardening notes (machine not repo; dry-run must be dry)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#26-27] — CAP-3 verify success (ten done-criteria)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#39] — §12 preconditions assertable via VerifyCapabilityUseCase
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#49] — no persisted provisioning state; verify re-derives on demand
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#51] — verify gate pins icons.yaml (NOT defaults.yaml)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#232-249] — plan §8 the ten done-criteria (the verify contract)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#146-167] — plan §6 layout: `roles/verify/ (tasks/main.yml)`, `playbooks/verify.yaml`, `playbooks/bootstrap.yaml`
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#224] — plan §7 `dotfiles-provision verify → runs verify.yaml → asserts §12 preconditions`
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#283] — plan §11 step 7 the exact role install order (bootstrap aggregate dependency order)
- [Source: src/provisioning/src/provisioning/cli/main.py#80-86] — CLI already wires `verify.yaml` + `bootstrap.yaml`
- [Source: src/provisioning/src/provisioning/application/use_cases.py#75-96] — VerifyCapabilityUseCase (real check, never --check)
- [Source: src/provisioning/src/provisioning/application/use_cases.py#99-117] — BootstrapUseCase (check param)
- [Source: src/provisioning/ansible/roles/config_copies/tasks/main.yml#54-60] — the fact-gathering assert mirror
- [Source: src/provisioning/ansible/roles/config_copies/tasks/main.yml#104-120] — the real-dir follow:false isdir check mirror
- [Source: src/provisioning/ansible/roles/settings/tasks/main.yml#42-54] — the hardened install_dir assert mirror
- [Source: src/provisioning/ansible/roles/settings/vars/main.yml#56-59] — the settings dest paths verify mirrors
- [Source: src/provisioning/ansible/roles/default_palette/tasks/main.yml#77-95] — the command -v + PATH-prepend + check-gated assert pair pattern
- [Source: src/provisioning/ansible/roles/default_palette/vars/main.yml#75-91] — the palette formats (conf/gtk.css/yaml) verify mirrors
- [Source: src/provisioning/ansible/roles/filesystem/vars/main.yml#23-52] — XDG derivations + spine dirs verify mirrors
- [Source: src/provisioning/ansible/roles/cli_tools/vars/main.yml#14] — cli_tools_bin_dir (`$HOME/.local/bin`)
- [Source: src/provisioning/ansible/roles/compositor_configs/vars/main.yml#63-80] — skeleton/fragment dest map verify mirrors
- [Source: src/provisioning/ansible/playbooks/settings.yaml] — the one-per-role playbook pattern (localhost/gather_facts/no become/no group_by)
- [Source: dotfiles/provisioning/config-copies.yaml] — the four config-copy targets (nvim/starship/wlogout/zsh)
- [Source: dotfiles/config/icon-template-color-scheme-mappings/icons.yaml] — the pinned ITR list gate target
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/info_cmd.py#43-44] — csg info vacuity (swallows ConfigResolutionError, exits 0)
- [Source: _bmad-output/implementation-artifacts/2-11-settings-role.md] — previous story (hardened assert, --config gate boundary, deferred 2.12 flags)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#3-8] — the 2.11 deferred flags for 2.12
- [Source: src/provisioning/tests/unit/test_settings_role.py] — the full helper suite + runtime exec test pattern to mirror
- [Source: src/provisioning/tests/unit/test_config_copies_role.py] — the 2.10 test pattern (runtime exec + idempotency + parity)
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml#77] — story 2-12 status (backlog → ready-for-dev)

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Baseline `555eafe`; working tree DIRTY with the uncommitted 2.11 review fixes (settings role + tests + artifacts) — build on the current tree, don't revert. 396 tests pass.
- The `verify` role and both playbooks DO NOT exist at baseline (verified 2026-08-13): no `roles/verify/`, no `playbooks/verify.yaml`, no `playbooks/bootstrap.yaml`. CLI `main.py:80-86` already references both playbook paths — the CLI would fail at runtime until they land.
- `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` exists (verified) — the ITR gate target is real.
- Every existing per-role playbook (except packages.yaml, which carries the distro group_by + become plays) is `hosts: localhost / gather_facts: true / roles: [<role>] / no become / no group_by`. The aggregate imports them unmodified.
- ansible-core 2.20.3; `command`/`shell` skip under `--check` (verified 2.7); `stat`/`assert` check-safe.

### Completion Notes List

(none yet — populated by the dev pass)

### File List

- `src/provisioning/ansible/roles/verify/tasks/main.yml` (NEW)
- `src/provisioning/ansible/roles/verify/vars/main.yml` (NEW)
- `src/provisioning/ansible/playbooks/verify.yaml` (NEW)
- `src/provisioning/ansible/playbooks/bootstrap.yaml` (NEW)
- `src/provisioning/tests/unit/test_verify_role.py` (NEW)
- `src/provisioning/tests/unit/test_bootstrap_playbook.py` (NEW)
- `_bmad-output/implementation-artifacts/2-12-verify-role-and-aggregate-bootstrap-playbook.md` (this story)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story status → ready-for-dev)

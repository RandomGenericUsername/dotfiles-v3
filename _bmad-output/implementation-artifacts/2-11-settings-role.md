---
baseline_commit: f3530b3
---

# Story 2.11: Settings Role

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-12: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-21).
- 2026-08-12: Implemented — settings role, three templates, playbook, and structural+template-content+runtime tests landed; full suite 396 pass (374 baseline + 22 new); status → review.

## Story

As an operator,
I want a `settings` role that renders the three per-tool `settings.toml` files from Jinja templates,
So that each tool reads from and writes to the install spine with no per-invocation path flags.

## Acceptance Criteria

1. `roles/settings/` role exists with `tasks/main.yml`, `vars/main.yml`, and `templates/{csg,weg,itr}-settings.toml.j2` (AC 1, FR-21)
2. CSG settings (`~/.config/color-scheme-generator/settings.toml`) render `output.directory` → `<install>/generated/palettes` and keep `overwrite = false` (AC 2, FR-21, NFR-6)
3. WEG settings (`~/.config/weg/settings.toml`) render `output.directory` → `<install>/generated/effects` and `processing.temp_dir` → `<install>/generated/.weg-tmp` (AC 3, FR-21, NFR-6)
4. ITR settings (`~/.config/itr/settings.toml`) render `output.output_dir` → `<install>/generated/icons`, `templates.dir` → `<install>/icon-templates`, and `color_scheme.path` → `<install>/generated/palettes/colors.yaml` (AC 4, FR-21, NFR-6, NFR-8)
5. Absolute install-dir paths come from the orchestrator seam extra-var (`install_dir`), never hardcoded (AC 5, NFR-6)
6. An undefined/empty `install_dir` fails loudly during render (Jinja undefined handling or pre-render validation) — no `None/generated/...` or empty-path settings files (AC 6, NFR-6)
7. The templates are Jinja-rendered by Ansible's `template` module — `csg/weg dump-*` commands are not used (AC 7, plan §3)
8. Each rendered file parses via its tool's `--config` gate (CSG `info`, WEG `info`, ITR `list`) (AC 8, FR-21, NFR-6) — full gate invocation is owned by Story 2.12 (verify role) + Story 3.3 (settings-parity integration tests); 2.11 locks the rendered content structurally + at runtime

## Tasks / Subtasks

- [x] Create `src/provisioning/ansible/roles/settings/vars/main.yml` (AC: 1-5)
  - [x] Open with the standard header comment: `# Settings role vars (Story 2.11).` + role-description + `# Mirror-and-adapt discipline (Epic 1 retro action item)` block itemizing what differs from each mirror
  - [x] `settings_xdg_config_home`: the EXACT derivation used by filesystem/compositor_configs/config_copies — `{{ ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.config', true) }}` (honors `$XDG_CONFIG_HOME`, defaults to `~/.config`; uses `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact — F4 lock) — see Dev Notes "The `~/.config` vs XDG home decision"
  - [x] `settings_config_dirs`: the three per-tool config subdirs under the XDG config home: `color-scheme-generator`, `weg`, `itr` (the filesystem role created only the XDG home itself + compositor dirs; template does NOT create dest parents) — see Dev Notes "Config-dir ensure"
  - [x] `settings_files`: list of `{name, template, dest}` dicts — exactly three entries (csg/weg/itr), `template` = the `.j2` filename (resolved by the template module relative to `roles/settings/templates/`), `dest` = `{{ settings_xdg_config_home }}/<subdir>/settings.toml` (see Dev Notes "Templates live inside the role — no repo_root")
  - [x] NO `settings_repo_root` var (unlike assets/compositor_configs/config_copies) — this role has NO repo-file sources; the templates ARE the role content (see Dev Notes "Templates live inside the role — no repo_root")
  - [x] NO hardcoded absolute paths; every install-spine value is `{{ install_dir | trim }}/...` (trim lock)
- [x] Create `src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2` (AC: 2, 5, 7)
  - [x] Mirrors the chaining-spine.md CSG settings contract (§ chaining-spine.md#35-63): `[output]` `directory = "{{ install_dir | trim }}/generated/palettes"`, `verbosity = 1`, `default_formats = ["json", "sh"]`, `overwrite = false` (AC 2 — MUST keep overwrite false; the default_palette role 2.7 owns the per-task `COLORSCHEME__OUTPUT__OVERWRITE` override), `[generation]` `backend = "pywal"`, `[runtime]` `mode = "local"`, `[container]` block per the packaged default
  - [x] Every path value derives from `{{ install_dir | trim }}` — never a literal absolute path; NO `default("")` / `default(None)` fallback on `install_dir` (AC 5/6 — a fallback would silently render an empty path)
  - [x] No TOML comments that would break the tool's TOML parse (the tool parses the rendered file via `--config`)
- [x] Create `src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2` (AC: 3, 5, 7)
  - [x] Mirrors the chaining-spine.md WEG settings contract (§ chaining-spine.md#65-95): `version = "1.0"`, `[execution]` per the contract, `[output]` `verbosity = 1`, `directory = "{{ install_dir | trim }}/generated/effects"`, `[processing]` `temp_dir = "{{ install_dir | trim }}/generated/.weg-tmp"`, `[backend]` `binary = "magick"`, `[runtime]` `mode = "local"`, `[container]` block per the packaged default
  - [x] Every path value derives from `{{ install_dir | trim }}`; NO fallback (AC 5/6)
  - [x] `[execution]` `strict = false` — RESOLVED: the WEG settings schema (`settings_schema.py:8`) declares `strict: bool = False` as its default and accepts both booleans; chaining-spine.md's `strict = false` matches the schema, so the rendered file uses `strict = false` (the shipped defaults file's `strict = true` is NOT the contract — see Dev Notes "The chaining-spine vs packaged-default discrepancy"). Lock `strict = false` in the structural test
- [x] Create `src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2` (AC: 4, 5, 7)
  - [x] Mirrors the chaining-spine.md ITR settings contract (§ chaining-spine.md#97-111): `[output]` `output_dir = "{{ install_dir | trim }}/generated/icons"`, `verbosity = 1`, `[templates]` `dir = "{{ install_dir | trim }}/icon-templates"`, `[color_scheme]` `path = "{{ install_dir | trim }}/generated/palettes/colors.yaml"` (AC 4 — ITR has NO dump command, so this file is provisioning-authored directly, 4 keys)
  - [x] `[templates]` and `[color_scheme]` sections MUST be present and UNCOMMENTED (the packaged default has them commented out — this role renders them active so the resolver chain reaches the spine paths)
  - [x] Every path value derives from `{{ install_dir | trim }}`; NO fallback (AC 5/6)
- [x] Create `src/provisioning/ansible/roles/settings/tasks/main.yml` (AC: 1-7)
  - [x] FIRST task: the fail-loud install_dir seam assert, copied verbatim from filesystem/assets/default_palette/compositor_configs (AC 6 — the pre-render validation; an undefined/empty install_dir aborts here before any template evaluates; do NOT alias install_dir into a var — lazy evaluation could surface a raw undefined-var error instead)
  - [x] `Ensure per-tool config dirs exist`: `ansible.builtin.file` `state: directory` loop on `{{ settings_config_dirs }}` (template does NOT create dest parents; ungated — check-safe; mirror 2.5/2.9 "Ensure ... dirs exist")
  - [x] `Render settings files`: `ansible.builtin.template`, `src: "{{ item.template }}"`, `dest: "{{ item.dest }}"`, `loop: "{{ settings_files }}"` (AC 2-5, 7). Default `force: true` (content-compare idempotent — NFR-1; a template change propagates on re-apply). NO `creates:` (a gate would freeze a stale path — mirror the no-creates discipline of 2.7/2.9). NO `when: not ansible_check_mode` gate (template module has FULL check-mode support — action plugin predicts changed without writing; verified pattern from 2.9)
  - [x] Header comment documenting scope + the install_dir seam + the no-dump-commands contract + the rendered-settings-are-the-only-authoring-surface note (2.7/2.9 must NOT author/modify settings; only this role does)
  - [x] NO become/become_user anywhere (user-scoped role, mirror 2.5-2.10)
  - [x] NO hardcoded absolute paths (everything via `{{ install_dir | trim }}` and `{{ settings_xdg_config_home }}`)
- [x] Create `src/provisioning/ansible/playbooks/settings.yaml` (AC: 1)
  - [x] Open with the standard explanatory comment block (mirror `compositor-configs.yaml`/`config-copies.yaml`): one-per-role playbook; user-scoped (NO become); distro-agnostic (NO group_by — role consumes no group_vars); why `gather_facts: true` is REQUIRED (vars derive from `ansible_facts.env.XDG_CONFIG_HOME`/`HOME`); the install_dir seam contract
  - [x] `hosts: localhost`, `gather_facts: true`, `roles: [settings]`, NO become, NO group_by
- [x] Add structural real-file tests `src/provisioning/tests/unit/test_settings_role.py` (AC: 1-8)
  - [x] Role tree exists: `tasks/main.yml`, `vars/main.yml`, and all three `templates/*-settings.toml.j2`
  - [x] Tasks parse to a list of named tasks
  - [x] First task is the fail-loud install_dir assert (asserts `install_dir is defined` and `install_dir | trim | length > 0` — AC 6)
  - [x] Config-dir ensure task: `file` `state: directory` loop over `settings_config_dirs`, ungated
  - [x] Render task: `ansible.builtin.template`, `src` = `{{ item.template }}`, `dest` prefixed `{{ settings_xdg_config_home }}/` AND ending `settings.toml`, loop over `settings_files`, NOT `force: false`, NO `creates:`, NOT check-gated (locks full check-mode support + content-compare idempotency)
  - [x] NO become/become_user anywhere
  - [x] No hardcoded absolute paths in module bodies or vars (trim lock)
  - [x] vars test: required keys (`settings_xdg_config_home`, `settings_config_dirs`, `settings_files`), XDG honors `$XDG_CONFIG_HOME` via `ansible_facts.env` + F4 lock (assert NO `{{ ansible_env.` present), NO `settings_repo_root` key (locks the no-repo-root design), exactly three `settings_files` entries with names `{csg, weg, itr}` and matching template filenames
  - [x] Template-content tests (AC 2-6): for each `.j2`, assert it references `{{ install_dir | trim }}` in the spine-path fields, assert NO `install_dir | default(` / `| default("")` fallback (AC 6 — an empty path must never render), assert the three spine-path dest values are present per tool; assert CSG template keeps `overwrite = false`; assert ITR template has `[templates]` `dir` + `[color_scheme]` `path` UNCOMMENTED
  - [x] Playbook test: parses, `hosts: localhost`, `gather_facts: true`, `roles: [settings]`, no become, no group_by
  - [x] `ansible-playbook --syntax-check` exits 0 (skip if ansible-playbook absent)
  - [x] **Runtime execution test** `test_playbook_executes_and_renders_settings`: temp `HOME` + `XDG_CONFIG_HOME` + `install_dir`, run the real playbook with `ANSIBLE_CONFIG` + `-e install_dir=...`, assert each of the three `settings.toml` files exists at `xdg/<subdir>/settings.toml`, parses as valid TOML (`tomllib`), and its spine paths equal `install_dir`-derived absolute paths; re-run reports `changed=0` (idempotent); assert `None`/empty-string paths are absent from every rendered file (AC 6)
  - [x] Optional runtime gate test: if `csg`/`weg`/`itr` are on PATH, invoke `csg info --config <rendered>`, `weg info --config <rendered>` (exit 0) — `pytest.skip` when the CLIs are absent (temp HOME won't find uv-installed tools; the authoritative gate is 2.12/3.3 — do NOT make this suite depend on the CLIs)
- [x] Verify full suite + lint + layering guard (AC: 8)
  - [x] `uv run pytest` — full suite green, no regressions from the 373-pass baseline (Story 2.10 + review fixes)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean (mypy baseline: 10 pre-existing errors in test_default_palette_role.py + test_cli_tools_role.py — new file must be clean)
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)
  - [x] `git status --short` shows ONLY the new role dir, playbook, test file, and story/status artifacts

### Review Findings

(none yet — created with review guidance folded into the design from the sibling roles' deferred findings)

## Dev Notes

### Scope — what Story 2.11 is and is not

**IS:** the `settings` Ansible role (FR-21): renders the three per-tool `settings.toml` files from role-authored Jinja templates via Ansible's `template` module — CSG `output.directory`, WEG `output.directory` + `processing.temp_dir`, ITR `output.output_dir` + `templates.dir` + `color_scheme.path` — baking absolute install-spine paths from the `install_dir` seam extra-var (AC 5, NFR-6). Plus its one-per-role playbook and a structural real-file test (incl. template-content locks and a runtime execution test).

**IS NOT:** the `default_palette` role (2.7 — it GENERATES the palette and MUST NOT author/modify any settings file; AC 4 in 2.7 is a NEGATIVE guarantee: `overwrite=true` is process-scoped via env, never persisted), the `compositor_configs` role (2.9), the `config_copies` role (2.10), the `verify` role or aggregate `bootstrap.yaml` (2.12), the settings-parity/default-palette integration tests (3.3), or any Python hexagon change. Do NOT touch `dotfiles/provisioning/*.yaml` (five manifests LOCKED in Story 2.1 — there is NO `settings.yaml` manifest and none should be added). Do NOT add any `.py` under `ansible/`. Do NOT author any other role or playbook. Do NOT modify the repo `dotfiles/config/` tree.

### The three rendered files — the exact contract (chaining-spine.md)

| File | Keys this role MUST render | Value |
|---|---|---|
| `~/.config/color-scheme-generator/settings.toml` | `[output] directory` | `<install>/generated/palettes` |
| | `[output] overwrite` | `false` (MUST stay false — 2.7 owns the per-task env override) |
| `~/.config/weg/settings.toml` | `[output] directory` | `<install>/generated/effects` |
| | `[processing] temp_dir` | `<install>/generated/.weg-tmp` |
| `~/.config/itr/settings.toml` | `[output] output_dir` | `<install>/generated/icons` |
| | `[templates] dir` | `<install>/icon-templates` |
| | `[color_scheme] path` | `<install>/generated/palettes/colors.yaml` |

Author each `.j2` so the rendered TOML matches **chaining-spine.md's settings contract** (§ chaining-spine.md#35-111) as the authoritative source, while including every schema-required field the tool's packaged default defines (`src/cli-tools/*/defaults/settings.toml`) so the file is complete and parses via `--config`. Substitute `{{ install_dir | trim }}` for `<install>` in the spine path values. Do NOT include fields the tool's schema rejects (the tool's pydantic schema is the parse gate — 3.3's settings-parity test invokes the tools against these files).

### Templates live inside the role — no repo_root

Unlike `assets` (2.6), `compositor_configs` (2.9), and `config_copies` (2.10), the `settings` role has **NO repo-file sources**: the `.j2` templates ARE the role content, and Ansible's `template` module resolves `src:` relative to `roles/settings/templates/`. Therefore **do NOT create a `settings_repo_root` var** and do NOT reference `{{ playbook_dir }}`. The structural test asserts the absence of `settings_repo_root` to lock this design. [Source: template module semantics; plan §6 `roles/settings/ (tasks/main.yml, templates/{csg,weg,itr}-settings.toml.j2, vars/main.yml)`]

### The install_dir seam and the first-task assert

`install_dir` is deliberately NEVER defaulted (`group_vars/all.yml` — see Dev Notes "Why the seam is fail-loud"): the orchestrator always provides it via `--extra-vars` (use-cases `_seam_extra_vars`), and direct runs pass `-e install_dir=...`. The FIRST task in `tasks/main.yml` is the verbatim fail-loud seam assert (identical copy from 2.5/2.6/2.7/2.9) — this IS the AC 6 pre-render validation. Do NOT alias `install_dir` into a var (lazy evaluation could surface a raw undefined-var error instead of the friendly `fail_msg`). In the templates, reference `{{ install_dir | trim }}` DIRECTLY — never `{{ install_dir | default("") }}` or `{{ install_dir | default(None, true) }}`: a fallback would silently render `None/generated/...` or an empty path, violating AC 6 exactly. The structural tests lock: template contains `{{ install_dir | trim }}` for every spine path AND no `| default(` fallback on install_dir.

### The `~/.config` vs XDG home decision

The ACs and FR-21 use `~/.config/...` shorthand. Derive `settings_xdg_config_home` with the IDENTICAL `ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME | default(ansible_facts.user_dir) + '/.config', true)` expression the filesystem/compositor_configs/config_copies roles use — do NOT hardcode `~/.config`. Use `ansible_facts.env`, NOT the deprecated top-level `ansible_env` fact (hard-breaks on ansible-core >= 2.24 — the repo-wide F4 lock). `gather_facts: true` on the playbook is REQUIRED for `ansible_facts.env` to be populated. [Source: filesystem/vars/main.yml#23, compositor_configs/vars/main.yml#40, config_copies/vars/main.yml]

### Config-dir ensure

The `template` module does NOT create the dest parent directory (mirror finding from 2.6/2.9 — copy/template do not create dest parents). The filesystem role (2.5) created the XDG config home itself (`~/.config`) and the compositor dirs (`hypr`/`hyprpaper`/`waybar`), but NOT the per-tool subdirs (`color-scheme-generator`/`weg`/`itr`). This role therefore ensures them via `settings_config_dirs` first (ungated — `file state: directory` is natively check-safe), so a direct `settings.yaml` run is self-contained. Do NOT assume a prior role created them. [Source: filesystem/tasks/main.yml, filesystem/vars/main.yml]

### template module semantics (mirror of the 2.9/2.10 verified facts)

- `ansible.builtin.template` renders a `.j2` with Jinja2; on localhost `src` is relative to `roles/settings/templates/`.
- Natively idempotent via content comparison: identical render reports `ok`/`changed: false` (NFR-1 — Ansible is the state authority). Default `force: true` means a template edit propagates on the next apply; do NOT set `force: false` (that would freeze the first render forever and a settings path change would never land).
- Check-mode support is FULL (the action plugin predicts changed without writing) — the render task needs NO `when: not ansible_check_mode` gate. This is the 2.9-verified pattern; do not cargo-cult the 2.3/2.4 command-module gate.
- NO `creates:` — a gate would freeze a stale path and silently break a spine-path change (mirror of the 2.7/2.9 no-creates discipline).

### The `--config` gate boundary (AC 8)

AC 8's "each rendered file parses via its tool's `--config` gate (CSG `info`, WEG `info`, ITR `list`)" is satisfied at three layers:
1. **2.11 (this story):** the rendered files are structurally locked (template-content tests) and validated at runtime (TOML parse via `tomllib` + path resolution). The runtime test MAY additionally invoke `csg info --config <rendered>` / `weg info --config <rendered>` with `pytest.skip` when the CLIs are absent — a temp HOME won't find uv-installed tools (`uv tool install` puts them in `~/.local/bin`, and the test overrides `HOME`), so the suite must NOT depend on them.
2. **2.12 (verify role):** asserts the settings parse gate against provisioned locations as part of the ten done-criteria (done-criterion 5).
3. **3.3 (settings-parity integration test):** invokes `csg info --config <rendered>`, `weg info --config <rendered>`, `itr list <install>/icon-mappings/icons.yaml --config <rendered>` and asserts each exits 0 and each spine path resolves to an existing directory (hardening: parse ≠ works).
The ITR `list` gate needs the `<install>/icon-mappings/icons.yaml` arg (verify pins it — NOT `defaults.yaml`, which lacks a `variants` field); that is 2.12/3.3's invocation, not this role's.

### The chaining-spine vs packaged-default discrepancy

chaining-spine.md's WEG `[execution]` block shows `strict = false`; the shipped defaults file (`wallpaper_effects_generator/defaults/settings.toml`) has `strict = true`. **RESOLVED (verified 2026-08-12):** the WEG settings schema — `adapters/schemas/settings_schema.py:8` `ExecutionSchema.strict: bool = False` and `domain/models.py:130` `ExecutionSettings.strict: bool = False` — declares `strict = false` as its default and accepts both booleans. chaining-spine.md is the contract and matches the schema, so the rendered file uses **`strict = false`**. The shipped defaults file is not authoritative for this key. The structural test locks `strict = false` so the discrepancy cannot silently flip. (Both values parse — the point of the lock is determinism: the rendered file must match the SPEC companion.)

### Check-mode / idempotency summary

| Task | Check-mode | Idempotency |
|---|---|---|
| install_dir assert (first task) | ungated (pure assert) | n/a |
| Ensure per-tool config dirs (`file` directory) | safe (native) | native |
| Render settings (`template`) | FULL support, no gate needed (verified) | content-compare — unchanged render reports `changed: false`; NOT `force: false` |

### Playbook naming

Playbook filename `settings.yaml`; role dir `settings/`. This is the one role where the playbook and role names are identical (no hyphen/underscore asymmetry — the only `settings` file in the tree). The `csg/weg/itr` settings DEST files (`~/.config/color-scheme-generator/settings.toml` etc.) are rendered at runtime and live on the machine, never in the repo. [Source: plan §6]

### The runtime execution test

Mirror 2.9/2.10's `test_playbook_executes_and_places_...` regression guard (structural tests alone cannot catch silent no-ops): create `tempfile.TemporaryDirectory()`, `home`/`xdg`/`install`, set `env["HOME"]`, `env["XDG_CONFIG_HOME"]`, `env["ANSIBLE_CONFIG"] = str(_ANSIBLE_DIR / "ansible.cfg")`, run `ansible-playbook playbooks/settings.yaml -e install_dir=<install>`, then for each `settings_files` entry:
- `(xdg / subdir / "settings.toml").is_file()` is True;
- `tomllib.loads(text)` succeeds (valid TOML);
- the spine-path values equal the `install`-derived absolute paths (e.g. `output.directory == str(install / "generated" / "palettes")`, ITR `color_scheme.path == str(install / "generated" / "palettes" / "colors.yaml")`);
- NO rendered value contains `None`, is empty, or starts with `/None` (AC 6).
Re-running the playbook must be a no-op (`changed=0` recap) to lock content-compare idempotency at runtime. No fixtures needed — the role renders from its own templates. [Source: test_compositor_configs_role.py#470-523, test_config_copies_role.py]

### Mirror-and-adapt discipline (Epic 1 retro action item)

"What differs from each mirror":
- **2.5 filesystem / 2.9 compositor_configs / 2.10 config_copies** (XDG config home): share the EXACT XDG derivation (`ansible_facts.env`, F4 lock); do not duplicate logic with a different result.
- **2.9 compositor_configs** (first-task install_dir assert + template check-mode + runtime exec test): 2.9 COPIES repo files via `template` with `force: false` (never re-touch placed skeletons); 2.11 RENDERS role-internal templates with default `force: true` (content-compare idempotent — the settings files ARE the overwrite candidates, not transfer-once skeletons). 2.9's fragment copies are check-gated (apply-time sources); 2.11's render is ungated (no external source dependency).
- **2.7 default_palette** (settings-file NEGATIVE guard): 2.7 GENERATES the palette and MUST NOT author/modify settings; 2.11 is the ONLY settings author. The `overwrite=false` in the CSG template + 2.7's per-task env override are a two-sided contract — do not change one side.
- **config_copies/assets/compositor_configs** (repo_root + parity test): 2.11 has NO repo_root and NO manifest parity (no settings manifest exists) — the templates + structural locks ARE the contract. Do not cargo-cult a repo_root var.

### Why the seam is fail-loud (carried from 2.2 scaffold)

`group_vars/all.yml` deliberately does NOT default `install_dir`: the orchestrator seam always provides it, and "an undefined `install_dir` must FAIL LOUDLY in the renders (Story 2.11) rather than silently resolve to a default" is an explicit scaffold comment. The first-task assert + the no-`default()` template rule together make a mis-invoked direct run abort with a friendly message instead of rendering `None/generated/...` files that would poison the verify gate. [Source: group_vars/all.yml header]

### Deferred work / not re-opened here

- **Container-mode env on the rendered files:** the CSG template's `[container]` block uses the packaged default engine (`docker`); the container engine is detected at RUNTIME by cli_tools (2.4, image build) and default_palette (2.7, generate). The rendered `settings.toml` is only consulted when a user invokes csg directly (interactive `csg generate`); Phase 1's provisioning chain uses env overrides. Do NOT add engine detection to this role — the rendered file is static per install_dir. [Source: chaining-spine.md#61-63]
- **WEG effects catalog path:** the WEG effects chain points at the deployed `<install>/weg-effects.yaml` via env `WALLPAPER_EFFECTS_CONFIG_FILE_PATH` or `--effects` — it is NOT a settings.toml key and this role does not render it. [Source: chaining-spine.md#67, plan §4 WEG]
- **CSG templates dir:** deliberately NOT a settings field — Phase 2 runtime passes `--templates-dir <install>/csg-templates/` per invocation (Option B locked). This role renders no templates-dir key. [Source: plan §9]

## Project Structure Notes

- `src/provisioning/ansible/roles/settings/tasks/main.yml` — NEW role tasks (install_dir assert, per-tool config-dir ensure, render loop).
- `src/provisioning/ansible/roles/settings/vars/main.yml` — NEW role vars (XDG config home, `settings_config_dirs`, `settings_files`).
- `src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2` — NEW CSG settings template (`[output] directory` → `<install>/generated/palettes`, `overwrite = false`).
- `src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2` — NEW WEG settings template (`[output] directory`, `[processing] temp_dir`).
- `src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2` — NEW ITR settings template (`[output] output_dir`, `[templates] dir`, `[color_scheme] path`, sections UNCOMMENTED).
- `src/provisioning/ansible/playbooks/settings.yaml` — NEW one-per-role playbook (localhost, gather_facts, roles: [settings], no become, no group_by).
- `src/provisioning/tests/unit/test_settings_role.py` — NEW structural real-file tests (mirror `test_compositor_configs_role.py` helper suite + template-content + runtime execution tests).
- Consumed, NOT modified: `src/cli-tools/{color-scheme-generator,wallpaper-effects-generator,icon-templates-renderer}/defaults/settings.toml` (schema sources, read-only), `src/provisioning/src/**` (Python hexagon untouched), `dotfiles/provisioning/*.yaml` (locked in 2.1), the sibling roles 2.5-2.10.
- No new dependencies. No Python outside the test file.

## Testing Requirements

- Full gates: `uv run pytest` (373-pass baseline from Story 2.10 + its review fixes — see Git Intelligence), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` (new file must be mypy-clean; 10 pre-existing baseline errors remain in test_default_palette_role.py/test_cli_tools_role.py — do NOT chase them), `python tests/architecture/test_layering.py` (standalone nicety).
- New `src/provisioning/tests/unit/test_settings_role.py` (see Tasks/Subtasks): copy the FULL helper suite verbatim from `test_compositor_configs_role.py` (`_find_ansible_dir()` walk-up resolver, `_TASK_KEYWORDS` (the extended set incl. block/rescue/delegate_to), `_module_key`/`_module`/`_module_text`/`_creates_value`, `_vars()`, `_tasks_with_module()`). Classes in order: `TestSettingsRoleTree`, `TestSettingsTasks`, `TestSettingsVars`, `TestSettingsTemplates`, `TestSettingsPlaybook`. Assert:
  - role tree (tasks + vars + three templates); tasks parse to named tasks
  - first task is the fail-loud install_dir assert (`install_dir is defined`, `install_dir | trim | length > 0`)
  - config-dir ensure task: `file` `state: directory` loop over `settings_config_dirs`, ungated
  - render task: `ansible.builtin.template`, `src: "{{ item.template }}"`, `dest` prefixed `{{ settings_xdg_config_home }}/` + `settings.toml` suffix, loop over `settings_files`, NOT `force: false`, NO `creates:`, NOT check-gated
  - no become; no hardcoded absolute paths (trim lock — scan vars too)
  - vars: required keys; `settings_xdg_config_home` honors + F4 lock (no `{{ ansible_env.`); NO `settings_repo_root`; `settings_files` == exactly the three `{name, template, dest}` entries; each `template` filename exists under `templates/`
  - template-content: each `.j2` contains `{{ install_dir | trim }}` spine paths; NO `install_dir | default(`; CSG keeps `overwrite = false`; ITR has `[templates] dir` + `[color_scheme] path` UNCOMMENTED; WEG path keys present + `strict = false` locked
  - playbook: parses, localhost/gather_facts/roles [settings], no become, no group_by; `--syntax-check` exit 0 (skip-if-absent)
  - runtime execution test (renders real files into temp HOME/XDG + install_dir; TOML parses; spine paths resolve; no None/empty paths; re-run is a no-op)
  - optional runtime gate test (skip-if-absent CLIs): `csg info --config <rendered>` / `weg info --config <rendered>` exit 0
- Do NOT re-use a shared conftest for role tests — the duplicated-helper pattern is the accepted repo convention.
- Reference the packaged defaults (`src/cli-tools/*/defaults/settings.toml`) as the schema source of truth when authoring template field completeness.

## Previous Story Intelligence

### Story 2.10 — Config Copies Role (DONE 2026-08-12, the immediate predecessor)
- Established the current canonical runtime-execution-test discipline (review finding 2026-08-12 — structural tests alone missed a silent copy no-op). THIS story's runtime test must prove the renders actually land and parse. [Source: 2-10-config-copies-role.md]
- Locked the XDG derivation + F4 lock (`ansible_facts.env`, never `ansible_env`) + first-task fail-loud assert + trim-lock discipline — all inherited here verbatim.
- 2.10 consumes NO install_dir (repo→config-home copies); 2.11 DOES (spine paths baked into rendered files) — the first task is the install_dir assert, NOT a fact-gathering assert.

### Story 2.9 — Compositor Configs Role (DONE 2026-08-12)
- The canonical `template`-module facts to mirror: full check-mode support (no gate), content-compare idempotency, template does NOT create dest parents (dir-ensure first). [Source: 2-9-compositor-configs-role.md, compositor_configs/tasks/main.yml#60-96]
- 2.9's fragment copies are the ONLY overwrite candidates; 2.11's rendered settings files are similarly the Phase 1 overwrite surface (template default `force: true`).

### Story 2.7 — Default Palette Role (DONE 2026-08-12)
- Load-bearing NEGATIVE contract: 2.7 must never author/modify a settings file; the `overwrite=true` semantic is scoped to its single generate task via `environment: COLORSCHEME__OUTPUT__OVERWRITE`. The CSG template here keeps `overwrite = false` — the two-sided contract. [Source: 2-7-default-palette-role.md AC 3/4, default_palette/tasks/main.yml#147-155]
- 2.7 documented that at default_palette time the rendered CSG settings file does NOT exist (this role runs LATER in the bootstrap order `cli_tools → assets → default_palette → compositor_configs → config_copies → settings → verify`) — that ordering is why 2.7 forces `output.directory`/`overwrite` via env. Do NOT reorder; this role depends on the spine dirs (2.5) and the palette files existing only for the RENDER's path strings, not for the render itself.

### Story 2.5 — Filesystem Role (the dir creator)
- Created the XDG config home + compositor dirs + full install spine (incl. `generated/{palettes,effects,icons,.weg-tmp}/`). This role renders paths POINTING at that spine; it does NOT create spine dirs (2.5 owns that). The per-tool config subdirs are NOT created by 2.5 — this role ensures them. [Source: filesystem/vars/main.yml, filesystem/tasks/main.yml]

### Story 2.2 — Ansible Scaffold
- The scaffold is in place; `group_vars/all.yml` explicitly documents that `install_dir` must "FAIL LOUDLY in the renders (Story 2.11)". `settings` adds only a role dir, playbook, templates, and test file — no inventory/config changes. [Source: 2-2-ansible-scaffold.md, group_vars/all.yml]

### Story 2.1 — Declarative Manifests
- The five manifests are locked (`packages`, `assets`, `filesystem`, `config-copies`, `cli-tools`). There is deliberately NO `settings.yaml` manifest — the settings contract lives in chaining-spine.md + the tool schemas. Do NOT add one. [Source: 2-1-declarative-manifests.md]

### Epic 1 retrospective (2026-08-08) — action item touching this story
- "Mirror-and-adapt discipline": explicit "what differs from the mirror" checklist (addressed in Dev Notes).

## Git Intelligence

- Baseline: `f3530b3` (`fix: auto-commit code review findings`, 2026-08-12 — the Story 2.10 review-fix commit). Working tree was CLEAN. 373 tests pass at baseline (Story 2.10 landed 18 tests on the 355-pass 2.9 baseline).
- This story adds ONLY: `src/provisioning/ansible/roles/settings/**` (tasks, vars, three templates), `src/provisioning/ansible/playbooks/settings.yaml`, `src/provisioning/tests/unit/test_settings_role.py`, and the story/status artifacts. Verify with `git status --short` that nothing else moved. It must NOT modify any existing role/playbook/test/manifest.
- Recent work pattern (2.8→2.9→2.10): each story is one role + one playbook + one structural test file + story/status artifacts; role tests duplicate the shared helper suite (no shared conftest). Commit titles follow `chore: create story X.Y ...` → `feat: implement story X.Y ...` → `fix: apply code review findings ...`.

## Latest Tech Information

- ansible-core **2.20.3** is the installed/runtime version (verified 2026-08-12 via `uv run ansible --version`); pyproject requires `ansible-core>=2.16`. Collections: community.general, ansible.posix, kewlfft.aur (pinned in requirements.yml). No new collections needed — `ansible.builtin.template`/`assert`/`file` are core.
- `ansible.builtin.template` (verified pattern 2026-08-12 via 2.9): `.j2` `src` resolves relative to `roles/<name>/templates/`; content-compare idempotent (unchanged → `changed: false`); default `force: true` (a changed template propagates on re-apply); does NOT create the dest parent (dir-ensure first); FULL check-mode support (action plugin predicts changed, writes nothing) — no `not ansible_check_mode` gate needed. [Source: compositor_configs/tasks/main.yml, 2.9 story]
- Tool settings schemas (the parse gate contract — verified against the actual codebase 2026-08-12):
  - CSG (`~/.config/color-scheme-generator/settings.toml`, env prefix `COLORSCHEME`): `[output] directory/verbosity/default_formats/overwrite`, `[generation] backend/default_params`, `[runtime] mode`, `[container] engine/image_prefix/image_tag/timeout_seconds/memory_limit/mount_timeout_seconds`. Defaults file: `color_scheme_generator/defaults/settings.toml`. `csg info --config` parses it.
  - WEG (`~/.config/weg/settings.toml`, env prefix `WALLPAPER`): `version`, `[execution] parallel/strict/max_workers`, `[output] verbosity/directory`, `[processing] temp_dir`, `[backend] binary`, `[runtime] mode`, `[container] engine/image_name/image_tag/image_registry`. Defaults file: `wallpaper_effects_generator/defaults/settings.toml`. `weg info --config` parses it.
  - ITR (`~/.config/itr/settings.toml`, env prefix `ICON_RENDERER`): `[output] output_dir/verbosity`, `[templates] dir`, `[color_scheme] path`. Defaults file: `icon_templates_renderer/defaults/settings.toml` (templates/color_scheme sections COMMENTED there — this role renders them ACTIVE). No dump command; file is provisioning-authored. `itr list <yaml> --config` is the parse gate.
- F4 lock (repo-wide): read env via `ansible_facts.env`, never the deprecated top-level `ansible_env` fact (INJECT_FACTS_AS_VARS hard-breaks on ansible-core >= 2.24).
- `gather_facts: true` is REQUIRED on the playbook (vars derive from `ansible_facts.env.XDG_CONFIG_HOME`/`HOME`).
- `tomllib` is available: `src/provisioning/pyproject.toml` declares `requires-python = ">=3.12"` (verified 2026-08-12) — `tomllib` is stdlib on Python 3.11+, so the runtime test can use it without a dependency.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#447-463] — Story 2.11 ACs (settings role, three settings files, install_dir seam, no dump-commands, --config gates)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#42] — FR-21 Settings Role
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#55] — NFR-6 Deterministic Settings
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#57] — NFR-8 Spine Containment
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#35-111] — the three per-tool settings contracts (authoritative rendered content)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#61-63] — CSG templates dir NOT a settings field; `overwrite = false` kept in the rendered file
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#67] — WEG effects catalog is a deployed file, not a settings key
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#99] — ITR resolver active; file provisioning-authored directly (4 keys)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#265-271] — FR-21 in the PRD (consequences: --config gates exit 0; no dump-commands)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#69-102] — plan §4 tool settings facts (per-tool keys, env prefixes, XDG subdirs)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#106-132] — plan §5 chaining spine + default palette
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#165,284] — plan §6 `roles/settings/` tree + §11 step 8 (the three Jinja settings templates)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#240-244] — done-criterion 5 (settings render + parse via csg/weg/itr --config gates)
- [Source: src/provisioning/ansible/group_vars/all.yml] — `install_dir` deliberately NOT defaulted; must fail loudly in Story 2.11 renders
- [Source: src/provisioning/ansible/roles/filesystem/vars/main.yml#23] — the `filesystem_xdg_config_home` derivation to mirror as `settings_xdg_config_home`
- [Source: src/provisioning/ansible/roles/compositor_configs/tasks/main.yml#52-96] — the first-task install_dir assert + template/module discipline to mirror
- [Source: src/provisioning/ansible/roles/default_palette/tasks/main.yml#147-155] — the env-scoped `COLORSCHEME__OUTPUT__OVERWRITE` generate (why the rendered CSG file keeps `overwrite = false`)
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/settings.toml] — CSG schema source of truth
- [Source: src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/defaults/settings.toml] — WEG schema source of truth
- [Source: src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/defaults/settings.toml] — ITR schema source of truth (templates/color_scheme commented)
- [Source: src/provisioning/tests/unit/test_compositor_configs_role.py] — the full helper suite + runtime execution test pattern to mirror
- [Source: src/provisioning/tests/unit/test_config_copies_role.py] — the 2.10 test pattern (runtime exec + idempotency + parity)
- [Source: _bmad-output/implementation-artifacts/2-10-config-copies-role.md] — previous story (XDG/F4/trim-lock/assert discipline; runtime exec test)
- [Source: _bmad-output/implementation-artifacts/2-9-compositor-configs-role.md] — template-module facts + review-fix baseline
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml#77] — story 2-11-settings-role status (backlog)

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Baseline `f3530b3` is the 2.10 review-fix commit; working tree clean; 373 tests pass.
- The `settings` role does NOT exist at baseline (verified 2026-08-12): no `roles/settings/`, no `playbooks/settings.yaml`, no `test_settings_role.py` — fully greenfield.
- Tool settings schemas verified against the actual defaults files + CLI command surface 2026-08-12 (`csg info`, `weg info`, `itr list` all exist with `--config`).
- Pre-existing mypy baseline: `uv run mypy src tests` reports 10 errors in `tests/unit/test_default_palette_role.py` and `tests/unit/test_cli_tools_role.py` — present at baseline, NOT introduced by this story. The new `test_settings_role.py` must be mypy-clean.
- Implementation verified 2026-08-12: `uv run pytest` = 396 passed (374 baseline + 22 new); `uv run ruff check .` clean; `uv run ruff format --check .` clean; `uv run mypy src tests` = the same 10 pre-existing errors, none in `test_settings_role.py`; `python tests/architecture/test_layering.py` = OK (17 files, 6 rules). `git status --short` shows only the new role dir, playbook, test file, and story/status artifacts.

### Completion Notes List

- IMPLEMENTED (2026-08-12): settings role landed per the story spec — `roles/settings/{tasks,vars}/main.yml`, three `.j2` templates, `playbooks/settings.yaml`, `tests/unit/test_settings_role.py`. Full suite 396 passed (374 baseline + 22 new), lint/format clean, new test file mypy-clean, layering guard OK.
- Render contract verified at runtime: real `ansible-playbook settings.yaml` into temp HOME/XDG/install_dir renders the three `settings.toml` files; each parses via `tomllib`; spine paths resolve to the install-dir-derived absolute paths (CSG palettes, WEG effects + .weg-tmp, ITR icons + icon-templates + colors.yaml); `overwrite = false` and WEG `strict = false` locked; re-run reports `changed=0` (content-compare idempotency).

### Completion Notes List

- Created Story 2.11 Settings context: `settings` role (install_dir assert + per-tool config-dir ensure + template render loop), three `.j2` templates (CSG/WEG/ITR per chaining-spine.md contract), `settings.yaml` playbook, structural + template-content + runtime tests.
- Locked the rendered-file contract: CSG `output.directory` → `<install>/generated/palettes` keeping `overwrite = false`; WEG `output.directory` → `<install>/generated/effects` + `processing.temp_dir` → `<install>/generated/.weg-tmp`; ITR `output.output_dir` → `<install>/generated/icons` + `templates.dir` → `<install>/icon-templates` + `color_scheme.path` → `<install>/generated/palettes/colors.yaml` (sections UNCOMMENTED).
- Locked the no-repo-root design: templates are role-internal; `src:` resolves relative to `roles/settings/templates/`; NO `settings_repo_root` var (structural test asserts absence).
- Locked AC 6 fail-loud rendering: first-task install_dir assert (verbatim seam copy) + templates reference `{{ install_dir | trim }}` DIRECTLY with NO `| default(` fallback (no `None/generated/...` or empty-path files).
- Locked the render contract: `template` module, default `force: true` (content-compare idempotency), NO `creates:`, ungated (full check-mode support).
- Locked the `--config` gate boundary: 2.11 locks content structurally + runtime TOML parse; full tool-gate invocation is 2.12 (verify) + 3.3 (settings-parity).
- Scope guards: no manifest edits (no settings.yaml exists), no settings-file authoring by other roles (2.7 negative contract preserved), no Python hexagon changes, no engine detection (rendered file is static per install_dir).
- Status → ready-for-dev.

### File List

- `src/provisioning/ansible/roles/settings/tasks/main.yml` (NEW)
- `src/provisioning/ansible/roles/settings/vars/main.yml` (NEW)
- `src/provisioning/ansible/roles/settings/templates/csg-settings.toml.j2` (NEW)
- `src/provisioning/ansible/roles/settings/templates/weg-settings.toml.j2` (NEW)
- `src/provisioning/ansible/roles/settings/templates/itr-settings.toml.j2` (NEW)
- `src/provisioning/ansible/playbooks/settings.yaml` (NEW)
- `src/provisioning/tests/unit/test_settings_role.py` (NEW)
- `_bmad-output/implementation-artifacts/2-11-settings-role.md` (this story)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story status → ready-for-dev)

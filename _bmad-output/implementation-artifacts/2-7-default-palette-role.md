---
baseline_commit: a6a74c8
---

# Story 2.7: Default Palette Role

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-10: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-18).
- 2026-08-10: Validation pass — verified env-override + check-mode claims against source (config_resolver.py rules, OsEnvironmentReader `__` separator, type_coercer bool map, command module's creates-only check-mode support). Applied fixes: `default_palette_formats` now LOAD-BEARING in the task (`join(' -f ')`) so the var and task cannot diverge; `command -v csg` guard prepends `default_palette_bin_dir` to PATH (avoids a false bootstrap failure when `~/.local/bin` is not on the inherited PATH); clarified guard gating (read-only shell check runs, only the assert is `--check`-gated).
- 2026-08-10: Implemented story — authored `roles/default_palette/` (`tasks/main.yml`, `vars/main.yml`), `playbooks/default-palette.yaml`, and `tests/unit/test_default_palette_role.py` (20 structural tests). Full suite 309 passed (baseline 289), ruff/mypy/layering clean, `ansible-playbook --syntax-check` exits 0. Status → review.
- 2026-08-12: Code review (container-mode pass) — product directive: CSG/WEG run via `install` in container mode, podman preferred. Fixes landed in e18ecfe + follow-ups: `csg install`/`weg install` build fresh images from uv-tool installs (PEP 610/--source-root); cli_tools builds the csg image; default_palette generate runs container mode with runtime-detected engine (podman→docker→fail, optional override escape hatch); podman/docker documented as dependencies (not installed by chain). Container-mode generate validated end-to-end (podman 6.0.1, `$accent == $color1`).
- 2026-08-12: P2 (post-generate verification) applied — stat loop + fail-loud assert on colors.conf/.css/.yaml after generate; 280 tests green; Status → done.

## Story

As an operator,
I want a `default_palette` role that generates the default palette at apply time,
So that first-boot colors exist and regenerate when the default wallpaper changes.

## Acceptance Criteria

1. `roles/default_palette/` exists with `tasks/main.yml` (AC 1, FR-18)
2. It invokes `csg generate <install>/wallpapers/default.png -f conf` (plus standard formats) writing to `<install>/generated/palettes/` (AC 2, FR-18)
3. `overwrite=true` is scoped to that single task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"` — never written into the rendered settings file (AC 3, FR-18)
4. The rendered `~/.config/color-scheme-generator/settings.toml` keeps `overwrite = false` — THIS ROLE MUST NOT AUTHOR, RENDER, OR MODIFY any settings file (AC 4, FR-18, NFR-6); that is Story 2.11's job
5. The emitted `colors.conf` matches the Hyprland syntax contract (`$accent` equals `$color1`) — the ROLE emits `conf` via `-f conf`; the syntax contract assertion itself is Story 3.3's integration test (AC 5, FR-18/FR-25)
6. `default.png` presence is asserted before generation (mirror of the Story 2.6 guard) — the task fails loudly if the tarball regresses (AC 6, FR-18, chaining-spine.md assumption)
7. Replacing `wallpapers.tar.gz` in the repo causes the next `apply` to regenerate — the generate task carries NO `creates:` and is NOT gated on palette-file existence (AC 7, FR-18)
8. The `install_dir` seam extra-var is required and fails loudly when missing — the FIRST task is a fail-loud assert, no silent default (group_vars/all.yml contract + Stories 2.5/2.6 discipline)
9. The generated palette's output directory is forced to `<install>/generated/palettes/` per-process (via `COLORSCHEME__OUTPUT__DIRECTORY` env), because at default_palette time the rendered settings file does NOT exist yet (Story 2.11 comes later in the dependency order) and CSG's packaged default directory is `/tmp/color-scheme` — WITHOUT this override the palette would silently land in /tmp and done-criterion 6 / Story 2.9 / Story 3.3 would all fail (AC 2, FR-18, chaining-spine.md)
10. No `become`/`become_user` anywhere in the role or playbook (user-scoped privilege context — inherited from 2.3 OQ-1 / 2.4/2.5/2.6 resolution)
11. The `csg` binary is resolved by prepending `{{ default_palette_bin_dir }}` (`{{ ansible_facts.env.HOME }}/.local/bin`) to PATH in the generate task — `csg` is installed by the `cli_tools` role (2.4) into the uv bin dir, which may not be on the inherited PATH (mirror of 2.6 `assets_weg_bin_dir`)
12. `playbooks/default-palette.yaml` exists: `hosts: localhost`, `gather_facts: true`, `roles: [default_palette]`, NO `become`, NO `group_by` (distro-agnostic — mirror assets/cli_tools, not packages)

## Tasks / Subtasks

- [x] Create the `roles/default_palette/` role directory tree (AC: 1)
  - [x] `src/provisioning/ansible/roles/default_palette/tasks/main.yml`
  - [x] `src/provisioning/ansible/roles/default_palette/vars/main.yml`
- [x] Author `vars/main.yml` (AC: 2, 3, 8, 9, 11)
  - [x] `default_palette_bin_dir` — `{{ ansible_facts.env.HOME }}/.local/bin` (mirror `assets_weg_bin_dir`/`cli_tools_bin_dir`; `ansible_facts.env`, NOT `ansible_env` — F4 lock)
  - [x] `default_palette_default_image` — `{{ install_dir | trim }}/wallpapers/default.png` (trim lock)
  - [x] `default_palette_output_dir` — `{{ install_dir | trim }}/generated/palettes` (trim lock)
  - [x] `default_palette_formats` — `[conf, gtk.css, yaml]` (documented contract: `conf` → Hyprland `colors.conf`, `gtk.css` → Waybar `colors.gtk.css` copied to `~/.config/waybar/colors.css` — corrected from `css` by review finding 2026-08-12; `yaml` → ITR spine chain `colors.yaml`; see Dev Notes "The format set — what 'standard formats' means")
- [x] Author `tasks/main.yml` (AC: 2, 3, 5, 6, 7, 8, 9, 10, 11)
  - [x] Fail-loud seam guard: `ansible.builtin.assert` that `install_dir is defined and install_dir | trim | length > 0` — the FIRST task, verbatim copy of the 2.5/2.6 assert (AC 8)
  - [x] Ensure the palette output dir exists: `ansible.builtin.file` `state: directory`, `path: "{{ default_palette_output_dir }}"` (self-contained direct-run + explicit dir contract; idempotent + check-safe; CSG would auto-create it anyway — this is belt-and-suspenders mirroring 2.6 AC 9 discipline)
  - [x] Fail-loud `csg` presence guard: `ansible.builtin.shell: command -v csg` (register, `changed_when: false`, `failed_when: false`, `environment.PATH: "{{ default_palette_bin_dir }}:{{ ansible_facts.env.PATH }}"` — prepend so the guard finds `csg` in the uv bin dir even when it is not on the inherited PATH) + `ansible.builtin.assert` rc==0, assert gated `when: not ansible_check_mode` (the read-only shell check may run under `--check`; only the assert needs the gate) (mirror of 2.6 "Check for weg"/"Ensure weg is available", with the PATH-prepend improvement)
  - [x] Fail-loud `default.png` presence guard: `ansible.builtin.stat` on `{{ default_palette_default_image }}` (register) + `ansible.builtin.assert` on `stat.exists`, both gated `when: not ansible_check_mode` (AC 6 — mirror of 2.6; 2.6's guard is the primary chain guard, this one makes a direct `default-palette.yaml` run fail loudly with a friendly message)
  - [x] Generate the palette: `ansible.builtin.command` `csg generate '{{ default_palette_default_image }}' -f {{ default_palette_formats | join(' -f ') }}` (formats are LOAD-BEARING from the var — renders `-f conf -f gtk.css -f yaml`) with `environment` = `COLORSCHEME__OUTPUT__DIRECTORY: "{{ default_palette_output_dir }}"`, `COLORSCHEME__OUTPUT__OVERWRITE: "true"`, `PATH: "{{ default_palette_bin_dir }}:{{ ansible_facts.env.PATH }}"`, gated `when: not ansible_check_mode` — NO `creates:` (AC 2, 3, 5, 7, 9, 11; check-mode gating keeps "dry-run must be dry" — the `command` module's check-mode support is ONLY via `creates`/`removes`, so an ungated generate would execute and WRITE under `--check`)
  - [x] No `become:` anywhere (AC 10)
- [x] Author `playbooks/default-palette.yaml` (AC: 12)
  - [x] `hosts: localhost`, `gather_facts: true`, `roles: [default_palette]`
  - [x] NO `become: true`
  - [x] NO `group_by` — palette generation is distro-agnostic (NFR-3); do not cargo-cult the packages pattern
  - [x] `gather_facts: true` REQUIRED — vars read `ansible_facts.env.*` (HOME, PATH)
- [x] Add structural real-file tests `tests/unit/test_default_palette_role.py` (AC: 1-12; mirror `test_assets_role.py`/`test_filesystem_role.py` conventions)
  - [x] Role tree exists: `tasks/main.yml`, `vars/main.yml` (walk up from test file anchored on `pyproject.toml` — reuse `_find_ansible_dir()`)
  - [x] `tasks/main.yml` parses as a list of named task dicts
  - [x] First task is the fail-loud `install_dir` assert (AC 8)
  - [x] A `file` `state: directory` task creates `{{ default_palette_output_dir }}` == `{{ install_dir | trim }}/generated/palettes` (AC 9 dir contract)
  - [x] An `ansible.builtin.command` task runs `csg generate` against `{{ default_palette_default_image }}` and its `-f`/`--format` flags EQUAL `default_palette_formats` (render the task's command string and assert each `-f <fmt>` for fmt in the var, and NO other format flags) (AC 2, AC 5, AC 9)
  - [x] The generate task's `environment` sets `COLORSCHEME__OUTPUT__OVERWRITE: "true"` and `COLORSCHEME__OUTPUT__DIRECTORY: "{{ default_palette_output_dir }}"` and `PATH` starts with `{{ default_palette_bin_dir }}:` (AC 3, AC 9, AC 11)
  - [x] The generate task carries NO `creates:` and is gated `when: not ansible_check_mode` (AC 7, dry-run-must-be-dry)
  - [x] A `command -v csg` shell guard exists (with `environment.PATH` starting with `{{ default_palette_bin_dir }}:`) plus an `assert` on its registered rc; the assert is gated `when: not ansible_check_mode` (AC 11)
  - [x] The `default.png` stat + assert exist and are gated `when: not ansible_check_mode` (AC 6)
  - [x] No `become`/`become_user` anywhere in the role (AC 10)
  - [x] `vars/main.yml` uses `ansible_facts.env`, never `{{ ansible_env.` (F4 lock)
  - [x] No absolute repo paths hardcoded — all paths derive from `{{ install_dir | trim }}` (trim lock)
  - [x] `playbooks/default-palette.yaml` parses: `hosts: localhost`, `gather_facts: true`, `roles: [default_palette]`, no `become`, no `group_by`
  - [x] `ansible-playbook --syntax-check` on `default-palette.yaml` (with `-e install_dir=/tmp/x`) exits 0 (skip-guard when `ansible-playbook` absent — mirror 2.4 F6)
- [x] Verify full suite + lint + layering guard (AC: 7)
  - [x] `uv run pytest` — full suite green, nothing regresses from the 289-pass baseline (Story 2.6)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)

## Dev Notes

### Scope — what Story 2.7 is and is not

**IS:** the `roles/default_palette/` role (`tasks/main.yml`, `vars/main.yml`) and the `playbooks/default-palette.yaml` playbook under `src/provisioning/ansible/`, plus structural real-file tests. The role generates the default palette from `default.png` at apply time via `csg generate`, writing into the `generated/palettes/` spine dir the filesystem role (2.5) created (FR-18, chaining-spine.md). It is the CONSUMER of the 2.6-unpacked `default.png` and the PREREQUISITE for `compositor_configs` (2.9, copies `colors.conf`/`colors.gtk.css`) and the verify gate (2.12, done-criterion 6).

**IS NOT:** other roles (`compositor_configs` — 2.9; `symlinks` — 2.10; `settings` — 2.11; `verify` — 2.12), the aggregate `bootstrap.yaml` (Story 2.12), `scripts/bootstrap.sh` (Story 3.1), integration `--check`/dry-run tests and the Hyprland-syntax-contract test (Story 3.2/3.3). Do NOT author any other role or playbook. Do NOT render settings, do NOT write `~/.config/color-scheme-generator/settings.toml`, do NOT place compositor configs (that is 2.9), do NOT modify `dotfiles/assets/**` or `dotfiles/provisioning/*.yaml` (locked in Story 2.1).
- **Do NOT create any `~/.config/.../settings.toml`** — AC 4 is a NEGATIVE guarantee: the role must never author or modify the CSG settings file (the `overwrite=true` semantic is process-scoped, never persisted). The rendered settings files are exclusively Story 2.11's output.
- **Do NOT add a `--templates-dir` flag** — Phase 1's `default_palette` uses CSG's bundled templates (deployed to `<install>/csg-templates/` by 2.6 but consumed via `--templates-dir` only in Phase 2 per chaining-spine.md#61). Keep the invocation contract exactly as FR-18 specifies.
- **Do NOT re-extract wallpapers or assert the tarball** — that is 2.6's role (AC 10 of 2.6: unarchive has NO creates so a new tarball re-extracts). 2.7 only asserts `default.png` presence on the filesystem before generating (AC 6).

### Where files live (locked by plan §6)

```
src/provisioning/ansible/
├── inventory/localhost.yaml          (Story 2.2 — unchanged)
├── requirements.yml                  (Story 2.2 — unchanged)
├── ansible.cfg                       (Story 2.2 — unchanged; roles_path = roles)
├── group_vars/{all,arch,debian-family}.yml   (Story 2.2 — UNCHANGED; this role consumes NO group_vars)
├── playbooks/
│   ├── packages.yaml                 (Story 2.3 — unchanged)
│   ├── cli-tools.yaml                (Story 2.4 — unchanged)
│   ├── filesystem.yaml               (Story 2.5 — unchanged)
│   ├── assets.yaml                   (Story 2.6 — unchanged)
│   └── default-palette.yaml          ← NEW (this story)
└── roles/
    ├── packages/                     (Story 2.3 — unchanged)
    ├── cli_tools/                    (Story 2.4 — unchanged)
    ├── filesystem/                   (Story 2.5 — unchanged)
    ├── assets/                       (Story 2.6 — unchanged)
    └── default_palette/
        ├── tasks/main.yml            ← NEW
        └── vars/main.yml             ← NEW
```

- Everything lives OUTSIDE `_SRC_ROOT` — YAML only, never scanned by `tests/architecture/test_layering.py`, never part of the Python hexagon. **Do NOT add any `.py` file under `ansible/`** (same rule as Stories 2.3-2.6).
- Naming: role dir `default_palette` (underscore) + playbook file `default-palette.yaml` (hyphen) mirrors the `cli_tools` role / `cli-tools.yaml` precedent — this divergence is ESTABLISHED, do not "fix" it.
- The playbook is runnable directly with `ansible-playbook` for `--check` verification; aggregation into `bootstrap.yaml` is Story 2.12 (dependency order `... assets → default_palette → compositor_configs ...`).

### The `csg generate` contract — the heart of this story

`csg` (installed by the 2.4 `cli_tools` role to `~/.local/bin/csg` via `uv tool install`) resolves its settings through the shared `config-assembler-engine`:

1. **Resolution chain** (config_resolver.py): CLI `--config` > ENV path var > directory traversal > **XDG `~/.config/color-scheme-generator/settings.toml`** > packaged bundled default (`src/color_scheme_generator/defaults/settings.toml`).
2. **At default_palette time the XDG file does NOT exist** — the settings role (2.11) that renders it runs LATER in the bootstrap order (`cli_tools → assets → default_palette → compositor_configs → settings`). So `csg generate` falls through to the **packaged default**: `output.directory = "/tmp/color-scheme"`, `default_formats = ["json", "sh"]`, `overwrite = false`.
3. **Therefore the role MUST force both the output directory AND overwrite via process env** on the single generate task (AC 3 + AC 9). Env overrides are declared in `OverrideRule("output.directory"|"output.overwrite", {CLI, ENV})` and the `OsEnvironmentReader` maps `COLORSCHEME__SECTION__KEY` → `section.key` (separator `__`; value coerced — bool: `raw.lower() in ("true","1","yes","on")`; Path: str → Path). Both overrides are applied ON TOP of whatever the resolved config is, so they win over both the packaged default AND (on a re-apply) a previously-rendered settings file.
   - **Do NOT rely on `-o`/`--output-dir` instead of the env directory override.** The env directory override is the design that keeps the task's command line identical to the AC text (`csg generate <install>/wallpapers/default.png -f conf`), extends the FR-18 "env-scoped override" framing to both keys cohesively, and is what the structural test locks. (`-o` is a valid fallback but would diverge from the documented contract — if you switch to it, you must update AC 3/AC 9 wording and the tests.)
4. **Formats:** the generate task passes `-f conf -f gtk.css -f yaml` explicitly. When `-f` is given, `resolved_formats` = the CLI formats (it REPLACES `settings.output.default_formats`), so the role's format set is fully self-declared and independent of any settings file. The Hyprland `conf` template renders `$background/$foreground/$cursor/$accent/$color0..15` with `$accent == rgb(colors[1])` and `$color1 == rgb(colors[1])` → `$accent` equals `$color1` (the contract Story 3.3 asserts on the output file). The Waybar fragment is the `gtk.css` format (review finding 2026-08-12: corrected from `css` — `gtk.css` renders `@define-color color_00..15` which the 2.8 skeleton consumes; `css` renders browser CSS custom properties GTK/Waybar cannot read).
5. **The renderer always writes** (`output_path.parent.mkdir(parents=True, exist_ok=True)` then `write_text`) in local mode — `overwrite` is honored on the container path; setting the env override is nonetheless REQUIRED because it is the SPEC-locked mechanism (FR-18, chaining-spine.md#63) and the rendered-settings-keeps-false guarantee (AC 4) only means anything if the role proves the per-task override is the ONLY place `true` appears.

### The format set — what "standard formats" means

The AC says "`-f conf` (plus standard formats)". Downstream Phase 1 consumers fix the set to exactly three:

| Format | Output file | Consumer |
|--------|-------------|----------|
| `conf` | `colors.conf` | Hyprland — copied by `compositor_configs` (2.9) to `~/.config/hypr/colors.conf`; done-criterion 6; Story 3.3 syntax test |
| `gtk.css` | `colors.gtk.css` | Waybar — copied by 2.9 to `~/.config/waybar/colors.css` (review finding 2026-08-12: corrected from `css`; `css` emits browser CSS custom properties GTK/Waybar cannot read, `gtk.css` emits `@define-color` the skeleton consumes) |
| `yaml` | `colors.yaml` | ITR spine chain — `color_scheme.path` → `<install>/generated/palettes/colors.yaml` (FR-21, done-criterion 6, Story 3.3 spine-chain) |

So `default_palette_formats = [conf, gtk.css, yaml]` is the role's contract set. The packaged `default_formats = ["json", "sh"]` (which the rendered settings file will keep for interactive `csg generate <img>` calls) are NOT part of this role's job — no Phase 1 consumer reads `colors.json`/`colors.sh`. Do NOT add `sh`/`json` "because the default settings have them" — the format set is contract-driven, not defaults-driven. Lock `default_palette_formats` in vars and let the structural test assert the task's `-f` flags equal the var.

### Idempotency vs. regenerate — the FR-18 tension (SPEC-ratified, do NOT "fix")

- The generate task must ALWAYS run on a real apply: **NO `creates:`** on the palette files and NO existence gate. FR-18's regenerate semantic ("replacing `wallpapers.tar.gz` causes the next `apply` to regenerate") requires that after the 2.6 unarchive re-extracts a new `default.png`, this role re-runs `csg generate` to pick it up. A `creates:`/existence gate on `colors.conf` would freeze the palette forever — the exact mistake 2.6's review called out for the tarball.
- Consequence: the task reports `changed` on every apply even when the palette content is identical. This is **accepted by design** (SPEC §FR-18, chaining-spine.md#23). Idempotency (NFR-1) means no STATE drift; the verify gate (2.12, done-criterion 6) checks the output files, not Ansible changed-counts. Document this in the role's header comment so a reviewer doesn't "fix" it.
- **Check mode:** the task MUST be gated `when: not ansible_check_mode`. `command`/`shell` modules DO execute under `--check` (their only check-mode support is the `creates`/`removes` file-gate, which this role deliberately omits) — without the gate, a `--check` run would actually call `csg generate` and WRITE files, violating the hardening rule "dry-run must be dry" that Story 3.2 will assert. The other guards are gated for the same reason, mirroring 2.6 exactly: the `default.png` stat and all `assert` tasks carry `when: not ansible_check_mode` (under `--check` the assets unarchive is skipped, so `default.png` is not yet present and an ungated assert would fail spuriously). The read-only `command -v csg` shell check MAY run under `--check` (it registers `rc` and mutates nothing) — only its assert needs the gate.

### Task design — the ordered task list (mirror-and-adapt of 2.6)

1. **Assert install_dir seam is provided** — `ansible.builtin.assert`, `that: install_dir is defined and install_dir | trim | length > 0`, referencing `install_dir` directly (no aliasing; lazy-eval could surface a raw undefined-var error). Copy verbatim from `roles/assets/tasks/main.yml:38-44`.
2. **Ensure palette output dir exists** — `ansible.builtin.file`, `path: "{{ default_palette_output_dir }}"`, `state: directory`. Idempotent + check-safe natively. Rationale: self-containment on a direct `default-palette.yaml` run + explicit dir contract (2.6 AC 9 discipline). CSG's renderer would auto-create it (`mkdir(parents=True, exist_ok=True)`) — this task is belt-and-suspenders so the role's ownership of the output dir is explicit and testable. NO `when:` gate (file module owns check-mode).
3. **Check for csg** — `ansible.builtin.shell: command -v csg`, `register: default_palette_csg_check`, `changed_when: false`, `failed_when: false`, with `environment: PATH: "{{ default_palette_bin_dir }}:{{ ansible_facts.env.PATH }}"`. `command -v` is a SHELL BUILTIN, must run via `shell` (review F1). The PATH prepend (mirror-and-adapt improvement over 2.6's `command -v weg`, which lacked it) ensures the guard finds `csg` in the uv bin dir even when `~/.local/bin` is not on the inherited playbook PATH — otherwise the bootstrap chain would FALSE-FAIL right after `cli_tools` installed `csg`. Read-only, so it runs under `--check` (no gate needed).
4. **Ensure csg is available** — `ansible.builtin.assert`, `that: default_palette_csg_check.rc == 0 and default_palette_csg_check.stdout | length > 0`, friendly fail_msg naming `~/.local/bin/csg` and the `cli-tools` playbook prerequisite, `when: not ansible_check_mode`.
5. **Check default.png presence** — `ansible.builtin.stat`, `path: "{{ default_palette_default_image }}"`, `register: default_palette_default_png`, `when: not ansible_check_mode`.
6. **Assert default.png is present** — `ansible.builtin.assert`, `that: default_palette_default_png.stat.exists`, fail_msg naming the exact path, `when: not ansible_check_mode`. (stat is check-safe; the assert MUST be gated because under `--check` the assets unarchive is skipped so the file is absent on a fresh target.) 2.6's guard is the primary chain guard; this one gives a friendly direct-run failure instead of a raw `csg` "file not found" traceback.
7. **Generate default palette** — `ansible.builtin.command` with the free-form form `"csg generate '{{ default_palette_default_image }}' -f {{ default_palette_formats | join(' -f ') }}"`. `default_palette_formats` is LOAD-BEARING (renders `-f conf -f gtk.css -f yaml`; do NOT hardcode the flags in the task, or the var and the task can silently diverge). Single-quote the path; the `command` module splits free-form args via shlex, so a space-containing `install_dir` is safe — mirror of 2.4's `uv tool install '{{ cli_tools_repo_root }}/{{ item.source }}'`. Plus:
   ```yaml
   environment:
     COLORSCHEME__OUTPUT__DIRECTORY: "{{ default_palette_output_dir }}"
     COLORSCHEME__OUTPUT__OVERWRITE: "true"
     PATH: "{{ default_palette_bin_dir }}:{{ ansible_facts.env.PATH }}"
   ```
   `when: not ansible_check_mode`. NO `creates:`. (An `argv:` list form is acceptable if you prefer it — see AC note — but the free-form quoted form matches the 2.4 precedent and keeps the AC's literal command readable. If you use `argv`, you must still emit one `-f`/`--format` per `default_palette_formats` entry.)
8. **No `become` anywhere** (AC 10) — locked by a structural test.

### The playbook — why no group_by (mirrors 2.4/2.5/2.6, not 2.3)

Palette generation is identical on Arch and Debian-family and consumes no `group_vars` (NFR-3). A simple `hosts: localhost` / `gather_facts: true` / `roles: [default_palette]` playbook is correct. `gather_facts: true` is REQUIRED — vars read `ansible_facts.env.*` (HOME, PATH).

### Privilege context (inherited from 2.3 OQ-1 / 2.4/2.5/2.6 resolution)

Everything this role writes lives under the user's `install_dir` and the user's `~/.local/bin`. Fully user-scoped: NO `become`/`become_user` anywhere (locked by a structural test). Corollary for Story 2.12's `bootstrap.yaml`: keep the default-palette play become-free.

### Decisions this story locks (make them explicit in the role header comment)

1. **Output dir mechanism:** env `COLORSCHEME__OUTPUT__DIRECTORY` (not `-o`), kept symmetric with the mandated `COLORSCHEME__OUTPUT__OVERWRITE` env override. The env override is load-bearing — without it the palette silently lands in `/tmp/color-scheme` (packaged default) and every downstream consumer fails.
2. **Format set:** `conf` + `gtk.css` + `yaml` (contract-driven, NOT the packaged `json`/`sh` defaults), and `default_palette_formats` is LOAD-BEARING — the task's `-f` flags derive from the var via `join(' -f ')`, never hardcoded, so the var and task cannot diverge.
3. **Regenerate semantics:** no `creates:`/existence gate; the task always runs on apply (reports `changed`) — SPEC-ratified.
4. **Check-mode:** generate + all assertion guards gated `when: not ansible_check_mode` so `--check` is genuinely dry.
5. **`~/.config/color-scheme-generator/settings.toml` is never touched by this role** (AC 4).

### Mirror-and-adapt discipline (Epic 1 retro action item)

This role deliberately mirrors the 2.6 assets role. The explicit "what differs from the mirror": (a) the single generate task uses `ansible.builtin.command` with free-form quoting instead of `argv` (2.6 used `argv` for the emit task; free-form matches 2.4 and keeps the `-f` flags readable), and it is gated `when: not ansible_check_mode` (2.6's emit was stat-gated rather than check-gated — a documented 2.6 limitation this role must NOT inherit); (b) `default_palette_output_dir` is a directory the role re-ensures, whereas 2.6's `assets_weg_effects_target` was a file; (c) the `command -v csg` guard prepends `default_palette_bin_dir` to PATH (2.6's `command -v weg` guard did not — a latent false-failure on the bootstrap chain if `~/.local/bin` is not on the inherited PATH); (d) the role has NO manifest parity test — there is no `dotfiles/provisioning/default-palette.yaml`; parity is replaced by locking `default_palette_formats` against the task's `-f` flags (via the load-bearing `join(' -f ')`) and the env contract. State this list in the role header.

## Project Structure Notes

- `src/provisioning/ansible/playbooks/default-palette.yaml` — NEW playbook (one-per-role; aggregate `bootstrap.yaml` is Story 2.12).
- `src/provisioning/ansible/roles/default_palette/tasks/main.yml` — NEW; only Python-free YAML.
- `src/provisioning/ansible/roles/default_palette/vars/main.yml` — NEW; bin dir + default image + output dir + formats (contract, not manifest parity).
- `src/provisioning/tests/unit/test_default_palette_role.py` — NEW structural real-file tests.
- Unchanged: `inventory/`, `requirements.yml`, `ansible.cfg`, `group_vars/`, `playbooks/{packages,cli-tools,filesystem,assets}.yaml`, `roles/{packages,cli_tools,filesystem,assets}/`, all of `src/provisioning/src/provisioning/` (the Python hexagon is untouched by this story), `dotfiles/provisioning/*.yaml`, `dotfiles/assets/**`.
- No new dependencies. No `bootstrap.yaml`. No other roles. No `.py` under `ansible/`.

## Testing Requirements

- Full gates: `uv run pytest` (289-pass baseline from Story 2.6 — see "Working tree" note below), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `python tests/architecture/test_layering.py` (standalone nicety).
- New `tests/unit/test_default_palette_role.py` (see Dev Notes "Task design" and the Tasks/Subtasks list): role tree existence; first-task install_dir assert; `file state: directory` on `{{ default_palette_output_dir }}`; `csg generate` command task whose `-f`/`--format` flags EQUAL `default_palette_formats`; env contract (`COLORSCHEME__OUTPUT__DIRECTORY` == `{{ default_palette_output_dir }}`, `COLORSCHEME__OUTPUT__OVERWRITE: "true"`, `PATH` starts with `{{ default_palette_bin_dir }}:`); NO `creates:`; `when: not ansible_check_mode` on the generate task; `command -v csg` shell guard (PATH prepended) + assert gated; `default.png` stat + assert gated; no `become`/`become_user`; vars use `ansible_facts.env` (F4); no absolute repo paths; playbook structure (localhost/gather_facts/roles, no become, no group_by); `ansible-playbook --syntax-check` skip-guard.
- Reuse the helpers from `test_filesystem_role.py`/`test_assets_role.py` verbatim: `_find_ansible_dir()`, `_TASK_KEYWORDS`, `_module_key()`, `_module()`, `_vars()`. Author a sibling test file — do NOT copy wholesale.
- Smoke check (manual, optional): `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg uv run ansible-playbook --syntax-check src/provisioning/ansible/playbooks/default-palette.yaml -e install_dir=/tmp/x`.

## Previous Story Intelligence

### Story 2.6 — Assets Role (the immediate predecessor; uncommitted review work in the tree — see "Working tree" below)
- **install_dir fail-loud assert** copied verbatim as the first task (`roles/assets/tasks/main.yml:38-44`). Reuse byte-for-byte.
- **`{{ install_dir | trim }}` trim lock** in all path-bearing vars/tasks — the assert validates the trimmed value; tasks must consume the trimmed value. [Source: 2-6-assets-role.md, roles/assets/tasks/main.yml]
- **`command -v` is a shell builtin → `ansible.builtin.shell` (F1)**; presence guard shape: register + `changed_when: false` + `failed_when: false`, then assert on `rc == 0 and stdout | length > 0`, gated `when: not ansible_check_mode`. [Source: 2-6-assets-role.md, roles/assets/tasks/main.yml:46-60]
- **default.png stat+assert pair** (stat registers, assert checks `stat.exists`), both gated `when: not ansible_check_mode` — an assert alone cannot check file existence; under `--check` the unarchive is skipped so the file is absent. [Source: 2-6-assets-role.md, roles/assets/tasks/main.yml:99-112]
- **`assets_weg_bin_dir` = `{{ ansible_facts.env.HOME }}/.local/bin`** prepended to PATH in the emit task (F4 lock: `ansible_facts.env`, never `ansible_env`). 2.7 mirrors as `default_palette_bin_dir` (same dir — it is where `csg` also lands via 2.4). [Source: roles/assets/vars/main.yml:25]
- **The 2.6 emit task is stat-gated, NOT check-gated** — a known 2.6 limitation (a fresh-target `--check` could run the command). 2.7 MUST NOT inherit this: gate the generate task `when: not ansible_check_mode`. [Source: 2-6-assets-role.md Review decision 1 + roles/assets/tasks/main.yml:114-128]
- **Test conventions:** `_find_ansible_dir()` anchored on `pyproject.toml`, `_module_key()`, `_creates_value` helper shape, syntax-check skip-guard. Reuse for `test_default_palette_role.py`. [Source: 2-6-assets-role.md, tests/unit/test_assets_role.py]
- **2.6 shipped the default.png guard AND explicitly expects 2.7 to re-assert it** before generating ("Story 2.7 re-asserts the same presence before generating the palette"). [Source: 2-6-assets-role.md Dev Notes "The default.png assert"]

### Story 2.5 — Filesystem Role
- Created `generated/palettes` in the spine (`roles/filesystem/vars/main.yml:37-46`) — 2.7 writes into it and re-ensures it for direct-run self-containment. [Source: roles/filesystem/vars/main.yml]

### Story 2.4 — CLI Tools Role
- Installs `csg`/`weg`/`itr` to `~/.local/bin` via `uv tool install` (`cli_tools_bin_dir`). 2.7's `default_palette_bin_dir` is the same dir — csg resolves on PATH only because of the prepend. [Source: roles/cli_tools/vars/main.yml:14]
- Free-form `command` with single-quoted path precedent: `uv tool install '{{ cli_tools_repo_root }}/{{ item.source }}'`. [Source: roles/cli_tools/tasks/main.yml:36-40]

### Story 2.2 — Ansible Scaffold
- `ansible.cfg` discovery via `ANSIBLE_CONFIG`; `roles_path = roles` resolves `roles/default_palette`. Direct runs must set `ANSIBLE_CONFIG`. [Source: 2-2-ansible-scaffold.md]
- `group_vars/all.yml` documents the `install_dir` fail-loud contract (never defaulted; orchestrator seam provides it). [Source: src/provisioning/ansible/group_vars/all.yml]

### Epic 1 retrospective (2026-08-08) — action item touching this story
- **"Mirror-and-adapt discipline"** — when copying sibling patterns, add an explicit "what differs from the mirror" checklist. Addressed in Dev Notes.

## Git Intelligence

- Current HEAD baseline: `a6a74c8` (`feat: implement story 2.6 assets role`).
- **Working tree note:** the tree currently carries UNCOMMITTED 2.6 code-review findings (`M src/provisioning/ansible/roles/assets/tasks/main.yml`, `M src/provisioning/tests/unit/test_assets_role.py`, `M 2-6-assets-role.md`, `M sprint-status.yaml`, `M deferred-work.md`) — the 2.6 review completed and landed on disk but was not yet committed. The 289-pass baseline includes them. Do NOT commit or revert them as part of this story; build on the current on-disk state. If a `git stash`/`checkout` is ever needed, preserve them.
- Commit flow pattern (follow it): `chore: create story 2.7 default palette role` (this story) → `feat: implement story 2.7 ...` → `fix: apply ... code review findings` → `chore: mark story 2.7 ... done`. Recent history: 2.6 landed the assets role (`117e5e3`, `a6a74c8`); 2.5 the filesystem role (`5325c8e`, `f95aa59`, `4f7f755`); 2.4 the cli_tools role (`d074371`, `13086b1`, `ec95944`); 2.3 the packages role (`48e826e`…`136f867`); 2.2 the Ansible scaffold; 2.1 the manifests.

## Latest Tech Information

- **ansible-core 2.20.3** installed locally; Python 3.12.12. `ansible.builtin.command`, `shell`, `file`, `stat`, `assert` are all ansible-core — no collections to install for this role.
- **`ansible.builtin.command` free-form is shlex-split with quote support** — single-quoting a path containing spaces is safe (2.4 precedent). The `command` module's check-mode support is ONLY the `creates`/`removes` file-gate — without it the command executes under `--check`, so the generate task MUST be gated `when: not ansible_check_mode`.
- **CSG settings resolution (config-assembler-engine):** `CompositePathResolver` = CLI `--config` → ENV path → traversal `settings.toml` (3 levels) → **XDG `~/.config/color-scheme-generator/settings.toml`** → packaged default (`src/color_scheme_generator/defaults/settings.toml`: `output.directory = "/tmp/color-scheme"`, `default_formats = ["json", "sh"]`, `overwrite = false`). Env prefix `COLORSCHEME`, separator `__`; `OsEnvironmentReader` lowercases the remainder into dotted keys. `OverrideRule("output.directory", {CLI, ENV})` and `OverrideRule("output.overwrite", {CLI, ENV})` are registered, so `COLORSCHEME__OUTPUT__DIRECTORY` and `COLORSCHEME__OUTPUT__OVERWRITE` are honored; bool coercion is `raw.lower() in ("true","1","yes","on")`. [Source: src/provisioning/../cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/config_resolver.py:84-101, src/shared/config-assembler-engine/src/config_assembler_engine/adapters/env_reader.py:7-16, type_coercer.py:23-24]
- **`csg generate` CLI:** positional `image_path`; `-f/--format` (multiple; `ColorFormat` enum incl. `conf`=`HYPRLAND`, `css`, `yaml`, `json`, `sh`, …); `-o/--output-dir`; `--backend`; `--config`; `--templates-dir`. When `-f` is provided it REPLACES `default_formats`. `resolved_output_dir = output_dir or settings.output.directory` — env `COLORSCHEME__OUTPUT__DIRECTORY` flows into `settings.output.directory` via the env override (NOT via `-o`), so it is honored. [Source: src/provisioning/../cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py:151-255]
- **Local renderer** always writes outputs (`output_path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)` then `write_text`); `overwrite` gates the container path. The env override is nonetheless REQUIRED by contract. [Source: src/provisioning/../color_scheme_generator/adapters/jinja_template_renderer.py:69-89]
- **`colors.conf.j2`** (CSG bundled template) renders `$background/$foreground/$cursor/$accent/$color0..15`; `$accent = rgb(colors[1])` and `$color1 = rgb(colors[1])` → **`$accent` equals `$color1`** (the Hyprland syntax contract Story 3.3 asserts on the generated file). [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.conf.j2]
- **`csg` binary location:** `uv tool install` default `$HOME/.local/bin/csg` (uv: `$UV_TOOL_BIN_DIR` → `$XDG_BIN_HOME` → `$HOME/.local/bin`). Prepending `default_palette_bin_dir` to PATH is required in the playbook run context.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#384-399] — Story 2.7 ACs (default_palette role)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#39] — FR-18 Default Palette Role
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#118] — Epic 2 internal dependency order (`cli_tools` → `assets` → `default_palette` → `compositor_configs` → `settings`; FR-18 needs FR-15 + FR-17)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#242-249] — FR-18 PRD detail + consequences (colors.conf Hyprland contract; tarball-replace → regenerate)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#245] — done-criterion 6 (palette generated; `$accent` == `$color1`; settings keep `overwrite = false`)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#45] — default palette generated at apply time; env-scoped overwrite; tarball-replace → regenerate
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#17] — `generated/palettes/` in the install spine
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#23] — default palette via `csg generate ... -f conf (plus standard formats)`; env-scoped overwrite never written into rendered settings
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#35-44] — CSG settings resolution + XDG path + packaged defaults; env prefix `COLORSCHEME`
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#63] — rendered settings keep `overwrite = false`; the role's single call overrides per-task
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#125-126] — colors.conf (Hyprland) / colors.css (Waybar) fragment provenance
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#61] — templates dir NOT a settings field; Phase 2 passes `--templates-dir` (Phase 1 does not)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#161] — plan §6 `roles/default_palette/` tree (`csg generate <install>/wallpapers/default.png -f conf`; env-scoped overwrite)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#152] — plan §6 `playbooks/default-palette.yaml`
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#204-205] — colors.conf/colors.css fragment contract
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#245] — done-criterion 6 detail
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#283] — plan §11 step 7 (roles in install order; `default_palette` after `assets`)
- [Source: src/provisioning/ansible/group_vars/all.yml] — `install_dir` fail-loud contract (never defaulted; orchestrator seam provides it)
- [Source: src/provisioning/ansible/roles/assets/tasks/main.yml:38-44] — install_dir assert to copy verbatim
- [Source: src/provisioning/ansible/roles/assets/tasks/main.yml:46-60] — `command -v weg` presence-guard shape (mirror for `csg`)
- [Source: src/provisioning/ansible/roles/assets/tasks/main.yml:99-112] — default.png stat+assert pair (mirror for 2.7)
- [Source: src/provisioning/ansible/roles/assets/vars/main.yml:25] — `assets_weg_bin_dir` derivation (mirror as `default_palette_bin_dir`)
- [Source: src/provisioning/ansible/roles/cli_tools/tasks/main.yml:36-40] — free-form single-quoted `command` precedent
- [Source: src/provisioning/ansible/roles/filesystem/vars/main.yml:37-46] — spine dirs incl. `generated/palettes` (2.5 created it)
- [Source: src/provisioning/tests/unit/test_assets_role.py] — structural-test template (helpers, parity shape, syntax-check skip-guard)
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py:151-255] — `csg generate` signature; `-f` replaces default_formats; output_dir resolution
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/config_resolver.py:84-101] — env override rules (`output.directory`, `output.overwrite` → ENV allowed)
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/settings/schema.py:16-20] — `OutputSettingsSchema` (`overwrite: bool = False` default)
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/settings.toml] — packaged defaults (`output.directory = "/tmp/color-scheme"`, `default_formats = ["json", "sh"]`, `overwrite = false`)
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py#31-40] — `ColorFormat` (HYPRLAND = "conf")
- [Source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.conf.j2] — Hyprland template (`$accent` == `$color1` contract)
- [Source: src/shared/config-assembler-engine/src/config_assembler_engine/adapters/env_reader.py:7-16] — env separator `__`; prefix-stripped dotted keys
- [Source: src/shared/config-assembler-engine/src/config_assembler_engine/adapters/type_coercer.py:23-24] — bool coercion (`"true"/"1"/"yes"/"on"`)
- [Source: _bmad-output/implementation-artifacts/2-6-assets-role.md] — previous-story intelligence (assert copy, trim lock, F1 shell, F4 ansible_facts, default.png guard, stat-vs-check gate limitation)
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml] — Epic 1 retro action item "Mirror-and-adapt discipline"; story 2-7 status
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — deferred items (none block 2.7; #164 resolved in 2.6)

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

### Completion Notes List

- Created Story 2.7 Default Palette Role context: `roles/default_palette/` (`tasks/main.yml`, `vars/main.yml`), `playbooks/default-palette.yaml`, `tests/unit/test_default_palette_role.py`.
- Locked the csg contract: env `COLORSCHEME__OUTPUT__DIRECTORY` + `COLORSCHEME__OUTPUT__OVERWRITE` scoped to the single generate task; explicit `-f conf -f gtk.css -f yaml`; NO `creates:` (FR-18 regenerate); `when: not ansible_check_mode` (dry-run must be dry).
- Status → ready-for-dev.
- Implemented the role: first task is the verbatim 2.5/2.6 fail-loud `install_dir` seam assert (AC 8); `file state: directory` re-ensures `{{ default_palette_output_dir }}` (AC 9, direct-run self-containment); `command -v csg` shell guard prepends `default_palette_bin_dir` to PATH (AC 11) + gated assert; `default.png` stat + assert pair both `--check`-gated (AC 6); the single `csg generate '{{ default_palette_default_image }}' -f {{ default_palette_formats | join(' -f ') }}` command task carries NO `creates:` (AC 7, FR-18 regenerate), is `--check`-gated, and sets the env contract (`COLORSCHEME__OUTPUT__DIRECTORY`, `COLORSCHEME__OUTPUT__OVERWRITE: "true"`, PATH prepend) — AC 2, 3, 5, 9. No `become` anywhere (AC 10).
- Tests: `tests/unit/test_default_palette_role.py` (20 tests) locks role tree, first-task assert, output-dir file task, `-f` flags == `default_palette_formats` (load-bearing join, no extra flags), env contract, no-`creates` + `--check` gate, csg guard (PATH prepend + gated assert), default.png stat+assert gates, no become, no absolute paths, `ansible_facts.env` (F4), trim lock, playbook structure (localhost/gather_facts/roles, no become, no group_by), and `ansible-playbook --syntax-check` (exit 0).
- Full suite 309 passed (baseline 289 + 20 new), `ruff check`/`ruff format --check`/`mypy` clean, `tests/architecture/test_layering.py` OK. Status → review.

### File List

- `src/provisioning/ansible/roles/default_palette/tasks/main.yml` (NEW)
- `src/provisioning/ansible/roles/default_palette/vars/main.yml` (NEW)
- `src/provisioning/ansible/playbooks/default-palette.yaml` (NEW)
- `src/provisioning/tests/unit/test_default_palette_role.py` (NEW)
- `_bmad-output/implementation-artifacts/2-7-default-palette-role.md` (this story)

### Review Findings

- [x] [Review][Patch] Use CSG in container mode (podman) — **DONE** in e18ecfe + follow-up and validated 2026-08-12: the `cli_tools` role builds the csg image (`csg install --container-engine <detected> --source-root {{ cli_tools_repo_root }}`, no `creates:`); the `default_palette` generate task sets `COLORSCHEME__RUNTIME__MODE: "container"` + `COLORSCHEME__CONTAINER__ENGINE: <detected>`; csg/weg `install` gained `--source-root` (env `CSG_SOURCE_ROOT`/`WEG_SOURCE_ROOT`) with PEP 610 `direct_url.json` fallback; `Dockerfile.base` normalized to `src/...` COPY paths (one context convention = repo root). **Engine is DETECTED at runtime (podman preferred, then docker, then fail loud)** — podman/docker are documented dependencies, not installed by this chain (see group_vars/all.yml; packages role 2.3 / bootstrap 3.1 to install). Empirical validation (podman 6.0.1 rootless): removed images → `csg install --container-engine podman --backend pywal` (no flag, direct_url fallback) rebuilt `csg-base`+`csg-pywal` from scratch (42s); container-mode `csg generate -f conf -f css -f yaml` → `success: True`, `colors.conf`/`colors.css`/`colors.yaml` in the forced output dir, `$accent == $color1`. Test suites green; ruff counts identical pre/post (no new lint debt). [src/provisioning/ansible/roles/default_palette/tasks/main.yml, roles/cli_tools/tasks/main.yml]
- [x] [Review][Patch] No post-generate verification of output files [src/provisioning/ansible/roles/default_palette/tasks/main.yml:110] — **DONE 2026-08-12**: added `Verify generated palette files exist` (stat loop over colors.conf/.css/.yaml in `{{ default_palette_output_dir }}`, registered, gated) + `Assert generated palette files are present` (`selectattr('stat.exists') | list | length == 3`, gated) after generate. `LocalProcessor._render_formats` collects render errors into `result.stderr` but `process_result` (adapters/output/base.py:24-27) never raises and `main.py` only exits 1 on `ColorSchemeError`, so csg can exit 0 with zero output files (also true in container mode). Validated: 3 present → pass, 1 missing → "Assertion failed"; `--check` dry-run clean; 280 tests green.
- [x] [Review][Defer] `default_palette_bin_dir` hardcodes `{{ ansible_facts.env.HOME }}/.local/bin`, ignoring uv's `$UV_TOOL_BIN_DIR → $XDG_BIN_HOME → $HOME/.local/bin` chain [src/provisioning/ansible/roles/default_palette/vars/main.yml:37-43] — deferred, pre-existing: the var's own comment documents the chain but only the last fallback is hardcoded; a user with either env var set gets `csg` installed elsewhere and the guard/generate false-fail. Mirrors the 2.4 `cli_tools_bin_dir` pattern verbatim; the fix (resolve uv's chain) must land chain-wide (2.4+) so 2.4's `creates:` and this role's PATH prepend agree — out of 2.7 scope.
- [x] [Review][Defer] `ansible_facts.env` (HOME/PATH) unguarded when the role is consumed outside its one-per-role playbook [src/provisioning/ansible/roles/default_palette/vars/main.yml:43, tasks/main.yml:72,104] — deferred, pre-existing: only a header comment in playbooks/default-palette.yaml:18-21 declares the `gather_facts: true` requirement; Story 2.12's aggregate `bootstrap.yaml` must set `gather_facts: true` on its play or every env reference raises a raw undefined-var error. Enforce/flag at 2.12 build time.
- [x] [Review][Defer] No root/user-scope guard; a root invocation silently writes the spine + palette under `/root/...` [src/provisioning/ansible/playbooks/default-palette.yaml:10-12] — deferred, pre-existing: `ansible_facts.env.HOME` follows the running user, so an elevated bootstrap diverges from the real user's layout with no detection. Matches the no-become discipline of 2.3-2.6; a chain-wide user-scope assertion (not just this role) is the right fix.
- [x] [Review][Defer] Non-string `install_dir` bypasses the friendly seam assert [src/provisioning/ansible/roles/default_palette/tasks/main.yml:55] — deferred, pre-existing: `-e install_dir=12345` passes `install_dir is defined`, then `install_dir | trim` raises a raw Jinja `strip()` TypeError instead of the intended `fail_msg`. The assert is a verbatim copy of the 2.5/2.6 assert; hardening (add `is string`) would diverge from the locked verbatim pattern — consider chain-wide. Edge case (non-string extra-var), low consequence.
- [x] [Review][Resolved] `csg install` could not bootstrap/refresh container images from a `uv tool`-installed csg (`_find_project_root` walked the installed venv → None → base build skipped, backend builds cache-hit a stale pre-`conf` image; fresh-machine build failed). **RESOLVED in e18ecfe**: `resolve_source_root()` (override → env → PEP 610 `direct_url.json` → package walk) in `oci_runtime/source_locator.py`; base image always built with `context_path` set. Empirically verified (see container-mode patch above). [src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/install_cmd.py]

### Review Findings — engine detection pass (2026-08-12)

- [x] [Review][Patch] Engine override escape hatch — **DONE**: added `cli_tools_container_engine_override: ""` / `default_palette_container_engine_override: ""` (empty = auto-detect podman→docker→fail; set e.g. `docker` to force). The probe is skipped when the override is set; a `set_fact` resolves `*_container_engine` from override-or-trimmed-probe; the fail-loud assert validates the RESOLVED value (still must be podman|docker) and its fail_msg shows the resolved value. Validated both paths (auto → `podman`, forced `docker`) with a throwaway playbook. [src/provisioning/ansible/roles/cli_tools/tasks/main.yml, roles/cli_tools/vars/main.yml, roles/default_palette/tasks/main.yml, roles/default_palette/vars/main.yml]
- [x] [Review][Patch] Fix stale docstring still referencing the deleted `default_palette_container_engine` [src/provisioning/tests/unit/test_default_palette_role.py:206] — **DONE**: docstring now documents the resolved `{{ default_palette_container_engine }}` value.
- [x] [Review][Patch] Reconcile contradictory check-mode doctrine in cli_tools tasks header [src/provisioning/ansible/roles/cli_tools/tasks/main.yml:8-9,68-70] — **DONE**: probe comment now states command/shell are skipped under `--check` (verified ansible-core 2.20.3) and the `Resolve container engine` set_fact falls back to "none" there; `default_palette` header claim "DO execute under --check" corrected to version-agnostic "gate kept as the locked contract".
- [x] [Review][Patch] Reword default_palette engine fail_msg — **DONE**: removed the self-defeating "run the cli-tools playbook first" hint; now names install/re-run and the override var.
- [x] [Review][Patch] Harden the engine assert against stdout whitespace — **DONE**: `| trim` applied to the probe stdout in the `set_fact` resolution.
- [x] [Review][Patch] Vars comment over-promise + deferred-work WEG pin — **DONE**: `default_palette` vars comment reframed; deferred-work WEG entry now says `<detected/override>` (mirror the detection), not a pinned podman.
- [x] [Review][Defer] Engine detection is presence-only, not usability — a broken podman (rootless misconfig, stale storage lock, missing cgroup/subuid) passes the probe, then `csg install`/`csg generate` fail later with the engine's raw error instead of the friendly message. A `podman info`/`docker info` usability pre-flight would make the fail-loud earlier. The chain still fails loudly downstream (no silent break). Deferred, pre-existing scope of "detect availability" [src/provisioning/ansible/roles/cli_tools/tasks/main.yml:75, roles/default_palette/tasks/main.yml:120]
- [x] [Review][Defer] Cross-role engine agreement is comment-only, not enforced — cli_tools builds `csg-<backend>-<engine>`; default_palette later re-probes with its own `default_palette_engine_check`. They agree when nothing changes PATH between runs (the bootstrap chain), but a direct-run split or an engine installed between the two roles can make generate request an image never built → missing-container-image error. Fix would be cli_tools `set_fact` propagation + default_palette prefer-fact-else-probe. Deferred (edge; both roles re-probe consistently in the aggregate play) [src/provisioning/ansible/roles/default_palette/tasks/main.yml:120,142]

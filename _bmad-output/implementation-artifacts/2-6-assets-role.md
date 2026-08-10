---
baseline_commit: 4f7f755
---

# Story 2.6: Assets Role

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-10: Implemented story — authored `roles/assets/` (`tasks/main.yml`, `vars/main.yml`), `playbooks/assets.yaml`, and `tests/unit/test_assets_role.py` (22 tests). Full suite 287 passed (baseline 265), ruff/mypy/layering clean. Status → review.
- 2026-08-10: Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor). Resolved 4 decisions + 8 patches: gated unarchive/copy under `--check` (fresh-target abort), added `tar -tzf` default.png membership guard, replaced emit `creates:` with stat-gate (regenerate on truncation), added fail-loud `weg` presence guard, `argv:` emit form (space-safe), parity tests now derive from `AssetKind.spine_segment()`, `_creates_value` checks module body, manifest name-uniqueness locked. 24 role tests (was 22) + 289 total passed, ruff/mypy/layering clean, syntax-check + `--check` fresh-target + real run + idempotency verified empirically. Status → done.

## Story

As an operator,
I want an `assets` role that deploys wallpaper, icon, template, and effect-catalog assets,
So that the tools have everything they need to read from the install spine.

## Acceptance Criteria

1. `roles/assets/` exists with `tasks/main.yml` and `vars/main.yml` (AC 1, FR-17)
2. `dotfiles/assets/wallpapers/wallpapers.tar.gz` unpacks to `<install>/wallpapers/` including `default.png` (AC 2, FR-17, chaining-spine.md)
3. SVG icon templates deploy to `<install>/icon-templates/` (AC 3, FR-17)
4. Icon color-mapping YAMLs deploy to `<install>/icon-mappings/` (AC 4, FR-17)
5. CSG bundled templates deploy to `<install>/csg-templates/` (AC 5, FR-17)
6. `weg dump-effects --output <install>/weg-effects.yaml` emits the effects catalog (AC 6, FR-17)
7. Every task is idempotent (AC 7, FR-17, NFR-1)
8. The `install_dir` seam extra-var is required and fails loudly when missing — the FIRST task is a fail-loud assert, no silent default (group_vars/all.yml contract + Story 2.5 discipline)
9. Asset deploy-target dirs are guaranteed to exist before unpack — `ansible.builtin.unarchive` does NOT create its `dest` ("The given path must exist"), so the role re-ensures its own four spine targets (self-contained + direct-playbook-run safe)
10. FR-18 regenerate semantics preserved: the unarchive task must NOT carry `creates:` on the tarball — replacing `wallpapers.tar.gz` in the repo must cause the next `apply` to re-extract so Story 2.7 can regenerate the palette
11. `default.png` presence is asserted after the unpack (via a `stat` + `assert` pair, gated `when: not ansible_check_mode`) — the role fails loudly if the tarball regresses (feeds Story 2.7's same assertion; chaining-spine.md assumption)
12. No `become`/`become_user` anywhere in the role or playbook (user-scoped privilege context — inherited from 2.3 OQ-1 / 2.4 resolution)
13. All sources are interpolated via `{{ assets_repo_root }}` — never absolute repo paths; directory copy sources end with `/` (contents-into-dest semantics, no accidental nested dir)
14. The `weg dump-effects` task is check-mode-safe and idempotent via `creates:` and resolves `weg` with `{{ assets_weg_bin_dir }}` prepended to PATH (mirror-and-adapt of Story 2.4); env facts via `ansible_facts.env.*`, never deprecated `ansible_env` (F4 lock)
15. The role vars partition the `dotfiles/provisioning/assets.yaml` manifest exactly (copy entries / wallpaper tarball / weg-effects emit) — parity locked by a structural test (resolves the Story 2.1 deferred item "Ansible should key off kind + spine_segment(), not name" at the role layer)
16. `playbooks/assets.yaml` exists: `hosts: localhost`, `gather_facts: true`, `roles: [assets]`, NO `become`, NO `group_by` (distro-agnostic — mirror filesystem/cli_tools, not packages)

## Tasks / Subtasks

- [x] Create the `roles/assets/` role directory tree (AC: 1)
  - [x] `src/provisioning/ansible/roles/assets/tasks/main.yml`
  - [x] `src/provisioning/ansible/roles/assets/vars/main.yml`
- [x] Author `vars/main.yml` (AC: 2, 3, 4, 5, 6, 14, 15)
  - [x] `assets_repo_root` — `{{ playbook_dir }}/../../../..` (mirror `cli_tools_repo_root` exactly)
  - [x] `assets_weg_bin_dir` — `{{ ansible_facts.env.HOME }}/.local/bin` (uv default bin dir, mirror `cli_tools_bin_dir`; uses `ansible_facts.env`, F4)
  - [x] `assets_deploy_dirs` — the four spine segments this role deploys into: `wallpapers`, `icon-templates`, `icon-mappings`, `csg-templates` (AC 9)
  - [x] `assets_wallpapers_tarball` — `dotfiles/assets/wallpapers/wallpapers.tar.gz` (bare manifest value; repo root is prefixed in the task)
  - [x] `assets_wallpapers_dest` — `{{ install_dir | trim }}/wallpapers` (trim lock: matches the `install_dir` assert's validated value)
  - [x] `assets_copies` — the three directory-based asset kinds as `(name, kind, source, target)` mirroring the manifest; each `source` ENDS WITH `/` (contents semantics); `target` is the spine segment:
    - `{ name: icon-templates, kind: icon-template, source: dotfiles/assets/icon-templates/, target: icon-templates }`
    - `{ name: icon-mappings, kind: icon-mapping, source: dotfiles/config/icon-template-color-scheme-mappings/, target: icon-mappings }`
    - `{ name: csg-templates, kind: csg-template, source: src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/, target: csg-templates }` (trailing `/` ADDED here; the manifest source has none — the parity test normalizes with `rstrip("/")`)
  - [x] `assets_weg_effects_target` — `{{ install_dir | trim }}/weg-effects.yaml` (trim lock)
- [x] Author `tasks/main.yml` (AC: 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14)
  - [x] Fail-loud seam guard: `ansible.builtin.assert` that `install_dir is defined and install_dir | trim | length > 0` — the FIRST task, exact copy of the 2.5 filesystem assert (AC 8)
  - [x] Ensure deploy targets exist: `ansible.builtin.file` `state: directory`, `path: "{{ install_dir | trim }}/{{ item }}"`, looping `assets_deploy_dirs` (AC 9 — unarchive's `dest` must pre-exist; idempotent; check-safe)
  - [x] Unpack wallpapers: `ansible.builtin.unarchive` `src: "{{ assets_repo_root }}/{{ assets_wallpapers_tarball }}"`, `dest: "{{ assets_wallpapers_dest }}"`, `remote_src: true` — NO `creates:` (AC 2, AC 10)
  - [x] Deploy directory kinds: `ansible.builtin.copy` `src: "{{ assets_repo_root }}/{{ item.source }}"`, `dest: "{{ install_dir | trim }}/{{ item.target }}"`, `remote_src: true`, looping `{{ assets_copies }}` (AC 3, 4, 5, 13)
  - [x] Assert `default.png` unpacked: `ansible.builtin.stat` on `{{ install_dir | trim }}/wallpapers/default.png` (register a var), then `ansible.builtin.assert` that the registered var's `stat.exists` is true — an `assert` alone CANNOT check file existence (it only evaluates a condition), the `stat` is mandatory; both tasks gated `when: not ansible_check_mode` (AC 11)
  - [x] Emit WEG effects: `ansible.builtin.command` `weg dump-effects --output {{ install_dir | trim }}/weg-effects.yaml`, `args.creates: "{{ install_dir | trim }}/weg-effects.yaml"`, `environment.PATH: "{{ assets_weg_bin_dir }}:{{ ansible_facts.env.PATH }}"` (AC 6, AC 14)
  - [x] No `become:` anywhere (AC 12)
- [x] Author `playbooks/assets.yaml` (AC: 16)
  - [x] `hosts: localhost`, `gather_facts: true`, `roles: [assets]`
  - [x] NO `become: true`
  - [x] NO `group_by` — asset deployment is distro-agnostic (NFR-3); do not cargo-cult the packages pattern
  - [x] `gather_facts: true` REQUIRED — vars read `ansible_facts.env.*` (PATH, HOME)
- [x] Add structural real-file tests `tests/unit/test_assets_role.py` (AC: 1-16; mirror `test_filesystem_role.py`/`test_cli_tools_role.py` conventions)
  - [x] Role tree exists: `tasks/main.yml`, `vars/main.yml` (walk up from test file anchored on `pyproject.toml` — mirror `_find_ansible_dir()`)
  - [x] `tasks/main.yml` parses as a list of named task dicts
  - [x] First task is the fail-loud `install_dir` assert (AC 8)
  - [x] A `file` `state: directory` task creates exactly the four deploy targets under `install_dir` (AC 9)
  - [x] An `ansible.builtin.unarchive` task unpacks `wallpapers.tar.gz` into `{{ install_dir }}/wallpapers` with `remote_src: true` (AC 2)
  - [x] The unarchive task carries NO `creates:` (AC 10 — FR-18 regenerate semantics)
  - [x] Exactly one `ansible.builtin.copy` task loops `{{ assets_copies }}`, `remote_src: true`, src `{{ assets_repo_root }}/{{ item.source }}`, dest `{{ install_dir }}/{{ item.target }}` (AC 3-5)
  - [x] Every copy `source` ends with `/` (contents-into-dest semantics, AC 13)
  - [x] An `ansible.builtin.command` task runs `weg dump-effects --output {{ install_dir }}/weg-effects.yaml` with `creates: "{{ install_dir }}/weg-effects.yaml"` and PATH prepending `{{ assets_weg_bin_dir }}` (AC 6, AC 14)
  - [x] A `ansible.builtin.stat` task targets `{{ install_dir }}/wallpapers/default.png`, and an `ansible.builtin.assert` checks the registered var's `stat.exists`, both gated `when: not ansible_check_mode` (AC 11)
  - [x] No `become`/`become_user` anywhere in the role (AC 12)
  - [x] No absolute repo paths hardcoded — all sources interpolated via `{{ assets_repo_root }}/` (AC 13)
  - [x] `vars/main.yml` uses `ansible_facts.env`, never `{{ ansible_env.` (F4 lock)
  - [x] Parity: `assets_copies` names ∪ `{wallpapers, weg-effects}` == manifest `entries` names; copies match the manifest by `(name, kind, source.rstrip("/"))`; every copy `target` equals the kind→spine-segment mapping `{icon-template: icon-templates, icon-mapping: icon-mappings, csg-template: csg-templates}` (the deferred #164 "key off spine_segment(), not name" lock); the wallpaper tarball var equals the manifest wallpapers `source`; the manifest `weg-effects` entry has kind `weg-effects` and no `source` (AC 15)
  - [x] `playbooks/assets.yaml` parses: `hosts: localhost`, `gather_facts: true`, `roles: [assets]`, no `become`
  - [x] `ansible-playbook --syntax-check` on `assets.yaml` (with `-e os_family=arch -e install_dir=/tmp/x`) exits 0 (skip-guard when `ansible-playbook` absent — mirror 2.4 F6)
- [x] Verify full suite + lint + layering guard (AC: 7)
  - [x] `uv run pytest` — full suite green, nothing regresses from the 265-pass baseline (Story 2.5)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)

### Review Findings

#### decision-needed

- [x] [Review][Decision] `--check` hard-fails on a fresh install_dir — RESOLVED: unarchive AND copy tasks gated `when: not ansible_check_mode`; fresh-target `--check` now completes cleanly (verified). [src/provisioning/ansible/roles/assets/tasks/main.yml:52]
- [x] [Review][Decision] AC 11 default.png guard is a no-op for content regression — RESOLVED: added `tar -tzf` archive-membership check + assert (locked by test) before unpack, so a regressed tarball fails loudly even when a stale default.png lingers. [src/provisioning/ansible/roles/assets/tasks/main.yml:65-78]
- [x] [Review][Decision] `creates:` freezes a corrupt/partial weg-effects.yaml forever — RESOLVED: replaced `creates:` with a stat-gated emit (`when: not exists or size == 0`) so a truncated/partial catalog regenerates on the next apply (FR-18-consistent); verified by truncating the catalog and re-running. [src/provisioning/ansible/roles/assets/tasks/main.yml:84]
- [x] [Review][Decision] Direct assets.yaml run without `weg` fails opaque rc=2 — RESOLVED: added the 2.4-mirror fail-loud `command -v weg` shell guard + assert (locked by test) before the deploy tasks. [src/provisioning/ansible/roles/assets/tasks/main.yml:80-86]

#### patch

- [x] [Review][Patch] Unquoted `--output` path breaks install_dir paths containing spaces — FIXED: emit task uses `argv:` list form (verified with a space-containing install_dir). [src/provisioning/ansible/roles/assets/tasks/main.yml:81]
- [x] [Review][Patch] #164 lock tests a hardcoded `kind_to_segment` literal, not the domain — FIXED: parity test imports `AssetKind` and derives targets from `spine_segment()`. [src/provisioning/tests/unit/test_assets_role.py:355]
- [x] [Review][Patch] `assets_weg_effects_target` is dead config — FIXED: emit task (argv + stat gate) now consumes the var; test asserts the task targets it. [src/provisioning/ansible/roles/assets/vars/main.yml:59]
- [x] [Review][Patch] `test_no_absolute_repo_paths_hardcoded` is hollow — FIXED: now inspects every task's `src`/`argv` and rejects hardcoded absolute paths. [src/provisioning/tests/unit/test_assets_role.py:285]
- [x] [Review][Patch] Parity never validates the wallpapers `kind` nor ties `assets_deploy_dirs` to `spine_segment()` — FIXED: wallpapers kind asserted; deploy dirs derived from the enum. [src/provisioning/tests/unit/test_assets_role.py:373]
- [x] [Review][Patch] `_creates_value` misses `creates` declared inside the module dict — FIXED: helper now checks top-level, args, and module body. [src/provisioning/tests/unit/test_assets_role.py:79-87]
- [x] [Review][Patch] Parity collapses duplicate manifest/copy names — FIXED: uniqueness asserted on manifest names. [src/provisioning/tests/unit/test_assets_role.py:347]
- [x] [Review][Patch] Playbook `become_user` unchecked — FIXED: test now asserts `become_user` absent at play level. [src/provisioning/tests/unit/test_assets_role.py:390]

#### defer

- [x] [Review][Defer] `assets_weg_bin_dir` re-derives `~/.local/bin` instead of consuming `cli_tools_bin_dir`; both diverge when UV_TOOL_BIN_DIR/XDG_BIN_HOME are set — cross-role shared-var design, not this story [src/provisioning/ansible/roles/assets/vars/main.yml:25] — deferred, pre-existing

## Dev Notes

### Scope — what Story 2.6 is and is not

**IS:** the `roles/assets/` role (`tasks/main.yml`, `vars/main.yml`) and the `playbooks/assets.yaml` playbook under `src/provisioning/ansible/`, plus structural real-file tests. The role deploys the five asset kinds from the repo into the install spine that the filesystem role (2.5) created (FR-17, chaining-spine.md). It is the CONSUMER of the 2.5 spine dirs and the PREREQUISITE for the `default_palette` (2.7) role (which needs `default.png` unpacked) and for `settings` (2.11) and the verify gate (2.12, done-criteria 4).

**IS NOT:** other roles (`default_palette` — 2.7; `compositor_configs` — 2.9; `symlinks` — 2.10; `settings` — 2.11; `verify` — 2.12), the aggregate `bootstrap.yaml` (Story 2.12), `scripts/bootstrap.sh` (Story 3.1), integration `--check`/dry-run tests (Story 3.2/3.3). Do NOT author any other role or playbook. Do NOT render settings, do NOT run `csg generate` (that is 2.7), do NOT place compositor configs (that is 2.9), do NOT modify the `dotfiles/assets/**` content or the `dotfiles/provisioning/assets.yaml` manifest (locked in Story 2.1; its `kind`+`source` schema is enforced by `yaml_manifest_reader.py`).
- **Do NOT create filesystem dirs beyond the four deploy targets** — the full spine layout is the filesystem role's (2.5) job and is parity-locked to `filesystem.yaml`. This role only re-ensures its own four deploy targets so `unarchive`'s "dest must exist" contract holds on a direct playbook run.

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
│   └── assets.yaml                   ← NEW (this story)
└── roles/
    ├── packages/                     (Story 2.3 — unchanged)
    ├── cli_tools/                    (Story 2.4 — unchanged)
    ├── filesystem/                   (Story 2.5 — unchanged)
    └── assets/
        ├── tasks/main.yml            ← NEW
        └── vars/main.yml             ← NEW
```

- Everything lives OUTSIDE `_SRC_ROOT` — YAML only, never scanned by `tests/architecture/test_layering.py`, never part of the Python hexagon. **Do NOT add any `.py` file under `ansible/`** (same rule as Stories 2.3-2.5).
- Role dir `assets` and playbook file `assets.yaml` are both single-word — no underscore/hyphen divergence (unlike `cli_tools` role vs `cli-tools.yaml`).
- The playbook is runnable directly with `ansible-playbook` for `--check` verification; aggregation into `bootstrap.yaml` is Story 2.12. The executor's `--tags all` (Story 1.8) applies to the aggregate playbook only.

### The manifest → role data flow (deferred item #164 resolved here)

- **The desired asset list lives in `dotfiles/provisioning/assets.yaml`** (Story 2.1): five entries, each `{name, kind, source}` (the `weg-effects` entry has NO `source` — it is emitted, not copied). The rich `kind`+`source` keys are validated by `YamlManifestReader` and read directly by Ansible.
- **Ansible does not read manifests** (Story 2.1 ratified). The assets role mirrors the manifest in `vars/main.yml` with a parity test — the exact analogue of 2.4's `cli_tools` parity and 2.5's filesystem parity.
- **Deferred item being resolved here:** deferred-work.md#164 — "`spine_segment()` 'single source of truth' unenforced — no check that entry `name` == `spine_segment()`; `weg-effects` name diverges (file target). Ansible (Stories 2.3-2.12) should key off `kind` + `spine_segment()`, not `name`." Resolution: the role keys deploy semantics off **kind** (wallpaper → `unarchive`; directory kinds → `copy` loop; `weg-effects` → command emit), and each entry's `target` IS the spine segment (`AssetKind.spine_segment()`). The parity test locks the role's partition against the manifest's `entries` AND asserts every copy `target` equals the kind→segment mapping (`icon-template`→`icon-templates`, `icon-mapping`→`icon-mappings`, `csg-template`→`csg-templates`) so the role can never silently diverge from `spine_segment()`. `weg-effects` → file target `weg-effects.yaml` is captured by `assets_weg_effects_target` (a FILE, not a dir) — never in `assets_deploy_dirs` or `assets_copies`. [Source: deferred-work.md#164, enums.py:87-104]
- **Three-role partition:** the manifest's five entries split into (a) the three directory copies (`icon-templates`, `icon-mappings`, `csg-templates`), (b) the wallpaper tarball (unarchive), (c) the `weg-effects` emit. A parity test asserts the union covers every manifest entry name exactly.

### Install-dir seam — fail loud, never default (AC 8)

- Same discipline as Story 2.5: `group_vars/all.yml` documents that `install_dir` is deliberately NOT defaulted; the orchestrator seam always provides it via `--extra-vars`. The FIRST task is the identical `ansible.builtin.assert` (copy it verbatim from `roles/filesystem/tasks/main.yml:24-30`), referencing `install_dir` directly — do NOT alias it into a var (lazy evaluation could surface a raw undefined-var error instead of the assert message).
- Use `{{ install_dir | trim }}` in the path-bearing tasks too (2.5 review lock: the assert validates the trimmed value, so tasks must consume the trimmed value).

### Module choices — the three different idempotency shapes in ONE role

This role is a mix of all three module classes, so do NOT cargo-cult a single pattern:

1. **`ansible.builtin.file` (dir guarantee, AC 9)** — `state: directory` loop over `assets_deploy_dirs` with `path: "{{ install_dir | trim }}/{{ item }}"`. Owns idempotency + check-mode natively. This exists because `unarchive` **does not create its `dest`** — "The given path must exist. Base directory is not created by this module" [Source: unarchive docs]. On the bootstrap chain `filesystem` (2.5) has already created these; on a direct `assets.yaml` run this task makes the role self-contained.
2. **`ansible.builtin.unarchive` (wallpapers, AC 2)** — `src: "{{ assets_repo_root }}/{{ assets_wallpapers_tarball }}"`, `dest: "{{ assets_wallpapers_dest }}"`, `remote_src: true` (the tarball is already on the target — the repo is local). **CRITICAL: NO `creates:`.** 
   - FR-18 (Story 2.7) requires "replacing `wallpapers.tar.gz` in the repo causes the next `apply` to regenerate [the palette]". A `creates: <install>/wallpapers/default.png` would skip the task whenever `default.png` exists, so a NEW tarball would never re-extract and the palette would never regenerate. The unarchive module's natural behavior re-extracts when archive content differs and reports `ok` when the dest already matches — that is the idempotency AC 7 wants AND the regenerability 2.7 depends on.
   - Check-mode caveat (document, do not fight it): `unarchive`'s check_mode support is **partial — "Not supported for gzipped tar files"**, so the task is SKIPPED under `--check` (reports `skipped`, never mutates). That keeps "dry-run must be dry" (hardening note) satisfied; the skip is acceptable and clean. Do not add a `when:` or hacks to force a would-change report.
   - The tarball was verified to contain `default.png` at its root (55 entries, no top-level dir) — it extracts directly into `<install>/wallpapers/`.
3. **`ansible.builtin.copy` (directory kinds, AC 3-5)** — `src: "{{ assets_repo_root }}/{{ item.source }}"`, `dest: "{{ install_dir | trim }}/{{ item.target }}"`, `remote_src: true`, loop over `assets_copies`. Check-mode support is **full**; idempotent via checksums; auto-creates `dest` when `src` is a directory. **Every `source` must end with `/`** so the *contents* land directly in the target — without the slash, the `templates` dir itself would nest under `csg-templates/`. The manifest's `csg-templates` source has NO trailing slash; add it in the role var and normalize (`rstrip("/")`) in the parity test.
   - Note: the `copy` module's recursive facility does not scale to hundreds of files — the icon-templates tree is ~48 files, well within limits. No `synchronize` needed.
4. **`ansible.builtin.command` (weg-effects, AC 6)** — `weg dump-effects --output {{ install_dir | trim }}/weg-effects.yaml` with `args.creates: "{{ install_dir | trim }}/weg-effects.yaml"` and `environment.PATH: "{{ assets_weg_bin_dir }}:{{ ansible_facts.env.PATH }}"`. This is the Story 2.4 command+`creates` pattern verbatim (check-mode-safe by construction — filesystem check, not a registered rc; idempotent — file exists ⇒ skipped). Use the trimmed `install_dir` (2.5 lock), consistent with `assets_weg_effects_target`.
   - The `--output` target ends in `.yaml`, so `weg dump-effects` writes the file directly (its `dump_effects_command` writes the file when `output_path.suffix == ".yaml"`, `mkdir(parents=True, exist_ok=True)` on the parent). It is a real tool output, never pre-seeded — the file must not be `state: touch`-ed or templated (filesystem 2.5 already guarantees its parent).
   - **PATH resolution:** `weg` is installed by the `cli_tools` role (2.4) into `~/.local/bin` (`uv tool install`), which may not be on the inherited PATH in the playbook run context. Prepend `{{ assets_weg_bin_dir }}` (== `{{ ansible_facts.env.HOME }}/.local/bin`, mirror of `cli_tools_bin_dir`) exactly like 2.4's verify task.
   - **Optional (mirror-and-adapt of 2.4's uv guard):** a fail-loud `weg`-presence assert (`ansible.builtin.shell command -v weg` register + `assert`, gated `when: not ansible_check_mode`) gives a friendlier message than a raw rc=127. It is OPTIONAL here — unlike 2.4 there is a single `weg` call, so the command's own failure is already loud. If you include it, mirror 2.4 exactly (shell module for the `command -v` builtin — code-review F1). The structural test only locks the command+`creates`+environment shape, which must exist either way.

### The default.png assert (AC 11)

- After the unarchive task, verify `<install>/wallpapers/default.png` was actually unpacked — a tarball regression must fail loudly at the assets role, not be discovered downstream. **Implementation shape (two tasks, not one):** an `ansible.builtin.stat` on `{{ install_dir | trim }}/wallpapers/default.png` with `register:`, followed by an `ansible.builtin.assert` on the registered var's `stat.exists` (e.g. `that: assets_default_png.stat.exists` with a clear fail_msg naming the expected path). An `ansible.builtin.assert` alone only evaluates a Jinja condition — it CANNOT check file existence; omitting the `stat` makes the guard a no-op. `stat` is read-only and check-mode-safe, so only the `assert` strictly needs the gate; gate BOTH with `when: not ansible_check_mode` anyway (like 2.4's uv assert) because under `--check` the unarchive task is skipped and the file would not be present yet, which would make the assert fail spuriously on a dry-run. Story 2.7 re-asserts the same presence before generating the palette — do not duplicate effort there, just ship the guard here.

### Playbook — why no group_by (mirrors 2.4/2.5, not 2.3)

`assets` deployment is identical on Arch and Debian-family and consumes no `group_vars` (NFR-3). A simple `hosts: localhost` / `gather_facts: true` / `roles: [assets]` playbook is correct. `gather_facts: true` is REQUIRED — vars read `ansible_facts.env.*` (HOME, PATH).

### Privilege context (inherited from 2.3 OQ-1 / 2.4/2.5 resolution)

Everything this role writes lives under the user's `install_dir`. Fully user-scoped: NO `become`/`become_user` anywhere (locked by a structural test). Corollary for Story 2.12's `bootstrap.yaml`: keep the assets play become-free.

### Testing — real-file structural tests (mirror 2.5/2.4 conventions)

- Author `tests/unit/test_assets_role.py` following `test_filesystem_role.py` exactly: `_find_ansible_dir()` walking up from the test file anchored on `pyproject.toml`, module-level `_ANSIBLE_DIR`/`_ROLES_DIR`/`_REPO_ROOT`, `_TASK_KEYWORDS` + `_module_key()`, `yaml.safe_load` on the real files. Do NOT copy the filesystem/cli_tools test files — author a sibling.
- The parity test is the critical one. Load `assets.yaml` entries and assert:
  - `{assets_copies names} ∪ {wallpapers, weg-effects} == {manifest entry names}`,
  - `assets_copies` matches the manifest by `(name, kind, source.rstrip("/"))` for the three directory entries,
  - every copy `target` equals the kind→spine-segment mapping `{icon-template: icon-templates, icon-mapping: icon-mappings, csg-template: csg-templates}` (deferred #164 lock — the role keys off `spine_segment()`, not `name`),
  - `assets_wallpapers_tarball == manifest wallpapers.source`,
  - the manifest `weg-effects` entry has `kind == "weg-effects"` and no `source`.
- `ansible-playbook --syntax-check` invocation (mirror 2.5/2.4): `ANSIBLE_CONFIG=<ansible>/ansible.cfg ansible-playbook --syntax-check <ansible>/playbooks/assets.yaml -e os_family=arch -e install_dir=/tmp/x`; wrap in `shutil.which("ansible-playbook")` skip-guard (2.4 review F6). `--syntax-check` does not run tasks (safe in CI).
- Do NOT add integration dry-run tests that actually unpack/copy — that is Story 3.2/3.3 territory. The structural module-shape assertions ARE the AC 2-7 lock.
- For the no-`creates` on unarchive test: locate the `ansible.builtin.unarchive` task and assert `_creates_value(task) is None` (reuse the `_creates_value` helper shape from `test_cli_tools_role.py`).

### Known limitations (accept, do not fix here)

- `unarchive` under `--check` reports `skipped` for the `.tar.gz` (partial check-mode support). The dry-run still "completes cleanly" (Story 3.2 requires clean completion, not would-change for every task).
- The role does not verify ITR listability of the deployed mappings (`icons.yaml`) — that is the verify gate (2.12) and integration tests (3.3).
- Copy does not prune files removed from the source trees (e.g. an icon deleted from `dotfiles/assets/icon-templates/` stays in `<install>/icon-templates/`). Acceptable — content hashing/pruning is out of scope (SPEC non-goals); a fresh machine starts clean.

## Project Structure Notes

- `src/provisioning/ansible/playbooks/assets.yaml` — NEW playbook (one-per-role; aggregate `bootstrap.yaml` is Story 2.12).
- `src/provisioning/ansible/roles/assets/tasks/main.yml` — NEW; only Python-free YAML.
- `src/provisioning/ansible/roles/assets/vars/main.yml` — NEW; repo root + bin dir + deploy-target dirs + copies (parity-locked to the manifest) + weg-effects target.
- `src/provisioning/tests/unit/test_assets_role.py` — NEW structural real-file tests.
- Unchanged: `inventory/`, `requirements.yml`, `ansible.cfg`, `group_vars/`, `playbooks/{packages,cli-tools,filesystem}.yaml`, `roles/{packages,cli_tools,filesystem}/`, all of `src/provisioning/src/provisioning/` (the Python hexagon is untouched by this story).
- Unchanged on the manifest side: `dotfiles/provisioning/assets.yaml` is the source of truth the role mirrors; do NOT edit it (locked in Story 2.1). Unchanged on the asset content side: everything under `dotfiles/assets/` and `dotfiles/config/icon-template-color-scheme-mappings/`.
- No new dependencies. No `bootstrap.yaml`. No other roles.

## Testing Requirements

- Full gates: `uv run pytest` (265-pass baseline from Story 2.5, HEAD `4f7f755`), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `python tests/architecture/test_layering.py` (standalone nicety).
- New `tests/unit/test_assets_role.py` (see Dev Notes "Testing") covering:
  - role tree existence + `tasks/main.yml` parses to a list of named tasks;
  - first task is the `ansible.builtin.assert` requiring `install_dir` (AC 8);
  - a `file` `state: directory` task creates exactly `{{ install_dir }}/{{ item }}` over `assets_deploy_dirs` == {wallpapers, icon-templates, icon-mappings, csg-templates} (AC 9);
  - the `ansible.builtin.unarchive` task unpacks `{{ assets_repo_root }}/{{ assets_wallpapers_tarball }}` → `{{ assets_wallpapers_dest }}` with `remote_src: true` (AC 2);
  - the unarchive task has NO `creates:` (AC 10);
  - exactly one `ansible.builtin.copy` task loops `{{ assets_copies }}`, `remote_src: true`, `src: "{{ assets_repo_root }}/{{ item.source }}"`, `dest: "{{ install_dir }}/{{ item.target }}"` (AC 3-5);
  - every copy `source` ends with `/` (AC 13);
  - an `ansible.builtin.command` task runs `weg dump-effects --output {{ install_dir }}/weg-effects.yaml` with `creates: "{{ install_dir }}/weg-effects.yaml"` and `environment.PATH` starting with `{{ assets_weg_bin_dir }}:` (AC 6, AC 14);
  - a `ansible.builtin.stat` task on `{{ install_dir }}/wallpapers/default.png` plus an `ansible.builtin.assert` on its registered `stat.exists`, both gated `when: not ansible_check_mode` (AC 11);
  - no `become`/`become_user` in the role (AC 12);
  - no absolute repo paths — sources interpolated via `{{ assets_repo_root }}/` (AC 13);
  - vars use `ansible_facts.env`, never `{{ ansible_env.` (F4 lock);
  - vars parity with `assets.yaml` manifest (union + copies-by-(name,kind,source) + copy `target`==spine-segment mapping + tarball + weg-effects-no-source) (AC 15);
  - `playbooks/assets.yaml` structure (`hosts: localhost`, `gather_facts: true`, `roles: [assets]`, no `become`);
  - `ansible-playbook --syntax-check` on `assets.yaml` (with `-e os_family=... -e install_dir=...`) exits 0, skip-guarded when `ansible-playbook` is absent.
- Smoke check (manual, optional): `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg uv run ansible-playbook --syntax-check src/provisioning/ansible/playbooks/assets.yaml -e os_family=arch -e install_dir=/tmp/x`.

## Previous Story Intelligence

### Story 2.5 — Filesystem Role (the immediate predecessor and the consumer of THIS role's output)
- **`install_dir` fail-loud assert pattern:** first task, `ansible.builtin.assert` on `install_dir is defined and install_dir | trim | length > 0`, referencing `install_dir` directly (no aliasing into a var). Copy verbatim; assets writes into the same spine. [Source: 2-5-filesystem-role.md "install_dir seam", roles/filesystem/tasks/main.yml:24-30]
- **`{{ install_dir | trim }}` in path-bearing tasks** (2.5 review lock) — the assert validates the trimmed value; tasks must consume the trimmed value. [Source: 2-5-filesystem-role.md Review Findings, roles/filesystem/tasks/main.yml:49]
- **The spine dirs already exist** — 2.5 created `wallpapers/`, `icon-templates/`, `icon-mappings/`, `csg-templates/` and the `weg-effects.yaml` parent. This role consumes them and (AC 9) re-ensures its own four deploy targets so the role is self-contained. [Source: 2-5-filesystem-role.md, roles/filesystem/vars/main.yml:37-46]
- **`weg-effects.yaml` is a FILE emitted here** — 2.5 deliberately never creates it ("parent-only"); the assets role owns its existence via `weg dump-effects --output`. [Source: 2-5-filesystem-role.md "The weg-effects.yaml file node"]
- **Test conventions:** `_find_ansible_dir()` anchored on `pyproject.toml`, `_module_key()`, parity-test shape (union + partitions), syntax-check skip-guard. Reuse verbatim for `test_assets_role.py`. [Source: 2-5-filesystem-role.md, tests/unit/test_filesystem_role.py]
- **Baseline:** 2.5 landed 265 passed, lint/mypy/layering clean. Keep it green.

### Story 2.4 — CLI Tools Role (the command-module template and the role that installs `weg`)
- **`command` + `creates:` is the ONLY idempotency/dry-run mechanism on command modules** — filesystem check (not a registered rc), check-mode-safe by construction. The assets `weg dump-effects` task uses this verbatim. [Source: 2-4-cli-tools-role.md "tasks/main.yml"]
- **`command -v` is a shell builtin** — must run via `ansible.builtin.shell` (F1). Only relevant if you add the optional weg-presence guard. [Source: 2-4-cli-tools-role.md F1]
- **PATH prepending to resolve `uv`-installed binaries:** 2.4's verify task uses `environment: PATH: "{{ cli_tools_bin_dir }}:{{ ansible_facts.env.PATH }}"`. The assets role mirrors it as `assets_weg_bin_dir` (same `{{ ansible_facts.env.HOME }}/.local/bin`). [Source: 2-4-cli-tools-role.md tasks/main.yml:40-45]
- **`ansible_facts.env.*` not `ansible_env.*` (F4 lock):** reuse exactly. [Source: 2-4-cli-tools-role.md Review Findings F4]
- **Repo-root derivation:** `{{ playbook_dir }}/../../../..` (playbooks → ansible → provisioning → src → repo root). Reuse as `assets_repo_root`. [Source: 2-4-cli-tools-role.md vars/main.yml]
- **Mirror-and-adapt discipline (Epic 1 retro action item):** this role deliberately mirrors 2.4/2.5 patterns. The explicit "what differs from the mirror": (a) command+creates used ONCE (weg-effects) instead of a loop, with PATH prepend; (b) `unarchive` replaces the command pattern for wallpapers because it is a non-command module that must NOT carry `creates` (FR-18); (c) a dir-guarantee `file` task exists solely to satisfy unarchive's dest-exists contract. [Source: sprint-status.yaml action_items "Mirror-and-adapt discipline"]

### Story 2.3 — Packages Role
- `group_by` + `group_vars` is the DISTRO-BRANCHING mechanism — **do NOT use it in assets** (distro-agnostic; asset deployment is identical on Arch and Debian-family). [Source: 2-3-packages-role.md]

### Story 2.2 — Ansible Scaffold
- `ansible.cfg` discovery: the executor passes `ANSIBLE_CONFIG` → `src/provisioning/ansible/ansible.cfg`, so `roles_path = roles` resolves `roles/assets`. Direct runs must set `ANSIBLE_CONFIG`. [Source: 2-2-ansible-scaffold.md]
- `group_vars/all.yml` documents the `install_dir` fail-loud contract this role enforces with its assert task. [Source: src/provisioning/ansible/group_vars/all.yml]

### Story 2.1 — Declarative Manifests
- `assets.yaml` holds the five-entry `{name, kind, source}` list; `ManifestKind.ASSETS` schema is locked by `yaml_manifest_reader.py`. The manifest is NOT consumed by Ansible — the role mirrors it and a test locks parity. [Source: 2-1-declarative-manifests.md, yaml_manifest_reader.py]
- **Deferred item handed to this story:** deferred-work.md#164 — "Ansible (Stories 2.3-2.12) should key off `kind` + `spine_segment()`, not `name`; `weg-effects` name diverges (file target)". Resolved here: role partitions by kind (unarchive / copy / emit), `target` == spine segment. [Source: deferred-work.md#164, enums.py:87-104]
- **The real-manifest reader test asserts `assets.yaml` parses non-empty** — do not change the manifest. [Source: tests/unit/adapters/test_yaml_manifest_reader.py]

### Epic 1 retrospective (2026-08-08) — one action item touches this story
- **"Mirror-and-adapt discipline"** action item: when copying sibling-package/role patterns, add an explicit "what differs from the mirror" checklist. Addressed in the Story 2.4 intelligence block above. [Source: sprint-status.yaml action_items]

## Git Intelligence

Recent commit pattern (follow the same flow): `chore: create story X` (this story) → `feat: ... implement story X` → `fix: apply X code review findings` → `chore: mark story X done`. Current HEAD baseline: `4f7f755` (fix: apply code review findings for story 2.5 filesystem role; 265 passed). Recent relevant history: 2.5 landed the filesystem role + `playbooks/filesystem.yaml` + `tests/unit/test_filesystem_role.py` (`f95aa59`, `4f7f755`); 2.4 landed the cli_tools role + `playbooks/cli-tools.yaml` + `tests/unit/test_cli_tools_role.py` (`13086b1`, `ec95944`); 2.3 landed the packages role (`48e826e`…`136f867`); 2.2 landed the Ansible scaffold; 2.1 landed `AssetKind.spine_segment()` + the five manifests incl. `assets.yaml`.

## Latest Tech Information

- **ansible-core 2.20.3** installed locally (`ansible-playbook [core 2.20.3]`); Python 3.12.12. `ansible.builtin.unarchive` and `ansible.builtin.copy` are part of ansible-core — no collections to install for this role.
- **`ansible.builtin.unarchive`** (ansible-core): `remote_src: yes` unpacks an archive already on the target; `dest` must pre-exist ("The given path must exist. Base directory is not created by this module"); supports a `creates` param, but this role deliberately OMITS it (AC 10, FR-18). Check-mode support is **partial — "Not supported for gzipped tar files"** → the task is skipped under `--check`. Requires `gtar` on the target (present on Arch/Debian-family). [Source: https://docs.ansible.com/ansible/latest/collections/ansible/builtin/unarchive_module.html]
- **`ansible.builtin.copy`** (ansible-core): check-mode support **full**; `remote_src: yes` supports recursive directory copies (≥2.8); `src` directory ending with `/` copies *contents* into `dest`, without `/` copies the directory itself (the trailing-slash rule this role encodes in vars); auto-creates `dest` when `src` is a directory. Recursive copy does not scale to hundreds of files — irrelevant here (~48 icons + 9 templates). [Source: https://docs.ansible.com/ansible/latest/collections/ansible/builtin/copy_module.html]
- **`weg dump-effects --output <path>`**: writes the packaged default `effects.yaml` to `<path>` when `<path>` ends in `.yaml` (otherwise treats it as a dir and writes `effects.yaml` inside), creating parents with `mkdir(parents=True, exist_ok=True)`. The effects catalog is user-facing/dump only — provisioning uses it exactly once to seed `<install>/weg-effects.yaml`. [Source: src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/dump_effects.py:17-23]
- **Wallpapers tarball verified:** 55 entries at the archive ROOT (no top-level dir), `default.png` present — extracts directly into `<install>/wallpapers/`. [Source: `tar -tzf dotfiles/assets/wallpapers/wallpapers.tar.gz`]
- **CSG bundled templates verified:** 9 `.j2` templates under `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/` (colors.yaml.j2, colors.conf.j2, colors.css.j2, …). [Source: repo tree]

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#367-382] — Story 2.6 ACs (assets role)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#38] — FR-17 Assets Role
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#118] — Epic 2 internal dependency order (`cli_tools` → `assets` → `default_palette` → `compositor_configs` → `settings`)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#234-240] — FR-17 PRD detail + idempotency consequence ("Replacing `wallpapers.tar.gz` in the repo causes the next `apply` to redeploy")
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#45] — default palette generated at apply time (replacing the tarball → next `apply` regenerates)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#75] — assumption: tarball contains `default.png` (verified present)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#9-21] — install-dir subtree (`wallpapers/`, `icon-templates/`, `icon-mappings/*.yaml`, `csg-templates/`, `weg-effects.yaml`)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#15] — `weg-effects.yaml` emitted via `weg dump-effects --output`
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#61] — CSG templates dir is NOT a settings field; deployed to `<install>/csg-templates/`; Phase 2 passes `--templates-dir`
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#160] — plan §6 `roles/assets/` tree (unpacks wallpapers.tar.gz + deploys icon-templates + icon-mappings + csg-templates)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#151] — plan §6 `playbooks/assets.yaml`
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#283] — plan §11 step 7 (roles in install order; `assets` fifth, after `filesystem`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#239] — done-criterion 4 (assets deployed; `weg-effects.yaml` emitted via `weg dump-effects --output`)
- [Source: dotfiles/provisioning/assets.yaml] — the desired asset list the role mirrors (parity-locked; five entries, `weg-effects` has no `source`)
- [Source: dotfiles/assets/wallpapers/wallpapers.tar.gz] — 55 entries at root incl. `default.png`; unarchive source
- [Source: src/provisioning/ansible/group_vars/all.yml] — `install_dir` fail-loud contract (never defaulted; orchestrator seam provides it)
- [Source: src/provisioning/src/provisioning/domain/enums.py#87-104] — `AssetKind.spine_segment()` (`WEG_EFFECTS` → `weg-effects.yaml` file target; others → directory segments)
- [Source: src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py] — `ManifestKind.ASSETS` `{name, kind, source}` entry schema (locked)
- [Source: src/cli-tools/wallpaper-effects-generator/src/wallpaper_effects_generator/cli/dump_effects.py#17-23] — `weg dump-effects --output` writes the file directly when the path ends `.yaml`
- [Source: src/provisioning/ansible/roles/filesystem/tasks/main.yml#24-30] — the `install_dir` fail-loud assert to copy verbatim
- [Source: src/provisioning/ansible/roles/filesystem/tasks/main.yml#47-51] — the `{{ install_dir | trim }}/{{ item }}` spine-task path pattern to reuse
- [Source: src/provisioning/ansible/roles/cli_tools/tasks/main.yml#34-38,40-45] — command+`creates` pattern + PATH-prepend verify task (weg-effects mirror)
- [Source: src/provisioning/ansible/roles/cli_tools/vars/main.yml#8-14] — `cli_tools_repo_root`/`cli_tools_bin_dir` derivation (assets mirrors as `assets_repo_root`/`assets_weg_bin_dir`)
- [Source: src/provisioning/tests/unit/test_filesystem_role.py] — structural test template: `_find_ansible_dir()`, `_module_key()`, parity test, syntax-check skip-guard
- [Source: src/provisioning/tests/unit/test_cli_tools_role.py#72-80] — `_creates_value()` helper shape (reused to assert NO creates on unarchive)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#164] — deferred item "Ansible should key off kind + spine_segment(), not name; weg-effects name diverges (file target)" (resolved in this story's vars partition + parity test)
- [Source: _bmad-output/implementation-artifacts/2-5-filesystem-role.md] — previous-story intelligence: install_dir assert, `| trim` lock, weg-effects parent-only guarantee, test conventions, 265-pass baseline
- [Source: _bmad-output/implementation-artifacts/2-4-cli-tools-role.md] — previous-story intelligence: command+`creates`, `ansible_facts.env` (F4), PATH prepend, repo-root derivation, `command -v` shell-builtin (F1), syntax-check guard
- [Source: _bmad-output/implementation-artifacts/sprint-status.yaml] — Epic 1 retro action item "Mirror-and-adapt discipline"
- [Source: https://docs.ansible.com/ansible/latest/collections/ansible/builtin/unarchive_module.html] — `remote_src`, `dest`-must-exist, partial check-mode (skipped for `.tar.gz`), `creates` param
- [Source: https://docs.ansible.com/ansible/latest/collections/ansible/builtin/copy_module.html] — `remote_src` recursive (≥2.8), full check-mode, trailing-slash contents semantics, auto-create dest for directory src

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Red phase: structural tests authored first; `test_no_group_by_distro_selection` initially failed because the playbook's own comment contained the literal word `group_by` (raw-text assert) — reworked to parse the play YAML and assert no `group_by`/`groups` key in the parsed play instead.
- `ruff format --check` reformatted 3 multi-line assert blocks; `mypy` flagged `.get("path")`/`.get("that")` on `object` in two list comprehensions — switched to the `_module()` helper (already used by sibling tests).

### Completion Notes List

- Implemented Story 2.6 Assets Role: `roles/assets/{tasks,vars}/main.yml`, `playbooks/assets.yaml`, `tests/unit/test_assets_role.py`.
- Role deploys all five manifest asset kinds into the 2.5 install spine: unarchive (wallpapers tarball, NO creates for FR-18), copy loop (icon-templates / icon-mappings / csg-templates), command emit (weg dump-effects with creates + PATH prepend).
- First task is the verbatim 2.5 fail-loud install_dir assert; `{{ install_dir | trim }}` trim lock applied across path-bearing vars/tasks.
- default.png presence guarded by stat+assert pair, both gated `when: not ansible_check_mode`.
- Parity test resolves deferred-work.md#164: assets_copies names ∪ {wallpapers, weg-effects} == manifest names; copies match by (name, kind, source.rstrip("/")); every target equals the kind→spine-segment mapping.
- Full suite: 287 passed (265 baseline + 22 new). ruff check/format + mypy clean; layering guard OK.

### File List

- `src/provisioning/ansible/roles/assets/tasks/main.yml` (NEW)
- `src/provisioning/ansible/roles/assets/vars/main.yml` (NEW)
- `src/provisioning/ansible/playbooks/assets.yaml` (NEW)
- `src/provisioning/tests/unit/test_assets_role.py` (NEW)

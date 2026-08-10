---
baseline_commit: ec95944
---

# Story 2.5: Filesystem Role

Status: ready-for-dev

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an operator,
I want a `filesystem` role that creates the machine layout,
So that XDG dirs and the install-spine subtree exist before assets land.

## Acceptance Criteria

1. `roles/filesystem/` exists with `tasks/main.yml` (AC 1, FR-16)
2. XDG config/state/cache dirs are created (AC 2, FR-16)
3. `~/.config/{hypr,hyprpaper,waybar}/` dirs are created (AC 3, FR-16)
4. The install-dir subtree exists: `wallpapers/`, `icon-templates/`, `icon-mappings/`, `csg-templates/`, `weg-effects.yaml` location, and `generated/{palettes,effects,icons,.weg-tmp}/` (AC 4, FR-16, NFR-8, chaining-spine.md)
5. Dirs are created only where missing — the role is idempotent (AC 5, FR-16, PRD FR-16 consequence, NFR-1)
6. The `install_dir` seam extra-var is required and fails loudly when missing — no silent default (group_vars/all.yml contract + Story 2.11 discipline)
7. The role's node map (XDG vs install-spine base, dir vs file) stays in parity with `dotfiles/provisioning/filesystem.yaml` — resolves the Story 2.1 deferred item at the role layer

## Tasks / Subtasks

- [ ] Create the `roles/filesystem/` role directory tree (AC: 1)
  - [ ] `src/provisioning/ansible/roles/filesystem/tasks/main.yml`
  - [ ] `src/provisioning/ansible/roles/filesystem/vars/main.yml`
- [ ] Author `vars/main.yml` (AC: 2, 3, 4, 7)
  - [ ] `filesystem_xdg_config_home` / `filesystem_xdg_state_home` / `filesystem_xdg_cache_home` — honor `ansible_facts.env.XDG_{CONFIG,STATE,CACHE}_HOME` with XDG-base-dir defaults (`~/.config`, `~/.local/state`, `~/.cache`) (AC 2)
  - [ ] `filesystem_compositor_dirs` — three entries under `filesystem_xdg_config_home`: `hypr`, `hyprpaper`, `waybar` (AC 3)
  - [ ] `filesystem_spine_dirs` — the install-spine dirs relative to `install_dir`: `wallpapers`, `icon-templates`, `icon-mappings`, `csg-templates`, `generated`, `generated/palettes`, `generated/effects`, `generated/icons`, `generated/.weg-tmp` (AC 4, parity-locked to the manifest)
  - [ ] `filesystem_file_nodes` — `weg-effects.yaml` (a FILE node whose parent must exist here; the file itself is the assets role's job in Story 2.6) (AC 4, parity-locked)
- [ ] Author `tasks/main.yml` (AC: 2, 3, 4, 5, 6)
  - [ ] Fail-loud seam guard: `ansible.builtin.assert` that `install_dir is defined and install_dir | trim | length > 0` — the FIRST task, so the role never runs against an undefined spine root (AC 6)
  - [ ] XDG base dirs: `ansible.builtin.file` `state: directory` looping over `filesystem_xdg_config_home`/`state_home`/`cache_home` (AC 2)
  - [ ] Compositor dirs: `ansible.builtin.file` `state: directory` looping over `filesystem_compositor_dirs` (AC 3)
  - [ ] Spine dirs: `ansible.builtin.file` `state: directory` with `path: "{{ install_dir }}/{{ item }}"` looping over `filesystem_spine_dirs` (AC 4)
  - [ ] NO task ever creates `weg-effects.yaml` itself (parent-only guarantee — AC 4 "location", see Dev Notes "The weg-effects.yaml file node")
  - [ ] No `become:` anywhere in the role or playbook (user-scoped — everything lives under the user's home + install dir; AC 2-4)
- [ ] Author `playbooks/filesystem.yaml` (AC: 1-6)
  - [ ] Simple playbook: `hosts: localhost`, `gather_facts: true`, `roles: [filesystem]`
  - [ ] NO `become: true` (user-scoped)
  - [ ] NO `group_by` distro-selection mechanism — filesystem creation is distro-agnostic (NFR-3); do not cargo-cult the packages pattern
  - [ ] `gather_facts: true` is REQUIRED — `vars/main.yml` reads `ansible_facts.env.*` (HOME, XDG_*), which only exist after the setup module runs (same rule as cli-tools.yaml)
- [ ] Add structural real-file tests `tests/unit/test_filesystem_role.py` (AC: 1-7)
  - [ ] Role tree exists: `tasks/main.yml`, `vars/main.yml` (walk up from test file, anchor on `pyproject.toml` — mirror `test_cli_tools_role.py` `_find_ansible_dir()`)
  - [ ] `tasks/main.yml` parses as a list of named task dicts
  - [ ] A fail-loud `assert` task requiring `install_dir` is present (locks AC 6 / group_vars/all.yml discipline)
  - [ ] XDG base dirs are created via `ansible.builtin.file` `state: directory` (AC 2)
  - [ ] Compositor dirs are created via `ansible.builtin.file` `state: directory`, exactly `hypr`/`hyprpaper`/`waybar` under the XDG config home (AC 3)
  - [ ] Install spine dirs are created via `ansible.builtin.file` `state: directory` with `path` = `{{ install_dir }}/{{ item }}` looping `filesystem_spine_dirs` (AC 4)
  - [ ] No task touches `weg-effects.yaml` (no `state: touch`, no `path` ending in `weg-effects.yaml`) (AC 4 parent-only)
  - [ ] No `become`/`become_user` anywhere in the role (user-scoped privilege context)
  - [ ] `vars/main.yml` `filesystem_spine_dirs` + `filesystem_file_nodes` + XDG names exactly cover the manifest `filesystem.yaml` entry names — the union equals the manifest set (AC 7 parity lock)
  - [ ] XDG homes honor `ansible_facts.env.XDG_*` with `| default(...)` — never a hardcoded `~/.config` literal; uses `ansible_facts.env` not deprecated `ansible_env` (F4 lock)
  - [ ] `playbooks/filesystem.yaml` parses: `hosts: localhost`, `gather_facts: true`, `roles: [filesystem]`, no `become`
  - [ ] `ansible-playbook --syntax-check` on `filesystem.yaml` (with `-e os_family=arch -e install_dir=/tmp/x`) exits 0 (guard when `ansible-playbook` absent — mirror 2.4)
- [ ] Verify full suite + lint + layering guard (AC: 5)
  - [ ] `uv run pytest` — full suite green, nothing regresses from the 247-pass baseline
  - [ ] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [ ] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)

## Dev Notes

### Scope — what Story 2.5 is and is not

**IS:** the `roles/filesystem/` role (`tasks/main.yml`, `vars/main.yml`) and the `playbooks/filesystem.yaml` playbook under `src/provisioning/ansible/`, plus structural real-file tests. The role creates the machine layout that the assets (`2.6`), default_palette (`2.7`), compositor_configs (`2.9`), and settings (`2.11`) roles will write into (FR-16, chaining-spine.md).

**IS NOT:** other roles (`assets` — 2.6; `default_palette` — 2.7; `compositor_configs` — 2.9; `symlinks` — 2.10; `settings` — 2.11; `verify` — 2.12), the aggregate `bootstrap.yaml` (Story 2.12), `scripts/bootstrap.sh` (Story 3.1), integration `--check`/dry-run tests (Story 3.2/3.3). Do NOT author any other role or playbook. The `assets` role (2.6) unpacks wallpapers and emits `weg-effects.yaml`; `compositor_configs` (2.9) places skeletons into `~/.config/{hypr,hyprpaper,waybar}/` — but that is LATER stories. This story only creates the directories and the XDG base dirs. It deploys NOTHING.
- **Do NOT create the settings-tool config dirs** (`~/.config/color-scheme-generator/`, `~/.config/weg/`, `~/.config/itr/`) — those are rendered by the `settings` role (2.11) and the `template` module auto-creates their parents. They are not in `filesystem.yaml`, so adding them would break the parity test and exceed the ACs.

### Where files live (locked by plan §6)

```
src/provisioning/ansible/
├── inventory/localhost.yaml          (Story 2.2 — unchanged)
├── requirements.yml                  (Story 2.2 — unchanged)
├── ansible.cfg                       (Story 2.2 — unchanged; roles_path = roles resolves relative to cfg dir)
├── group_vars/{all,arch,debian-family}.yml   (Story 2.2 — UNCHANGED; this role consumes NO group_vars)
├── playbooks/
│   ├── packages.yaml                 (Story 2.3 — unchanged)
│   ├── cli-tools.yaml                (Story 2.4 — unchanged)
│   └── filesystem.yaml               ← NEW (this story)
└── roles/
    ├── packages/                     (Story 2.3 — unchanged)
    ├── cli_tools/                    (Story 2.4 — unchanged)
    └── filesystem/
        ├── tasks/main.yml            ← NEW
        └── vars/main.yml             ← NEW
```

- Everything lives OUTSIDE `_SRC_ROOT` (`src/provisioning/src/provisioning`) — it is YAML only, never scanned by `tests/architecture/test_layering.py`, never part of the Python hexagon. **Do NOT add any `.py` file under `ansible/`** (same rule as Stories 2.3/2.4).
- Role dir `filesystem` and playbook file `filesystem.yaml` are both single-word per plan §6 — no underscore/hyphen divergence to worry about (unlike `cli_tools` role vs `cli-tools.yaml`).
- The playbook is runnable directly with `ansible-playbook` for `--check` verification; aggregation into `bootstrap.yaml` is Story 2.12. The executor's `--tags all` (Story 1.8) applies to the aggregate playbook only; no tag contract applies to this story's direct playbook yet.

### The manifest → role data flow (load-bearing + the deferred-item resolution)

- **The desired node list lives in `dotfiles/provisioning/filesystem.yaml`** (Story 2.1): a flat `entries` list — `config`, `state`, `cache`, `wallpapers`, `icon-templates`, `icon-mappings`, `csg-templates`, `weg-effects.yaml`, `generated`, `generated/palettes`, `generated/effects`, `generated/icons`, `generated/.weg-tmp`.
- **Ansible does not read manifests** (Story 2.1 ratified: "Ansible should key off `kind` + `spine_segment()`, not `name`"; the packages and cli_tools roles mirrored their data in vars with a parity test). The filesystem role does the same: `vars/main.yml` encodes the structure and a structural test locks parity with the manifest.
- **Deferred item being resolved here:** Story 2.1's review deferred "filesystem.yaml flat `name` list can't express base (XDG vs install-spine) or node type (file vs dir)" to Story 2.5. Resolution: the flat manifest is UNCHANGED (its schema is `{name}` only — locked by `yaml_manifest_reader.py:36` and the `test_filesystem_kind_allows_only_name` test; editing it would break the 2.1 reader contract). Instead, the role's vars partition the manifest names into three semantically-typed groups:
  - **XDG base dirs** — `config`, `state`, `cache` → the three XDG base directories (absolute paths, env-honoring).
  - **Install-spine dirs** — everything else that is a directory under `install_dir` (`wallpapers`, `icon-templates`, `icon-mappings`, `csg-templates`, `generated`, and the four `generated/...` leaves).
  - **File nodes** — `weg-effects.yaml` (a file, not a dir).
  - A parity test asserts the union of the three groups equals the manifest's `entries` set — the manifest stays the single source of truth and the role cannot silently diverge from it (exact analogue of 2.3's value-shape parity and 2.4's `cli_tools` parity locks).
- **`generated` + nested leaves:** the manifest lists `generated` AND `generated/palettes`, etc. Keep BOTH in `filesystem_spine_dirs` (parity) — `ansible.builtin.file` `state: directory` on the leaves auto-creates parents, and the explicit `generated` entry is harmless and idempotent. Do not "optimize" the list to leaves-only; the test locks exact set equality with the manifest.

### XDG base dir resolution (AC 2 — honor the spec, not a hardcode)

- The three XDG base dirs resolve per the XDG base-directory spec: `$XDG_CONFIG_HOME` → default `~/.config`; `$XDG_STATE_HOME` → default `~/.local/state`; `$XDG_CACHE_HOME` → default `~/.cache`.
- Implement as vars using the env fact with a `default` fallback:
  ```yaml
  filesystem_xdg_config_home: "{{ ansible_facts.env.XDG_CONFIG_HOME | default(ansible_facts.env.HOME + '/.config') }}"
  filesystem_xdg_state_home: "{{ ansible_facts.env.XDG_STATE_HOME | default(ansible_facts.env.HOME + '/.local/state') }}"
  filesystem_xdg_cache_home: "{{ ansible_facts.env.XDG_CACHE_HOME | default(ansible_facts.env.HOME + '/.cache') }}"
  ```
- Use `ansible_facts.env.*`, NOT the deprecated top-level `ansible_env.*` fact (code-review F4 lock from Story 2.4 — `ansible_env` is INJECT_FACTS_AS_VARS injection that hard-breaks on ansible-core ≥ 2.24; the lock is already asserted by a structural test in `test_cli_tools_role.py`).
- Note `~/.config` creation is implied by creating `~/.config/{hypr,hyprpaper,waybar}` (file module auto-creates parents), but keep the explicit XDG base-dir task too — it is what makes the manifest `config`/`state`/`cache` entries observable and parity-testable.
- **Consistency with the Python resolver:** the `install_dir` seam is resolved by `use_cases.resolve_install_dir()` via `$XDG_DATA_HOME` (default `Path.home()/.local/share`). The role derives `~` from `ansible_facts.env.HOME`. On a normal local run these agree (same user, same env); do NOT try to re-resolve `XDG_DATA_HOME` in the role — `install_dir` arrives already resolved and absolute.

### The weg-effects.yaml file node (AC 4 — "location", parent-only)

- `weg-effects.yaml` is a **file**, emitted by the `assets` role (Story 2.6) via `weg dump-effects --output <install>/weg-effects.yaml`. It is listed in `filesystem.yaml` because the desired *state* includes it, but creating it is NOT this role's job.
- This role's guarantee for that node is only that its **parent exists** — which is `<install_dir>/` itself, created by the spine task. Do NOT `state: touch` or write any placeholder. An empty placeholder would be overwritten by 2.6 and could mask a `weg dump-effects` failure (the file must be produced by the real tool, never pre-seeded).
- `assets.yaml`'s `WEG_EFFECTS` entry maps to spine segment `weg-effects.yaml` via `AssetKind.spine_segment()` (`enums.py:103`) — this role is the place that guarantees the parent for that segment. [Source: enums.py:98-104, chaining-spine.md:14]

### `install_dir` seam — fail loud, never default (AC 6)

- `group_vars/all.yml` explicitly documents: `install_dir` is deliberately NOT defaulted there; the orchestrator seam always provides it via `--extra-vars` (`use_cases._seam_extra_vars`), and an undefined `install_dir` must FAIL LOUDLY rather than silently resolve to a default. Story 2.11 applies this discipline to the settings renders; this story applies it to the role that creates the spine root.
- Implementation: the FIRST task is an `ansible.builtin.assert`:
  ```yaml
  - name: Assert install_dir seam is provided
    ansible.builtin.assert:
      that: install_dir is defined and install_dir | trim | length > 0
      fail_msg: >-
        install_dir is undefined — the filesystem role requires the
        install_dir seam extra-var (the orchestrator resolves
        $XDG_DATA_HOME/dotfiles/; direct runs pass -e install_dir=...)
  ```
- Because the assert runs first and `install_dir` is referenced directly in the spine task (`{{ install_dir }}/{{ item }}`), an undefined seam aborts with the friendly message before any dir task evaluates. **Do NOT alias `install_dir` into a var** (e.g. `filesystem_install_dir: "{{ install_dir }}"`) — lazy var evaluation can surface a raw undefined-var error instead of the assert message.
- This is an `assert`, which runs normally in `--check` mode (unlike command/shell modules) — the guard is check-mode-safe by construction.

### `tasks/main.yml` — why `ansible.builtin.file` and no `creates`

```yaml
- name: Create XDG base dirs
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
  loop:
    - "{{ filesystem_xdg_config_home }}"
    - "{{ filesystem_xdg_state_home }}"
    - "{{ filesystem_xdg_cache_home }}"

- name: Create compositor config dirs
  ansible.builtin.file:
    path: "{{ item }}"
    state: directory
  loop: "{{ filesystem_compositor_dirs }}"

- name: Create install spine dirs
  ansible.builtin.file:
    path: "{{ install_dir }}/{{ item }}"
    state: directory
  loop: "{{ filesystem_spine_dirs }}"
```

- `ansible.builtin.file` `state: directory` gives AC 5 (idempotent — only missing dirs are created) AND check-mode safety (dry-run reports `changed` when a dir is missing, `ok` otherwise, and never mutates) natively. Unlike Stories 2.3/2.4 there is **no `creates` needed** and no presence-check rc to worry about — the module owns both guarantees. This is the one role where the check-mode lesson does NOT require the `creates` pattern; do not cargo-cult it here.
- The spine task's `path: "{{ install_dir }}/{{ item }}"` also creates the `<install_dir>` root itself (and any missing ancestors) via the file module's parent auto-creation — this is what satisfies AC 4's "install-dir subtree exists" and the `weg-effects.yaml` "location" (its parent). No separate "create install_dir" task is needed.
- No `when:` gates anywhere. No `changed_when` overrides (file module's default changed/ok reporting is correct for this role).
- No `mode`/`owner`/`group` on the tasks — user-home + install dir with default umask is correct; do not invent ownership requirements.
- `loop` over vars is the established convention (mirrors `cli_tools` loop in 2.4); three unrolled tasks are also acceptable but the tests assert "one task per group looping the var" shape, so prefer the loops.

### Privilege context (inherited from 2.3 OQ-1 / 2.4 resolution)

- Everything this role creates lives under the **user's home** (`~/.config`, `~/.local/state`, `~/.cache`) and the user-owned `install_dir`. It is fully user-scoped: **NO `become`/`become_user`** anywhere in the role or playbook (locked by a structural test). Running as root would create `~`-paths under `/root/...`, silently diverging from the intended user's layout.
- Corollary for Story 2.12's `bootstrap.yaml`: when it aggregates `filesystem.yaml`, that play's become context must likewise be off. Do not change anything in Story 2.12 now; just keep this playbook become-free.

### Playbook — why no group_by (mirrors 2.4, not 2.3)

`packages.yaml` (2.3) needed the `group_by` + `group_vars` mechanism because packages branch on distro. `filesystem` does NOT: directory creation is identical on Arch and Debian-family, and the role consumes no `group_vars`. A simple `hosts: localhost` / `gather_facts: true` / `roles: [filesystem]` playbook is correct (NFR-3). Note `gather_facts: true` is required — `vars/main.yml` reads `ansible_facts.env.*`, which only exist after the fact-gathering setup module runs.

### Testing — real-file structural tests (mirror 2.4/2.3 conventions)

- Author `tests/unit/test_filesystem_role.py` following `test_cli_tools_role.py` exactly: `_find_ansible_dir()` walking up from the test file anchored on `pyproject.toml`, module-level `_ANSIBLE_DIR`/`_ROLES_DIR`/`_REPO_ROOT`, `_TASK_KEYWORDS` + `_module_key()` helper, `yaml.safe_load` on the real files. Do NOT copy the cli_tools test file — author a sibling.
- The parity test is the critical one. Load `filesystem.yaml` entries (like `_manifest_entries()` in `test_cli_tools_role.py`) and assert:
  - `{filesystem_spine_dirs} ∪ {filesystem_file_nodes} ∪ {config,state,cache} == {manifest entry names}` (set equality),
  - `filesystem_spine_dirs ∪ filesystem_file_nodes == manifest entries minus {config,state,cache}` (base partition), and
  - `filesystem_file_nodes == {"weg-effects.yaml"}` (file-node partition).
- `ansible-playbook --syntax-check` invocation (mirror 2.4): `ANSIBLE_CONFIG=<ansible>/ansible.cfg ansible-playbook --syntax-check <ansible>/playbooks/filesystem.yaml -e os_family=arch -e install_dir=/tmp/x`; wrap in `shutil.which("ansible-playbook")` skip-guard (2.4 review F6 — a bare `FileNotFoundError` fails the whole suite). Exit 0 asserts well-formedness. `--syntax-check` does not run tasks (safe in CI).
- Do NOT add integration dry-run tests that actually create dirs — that is Story 3.2/3.3 territory. The structural `ansible.builtin.file` shape assertions ARE the AC 4/5 lock.
- For the `install_dir` assert task test, locate the task whose module key is `ansible.builtin.assert` and assert its `that` list mentions `install_dir is defined`.

### Known limitations (accept, do not fix here)

- XDG dirs are created but the role does NOT touch `XDG_RUNTIME_DIR` (`/run/user/...`) — out of scope; the spec only names config/state/cache.
- The role guarantees the `weg-effects.yaml` parent, not the file — if `weg dump-effects` (2.6) is later removed, this node's parent is still created. Acceptable; the assets role owns the file's existence.
- `install_dir` arriving non-absolute (a caller passing a relative path) is not normalized here — the orchestrator always resolves it absolute (`resolve_install_dir()` calls `.resolve()`); direct invokers are responsible for passing an absolute path. Document in vars; no normalization needed.

## Project Structure Notes

- `src/provisioning/ansible/playbooks/filesystem.yaml` — NEW playbook (one-per-role; aggregate `bootstrap.yaml` is Story 2.12).
- `src/provisioning/ansible/roles/filesystem/tasks/main.yml` — NEW; only Python-free YAML.
- `src/provisioning/ansible/roles/filesystem/vars/main.yml` — NEW; XDG homes + compositor dirs + `filesystem_spine_dirs` + `filesystem_file_nodes` (parity-locked to the manifest).
- `src/provisioning/tests/unit/test_filesystem_role.py` — NEW structural real-file tests.
- Unchanged: `inventory/`, `requirements.yml`, `ansible.cfg`, `group_vars/`, `playbooks/{packages,cli-tools}.yaml`, `roles/{packages,cli_tools}/`, all of `src/provisioning/src/provisioning/` (the Python hexagon is untouched by this story).
- Unchanged on the manifest side: `dotfiles/provisioning/filesystem.yaml` is the source of truth the role mirrors; do NOT edit it in this story (locked in Story 2.1; its `{name}`-only schema is enforced by `yaml_manifest_reader.py:36`).
- No new dependencies. No `bootstrap.yaml`. No other roles.

## Testing Requirements

- Full gates: `uv run pytest` (247-pass baseline from Story 2.4), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `python tests/architecture/test_layering.py` (standalone nicety).
- New `tests/unit/test_filesystem_role.py` (see Dev Notes "Testing") covering:
  - role tree existence + `tasks/main.yml` parses to a list of named tasks;
  - first task is an `ansible.builtin.assert` requiring `install_dir` (AC 6 fail-loud seam guard);
  - XDG base dirs via `ansible.builtin.file` `state: directory` (AC 2);
  - compositor dirs exactly `hypr`/`hyprpaper`/`waybar` under the XDG config home (AC 3);
  - spine dirs via `ansible.builtin.file` `state: directory` with `path: "{{ install_dir }}/{{ item }}"` looping `filesystem_spine_dirs` (AC 4);
  - no task creates `weg-effects.yaml` (parent-only, AC 4);
  - no `become`/`become_user` in the role (user-scoped privilege context);
  - vars parity with `filesystem.yaml` manifest (union + base partition + file partition) (AC 7);
  - XDG homes honor `ansible_facts.env.XDG_* | default(...)` and use `ansible_facts.env`, never deprecated `ansible_env` (F4 lock);
  - `playbooks/filesystem.yaml` structure (`hosts: localhost`, `gather_facts: true`, `roles: [filesystem]`, no `become`);
  - `ansible-playbook --syntax-check` on `filesystem.yaml` (with `-e os_family=... -e install_dir=...`) exits 0, skip-guarded when `ansible-playbook` is absent.
- Smoke check (manual, optional): `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg uv run ansible-playbook --syntax-check src/provisioning/ansible/playbooks/filesystem.yaml -e os_family=arch -e install_dir=/tmp/x`.

## Previous Story Intelligence

### Story 2.4 — CLI Tools Role (the immediate predecessor and template)
- **Check-mode discipline has a DIFFERENT shape here:** 2.4 needed `creates:` because it shelled to `uv tool install` (a command module that re-creates state). The filesystem role uses `ansible.builtin.file` `state: directory`, which owns idempotency and check-mode natively — NO `creates`, NO presence-check rc, NO `when:` gates. Do not cargo-cult the command-module pattern. [Source: 2-4-cli-tools-role.md "tasks/main.yml"]
- **`ansible_facts.env.*` not `ansible_env.*`** (F4 lock): use `ansible_facts.env.HOME` / `ansible_facts.env.XDG_*`; the deprecated top-level `ansible_env` fact hard-breaks on ansible-core ≥ 2.24. Reuse this exactly. [Source: 2-4-cli-tools-role.md Review Findings F4]
- **`gather_facts: true` is REQUIRED** in a playbook whose role vars read `ansible_facts.env.*` — env facts only exist after the setup module runs. [Source: 2-4-cli-tools-role.md "Playbook"]
- **User-scoped privilege context:** `uv tool install` (2.4) and `~/.config` symlinks (2.10) are user-scoped; filesystem dirs under the user's home + install dir are the same — NO become. [Source: 2-4-cli-tools-role.md "Privilege context"]
- **Distro-agnostic roles skip group_by:** `cli_tools` did; `filesystem` does too. Only distro-branching roles (packages) use `group_by` + `group_vars`. [Source: 2-4-cli-tools-role.md "Playbook — why no group_by"]
- **Parity-lock test pattern:** `test_cli_tools_role.py` locks role vars against the manifest by `(name, source)`. The filesystem analogue locks the node partition (XDG vs spine vs file) against `filesystem.yaml`. [Source: 2-4-cli-tools-role.md Testing]
- **Syntax-check skip-guard:** `shutil.which("ansible-playbook")` + `pytest.skip` (2.4 review F6); `-e os_family=... -e install_dir=...` kept for executor-seam parity. [Source: 2-4-cli-tools-role.md test_syntax_check_exits_zero]
- **Test conventions:** `_find_ansible_dir()` anchored on `pyproject.toml`; module-level `_ANSIBLE_DIR`; `_TASK_KEYWORDS`/`_module_key()`; per-file structural test classes. [Source: 2-4-cli-tools-role.md Dev Notes "Testing"]
- **Baseline:** Story 2.4 landed 247 passed, lint/mypy/layering clean. Keep it green.
- **Deferred-not-fixed in 2.4:** `command -v yay` in `roles/packages/tasks/main.yml:59` uses the shell-builtin-as-command defect (deferred-work.md#5). NOT in scope here (packages role untouched by this story).

### Story 2.3 — Packages Role (distro-branching counterexample)
- `group_by: key: "{{ os_family }}"` + `group_vars/{arch,debian-family}.yml` is the distro-selection mechanism — **do NOT use it in filesystem** (distro-agnostic). [Source: 2-3-packages-role.md]
- `creates:`-as-dry-run guard and the check-mode rc lesson apply to COMMAND modules only; see the 2.4 note above for why the file module changes the shape. [Source: 2-3-packages-role.md, 2-4-cli-tools-role.md Previous Story Intelligence]

### Story 2.2 — Ansible Scaffold
- `ansible.cfg` discovery: the executor passes `ANSIBLE_CONFIG` → `src/provisioning/ansible/ansible.cfg`, so `roles_path = roles` resolves and `roles/filesystem` is found. Direct `ansible-playbook` runs must set `ANSIBLE_CONFIG`. [Source: 2-2-ansible-scaffold.md]
- `group_vars/all.yml` documents the `install_dir` fail-loud contract this story enforces with its assert task. [Source: src/provisioning/ansible/group_vars/all.yml]

### Story 2.1 — Declarative Manifests
- `filesystem.yaml` holds the flat desired-node list; `ManifestKind.FILESYSTEM` schema is `{name}`-only (`yaml_manifest_reader.py:36`). The manifest is NOT consumed by Ansible — the role mirrors it and a test locks parity. [Source: 2-1-declarative-manifests.md, yaml_manifest_reader.py:36]
- The real-manifest reader test asserts `filesystem.yaml` parses to a non-empty `ProvisionManifest` (`test_yaml_manifest_reader.py:316,321-324`) — do not change the manifest or the schema. [Source: test_yaml_manifest_reader.py]
- **Deferred item handed to this story:** the flat list "can't express base (XDG vs install-spine) or node type (file vs dir) — revisit at Story 2.5 (filesystem role)". This story resolves it in the role vars + parity test (see Dev Notes). [Source: deferred-work.md#165]

### Epic 1 retrospective (2026-08-08) — nothing pending for this story
- Epic-1 retro action items are Epic 1 / 2.12 scope; none block the filesystem role. [Source: epic-1-retro-2026-08-08.md]

## Git Intelligence

Recent commit pattern (follow the same flow): `chore: create story X` (this story) → `feat: ... implement story X` → `fix: apply X code review findings` → `chore: mark story X done`. Current HEAD baseline: `ec95944` (fix: apply code review findings for story 2.4 cli tools role; 247 passed). Recent relevant history: 2.4 landed the cli_tools role + `playbooks/cli-tools.yaml` + `tests/unit/test_cli_tools_role.py` (`d074371`, `13086b1`, `ec95944`); 2.3 landed the packages role + `playbooks/packages.yaml` + `tests/unit/test_packages_role.py` (`48e826e`, `451d4ce`, `56478b8`, `136f867`); 2.2 landed the Ansible scaffold + `ANSIBLE_CONFIG` wiring; 2.1 landed `ManifestKind`/`AssetKind.spine_segment` + the five manifests incl. `filesystem.yaml`.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#352-365] — Story 2.5 ACs (filesystem role)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#37] — FR-16 Filesystem Role
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#227-232] — FR-16 PRD detail + idempotency consequence
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#5-21] — install dir + exact spine subtree (`wallpapers/`, `icon-templates/`, `icon-mappings/`, `csg-templates/`, `weg-effects.yaml`, `generated/{palettes,effects,icons,.weg-tmp}`)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md#14] — `weg-effects.yaml` is a deployed FILE (parent-only guarantee for this role)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#193] — plan §5 `filesystem.yaml` (XDG + install dir subtree layout)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#163] — plan §6 `roles/filesystem/` tree
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#150] — plan §6 `playbooks/filesystem.yaml`
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#283] — plan §11 step 7 (roles in install order; `filesystem` fourth, after `cli_tools`)
- [Source: dotfiles/provisioning/filesystem.yaml] — desired node list the role mirrors (parity-locked)
- [Source: src/provisioning/ansible/group_vars/all.yml] — `install_dir` fail-loud contract (never defaulted; orchestrator seam provides it)
- [Source: src/provisioning/src/provisioning/application/use_cases.py#27-48] — `resolve_install_dir()` (`$XDG_DATA_HOME/dotfiles/`) + `_seam_extra_vars` (exactly `install_dir`, `os_family`)
- [Source: src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py#36] — `ManifestKind.FILESYSTEM` `{name}`-only entry schema
- [Source: src/provisioning/src/provisioning/domain/enums.py#98-104] — `AssetKind.spine_segment()` (`WEG_EFFECTS` → `weg-effects.yaml` file target)
- [Source: src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py#316,321-324] — real-manifest reader test (filesystem.yaml parses non-empty)
- [Source: src/provisioning/tests/unit/test_cli_tools_role.py] — structural test template: `_find_ansible_dir()`, `_TASK_KEYWORDS`/`_module_key()`, parity test, syntax-check skip-guard
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#165] — deferred item "filesystem.yaml flat name list can't express base/node-type — revisit at Story 2.5" (resolved in this story's role vars + parity test)
- [Source: _bmad-output/implementation-artifacts/2-4-cli-tools-role.md] — previous-story intelligence: `ansible_facts.env` (F4), `gather_facts` requirement, no-become user scope, no-group_by, syntax-check guard, 247-pass baseline
- [Source: https://docs.ansible.com/ansible/latest/collections/ansible/builtin/file_module.html] — `ansible.builtin.file` `state: directory`: idempotent create-if-missing + check-mode-safe (would-change reporting, no mutation) — the reason this role needs no `creates`

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-10: Resolved the Story 2.1 deferred item (deferred-work.md#165): the flat `filesystem.yaml` list stays unchanged (schema locked at `yaml_manifest_reader.py:36`), and the role vars partition names into XDG base dirs (`config`/`state`/`cache`), install-spine dirs, and the `weg-effects.yaml` file node — with a parity test locking the union.
- 2026-08-10: Confirmed `install_dir` arrives resolved+absolute from `resolve_install_dir()` via the `_seam_extra_vars` (exactly `install_dir` + `os_family`); `group_vars/all.yml` mandates fail-loud on undefined — the role's assert task is the first task.
- 2026-08-10: Confirmed `ansible.builtin.file` `state: directory` natively satisfies idempotency (AC 5) and check-mode dry-run (reports would-change) — no `creates` needed, unlike command-module roles 2.3/2.4.
- 2026-08-10: Confirmed `weg-effects.yaml` is a file emitted by the assets role (2.6); this role guarantees only its parent `<install_dir>/` (chaining-spine.md:14, enums.py:103).
- 2026-08-10: Baseline verified: `uv run pytest` 247 passed (HEAD `ec95944`); `ansible-playbook` 2.20.3 present for the syntax-check test.

### Completion Notes List

- 2026-08-10: Story created — ultimate context engine analysis completed; comprehensive developer guide created. Status → ready-for-dev.

### File List

- NEW `_bmad-output/implementation-artifacts/2-5-filesystem-role.md` (this file)
- NEW `src/provisioning/ansible/roles/filesystem/tasks/main.yml`
- NEW `src/provisioning/ansible/roles/filesystem/vars/main.yml`
- NEW `src/provisioning/ansible/playbooks/filesystem.yaml`
- NEW `src/provisioning/tests/unit/test_filesystem_role.py`

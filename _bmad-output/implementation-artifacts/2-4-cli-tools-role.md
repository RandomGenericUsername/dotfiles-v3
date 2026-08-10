---
baseline_commit: 136f867
---

# Story 2.4: CLI Tools Role

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-10: Story created — ultimate context engine analysis completed; comprehensive developer guide created.
- 2026-08-10: Validated against checklist — fixed 3 internal bugs before finalizing: (1) `gather_facts: false` contradicted `vars/main.yml` reading `{{ ansible_env.HOME }}` (ansible_env only populated after fact gathering) → playbook now mandates `gather_facts: true`; (2) uv-absent assert task would have crashed under `--check` when the skipped `command -v uv` left `uv_check.rc` undefined → assert gated `when: not ansible_check_mode`; (3) test spec said "exactly three install tasks" while Dev Notes prescribe a single `loop: {{ cli_tools }}` task → reconciled (one loop task covering all three entries, or three unrolled tasks, tests assert one-per-entry either way).
- 2026-08-10: Implemented story — authored `roles/cli_tools/` (`tasks/main.yml`, `vars/main.yml`), `playbooks/cli-tools.yaml`, and `tests/unit/test_cli_tools_role.py` (12 tests). Full suite 244 passed (baseline 232), ruff/mypy/layering clean. Status → review.
- 2026-08-10: Code review (6 patch + 1 defer) — F1 CRITICAL: `command -v` via `ansible.builtin.command` can never resolve (shell builtin, no executable); fixed to `ansible.builtin.shell` (empirically verified rc=0 vs rc=2) + 3 new lock tests. Also quoted the repo-root path (F3), switched `ansible_env.*` → `ansible_facts.env.*` (F4, deprecated fact injection), loosened the one-install-task test (F5), added ansible-playbook presence guard (F6). Suite 247 passed, ruff/mypy clean. Status → done.

## Story

As an operator,
I want a `cli_tools` role that installs the dotfiles CLIs,
So that `csg`, `weg`, and icon-renderer are available on PATH.

## Acceptance Criteria

1. `roles/cli_tools/` exists with `tasks/main.yml` (AC 1, FR-15)
2. `csg`, `weg`, and icon-renderer are installed via `uv tool install` against the repo package paths (AC 2, FR-15, plan §3)
3. Each installed binary is on PATH after the role completes (AC 3, FR-15)
4. The role is idempotent — a re-run produces no changed state for already-installed tools (AC 4, FR-15, NFR-1)
5. `--check` reports would-change without installing (AC 5, FR-15, hardening: dry-run must be dry)

## Tasks / Subtasks

- [x] Create the `roles/cli_tools/` role directory tree (AC: 1)
  - [x] `src/provisioning/ansible/roles/cli_tools/tasks/main.yml`
  - [x] `src/provisioning/ansible/roles/cli_tools/vars/main.yml`
- [x] Author `vars/main.yml` (AC: 1, 2, 3)
  - [x] `cli_tools_repo_root` — repo root derived from `{{ playbook_dir }}` (playbooks → ansible → provisioning → src → repo root = `{{ playbook_dir }}/../../../..`), overridable
  - [x] `cli_tools_bin_dir` — uv executable dir, default `{{ ansible_env.HOME }}/.local/bin` (uv default when `UV_TOOL_BIN_DIR`/`XDG_BIN_HOME` unset), overridable
  - [x] `cli_tools` — list of `{name, source}` exactly mirroring `dotfiles/provisioning/cli-tools.yaml` entries (csg/weg/itr); the `uv tool install` targets (AC 2)
- [x] Author `tasks/main.yml` (AC: 2, 3, 4, 5)
  - [x] uv precondition (fail-loud, NOT part of install gating): `ansible.builtin.command: command -v uv` (register `uv_check`, `failed_when: false`), then a separate `ansible.builtin.assert` task gated on `when: not ansible_check_mode` that fails with a friendly message if uv is absent — the install tasks themselves have NO `when:` (NFR-9 fail-loud; see Dev Notes "tasks/main.yml" for the check-mode reason)
  - [x] Install task: ONE `ansible.builtin.command: uv tool install {{ cli_tools_repo_root }}/{{ item.source }}` with `loop: "{{ cli_tools }}"` (three iterations, one per manifest entry; three unrolled per-entry tasks is an acceptable alternative — see test bullet below) with:
    - [x] `creates: "{{ cli_tools_bin_dir }}/{{ item.name }}"` — the ONLY idempotency guard (AC 4) AND the dry-run mechanism (AC 5: `creates` present ⇒ skip, absent ⇒ would-change under `--check`)
    - [x] NO `when:` gated on a presence-check rc — under `--check` a skipped `command -v` registers `rc: 0` and would make the install report `skipped` instead of would-change (locked lesson from Story 2.3 review; see Dev Notes "Why creates, not a when-guard")
    - [x] `changed_when`/`failed_when` left to defaults (command module)
  - [x] Verification loop (AC 3): for each entry, `ansible.builtin.command: command -v {{ item.name }}` run with `environment: PATH: "{{ cli_tools_bin_dir }}:{{ ansible_env.PATH }}"` so the role asserts the binary resolves on PATH in the run context; `changed_when: false`
  - [x] No `become:` anywhere in the role — `uv tool install` is a user-scoped step that must target the intended user, not root (OQ-1 resolution from Story 2.3; see Dev Notes "Privilege context")
- [x] Author `playbooks/cli-tools.yaml` (AC: 1-5)
  - [x] Simple playbook: `hosts: localhost`, `gather_facts: true`, `roles: [cli_tools]`
  - [x] NO `become: true` (user-scoped — installing as root would put binaries in `/root/.local/bin`)
  - [x] NO `group_by` distro-selection mechanism — this role is distro-agnostic (uv tool install works on Arch and Debian-family alike); the `group_by`+`group_vars` pattern is only required for distro-branching roles like `packages` (2.3)
  - [x] `gather_facts: true` is REQUIRED — `vars/main.yml` derives `cli_tools_bin_dir` from `{{ ansible_env.HOME }}`, and `ansible_env` is only populated when facts are gathered (same as the packages playbook)
- [x] Add structural real-file tests `tests/unit/test_cli_tools_role.py` (AC: 1-5)
  - [x] Role tree exists: `tasks/main.yml`, `vars/main.yml` (walk up from test file, anchor on `pyproject.toml` — mirror `test_packages_role.py` `_find_ansible_dir()`)
  - [x] `tasks/main.yml` parses as a list of task dicts; each task has `name`
  - [x] Exactly ONE install task (`uv tool install {{ cli_tools_repo_root }}/{{ item.source }}` with `loop: "{{ cli_tools }}"`), covering all three manifest entries (if the dev agent prefers three unrolled tasks instead, that is also acceptable — the tests below must still assert one install task per manifest entry either way)
  - [x] Install tasks are `ansible.builtin.command` with `creates: "{{ cli_tools_bin_dir }}/{{ item.name }}"` (dry-run guard — dry-run must be dry)
  - [x] Install tasks are NOT gated on a presence-check rc (locks the 2.3 lesson: `command -v` skipped under `--check` registers `rc: 0`)
  - [x] No `become`/`become_user` on install tasks (user-scoped privilege context)
  - [x] `vars/main.yml` `cli_tools` list exactly matches `dotfiles/provisioning/cli-tools.yaml` entries by `(name, source)` — parity lock so the manifest and the role can never silently diverge
  - [x] No absolute repo paths hardcoded in tasks — every source is `{{ cli_tools_repo_root }}/...`
  - [x] `playbooks/cli-tools.yaml` parses: `hosts: localhost`, `gather_facts: true`, `roles: [cli_tools]`, no `become`
  - [x] `ansible-playbook --syntax-check` on `cli-tools.yaml` (with `-e os_family=arch -e install_dir=/tmp/x`) exits 0
- [x] Verify full suite + lint + layering guard (AC: 4, 5)
  - [x] `uv run pytest` — full suite green, nothing regresses from the 232-pass baseline
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)

## Dev Notes

### Scope — what Story 2.4 is and is not

**IS:** the `roles/cli_tools/` role (`tasks/main.yml`, `vars/main.yml`) and the `playbooks/cli-tools.yaml` playbook under `src/provisioning/ansible/`, plus structural real-file tests. The role installs the three compute-provider CLIs (`csg`, `weg`, `itr`) via `uv tool install` from the repo's source paths (FR-15, plan §3 locked decision: "CLI tool install — Ansible task using `uv tool install` against repo paths, lives inside the `cli_tools` role — not a separate Python adapter").

**IS NOT:** other roles (`filesystem` — 2.5; `assets` — 2.6; `default_palette` — 2.7; `compositor_configs` — 2.9; `symlinks` — 2.10; `settings` — 2.11; `verify` — 2.12), the aggregate `bootstrap.yaml` (Story 2.12), `scripts/bootstrap.sh` (Story 3.1), integration `--check`/dry-run tests (Story 3.2/3.3). Do NOT author any other role or playbook. The `default_palette` role (2.7) will call `csg generate`; the `assets` role (2.6) will call `weg dump-effects`; `verify` (2.12) asserts the binaries on PATH — but all of that is LATER stories. This story only installs the CLIs.

### Where files live (locked by plan §6)

```
src/provisioning/ansible/
├── inventory/localhost.yaml          (Story 2.2 — unchanged)
├── requirements.yml                  (Story 2.2 — unchanged)
├── ansible.cfg                       (Story 2.2 — unchanged; roles_path = roles resolves relative to cfg dir)
├── group_vars/{all,arch,debian-family}.yml   (Story 2.2 — UNCHANGED; this role does not consume group_vars)
├── playbooks/
│   ├── packages.yaml                 (Story 2.3 — unchanged)
│   └── cli-tools.yaml                ← NEW (this story)
└── roles/
    ├── packages/                     (Story 2.3 — unchanged)
    └── cli_tools/
        ├── tasks/main.yml            ← NEW
        └── vars/main.yml             ← NEW
```

- Everything lives OUTSIDE `_SRC_ROOT` (`src/provisioning/src/provisioning`) — it is YAML only, never scanned by `tests/architecture/test_layering.py`, never part of the Python hexagon. **Do NOT add any `.py` file under `ansible/`** (same rule as Story 2.3).
- The role directory is `cli_tools` (underscore) per plan §6 and the epics story; the playbook file is `cli-tools.yaml` (hyphen) per plan §6. Keep both names exactly as specified.
- The playbook is runnable directly with `ansible-playbook` for `--check` verification; aggregation into `bootstrap.yaml` is Story 2.12. The executor's `--tags all` (Story 1.8) applies to the aggregate playbook only; no tag contract applies to this story's direct playbook yet.

### The manifest → role data flow (load-bearing)

- **The install specs live in `dotfiles/provisioning/cli-tools.yaml`** (Story 2.1): three entries — `csg` → `src/cli-tools/color-scheme-generator`, `weg` → `src/cli-tools/wallpaper-effects-generator`, `itr` → `src/cli-tools/icon-templates-renderer`. `src/cli-tools/openspec/` is NOT an install target and must not be listed.
- **Ansible does not read manifests** (Story 2.1 ratified: "Ansible should key off `kind` + `spine_segment()`, not `name`"; the packages role consumed `group_vars`, not the manifest). Therefore the role declares the same list in `roles/cli_tools/vars/main.yml` as `cli_tools`, and a structural test locks **parity** between the manifest entries and the role var (name AND source). This is the exact analogue of Story 2.3's value-shape parity test — the mechanism that prevents silent drift.
- **Binary-name mapping:** the manifest entry name `itr` is the console-script name (`[project.scripts] itr = "icon_templates_renderer.cli.main:app"`), which AC 2 calls "icon-renderer". The role operates on the console-script names: `csg`, `weg`, `itr`. There is no `icon-renderer` binary; `itr` IS the icon-renderer.
- **Repo-root resolution:** the executor passes exactly the two seam extra-vars (`install_dir`, `os_family` — pinned by Story 1.5's seam contract test) and no others, so the role CANNOT receive a `repo_root` extra-var. Derive it from the playbook's own location: `cli-tools.yaml` lives at `<repo>/src/provisioning/ansible/playbooks/`, so `<repo>` = `{{ playbook_dir }}/../../../..`. Define `cli_tools_repo_root` in `vars/main.yml` with that derivation and allow override (a future user running playbooks from a moved repo can set it). Do NOT hardcode any absolute path in tasks (locked by a structural test).
- **`uv tool install` from a repo path:** `uv tool install <repo>/src/cli-tools/color-scheme-generator` reads that package's `pyproject.toml`, builds it, installs its console scripts into the uv executable dir. Each tool's `pyproject.toml` carries `[tool.uv.sources]` entries pointing at sibling shared packages (`cli-output`, `config-assembler-engine`, `oci-runtime`) via relative `../../shared/...` paths — uv resolves those relative to the tool package's own pyproject location, so installing from the intact repo tree works. **Verify this on first implementation** (`uv tool install --help`, and a real local smoke install on one tool); if a path-source resolution error surfaces, record it in Dev Agent Record rather than papering over it — do NOT switch to registry installs of the CLI tools (that would break the repo-source contract in AC 2).

### The uv executable dir and PATH (AC 3 — the subtle one)

- uv installs tool executables into the **executable directory**: `$UV_TOOL_BIN_DIR` → `$XDG_BIN_HOME` → `$HOME/.local/bin` (default on Linux). If the dir is not on `PATH`, uv prints a warning and `uv tool update-shell` exists to add it.
- AC 3 ("each installed binary is on PATH after the role completes") is scoped to the provisioning run context: the role MUST verify each binary resolves with the uv bin dir on PATH. Do this by running the verification `command -v` tasks with `environment: PATH: "{{ cli_tools_bin_dir }}:{{ ansible_env.PATH }}"` — this asserts AC 3 without mutating shell config.
- **Persistent shell PATH is NOT this role's job.** Whether `~/.local/bin` stays on the user's interactive shell PATH is a user-dotfiles / `bootstrap.sh` concern (Story 3.1). The `verify` role (Story 2.12) asserts the binaries resolve in the provisioning context, matching this role's guarantee. If the operator later finds `csg` missing from an interactive shell, the fix is their shell PATH config, not this role. Do not call `uv tool update-shell` (it would rewrite the user's shell init files — out of scope and intrusive).

### `tasks/main.yml` — the install + verify loop (FR-15, plan §3)

```yaml
# roles/cli_tools/vars/main.yml
cli_tools_repo_root: "{{ playbook_dir }}/../../../.."
cli_tools_bin_dir: "{{ ansible_env.HOME }}/.local/bin"
cli_tools:
  - { name: csg, source: src/cli-tools/color-scheme-generator }
  - { name: weg, source: src/cli-tools/wallpaper-effects-generator }
  - { name: itr, source: src/cli-tools/icon-templates-renderer }
```

```yaml
# roles/cli_tools/tasks/main.yml
- name: Check for uv
  ansible.builtin.command: command -v uv
  register: uv_check
  changed_when: false
  failed_when: false
```

Note the fail-loud shape: uv presence is a SEPARATE concern from tool idempotency. The correct split is:

1. A **uv-absent fail-loud** guard, independent of the install loop. It must be gated `when: not ansible_check_mode`: under `--check` the `command -v uv` task is skipped (command modules never run in check mode), so `uv_check.rc` may be undefined there — the guard is a real-run precondition only, never exercised by a dry run:
   ```yaml
   - name: Ensure uv is available
     ansible.builtin.assert:
       that: uv_check.rc == 0 and uv_check.stdout | length > 0
       fail_msg: "uv not found on PATH — the cli_tools role requires uv (bootstrap.sh pre-seeds it; Story 3.1)"
     when: not ansible_check_mode
   ```
2. The **install loop** with ONLY the `creates` guard — no `when:` at all on the tool install tasks. Each `uv tool install` task runs unconditionally except for `creates` (skips when the binary already exists). This gives AC 4 (idempotent: binary present ⇒ `creates` skips ⇒ no change) and AC 5 (`--check`: binary absent ⇒ would-change; binary present ⇒ skipped). `creates` is check-mode-safe by construction.
   ```yaml
   - name: Install csg/weg/itr via uv tool install
     ansible.builtin.command: "uv tool install {{ cli_tools_repo_root }}/{{ item.source }}"
     loop: "{{ cli_tools }}"
     creates: "{{ cli_tools_bin_dir }}/{{ item.name }}"
   ```

Why this shape (the locked Story 2.3 lesson):
- **Under `--check`, a skipped `command -v` task registers `rc: 0`** (empirically verified in 2.3's review). Any `when:` gated on a presence-check rc therefore evaluates false at check time and the install reports `skipped` — failing AC 5's "reports would-change". `creates` checks the filesystem, not a registered rc, so it is the ONLY guard that is correct in both real and check mode.
- **`creates` also makes the task idempotent** in real runs (AC 4): the `uv tool install` command simply never runs when `{{ cli_tools_bin_dir }}/{{ item.name }}` exists, so a re-run reports no changed state. Without it, `uv tool install` would re-create the tool environment every apply (uv docs: tool environments are "re-created entirely via subsequent `uv tool install` operations") — that would report drift on every re-run.
- **Accept the known limitation** (mirrors 2.3's `creates: /usr/bin/yay` deferral): because `creates` skips when the binary exists, a repo update that changes a tool's source never re-installs it — `uv tool install --force` / `uv tool upgrade` is the manual path. Record in Dev Agent Record; do not try to auto-detect source changes (content hashing is explicitly out of scope).

### Privilege context (AC 7 from Story 2.3 / OQ-1 — inherited resolution)

- `uv tool install` writes to the user's uv dirs (`$HOME/.local/bin`, `$XDG_DATA_HOME/uv`) and must target the **intended user**, exactly like the `~/.config` symlinks (Story 2.10). It is a **user-scoped** step.
- Story 2.3 resolved OQ-1 for the packages playbook as: privileged steps (`pacman`/`apt`, makepkg) run with `become: true`; user-scoped steps run as the invoking user. The cli-tools playbook therefore MUST NOT use `become: true` — running as root would install into `/root/.local/bin` and the intended user would never see the binaries (AC 3 would be silently false). No `become`/`become_user` anywhere in the role or playbook (locked by a structural test).
- Corollary for Story 2.12's `bootstrap.yaml`: when it aggregates `cli-tools.yaml`, that play's become context must likewise be off for this play. Do not change anything in Story 2.12 now; just keep this playbook become-free.

### Playbook — why no group_by (unlike Story 2.3)

`packages.yaml` (2.3) needed the `group_by` + `group_vars` distro-selection mechanism because the packages role branches on distro. `cli_tools` does NOT: `uv tool install` is identical on Arch and Debian-family, and the role consumes no `group_vars`. A simple `hosts: localhost` / `gather_facts: true` / `roles: [cli_tools]` playbook is correct and keeps the role distro-agnostic (NFR-3). Do not cargo-cult the group_by pattern here. Note `gather_facts: true` is required even though no facts are branched on — `vars/main.yml` reads `{{ ansible_env.HOME }}`, which only exists after the fact-gathering setup module runs.

### Testing — real-file structural tests (mirror Story 2.3 conventions)

- Author `tests/unit/test_cli_tools_role.py` following `tests/unit/test_packages_role.py` exactly: `_find_ansible_dir()` walking up from the test file anchored on `pyproject.toml`, module-level `_ANSIBLE_DIR`, per-file test classes. Do NOT copy the packages test file — author a sibling.
- Use `yaml.safe_load` on the real role files; use `_module_key()`-style helper (reserved-task-keyword set) to identify the `command` tasks.
- `ansible-playbook --syntax-check` invocation (mirror 2.3):
  ```
  ANSIBLE_CONFIG=<ansible>/ansible.cfg ansible-playbook --syntax-check <ansible>/playbooks/cli-tools.yaml -e os_family=arch -e install_dir=/tmp/x
  ```
  Exit 0 asserts well-formedness. `--syntax-check` does not run tasks (safe in CI). `-e os_family=...`/`install_dir` are provided for parity with the executor seam even though this playbook does not consume them — keep them so the command mirrors a real executor invocation.
- Do NOT add integration dry-run tests that actually run `uv tool install` — that is Story 3.2/3.3 territory (real `--check` runs need a real host). The structural `creates`-guard test IS the AC 5 lock.

### Known limitations (accept, do not fix here)

- `uv tool install` may need to download/build Python versions (csg/itr require `>=3.14`, weg `>=3.12`) on a host whose uv-managed Pythons are absent — a network fetch at apply time is expected and acceptable (bootstrap pre-seeds uv; NFR-9). If this proves slow/fragile it is an integration-story (3.2/3.3) concern, not this story's.
- The role installs whatever the repo currently is at `{{ cli_tools_repo_root }}` — no version pinning (the tools are 0.1.0 local packages; version pinning is out of scope and would fight the repo-source contract).
- `creates` never upgrades already-installed tools — accepted (see Dev Notes "Why creates, not a when-guard").
- The executable-dir default `~/.local/bin` assumes `UV_TOOL_BIN_DIR`/`XDG_BIN_HOME` are unset; operators who set them must override `cli_tools_bin_dir`. Documented in vars; no auto-detection needed.

## Project Structure Notes

- `src/provisioning/ansible/playbooks/cli-tools.yaml` — NEW playbook (one-per-role; aggregate `bootstrap.yaml` is Story 2.12).
- `src/provisioning/ansible/roles/cli_tools/tasks/main.yml` — NEW; only Python-free YAML.
- `src/provisioning/ansible/roles/cli_tools/vars/main.yml` — NEW; `cli_tools_repo_root`, `cli_tools_bin_dir`, `cli_tools` list (parity-locked to the manifest).
- `src/provisioning/tests/unit/test_cli_tools_role.py` — NEW structural real-file tests.
- Unchanged: `inventory/`, `requirements.yml`, `ansible.cfg`, `group_vars/`, `playbooks/packages.yaml`, `roles/packages/`, all of `src/provisioning/src/provisioning/` (the Python hexagon is untouched by this story).
- Unchanged on the manifest side: `dotfiles/provisioning/cli-tools.yaml` is the source of truth the role mirrors; do NOT edit it in this story (it was locked in Story 2.1).
- No new dependencies. No `bootstrap.yaml`. No other roles.

## Testing Requirements

- Full gates: `uv run pytest` (232-pass baseline from Story 2.3), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `python tests/architecture/test_layering.py` (standalone nicety).
- New `tests/unit/test_cli_tools_role.py` (see Dev Notes "Testing") covering:
  - role tree existence + `tasks/main.yml` parses to a list of named tasks;
  - one `uv tool install` command task (looping over `cli_tools`, or three unrolled instances) covering each manifest entry;
  - each install task carries `creates: "{{ cli_tools_bin_dir }}/{{ item.name }}"` (dry-run guard);
  - install tasks are NOT gated on a presence-check rc (locks the 2.3 check-mode lesson);
  - no `become`/`become_user` on install tasks (user-scoped privilege context);
  - `vars/main.yml` `cli_tools` parity with `dotfiles/provisioning/cli-tools.yaml` entries by `(name, source)`;
  - no absolute repo paths in tasks (every source is `{{ cli_tools_repo_root }}/...`);
  - `playbooks/cli-tools.yaml` structure (`hosts: localhost`, `gather_facts: true`, `roles: [cli_tools]`, no `become`);
  - `ansible-playbook --syntax-check` on `cli-tools.yaml` (with `-e os_family=... -e install_dir=...`) exits 0.
- Smoke check (manual, optional): `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg uv run ansible-playbook --syntax-check src/provisioning/ansible/playbooks/cli-tools.yaml -e os_family=arch -e install_dir=/tmp/x`.

## Previous Story Intelligence

### Story 2.3 — Packages Role (the immediate predecessor and template)
- **Locked group_by distro-selection pattern** — NOT needed here (cli_tools is distro-agnostic). Do not cargo-cult it. [Source: 2-3-packages-role.md "The playbook (locked distro-selection mechanism)"]
- **Check-mode rc lesson (CRITICAL):** under `--check`, a skipped `command -v` registers `rc: 0`; gating install on a presence-check rc makes it report `skipped` instead of would-change. Fix pattern: use `creates:` as the only guard on the install command. Reuse this exact lesson. [Source: 2-3-packages-role.md Review Findings → makepkg when-not-gated-on-yay_check.rc, resolved 2026-08-10]
- **`creates` is both the idempotency AND the dry-run mechanism** — the makepkg task used `creates: /usr/bin/yay` so it is idempotent AND check-safe. Same idea here: `creates: {{ cli_tools_bin_dir }}/{{ item.name }}`. [Source: 2-3-packages-role.md "Why this is check-mode-safe (AC 5)"]
- **Privilege context split (OQ-1):** privileged steps `become: true`; user-scoped steps (`uv tool install`, `~/.config` symlinks) run as the intended user with NO become. This story is the first user-scoped playbook — keep it become-free. [Source: 2-3-packages-role.md "Privilege context (AC 7 — resolves OQ-1 for this story)"]
- **Test conventions:** `_find_ansible_dir()` anchored on `pyproject.toml`; module-level `_ANSIBLE_DIR`; per-file structural test classes; `ansible-playbook --syntax-check` with `-e os_family=... -e install_dir=...`. [Source: 2-3-packages-role.md "Testing"]
- **Baseline:** Story 2.3 landed 232 passed, lint/mypy/layering clean. Keep it green.

### Story 2.2 — Ansible Scaffold
- `ansible.cfg` discovery: the executor passes `ANSIBLE_CONFIG` → `src/provisioning/ansible/ansible.cfg`, so `roles_path = roles` resolves relative to the cfg dir and `roles/cli_tools` is found. Direct `ansible-playbook` runs must set `ANSIBLE_CONFIG` (or run from a dir where discovery works). [Source: 2-2-ansible-scaffold.md, 2-3-packages-role.md "ansible.cfg discovery"]

### Story 2.1 — Declarative Manifests
- `dotfiles/provisioning/cli-tools.yaml` holds the install specs (`csg`/`weg`/`itr` + repo `source` paths); `ManifestKind.CLI_TOOLS` validated by `YamlManifestReader` (`_ENTRY_SCHEMAS` requires `name` + `source`). The manifest is NOT consumed by Ansible — the role mirrors it and a test locks parity. [Source: 2-1-declarative-manifests.md "Manifest authoring", src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py:41-44]
- Existing manifest-reader test asserts the real manifest has exactly `{csg, weg, itr}` names — the role's var must match. [Source: src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py:341-345]

### Epic 1 retrospective (2026-08-08) — nothing pending for this story
- Epic-1 retro action items are Epic 1 / 2.12 scope; none block the cli_tools role. [Source: epic-1-retro-2026-08-08.md]

## Git Intelligence

Recent commit pattern (follow the same flow): `chore: create story X` (this story) → `feat: ... implement story X` → `fix: apply X code review findings` → `chore: mark story X done`. Current HEAD baseline: `136f867` (fix: auto-commit code review findings — Story 2.3's 6 findings applied, 232 passed). Recent relevant history: 2.3 landed the packages role + `playbooks/packages.yaml` + `tests/unit/test_packages_role.py` (`48e826e`, `451d4ce`, `56478b8`, `136f867`); 2.2 landed the Ansible scaffold + `ANSIBLE_CONFIG` wiring (`422e358`, `a45b245`); 2.1 landed `ManifestKind`/`AssetKind.spine_segment` + the five manifests incl. `cli-tools.yaml` (`49c0065`).

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#337-351] — Story 2.4 ACs (cli_tools role)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#36] — FR-15 CLI Tools Role
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#219-225] — FR-15 PRD detail
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#54] — locked decision: CLI tool install via `uv tool install` against repo paths, lives in the cli_tools role
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#159] — plan §6 `roles/cli_tools/` tree (`tasks/main.yml — uv tool install csg/weg/itr`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#149] — plan §6 `playbooks/cli-tools.yaml`
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#283] — plan §11 step 7 (roles in install order; `cli_tools` third, after `packages`)
- [Source: dotfiles/provisioning/cli-tools.yaml] — install specs (name + source) the role mirrors
- [Source: src/cli-tools/color-scheme-generator/pyproject.toml] — `csg` script; `requires-python >=3.14`; `[tool.uv.sources]` path pattern
- [Source: src/cli-tools/wallpaper-effects-generator/pyproject.toml] — `weg` script; `requires-python >=3.12`
- [Source: src/cli-tools/icon-templates-renderer/pyproject.toml] — `itr` script (the "icon-renderer" binary); `requires-python >=3.14`
- [Source: src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py#41-44] — `ManifestKind.CLI_TOOLS` schema (`name` + `source` required)
- [Source: src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py#341-345] — real-manifest cli-tools test (`{csg, weg, itr}`)
- [Source: src/provisioning/src/provisioning/cli/main.py#68-86] — `_ANSIBLE_ROOT` + `build_deps()` executor construction (seam extra-vars `install_dir` + `os_family` only)
- [Source: src/provisioning/src/provisioning/application/use_cases.py#38-48] — `_seam_extra_vars` (exactly `install_dir`, `os_family`; no `repo_root` may be added)
- [Source: https://docs.astral.sh/uv/concepts/tools/] — uv tools interface: `uv tool install` from a path; executable directory (`$UV_TOOL_BIN_DIR`/`$XDG_BIN_HOME`/`~/.local/bin`); PATH warning + `uv tool update-shell`; tool envs "re-created entirely via subsequent `uv tool install` operations" (why `creates` guard is required for AC 4)
- [Source: https://docs.astral.sh/uv/guides/tools/] — `uv tool install <path>` installs a local package's console scripts; `--python` override
- [Source: _bmad-output/implementation-artifacts/2-3-packages-role.md] — previous-story intelligence: `creates` check-mode lesson, privilege context (OQ-1), test conventions
- [Source: _bmad-output/implementation-artifacts/2-3-packages-role.md#351-352] — locked lesson: makepkg task must not gate on `yay_check.rc` (skipped command registers `rc: 0` under `--check`)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-10: Researched `uv tool install` semantics (astral docs): local-path installs read the target package's pyproject (incl. `[tool.uv.sources]`), executables land in `$UV_TOOL_BIN_DIR`/`$XDG_BIN_HOME`/`~/.local/bin`, and repeated `uv tool install` re-creates the tool env — so Ansible idempotency must come from a `creates` guard, not from uv itself.
- 2026-08-10: Confirmed `roles_path = roles` + `ANSIBLE_CONFIG` wiring (Story 2.2) means `roles/cli_tools` resolves; `playbooks/` and `roles/cli_tools/` do not exist yet and are created in this story.
- 2026-08-10: Confirmed manifest `cli-tools.yaml` entries (`csg`/`weg`/`itr`) match each tool's `[project.scripts]`; `itr` is the binary for "icon-renderer".
- 2026-08-10: Story created with baseline `136f867`; suite baseline 232 passed.
- 2026-08-10: Implemented. Real-file smoke check via `ansible-playbook --syntax-check` surfaced one Ansible shape issue: a free-form `command` module task cannot carry top-level `creates` alongside the module key ("conflicting action statements: ansible.builtin.command, creates") — moved `creates` under `args:` (same shape as 2.3's makepkg task). Syntax-check now exits 0.
- 2026-08-10: Full gates green — `uv run pytest` 244 passed (12 new), `ruff check`/`format` clean, `mypy src tests` clean, `test_layering.py` exit 0.

### Completion Notes List

- 2026-08-10: Story created — ultimate context engine analysis completed; comprehensive developer guide created. Status → ready-for-dev.
- 2026-08-10: Validation complete (2nd pass) — verified every reference line number against source docs (epics #337-351/#36, plan #54/#149/#159/#283); tightened install-task wording to a single loop contract and aligned the playbook-structure test bullets with `gather_facts: true`; no source-document contradictions remain.
- 2026-08-10: Implemented Story 2.4 — `roles/cli_tools/` (tasks/vars), `playbooks/cli-tools.yaml`, `tests/unit/test_cli_tools_role.py` (12 structural real-file tests). One design correction during syntax-check: `creates` moved under `args:` for the free-form command task. All 5 ACs satisfied (role tree, uv tool install from repo paths, PATH verification, idempotent `creates` guard, check-mode-safe dry-run). No `become` anywhere; `gather_facts: true`; distro-agnostic (no group_by). Full suite 244 passed, lint/mypy/layering clean. Status → review.

### File List

- NEW `_bmad-output/implementation-artifacts/2-4-cli-tools-role.md` (this file)
- NEW `src/provisioning/ansible/roles/cli_tools/tasks/main.yml`
- NEW `src/provisioning/ansible/roles/cli_tools/vars/main.yml`
- NEW `src/provisioning/ansible/playbooks/cli-tools.yaml`
- NEW `src/provisioning/tests/unit/test_cli_tools_role.py`

### Review Findings

- [x] [Review][Patch] Critical: `command -v` executed via `ansible.builtin.command` can never resolve — `command` is a shell builtin, not an executable (no `/usr/bin/command`); the uv-check task (`failed_when: false`) swallows the `rc=2`/exec error so the assert at tasks/main.yml:25 fails even when uv IS installed, and the verify loop at tasks/main.yml:38 fails every real run. Role cannot complete a non-`--check` run. Fix: `ansible.builtin.shell: command -v uv` (shell modules still skip under `--check`, preserving the locked check-mode reasoning) [src/provisioning/ansible/roles/cli_tools/tasks/main.yml:18,38]
- [x] [Review][Patch] AC 3 verify loop has zero test coverage and the 12-test suite is purely structural — it passed green while the role was broken at runtime. Add a structural test asserting the verify task's shape (command module, `environment.PATH` prepends `cli_tools_bin_dir`, `changed_when: false`) [src/provisioning/tests/unit/test_cli_tools_role.py]
- [x] [Review][Patch] Unquoted `{{ cli_tools_repo_root }}` in the free-form `uv tool install` command splits argv on whitespace if the repo checkout path contains spaces; quote the interpolated path [src/provisioning/ansible/roles/cli_tools/tasks/main.yml:32]
- [x] [Review][Patch] `ansible_env.HOME`/`ansible_env.PATH` use deprecated top-level fact injection (INJECT_FACTS_AS_VARS) — deprecation warning today, hard break on ansible-core ≥ 2.24; use `ansible_facts.env.HOME`/`ansible_facts.env.PATH` [src/provisioning/ansible/roles/cli_tools/vars/main.yml:13, src/provisioning/ansible/roles/cli_tools/tasks/main.yml:41]
- [x] [Review][Patch] `test_one_install_task_covers_all_manifest_entries` over-constrains to exactly one install task, contradicting the spec's sanctioned "three unrolled per-entry tasks" alternative; loosen to "one install task per manifest entry" [src/provisioning/tests/unit/test_cli_tools_role.py]
- [x] [Review][Patch] `test_syntax_check_exits_zero` raises uncaught `FileNotFoundError` (fails whole suite) when `ansible-playbook` is not installed in the test env; add a presence/skip guard [src/provisioning/tests/unit/test_cli_tools_role.py]
- [x] [Review][Defer] `command -v yay` in the sibling packages role has the same shell-builtin defect (Story 2.3's `failed_when: false` swallows the exec error) — deferred, pre-existing [src/provisioning/ansible/roles/packages/tasks/main.yml:59] — real but caused by Story 2.3, not this change; fix together with F1 when packages role is next touched

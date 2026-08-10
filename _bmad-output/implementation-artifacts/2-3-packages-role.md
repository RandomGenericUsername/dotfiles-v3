---
baseline_commit: 3cf656f
---

# Story 2.3: Packages Role

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-09: Story created — ultimate context engine analysis completed; comprehensive developer guide created.
- 2026-08-09: Implemented story — authored `roles/packages/` (tasks + vars/{main,arch,debian}), `playbooks/packages.yaml`, and structural tests; all gates green (230 passed, lint/mypy/layering clean); status → review.
- 2026-08-10: Applied 6 code-review findings — os_family seam guard (assert vs ansible_os_family), makepkg `when` no longer gated on `yay_check.rc` (AC5 would-change), git clone `force: true`, `reject('equalto', '')` on flatten, shared `aur_packages: []` default, sudoers `mode: 0440` + `regexp`; 2 new locking tests (232 passed); status → done.

## Story

As an operator,
I want a `packages` role that installs system packages per distro,
So that Hyprland, Hyprpaper, Waybar, and fonts are present on the machine.

## Acceptance Criteria

1. `roles/packages/` exists with `tasks/main.yml` and `vars/{main,arch,debian}.yml` (AC 1, FR-14)
2. Arch uses `pacman` (via `ansible.builtin.package` auto-detect) and self-bootstraps `yay` — `base-devel`+`git` installed, then a guarded `makepkg -si yay-bin` that skips when `yay` is already present, then AUR installs driven via `kewlfft.aur.aur` (AC 2, FR-14, plan §3)
3. Debian-family uses `apt` for the same logical package set (AC 3, FR-14)
4. Distro logic lives in `vars/arch.yml`/`vars/debian.yml` only — `tasks/main.yml` branches on `ansible_os_family` ONLY in the two `include_vars` tasks; all Arch-specific behavior after that gates on `packages_use_aur | bool` (a var loaded from `vars/arch.yml`) (AC 4, FR-14, NFR-3)
5. A `--check` run reports would-change without ever executing `makepkg` or mutating the host (AC 5, hardening: dry-run must be dry)
6. The role is idempotent — a re-run reports no drift (AC 6, NFR-1)
7. Privilege context is explicitly defined: the playbook run's user has rights to run `pacman`/`apt` (via sudo `become: true`), while `makepkg`/AUR tasks run as a dedicated non-root `aur_builder` user (`become_user`); user-scoped steps (`uv tool install`, `~/.config` symlinks) belong to later stories (2.4/2.10) and are OUT of scope here — if a single run context cannot satisfy both, record it as an open question (AC 7, OQ-1)

## Tasks / Subtasks

- [x] Create the `roles/packages/` role directory tree (AC: 1)
  - [x] `src/provisioning/ansible/roles/packages/tasks/main.yml`
  - [x] `src/provisioning/ansible/roles/packages/vars/main.yml`
  - [x] `src/provisioning/ansible/roles/packages/vars/arch.yml`
  - [x] `src/provisioning/ansible/roles/packages/vars/debian.yml`
- [x] Author `vars/main.yml` (AC: 4)
  - [x] Shared defaults only: `packages_state: present`, `aur_build_dir: /tmp/dotfiles-aur-build`
  - [x] NO distro-specific content
- [x] Author `vars/arch.yml` (AC: 2, 4)
  - [x] `packages_use_aur: true` (the var that gates the Arch yay-bootstrap + AUR block — see Dev Notes "distro logic in vars")
  - [x] `aur_builder_user: aur_builder`, `aur_builder_group: wheel`
  - [x] `aur_packages: []` (empty for the current package set — all four logical entries resolve from official repos; kewlfft.aur.aur task is still authored and gated on non-empty)
  - [x] `yay_repo: https://aur.archlinux.org/yay-bin.git`
  - [x] NO pacman package names here — the names live in `group_vars/arch.yml` (NFR-3)
- [x] Author `vars/debian.yml` (AC: 3, 4)
  - [x] `packages_use_aur: false`
  - [x] NO apt package names here — the names live in `group_vars/debian-family.yml`
  - [x] No `apt_update_cache`/`apt_cache_valid_time` vars — `ansible.builtin.package` proxies to `apt` which refreshes its cache automatically; don't add dead config
- [x] Author `tasks/main.yml` (AC: 2, 3, 4, 5, 6)
  - [x] `include_vars` arch.yml when `ansible_os_family == "Archlinux"`, debian.yml when `ansible_os_family == "Debian"` — the ONLY `ansible_os_family` branching in tasks; everything Arch-specific after that gates on `when: packages_use_aur | bool` (a var loaded from `vars/arch.yml`, never on `ansible_os_family` directly)
  - [x] Flatten the `group_vars` `packages` map (scalar + list values) into one install list via `packages.values() | list | flatten`
  - [x] Install the flattened list with `ansible.builtin.package` `state: present` `become: true` — auto-selects pacman/apt (AC 2, 3)
  - [x] `when: packages_use_aur | bool`: install `base-devel` + `git` via `ansible.builtin.package` `become: true`
  - [x] `when: packages_use_aur | bool`: create `aur_builder` user (group `wheel`, `create_home: true`) + NOPASSWD `pacman` line in `/etc/sudoers.d/11-install-aur_builder` (kewlfft.aur requirement — makepkg/yay refuse root) — both `become: true`
  - [x] `when: packages_use_aur | bool`: guarded yay-bootstrap: `command -v yay` check (`changed_when: false`, `failed_when: false`), then `git clone {{ yay_repo }}` + `makepkg -si --noconfirm` run `become: true become_user: "{{ aur_builder_user }}"` with `creates: /usr/bin/yay` and `when: yay absent` — the `command` module + `creates` guard makes this dry-run-safe (AC 5) and idempotent (AC 6)
  - [x] `when: packages_use_aur | bool`: AUR installs via `kewlfft.aur.aur` `name: "{{ aur_packages }}"` `state: present` `use: yay`, `become: true become_user: "{{ aur_builder_user }}"`, `when: aur_packages | length > 0`
  - [x] `become` is scoped per-task — the play-level become context stays explicit in the playbook (see Dev Notes "Privilege context")
- [x] Author `playbooks/packages.yaml` (AC: 1-7, locked distro-selection pattern from Story 2.2)
  - [x] Lead play: `hosts: localhost`, `gather_facts: true`, task `ansible.builtin.group_by: key: "{{ os_family }}"` (creates the dynamic `arch`/`debian-family` group so `group_vars` auto-apply)
  - [x] Second play: `hosts: "{{ os_family }}"`, `become: true`, `roles: [packages]`
  - [x] `gather_facts: true` is required so `ansible.builtin.package` can auto-detect pacman/apt
- [x] Add structural real-file tests `tests/unit/test_packages_role.py` (AC: 1-7)
  - [x] Role tree exists: `tasks/main.yml`, `vars/{main,arch,debian}.yml` (walk up from test file, anchor on `pyproject.toml` — mirror `test_ansible_scaffold.py` `_find_ansible_dir()`)
  - [x] `tasks/main.yml` parses as a list of task dicts; each task has `name`
  - [x] `vars/{main,arch,debian}.yml` parse as dicts with the required keys from the tasks above
  - [x] `vars/arch.yml` does NOT contain any pacman package names (names live in `group_vars/arch.yml`); `vars/debian.yml` similarly
  - [x] `playbooks/packages.yaml` parses: first play `group_by: key: "{{ os_family }}"`, second play `roles: [packages]` + `become: true`
  - [x] Dry-run guard: the `makepkg` task is a `command` module with `creates` (assert the guarded bootstrap task exists) — dry-run must be dry
  - [x] Distro-branching contract: `tasks/main.yml` references `ansible_os_family` ONLY inside the two `include_vars` tasks; no `when: ansible_os_family` on any other task, no hardcoded `pacman`/`apt` module FQCNs (only `ansible.builtin.package`)
  - [x] `ansible-playbook --syntax-check` on `playbooks/packages.yaml` (with `-e os_family=arch -e install_dir=/tmp/x`) exits 0 (ansible-core is a runtime dep — available in the test env)
  - [x] Value-shape contract (locks deferred D3): assert every value in `group_vars/{arch,debian-family}.yml` `packages` map is either a non-empty `str` or a non-empty `list[str]`
- [x] Verify full suite + lint + layering guard (AC: 5)
  - [x] `uv run pytest` — full suite green, nothing regresses from the 217-pass baseline
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)

## Dev Notes

### Scope — what Story 2.3 is and is not

**IS:** the `roles/packages/` role (`tasks/main.yml`, `vars/{main,arch,debian}.yml`) and the `playbooks/packages.yaml` playbook under `src/provisioning/ansible/`, plus structural real-file tests. The role consumes the `group_vars` `packages` map authored in Story 2.2 and installs the four logical entries (`hyprland`, `hyprpaper`, `waybar`, `fonts`) per distro, with Arch's `yay` self-bootstrap and the `kewlfft.aur.aur` AUR path.

**IS NOT:** other roles (`cli_tools` — Story 2.4; `filesystem` — 2.5; `assets` — 2.6; `default_palette` — 2.7; `compositor_configs` — 2.9; `symlinks` — 2.10; `settings` — 2.11; `verify` — 2.12), the aggregate `bootstrap.yaml` (Story 2.12), `scripts/bootstrap.sh` (Story 3.1), integration `--check`/dry-run tests (Story 3.2/3.3), any playbook that runs `uv tool install` or creates `~/.config` symlinks (user-scoped privilege context — later stories). Do NOT author any other role or playbook.

### Where files live (locked by plan §6)

```
src/provisioning/ansible/
├── inventory/localhost.yaml          (Story 2.2 — unchanged)
├── requirements.yml                  (Story 2.2 — unchanged; kewlfft.aur 0.13.0 already pinned)
├── ansible.cfg                       (Story 2.2 — unchanged; roles_path = roles resolves relative to cfg dir)
├── group_vars/{all,arch,debian-family}.yml   (Story 2.2 — the `packages` map this role consumes)
├── playbooks/
│   └── packages.yaml                 ← NEW (this story; first playbook)
└── roles/
    └── packages/
        ├── tasks/main.yml            ← NEW
        └── vars/{main,arch,debian}.yml  ← NEW
```

- Everything lives OUTSIDE `_SRC_ROOT` (`src/provisioning/src/provisioning`) — it is YAML/INI data only, never scanned by `tests/architecture/test_layering.py`, never part of the Python hexagon. **Do NOT add any `.py` file under `ansible/`** (dead code; the layering scanner would not read it, but it belongs in `tests/`).
- `_ANSIBLE_ROOT` (`src/provisioning/ansible`) is already wired in the CLI composition root (Story 1.8): `build_deps()` passes `config_file=_ANSIBLE_ROOT / "ansible.cfg"` (Story 2.2) and the use cases point at `playbooks/bootstrap.yaml`/`playbooks/verify.yaml`. Individual role playbooks like `packages.yaml` are runnable directly with `ansible-playbook` for `--check` verification; aggregation into `bootstrap.yaml` is Story 2.12.

### The data flow — group_vars → role (load-bearing)

- **Names live in `group_vars`, never in the role or Python.** Story 2.1 ratified: "per-manager names resolve in Ansible `group_vars` (Story 2.2/2.3), per NFR-3". The `packages` map was authored in Story 2.2:
  - `group_vars/arch.yml`: `hyprland: hyprland`, `hyprpaper: hyprpaper`, `waybar: waybar`, `fonts: [ttf-jetbrains-mono-nerd, noto-fonts, noto-fonts-cjk, ttf-nerd-fonts-symbols]`
  - `group_vars/debian-family.yml`: `hyprland: hyprland`, `hyprpaper: hyprpaper`, `waybar: waybar`, `fonts: [fonts-noto, fonts-noto-cjk, fonts-noto-color-emoji]`
- **Value-shape contract (lock deferred D3 from Story 2.2 review):** each `packages` key maps to either a scalar package name (`hyprland`) or a list of names (`fonts`). The role MUST flatten both shapes into one install list:
  ```yaml
  - name: Assemble package list
    ansible.builtin.set_fact:
      packages_flat: "{{ packages.values() | list | flatten }}"
  ```
  `[hyprland, hyprpaper, waybar, [f1, f2, f3]] | flatten` → `[hyprland, hyprpaper, waybar, f1, f2, f3]`.
- **The `packages` var is available because of the playbook's `group_by`.** `group_vars/{arch,debian-family}.yml` only auto-load for hosts in a group of that name. The playbook must create the dynamic group via the seam extra-var `os_family` (`arch`/`debian-family` — the `IFactReader.os_family()` seam). This is the locked pattern from Story 2.2 Dev Notes; do not rediscover it.
- **`ansible.builtin.package` auto-detects the manager** (pacman on Arch, apt on Debian) — do NOT add a `pkg_manager` var and do NOT hardcode `pacman`/`apt` module calls in tasks (NFR-3: distro isolation; also enforced by the story's structural test).
- **Distro branching in vars, not tasks.** `include_vars` is the ONLY task-level place `ansible_os_family` appears: load `vars/arch.yml` when `ansible_os_family == "Archlinux"`, `vars/debian.yml` when `== "Debian"`. Every Arch-specific task thereafter gates on `when: packages_use_aur | bool` — `true` in `vars/arch.yml`, `false` in `vars/debian.yml`. This keeps the AC-4 contract mechanically testable and keeps distro logic in vars.
- **Debian-family availability caveat:** Hyprland/Hyprpaper are NOT in Debian stable / Ubuntu default repos. Story 2.2 explicitly deferred third-party repo / PPA enablement to this story's `packages` role concern (deferred W3/D5). Decision: author the plain `apt` path with `ansible.builtin.package`; record the Debian repo/PPA enablement as an open question if the names do not resolve in the target distro's configured repos (fail-loud beats silent skip — NFR-9). Do NOT invent PPA setup that is not verifiable in this story; note it for the integration stories (3.2/3.3) to exercise on a real Debian-family host.

### The playbook (locked distro-selection mechanism)

`playbooks/packages.yaml` — from Story 2.2 Dev Notes, this exact pattern is the contract for Stories 2.3+:

```yaml
# playbooks/packages.yaml
- name: Assign distro group
  hosts: localhost
  gather_facts: true
  tasks:
    - name: Group host by os_family seam
      ansible.builtin.group_by:
        key: "{{ os_family }}"
- name: Provision packages
  hosts: "{{ os_family }}"
  become: true
  roles:
    - packages
```

- The `group_by` key is the `os_family` EXTRA-VAR (values `arch`/`debian-family`), NOT raw `ansible_os_family` (`Archlinux`/`Debian`) — the group name must match the `group_vars` filename seam.
- `gather_facts: true` is required so `ansible.builtin.package` can detect pacman/apt (`ansible_os_family` also drives the `include_vars` + `when` in the role).
- The executor provides `os_family` + `install_dir` via `--extra-vars` (Story 1.5 seam contract — those two keys and no others). Running the playbook directly requires `-e os_family=arch` (or `debian-family`); an undefined `os_family` fails loudly, which is correct.
- `ansible.cfg` discovery: the executor passes `ANSIBLE_CONFIG` → `src/provisioning/ansible/ansible.cfg` (Story 2.2 `_ansible_env`), so `roles_path = roles` resolves relative to the cfg dir and `roles/packages` is found. Direct `ansible-playbook` runs must set `ANSIBLE_CONFIG` (or run from a dir where discovery works) — see the smoke-test note in Testing.

### `tasks/main.yml` — the Arch yay self-bootstrap (FR-14, plan §3)

The locked AUR strategy: `base-devel`+`git` → guarded `makepkg -si yay-bin` (skip if `yay` present) → `kewlfft.aur.aur` drives AUR installs. Distro logic stays in `vars/arch.yml`.

```yaml
# Arch-only: prerequisites + aur_builder user (become: true).
# Gated on `packages_use_aur` (loaded from vars/arch.yml by include_vars) so
# tasks never branch on ansible_os_family — distro logic lives in vars.
- name: Install base-devel and git
  ansible.builtin.package:
    name: [base-devel, git]
    state: present
  become: true
  when: packages_use_aur | bool

- name: Create aur_builder user
  ansible.builtin.user:
    name: "{{ aur_builder_user }}"
    group: "{{ aur_builder_group }}"
    create_home: true
  become: true
  when: packages_use_aur | bool

- name: Allow aur_builder to run pacman without password
  ansible.builtin.lineinfile:
    path: "/etc/sudoers.d/11-install-{{ aur_builder_user }}"
    line: "{{ aur_builder_user }} ALL=(ALL) NOPASSWD: /usr/bin/pacman"
    create: true
    mode: "0644"
    validate: "visudo -cf %s"
  become: true
  when: packages_use_aur | bool

# Guarded yay-bootstrap — dry-run-safe by construction
- name: Check for existing yay
  ansible.builtin.command: command -v yay
  register: yay_check
  changed_when: false
  failed_when: false
  when: packages_use_aur | bool

- name: Clone yay-bin PKGBUILD
  ansible.builtin.git:
    repo: "{{ yay_repo }}"
    dest: "{{ aur_build_dir }}"
  become: true
  become_user: "{{ aur_builder_user }}"
  when: packages_use_aur | bool and yay_check.rc != 0

- name: Build and install yay-bin via makepkg
  ansible.builtin.command: makepkg -si --noconfirm
  args:
    chdir: "{{ aur_build_dir }}"
  become: true
  become_user: "{{ aur_builder_user }}"
  creates: /usr/bin/yay
  when: packages_use_aur | bool and yay_check.rc != 0

# AUR installs (empty for the current set; still authored, gated on non-empty)
- name: Install AUR packages via yay
  kewlfft.aur.aur:
    name: "{{ aur_packages }}"
    state: present
    use: yay
  become: true
  become_user: "{{ aur_builder_user }}"
  when: packages_use_aur | bool and aur_packages | length > 0
```

Why this is check-mode-safe (AC 5, hardening "dry-run must be dry"):
- `ansible.builtin.command` and `ansible.builtin.git` do NOT execute under `--check`; `command` reports `changed` (would-change) without running, `git` reports changed without cloning when dest is absent.
- `creates: /usr/bin/yay` makes the `makepkg` task idempotent (skips when yay exists) AND safe in check mode (never executes `makepkg`).
- The `command -v yay` presence check (`changed_when: false`, `failed_when: false`) is the skip-guard so a host with yay already present never clones/builds.

Why idempotent (AC 6): `ansible.builtin.package`/`apt`/`pacman` with `state: present` are idempotent; `user`/`lineinfile` (sudoers, with `validate: visudo -cf %s`) are idempotent; the yay-bootstrap has the `creates` guard; `kewlfft.aur.aur` uses `--needed` semantics and skips up-to-date packages. A re-run reports no drift.

**makepkg/root rule:** `makepkg` (and yay) refuse to run as root ("you cannot perform this operation as root"). Hence the `aur_builder` user + `become_user`. The sudoers NOPASSWD `pacman` line lets `makepkg -si` and yay escalate `pacman` internally (kewlfft.aur README requirement). `aur_builder` gets `create_home: true` so the git clone target (`/tmp/dotfiles-aur-build`, or `~aur_builder`) is owned by it.

### Privilege context (AC 7 — resolves OQ-1 for this story)

- **System packages (`ansible.builtin.package`):** `become: true` — the invoking user must be a sudoer able to run `pacman`/`apt` without a password prompt blocking an unattended run. Document this as a precondition (bootstrap runs unattended).
- **AUR steps:** `become: true` + `become_user: "{{ aur_builder_user }}"` — makepkg/yay must not run as root.
- **User-scoped steps** (`uv tool install`, `~/.config` symlinks, settings renders) are LATER stories (2.4/2.10/2.11) and run as the invoking user — they are separate playbooks with their own become context. This story does NOT need to resolve the full run-as-user decision; the packages playbook is privileged-scoped and that is the extent of OQ-1 for story 2.3. Record this scoping in the story's completion notes.
- Do NOT make the whole play `become: true` AND run user-scoped steps inside it — the packages playbook has no user-scoped steps. If the dev agent finds a single-context conflict while implementing, record it as an open question (per AC 7) rather than inventing a workaround.

### Testing — real-file structural tests (mirror Story 2.2 conventions)

- Follow `tests/unit/test_ansible_scaffold.py` exactly: `_find_ansible_dir()` walking up from the test file anchored on `pyproject.toml`, module-level `_ANSIBLE_DIR`, and per-file test classes asserting existence + parse + content contracts. Do NOT copy the file — author a sibling `tests/unit/test_packages_role.py`.
- `ansible-core` is a runtime dependency (already in `pyproject.toml`), so `ansible-playbook --syntax-check` is available in the test env; use `subprocess.run` in the test (tests live OUTSIDE the hexagon — no layering constraint on tests) and `pytest.importorskip("ansible...")` is unnecessary but harmless.
- Syntax-check invocation:
  ```
  ANSIBLE_CONFIG=<ansible>/ansible.cfg ansible-playbook --syntax-check <ansible>/playbooks/packages.yaml -e os_family=arch -e install_dir=/tmp/x
  ```
  Exit 0 asserts the playbook is well-formed. `--syntax-check` does NOT run tasks (no mutation, safe in CI).
- Do NOT add integration dry-run tests of actual installs — that is Story 3.2/3.3 (real `--check` runs need collections installed + a real host).

### Known limitations (accept, do not fix here)

- `kewlfft.aur.aur` check-mode support is not documented upstream; the current `aur_packages` list is empty so the AUR task is skipped under `--check`. Do not add `check_mode: no` (that would violate dry-run-must-be-dry); gate the task on non-empty as designed and note the limitation.
- Debian-family Hyprland/Hyprpaper/Waybar availability in default repos is unverified; PPA/repo enablement is out of scope (open question). The role must fail loudly on resolution failure, not skip silently.
- The executor's `--tags all` (Story 1.8) applies to the aggregate `bootstrap.yaml` (Story 2.12); this story's playbook is invoked directly, so no tag contract applies yet.

## Project Structure Notes

- `src/provisioning/ansible/playbooks/packages.yaml` — NEW playbook (first of one-per-role; aggregate `bootstrap.yaml` is Story 2.12).
- `src/provisioning/ansible/roles/packages/tasks/main.yml` — NEW; only Python-free YAML (no `.py` under `ansible/`).
- `src/provisioning/ansible/roles/packages/vars/{main,arch,debian}.yml` — NEW; distro logic confined here (AC 4).
- `src/provisioning/tests/unit/test_packages_role.py` — NEW structural real-file tests.
- Unchanged: `inventory/`, `requirements.yml`, `ansible.cfg`, `group_vars/`, all of `src/provisioning/src/provisioning/` (the Python hexagon is untouched by this story).
- No new dependencies. No `bootstrap.yaml`. No other roles.

## Testing Requirements

- Full gates: `uv run pytest` (217-pass baseline), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `python tests/architecture/test_layering.py` (standalone nicety).
- New `tests/unit/test_packages_role.py` (see Dev Notes "Testing") covering:
  - role tree existence + `tasks/main.yml` parses to a list of named tasks;
  - `vars/{main,arch,debian}.yml` parse and carry the required keys; no package names in role vars (they live in `group_vars`);
  - `playbooks/packages.yaml` structure (group_by lead-in → `roles: [packages]`, `become: true`);
  - dry-run guard present (guarded `command` makepkg task with `creates`);
  - distro-branching contract (only `include_vars` tasks branch on `ansible_os_family`; no hardcoded pacman/apt module FQCNs in tasks);
  - `ansible-playbook --syntax-check` on `packages.yaml` (with `-e os_family=... -e install_dir=...`) exits 0;
  - value-shape contract: every `group_vars/{arch,debian-family}.yml` `packages` value is a non-empty `str` or non-empty `list[str]`.
- Smoke check (manual, optional): `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg uv run ansible-playbook --syntax-check src/provisioning/ansible/playbooks/packages.yaml -e os_family=arch -e install_dir=/tmp/x`.

## Previous Story Intelligence

### Story 2.2 — Ansible Scaffold (the foundation this role consumes)
- `group_vars/{all,arch,debian-family}.yml` carry the `packages` map; the `arch`/`debian-family` basenames are the `IFactReader.os_family()` seam contract and MUST NOT change. [Source: 2-2-ansible-scaffold.md "The seam contract"]
- Locked distro-selection pattern (group_by on the `os_family` extra-var → dynamic `arch`/`debian-family` group → `group_vars` auto-apply) — reproduced in this story's playbook. [Source: 2-2-ansible-scaffold.md "Distro selection mechanism"]
- `ANSIBLE_CONFIG` wiring: `AnsibleExecutor(config_file=_ANSIBLE_ROOT / "ansible.cfg", ...)`; relative `inventory`/`roles_path` resolve from the cfg dir. `_ANSIBLE_ROOT` = `src/provisioning/ansible`. [Source: src/provisioning/src/provisioning/cli/main.py:68-86, 2-2-ansible-scaffold.md]
- Deferred to this story (lock here): D3 `packages` map value-shape contract (scalar vs list) — LOCKED in Dev Notes; D5 font-set parity (arch 4 fonts incl. nerd font vs debian 3) — carried as-authored, Debian repo enablement is the open question. [Source: 2-2-ansible-scaffold.md Review Findings / deferred-work.md]

### Story 2.1 — Declarative Manifests
- `dotfiles/provisioning/packages.yaml` carries the distro-agnostic logical set (`hyprland`, `hyprpaper`, `waybar`, `fonts`); ratified interpretation: per-manager names resolve in `group_vars` (2.2/2.3), never in the manifest or Python. [Source: 2-1-declarative-manifests.md "Manifest authoring", packages.yaml]
- Review note: Ansible (Stories 2.3-2.12) should key off `kind` + `spine_segment()`, not `name`. The packages role consumes group_vars directly — the manifest itself is not consumed by Ansible (data lives in group_vars). [Source: 2-1-declarative-manifests.md Review Findings]

### Epic 1 retrospective (2026-08-08) — nothing pending for this story
- Epic-1 retro action items (use-case duplication, production timeout decision, mirror-and-adapt discipline, version-command hardening) are all Epic 1/2.12-scope; none block the packages role. [Source: epic-1-retro-2026-08-08.md]

## Git Intelligence

Recent commit pattern (follow the same flow): `chore: create story X` (this story) → `feat: ... implement story X` → `fix: apply X code review findings` → `chore: mark story X done`. Current HEAD baseline: `3cf656f` (chore: mark story 2.2 done). Recent relevant history: 2.2 landed the Ansible scaffold + `ANSIBLE_CONFIG` wiring (`422e358`, `a45b245`); 2.1 landed `ManifestKind`/`AssetKind.spine_segment` + the five manifests (`49c0065`).

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#320-335] — Story 2.3 ACs (packages role)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#35] — FR-14 Packages Role
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#211-213] — FR-14 PRD detail
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#393] — OQ-1 run-as-user privilege context (owner: implementation, story 2.3)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#57] — plan §3 AUR helper strategy (yay self-bootstrap, distro logic in vars/arch.yml)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#158] — plan §6 `roles/packages/` tree
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#283] — plan §11 step 7 (roles in install order; `packages` first)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#48] — AUR strategy constraint
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#44] — distro differences isolated to group_vars
- [Source: _bmad-output/implementation-artifacts/2-2-ansible-scaffold.md#118-140] — locked distro-selection pattern (group_by `os_family` seam)
- [Source: _bmad-output/implementation-artifacts/2-2-ansible-scaffold.md#188-221] — group_vars content + packages map contract
- [Source: dotfiles/provisioning/packages.yaml] — logical package set
- [Source: src/provisioning/ansible/group_vars/{arch,debian-family}.yml] — per-distro names the role consumes
- [Source: src/provisioning/ansible/requirements.yml] — kewlfft.aur 0.13.0 pinned
- [Source: src/provisioning/src/provisioning/cli/main.py#68-86] — `_ANSIBLE_ROOT` + `build_deps()` executor construction
- [Source: src/provisioning/src/provisioning/application/use_cases.py#38-48] — `_seam_extra_vars` (`install_dir`, `os_family`)
- [Source: https://docs.ansible.com/ansible/latest/collections/ansible/builtin/package_module.html] — `ansible.builtin.package` auto-detect; `use: auto` default
- [Source: https://github.com/kewlfft/ansible-aur] — `kewlfft.aur.aur` options (name/state/use/upgrade); `aur_builder` user + NOPASSWD pacman sudoers requirement; makepkg refuses root

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-09: Researched `ansible.builtin.package` (auto-detects pacman/apt, `use: auto`) and `kewlfft.aur.aur` (auto-selects yay; requires a non-root builder user with NOPASSWD pacman in sudoers because makepkg/yay refuse root).
- 2026-08-09: Confirmed `roles_path = roles` + `ANSIBLE_CONFIG` wiring (Story 2.2) means the role at `roles/packages` resolves; `playbooks/` and `roles/` dirs do not exist yet and are created in this story.
- 2026-08-09: Story created with baseline `3cf656f`; suite baseline 217 passed.

### Completion Notes List

- 2026-08-09: Implemented Story 2.3 Packages Role.
  - Authored `roles/packages/tasks/main.yml`: two `include_vars` tasks branch on `ansible_os_family` (arch/debian) — the ONLY os-family branching in tasks; everything Arch-specific gates on `packages_use_aur | bool` (AC 4). Flattens the `group_vars` `packages` map via `packages.values() | list | flatten` and installs with `ansible.builtin.package` (auto-detects pacman/apt, NFR-3). Arch path: base-devel+git → `aur_builder` user (group wheel, create_home) + NOPASSWD pacman sudoers → guarded `command -v yay` check → `git clone` + `makepkg -si --noconfirm` (creates: /usr/bin/yay, become_user aur_builder) → `kewlfft.aur.aur` gated on non-empty (AC 2/5/6).
  - Authored `vars/{main,arch,debian}.yml` — distro logic confined to vars; no package names in role vars (NFR-3). `vars/main.yml` has shared defaults only (`packages_state`, `aur_build_dir`); `vars/arch.yml` sets `packages_use_aur: true` + `aur_packages: []` + `yay_repo`; `vars/debian.yml` sets `packages_use_aur: false`.
  - Authored `playbooks/packages.yaml`: locked group_by distro-selection pattern (Story 2.2) — lead play `group_by: key: "{{ os_family }}"` on localhost, second play `hosts: "{{ os_family }}"`, `become: true`, `roles: [packages]`.
  - Authored `tests/unit/test_packages_role.py` (13 tests): role tree, tasks parse + distro-branching contract, no hardcoded pacman/apt FQCNs, makepkg dry-run guard (`command` + `creates`), vars required keys + no package names, playbook structure, `ansible-playbook --syntax-check` exit 0 for both distros, group_vars value-shape contract (locks deferred D3).
  - Privilege context (AC 7 / OQ-1): system packages run `become: true`; makepkg/yay/AUR run `become: true become_user: aur_builder`; no user-scoped steps in this playbook (2.4/2.10 later) — no single-context conflict encountered.
  - Dry-run/idempotency (AC 5/6): `command`/`git` never execute under `--check`; `creates` guard makes the makepkg task idempotent; `command -v yay` skip-guard prevents redundant rebuilds.
  - Installed pinned ansible collections (requirements.yml: community.general 13.2.0, ansible.posix 2.2.2, kewlfft.aur 0.13.0) locally so `--syntax-check` resolves `kewlfft.aur.aur`.
  - Verification: `uv run pytest` 230 passed (217 baseline + 13 new), `ruff check` + `ruff format --check` clean, `mypy src tests` clean, `python tests/architecture/test_layering.py` exit 0.

### File List

- NEW `src/provisioning/ansible/roles/packages/tasks/main.yml`
- NEW `src/provisioning/ansible/roles/packages/vars/main.yml`
- NEW `src/provisioning/ansible/roles/packages/vars/arch.yml`
- NEW `src/provisioning/ansible/roles/packages/vars/debian.yml`
- NEW `src/provisioning/ansible/playbooks/packages.yaml`
- NEW `src/provisioning/tests/unit/test_packages_role.py`

### Review Findings

- [x] [Review][Patch] `os_family` seam not validated against `ansible_os_family` — wrong-distro run loads wrong group_vars [playbooks/packages.yaml:20-23, tasks/main.yml:12-24]
  The playbook groups by the `os_family` EXTRA-VAR seam while the role branches on `ansible_os_family`. A manual `-e os_family=arch` on a Debian host (or `debian-family` on Arch) silently loads the wrong `group_vars` `packages` map and hands the wrong names to the auto-detected package manager (partial installs before a hard fail; AUR path silently disabled). Decision (resolved 2026-08-10): add a guard task in the first play asserting the seam maps to the fact (`arch`↔`Archlinux`, `debian-family`↔`Debian`), failing loudly on mismatch (NFR-9).
- [x] [Review][Patch] Check-mode silently skips clone + makepkg — AC5 "reports would-change" under-reported [tasks/main.yml:57-79]
  In `--check`, the `command -v yay` task is skipped, and a skipped command registers `rc: 0` (verified empirically: ansible-playbook 2.20). The `when: ... and yay_check.rc != 0` guard then evaluates false, so the git clone and makepkg tasks report `skipped` instead of `would-change` — the check preview does not surface the pending yay build. Dry-run stays dry (makepkg never executes), but AC5's "reports would-change" is not met and the yay build is invisible in the preview. Fix: drop `and yay_check.rc != 0` from the makepkg task's `when` (the `creates: /usr/bin/yay` guard already makes it idempotent AND makes check mode report would-change); keep the guard on the git clone task. Add a structural check-mode assertion (e.g. verify the makepkg task's `when` contains no `yay_check.rc` reference, or run `ansible-playbook --check` under a mock) so this contract is locked.
- [x] [Review][Patch] Git clone dest collision on interrupted-run retry [tasks/main.yml:64-70]
  If a first run fails mid-clone (network drop, timeout), `/tmp/dotfiles-aur-build` is left as a non-empty non-git directory; the retry `ansible.builtin.git` task errors ("destination path already exists and is not a git repository") because `force` is unset. `/tmp` purge mitigates across reboots but not within a session. Fix: add `force: true` to the git task (or a pre-task removing a stale non-repo dest). Note: `force: true` also rebinds a valid clone from a different repo URL (e.g. yay vs yay-bin).
- [x] [Review][Patch] Empty-string package values leak to the package manager [tasks/main.yml:22-30]
  `packages.values() | list | flatten` drops empty lists but passes blank strings through to `ansible.builtin.package`. The D3 value-shape contract test locks today's group_vars, but the role itself offers no defense if a future group_vars edit introduces `""`. Fix: `packages.values() | list | flatten | reject('equalto', '') | list`.
- [x] [Review][Patch] `aur_packages` undefined on non-Arch — fragile Jinja short-circuit [vars/main.yml, tasks/main.yml:81-88]
  `aur_packages` is only defined by `include_vars` of `vars/arch.yml`. The AUR task works today only because `packages_use_aur | bool` short-circuits on Debian. Any reordering (or a future `packages_use_aur: true` default) becomes an UndefinedError. Fix: add `aur_packages: []` as a shared default in `vars/main.yml` (a distro-agnostic default, consistent with the spec's "shared defaults only" intent).
- [x] [Review][Patch] sudoers.d file mode 0644 and `lineinfile` without `regexp` — non-conformant mode, stale/duplicate lines accumulate [tasks/main.yml:47-55]
  `sudoers` man page mandates 0440 for `/etc/sudoers.d` files; 0644 functions (sudo only rejects group/other *write*) but is non-conformant and leaks the rule. `lineinfile` without `regexp` appends rather than replacing an existing stale line for the same user. Fix: `mode: "0440"` and add `regexp: "^{{ aur_builder_user }} "` so the exact rule is replaced idempotently.
- [x] [Review][Defer] Debian-family `hyprland`/`hyprpaper`/`waybar` don't resolve in default apt repos — AC3 unreachable on stock Debian/Ubuntu [group_vars/debian-family.yml:11-16]
  `ansible.builtin.package` → apt fails ("Unable to locate package") on an unmodified Debian/Ubuntu host, so the AC3 goal ("packages present on the machine") cannot be met for the three Hyprland-family entries. This is the spec's explicitly acknowledged open question ("third-party repo / PPA enablement ... not resolved here", Dev Notes "Debian-family availability caveat"; fail-loud beats silent skip — NFR-9). The role matches spec intent (plain apt path, fail-loud); PPA/repo enablement is deferred to the integration stories (3.2/3.3) — deferred, pre-existing spec decision.
- [x] [Review][Defer] Pre-existing `aur_builder` user with non-login shell or missing `wheel` group breaks makepkg [tasks/main.yml:39-45]
  The `ansible.builtin.user` task sets group/home but never `shell`; if `aur_builder` pre-exists with `/usr/sbin/nologin`, `makepkg`/`yay` fail. On Arch `wheel` always exists; forcing `packages_use_aur=true` on a non-Arch host errors "group wheel does not exist". The deployment path is a fresh-machine bootstrap where the user does not pre-exist — deferred, pre-existing assumption.
- [x] [Review][Defer] `creates: /usr/bin/yay` means the role never upgrades yay; stale/broken binary not rebound [tasks/main.yml:72-79]
  Once `/usr/bin/yay` exists the makepkg task is permanently `creates`-skipped, so yay is never updated by this role even when the PKGBUILD changes. Accept: yay is a bootstrap that self-updates via `yay`; the `kewlfft.aur.aur` task fails loudly if the binary is broken (NFR-9). Deferred, by-design.

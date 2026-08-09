---
baseline_commit: 2e59b7d
---

# Story 2.2: Ansible Scaffold

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-08: Story created — ultimate context engine analysis completed; comprehensive developer guide created.
- 2026-08-09: Story implemented — scaffold authored, ANSIBLE_CONFIG wiring landed, 14 new tests, all gates green.

## Story

As an operator,
I want the Ansible project scaffold in place,
So that playbooks can run against the local host with distro-aware group variables.

## Acceptance Criteria

1. `src/provisioning/ansible/inventory/localhost.yaml` targets the local host (AC 1, FR-13)
2. `src/provisioning/ansible/requirements.yml` declares `community.general`, `ansible.posix`, and `kewlfft.aur` (AC 2, FR-13)
3. `src/provisioning/ansible/ansible.cfg` configures inventory and roles paths (AC 3, FR-13)
4. `src/provisioning/ansible/group_vars/{all,arch,debian-family}.yml` exist with per-distro package settings; the `arch`/`debian-family` filenames match the `IFactReader.os_family()` seam contract (AC 4, FR-13)
5. Distro differences are isolated to `group_vars` — no distro branching in Python or `bootstrap.sh` (AC 5, FR-13, NFR-3)

## Tasks / Subtasks

- [x] Create the Ansible scaffold directory tree (AC: 1, 2, 3, 4)
  - [x] `src/provisioning/ansible/inventory/`
  - [x] `src/provisioning/ansible/group_vars/`
  - [x] Note: `playbooks/` and `roles/` dirs are NOT created in this story (Stories 2.3–2.12)
- [x] Author `inventory/localhost.yaml` (AC: 1)
  - [x] `all.hosts.localhost` with `ansible_connection: local`
  - [x] `ansible_python_interpreter: "{{ ansible_playbook_python }}"` (same interpreter that runs ansible-playbook — the uv venv python)
  - [x] Do NOT statically place localhost under `arch`/`debian-family` children groups (both var sets would merge — see Dev Notes distro-selection)
- [x] Author `requirements.yml` (AC: 2)
  - [x] Declare `community.general`, `ansible.posix`, `kewlfft.aur`; pin verified collection versions (resolve compatibility against installed `ansible-core` 2.21 at implementation time)
- [x] Author `ansible.cfg` (AC: 3)
  - [x] `[defaults]` with `inventory = inventory/localhost.yaml` and `roles_path = roles`
  - [x] Relative paths resolve relative to the cfg file's own directory (empirically verified against ansible-core 2.21 — see Dev Notes)
- [x] Author `group_vars/all.yml`, `group_vars/arch.yml`, `group_vars/debian-family.yml` (AC: 4)
  - [x] `arch.yml`/`debian-family.yml`: per-distro `packages` map covering EVERY logical entry in `dotfiles/provisioning/packages.yaml` (`hyprland`, `hyprpaper`, `waybar`, `fonts`) — non-empty, no typo'd names
  - [x] `all.yml`: shared distro-agnostic settings ONLY; do NOT default `install_dir` (must stay fail-loud, Story 2.11)
- [x] Wire `ANSIBLE_CONFIG` so the scaffold is actually consumable (AC: 3 — see Dev Notes "ansible.cfg discovery")
  - [x] Add `config_file: Path | None = None` param to `AnsibleExecutor` + `_ansible_env()` helper in `src/provisioning/src/provisioning/adapters/ansible_executor.py` (backward compatible — injected-runner contract unchanged)
  - [x] Pass `config_file=_ANSIBLE_ROOT / "ansible.cfg"` from `build_deps()` in `src/provisioning/src/provisioning/cli/main.py`
  - [x] Preserve ALL existing executor behavior (command shape, extra-vars seam, error mapping) — full suite must stay green
- [x] Add scaffold tests (AC: 1, 2, 3, 4)
  - [x] `tests/unit/test_ansible_scaffold.py`: real-file structural tests (exist + parse + content contracts)
  - [x] `tests/unit/adapters/test_ansible_executor.py`: `_ansible_env()` cases + config_file-with-injected-runner regression guard
- [x] Verify full suite + lint + layering guard (AC: 5)
  - [x] `uv run pytest` — full suite green, nothing regresses from the 194-pass baseline
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)

## Dev Notes

### Scope — what Story 2.2 is and is not

**IS:** the Ansible project scaffold under `src/provisioning/ansible/` — inventory, collection `requirements.yml`, `ansible.cfg`, and `group_vars/{all,arch,debian-family}.yml` with per-distro package settings, plus the minimal executor/CLI wiring so `ansible.cfg` is actually honored by `ansible-playbook` (the scaffold is only "correct" if Ansible can consume it).

**IS NOT:** playbooks (`playbooks/` — Story 2.12 aggregates, Story 2.3+ per-role), roles (`roles/` — Stories 2.3–2.12), compositor skeleton configs `dotfiles/config/{hypr,hyprpaper,waybar}/` (Story 2.8), the `settings`/`verify` role templates (Stories 2.11/2.12), `scripts/bootstrap.sh` (Story 3.1), integration tests (Story 3.2/3.3). Do NOT author any playbook or role in this story.

### Where files live (locked by plan §6)

```
src/provisioning/ansible/            ← NEW dir — sibling of src/provisioning/src, NOT inside the Python package
├── inventory/localhost.yaml
├── requirements.yml
├── ansible.cfg
└── group_vars/{all,arch,debian-family}.yml
```

- `src/provisioning/ansible/` is OUTSIDE `_SRC_ROOT` (`src/provisioning/src/provisioning`), so the layering test (`tests/architecture/test_layering.py`) never scans it and it is not part of the Python hexagon. It is YAML/INI data only.
- `_ANSIBLE_ROOT` is already wired in the CLI composition root (Story 1.8): `_ANSIBLE_ROOT = Path(__file__).resolve().parents[3] / "ansible"` resolves to `src/provisioning/ansible` and `build_deps()` already constructs `AnsibleExecutor(inventory=_ANSIBLE_ROOT / "inventory" / "localhost.yaml", tags="all")` and points use cases at `playbooks/bootstrap.yaml` / `playbooks/verify.yaml`. [Source: src/provisioning/src/provisioning/cli/main.py:68-86]

### The seam contract (load-bearing, do not break)

- `IFactReader.os_family()` returns the `group_vars` basename: `"arch"` or `"debian-family"` (mapping `Archlinux`→`arch`, `Debian`/`Ubuntu`→`debian-family`, fail-loud otherwise). [Source: src/provisioning/src/provisioning/adapters/ansible_fact_reader.py:29-33, 119-124]
- `Distro` enum values are exactly `"arch"` and `"debian-family"` and "MUST match the `group_vars` filenames" (docstring). [Source: src/provisioning/src/provisioning/domain/enums.py:8-17]
- The Python side passes exactly `{"install_dir": ..., "os_family": <group_vars basename>}` as `--extra-vars` (Story 1.5 seam contract test pins these two keys and no others). [Source: src/provisioning/src/provisioning/application/use_cases.py:38-48, tests/unit/adapters/test_ansible_executor.py:80-105]
- **Therefore the `group_vars` filenames MUST be exactly `arch.yml` and `debian-family.yml`** (plus `all.yml`). Any rename breaks the seam. There is no "contexted"/legacy variant — keep it exact.

### Distro selection mechanism (lock now so Stories 2.3+ don't rediscover it)

`group_vars` only auto-load for groups the host is a member of. The `os_family` extra-var must therefore be turned into a group membership at play time. The locked pattern for Stories 2.3+ (each playbook that needs distro vars leads with this):

```yaml
# playbooks/packages.yaml — pattern for Stories 2.3+ (NOT authored in this story)
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

- `group_by: key: "{{ os_family }}"` creates a dynamic group named `arch` or `debian-family`; `group_vars/<that name>.yml` then auto-applies to the host. This keeps distro logic in `group_vars` (Ansible-native) with zero Python/branching.
- **Anti-pattern to prevent:** do NOT statically declare `arch:` / `debian-family:` children groups containing `localhost` in the inventory — a host in two groups merges BOTH `group_vars` sets (distro isolation breaks). The inventory stays a plain localhost host entry.
- The `group_by` key is the `os_family` EXTRA-VAR (values `arch`/`debian-family`), NOT raw `ansible_os_family` (`Archlinux`/`Debian`) — the group name must match the group_vars filename.

### `inventory/localhost.yaml`

```yaml
# Runs against the local host only (plan §6 / FR-13).
all:
  hosts:
    localhost:
      ansible_connection: local
      ansible_host: 127.0.0.1
      ansible_python_interpreter: "{{ ansible_playbook_python }}"
```

- `ansible_connection: local` — no SSH transport.
- `ansible_python_interpreter: "{{ ansible_playbook_python }}"` — make the local connection run modules with the SAME interpreter that executes `ansible-playbook` (the uv venv python that resolves `ansible-core`), avoiding interpreter mismatch on the local connection.
- `become` is a playbook/role concern (Story 2.3 packages role), not an inventory concern — leave it out.

### `requirements.yml`

```yaml
---
collections:
  - name: community.general
  - name: ansible.posix
  - name: kewlfft.aur
```

- Resolved via `ansible-galaxy collection install -r requirements.yml` at bootstrap start (locked decision, plan §3) — a resolution failure must abort loudly (Story 3.1) rather than proceed with missing modules.
- **Pin verified collection versions** at implementation time (NFR-9 reproducibility). Resolve versions compatible with the installed `ansible-core` 2.21 (`uv run ansible-galaxy collection list` or the Galaxy API). `community.general` and `ansible.posix` also ship with ansible-core but explicit declarations are the locked contract (plan §3); `kewlfft.aur` is required for the Story 2.3 AUR installs.
- Do NOT declare `ansible.builtin` — it is implicit.

### `ansible.cfg`

```ini
[defaults]
inventory = inventory/localhost.yaml
roles_path = roles
```

- **Discovery is the load-bearing problem.** `find_ini_config_file()` in ansible-core 2.21 searches ENV (`ANSIBLE_CONFIG`) → CWD (`./ansible.cfg`) → HOME → `/etc/ansible` — there is NO playbook-relative discovery. The executor runs `ansible-playbook` with CWD = `src/provisioning` (via `uv run --directory ./src/provisioning`), so `src/provisioning/ansible/ansible.cfg` is NOT found by CWD discovery. **Therefore the executor must pass `ANSIBLE_CONFIG` pointing at this file** (Task: executor `config_file` param + `_ansible_env()` helper). Without it, `roles_path` never applies and the Story 2.3+ roles (at `ansible/roles/`, not `ansible/playbooks/roles/`) will not resolve.
- **Relative paths are safe.** Empirically verified against ansible-core 2.21: with `ANSIBLE_CONFIG=/.../ansible/ansible.cfg` containing `inventory = inventory/localhost.yaml` and `roles_path = roles`, both resolve relative to the cfg file's own directory (`.../ansible/inventory/...`, `.../ansible/roles/`), regardless of CWD. So relative paths in this file are correct and portable.
- `inventory` is technically redundant (the executor passes `-i <absolute inventory>`), but keeping it makes bare `ansible-playbook` invocations work and matches AC 3's "configures inventory and roles paths".

### `group_vars/` content

**`all.yml`** — shared, distro-agnostic settings. Keep MINIMAL. Do NOT default `install_dir` (the orchestrator seam always provides it; an undefined `install_dir` must fail loudly in Story 2.11's renders, not silently resolve to a default). Spine sub-path variables (e.g. `spine_wallpapers_dir`) are authored when the filesystem/assets/settings roles land (Stories 2.5–2.11) — do not guess them here. A documented header explaining the seam is encouraged.

**`arch.yml`** — per-distro package settings (the `arch` basename = the seam value):
```yaml
# Arch (pacman + AUR) — consumed by the packages role (Story 2.3).
# Filename matches the IFactReader.os_family() seam contract.
packages:
  hyprland: hyprland
  hyprpaper: hyprpaper
  waybar: waybar
  fonts:
    - ttf-jetbrains-mono-nerd
    - noto-fonts
    - noto-fonts-cjk
    - ttf-nerd-fonts-symbols
```

**`debian-family.yml`** — per-distro package settings:
```yaml
# Debian-family (apt) — consumed by the packages role (Story 2.3).
# Filename matches the IFactReader.os_family() seam contract.
packages:
  hyprland: hyprland
  hyprpaper: hyprpaper
  waybar: waybar
  fonts:
    - fonts-noto
    - fonts-noto-cjk
    - fonts-noto-color-emoji
```

Ground rules for `group_vars` authoring:
- The `packages` map MUST cover every logical entry in `dotfiles/provisioning/packages.yaml` (Story 2.1): `hyprland`, `hyprpaper`, `waybar`, `fonts`. Per-manager names resolve HERE, not in the manifest and not in Python (NFR-3, Story 2.1 ratified interpretation). [Source: dotfiles/provisioning/packages.yaml]
- The `packages` role (Story 2.3) should drive installs with `ansible.builtin.package` (auto-selects pacman/apt) and consume this `packages` map — do NOT add a `pkg_manager` var; the module auto-detects the manager.
- `fonts` is a package-group key (Capability.FONTS = PACKAGE_GROUP, not a PATH binary) [Source: src/provisioning/src/provisioning/domain/enums.py:52-60]. The exact font packages are NOT spec-locked — verify each name at implementation time (`pacman -Si <name>` / `apt-cache show <name>`) and lock the verified set in the file. The sets above are starting recommendations only.
- Debian-family availability of Hyprland/Hyprpaper (not in Debian stable / Ubuntu default repos) is a Story 2.3 `packages` role concern (third-party repo / PPA enablement), NOT something this story resolves — group_vars only carries the names.

### Executor wiring change (the one Python touch)

`src/provisioning/src/provisioning/adapters/ansible_executor.py` (Story 1.5 adapter — modify minimally, preserve everything):
- Add `import os` (stdlib, adapter layer — no layering concern).
- Add module helper:
  ```python
  def _ansible_env(config_file: Path | None) -> dict[str, str] | None:
      if config_file is None:
          return None
      return {**os.environ, "ANSIBLE_CONFIG": str(config_file)}
  ```
- Change `_default_runner(command, timeout=None, env=None)` to forward `env=env` to `subprocess.run`.
- `AnsibleExecutor.__init__(..., config_file: Path | None = None)` — store it; when `runner` is NOT injected, build `self._runner = lambda command: _default_runner(command, timeout, _ansible_env(config_file))`. When `runner` IS injected (all existing tests), leave it untouched — **the injected-runner contract `Callable[[list[str]], CompletedProcess]` must NOT change** (it is used by every existing test fake).
- Do NOT touch the command construction (`-i`, `--tags`, `--check`, `--extra-vars`), the extra-vars seam, `_parse_tasks`, or the error/exception mapping. The Story 1.5 seam contract tests must stay green unchanged.

`src/provisioning/src/provisioning/cli/main.py` `build_deps()` — add `config_file=_ANSIBLE_ROOT / "ansible.cfg"` to the `AnsibleExecutor(...)` construction. (Note: `build_deps()` is monkeypatched in all CLI tests, so no CLI-test churn. The open sprint action item about a production `timeout` for the executor is adjacent but separate — do not resolve it here unless trivial.)

### Layering guard & regression care (Story 1.3)

- The only Python changes are in `adapters/ansible_executor.py` (new import `os`, new optional param) and `cli/main.py` (`build_deps` one-liner). Both are outer layers — no domain/ports change, no allowlist/banned-stdlib concern.
- `src/provisioning/ansible/` is not under `_SRC_ROOT`, so the layering scanner never reads it; do NOT add a `.py` file anywhere under `ansible/` (a stray Python module there would not be scanned, but it would be dead code — keep ansible/ data-only).
- The layering test also derives allowed third-party roots from `pyproject.toml`; `ansible-core` is already declared (Story 1.1) and normalizes to `ansible` — no dependency changes needed.
- Run the FULL suite; nothing may regress from the 194-pass baseline.

### Known limitations (accept, do not fix here)

- The `dotfiles-provision` wheel does not bundle `ansible/` (hatchling `packages = ["src/provisioning"]`); `_ANSIBLE_ROOT` only resolves correctly when run from the source tree, which is exactly the locked bootstrap flow (`uv run --directory ./src/provisioning ...`). Fine for Phase 1; note it for Phase 2 if install-based usage appears.
- No playbook exists yet, so `plan`/`apply`/`verify`/`bootstrap` remain not-runable end-to-end until Story 2.12 — expected; this story only ensures the scaffold + `ANSIBLE_CONFIG` wiring so Story 2.3+ playbooks resolve roles.

## Project Structure Notes

- `src/provisioning/ansible/` — NEW data-only tree (plan §6): `inventory/localhost.yaml`, `requirements.yml`, `ansible.cfg`, `group_vars/{all,arch,debian-family}.yml`. Not part of the Python hexagon.
- `src/provisioning/src/provisioning/adapters/ansible_executor.py` — modified: optional `config_file` + `_ansible_env()` (backward compatible).
- `src/provisioning/src/provisioning/cli/main.py` — modified: `build_deps()` passes `config_file=_ANSIBLE_ROOT / "ansible.cfg"`.
- `src/provisioning/tests/unit/test_ansible_scaffold.py` — NEW structural tests.
- `src/provisioning/tests/unit/adapters/test_ansible_executor.py` — extended (`_ansible_env`, config_file regression guard).
- No new dependencies. No `playbooks/`, `roles/`, `dotfiles/config/{hypr,hyprpaper,waybar}/`, `scripts/bootstrap.sh` in this story.

## Testing Requirements

- **Real-file scaffold tests** (`tests/unit/test_ansible_scaffold.py`) — for each real file under `src/provisioning/ansible/`, resolve it from the test file and assert:
  - Files exist: `inventory/localhost.yaml`, `requirements.yml`, `ansible.cfg`, `group_vars/all.yml`, `group_vars/arch.yml`, `group_vars/debian-family.yml`.
  - `group_vars` filenames match the seam contract exactly: `all`, `arch`, `debian-family` (assert against `Distro` enum values where practical, or a literal tuple).
  - `group_vars/{arch,debian-family}.yml` parse as YAML and their `packages` map covers the four logical entries from `dotfiles/provisioning/packages.yaml` (hyprland, hyprpaper, waybar, fonts) with non-empty names.
  - `inventory/localhost.yaml` parses and has `localhost` with `ansible_connection: local`; assert it does NOT statically place localhost under `arch`/`debian-family` groups.
  - `requirements.yml` parses and declares `community.general`, `ansible.posix`, `kewlfft.aur`.
  - `ansible.cfg` declares `inventory` and `roles_path` under `[defaults]`.
- **Executor tests** (`tests/unit/adapters/test_ansible_executor.py`):
  - `_ansible_env(None) is None`.
  - `_ansible_env(Path("ansible.cfg"))` contains `ANSIBLE_CONFIG == "ansible.cfg"` and preserves existing env entries.
  - Constructing `AnsibleExecutor(..., config_file=Path("ansible.cfg"))` with an injected fake runner still records/returns correctly (regression guard: injected-runner contract unchanged).
- **Smoke checks (manual, optional for CI):** `ANSIBLE_CONFIG=src/provisioning/ansible/ansible.cfg uv run ansible-config dump --only-changed` shows `DEFAULT_HOST_LIST` and `DEFAULT_ROLES_PATH` resolving under `src/provisioning/ansible/`.
- Full gates: `uv run pytest` (194-pass baseline), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests`, `python tests/architecture/test_layering.py` (standalone).

## Previous Story Intelligence

### Story 2.1 — Declarative Manifests (the data this scaffold's group_vars consumes)
- `dotfiles/provisioning/packages.yaml` carries the distro-agnostic logical package set: `hyprland`, `hyprpaper`, `waybar`, `fonts`. Ratified interpretation: per-manager names resolve in Ansible `group_vars` (this story) — never in the manifest or Python. [Source: dotfiles/provisioning/packages.yaml; 2-1-declarative-manifests.md Dev Notes "Manifest authoring"]
- `ManifestKind` + `AssetKind.spine_segment()` landed; the reader is strict/fail-closed; Ansible (Stories 2.3–2.12) is the primary consumer of the manifests and should key off `kind` + `spine_segment()`, not `name`. [Source: 2-1-declarative-manifests.md Completion Notes]

### Story 1.8 — Typer CLI (already wires the ansible root)
- `build_deps()` resolves `_ANSIBLE_ROOT` to `src/provisioning/ansible` and constructs `AnsibleExecutor(inventory=_ANSIBLE_ROOT/"inventory"/"localhost.yaml", tags="all")` plus use cases pointed at `playbooks/{bootstrap,verify}.yaml`. CLI tests monkeypatch `build_deps` — safe to extend the executor construction. [Source: src/provisioning/src/provisioning/cli/main.py:68-86, tests/unit/cli/conftest.py:82]

### Story 1.5 — Adapters (the executor being extended)
- `AnsibleExecutor` shells `ansible-playbook -i <inventory> --tags <tags> [--check] --extra-vars <json> <playbook>`; the extra-vars seam is sealed to exactly `install_dir` + `os_family`; injected-runner contract is `Callable[[list[str]], CompletedProcess]`; `ProvisionTimeoutError`/`ProvisionExecutorError` mapping. Preserve ALL of it. [Source: src/provisioning/src/provisioning/adapters/ansible_executor.py]

### Story 1.4/1.6/1.7 — Ports & use cases
- `IFactReader.os_family() -> str` returns the `group_vars` basename; `_seam_extra_vars()` builds `{"install_dir", "os_family"}`. No Python distro branching exists or may be added. [Source: src/provisioning/src/provisioning/ports/fact_reader.py, application/use_cases.py:38-48]

### Retro AI-1 (Epic 1 retrospective) — resolved in Story 2.1
- Deferred domain shapes reconciled in 2.1; nothing pending for this story from the retro.

## Git Intelligence

Recent commit pattern (follow the same flow): `chore: create story X` (this story) → `feat: ... implement story X` → `fix: auto-commit code review findings`. Current HEAD for baseline: `2e59b7d`. Recent relevant history: 2.1 landed `ManifestKind`/`AssetKind.spine_segment` + the five manifests (49c0065, 2e59b7d).

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#304-318] — Story 2.2 ACs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#197-203] — FR-13 Ansible Scaffold
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#142-167] — plan §6 `src/provisioning/ansible/` tree
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#56] — plan §3 collections resolved via `ansible-galaxy` at bootstrap start
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#44] — distro differences isolated to `group_vars`
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#47] — external collections declared in `ansible/requirements.yml`
- [Source: src/provisioning/src/provisioning/adapters/ansible_fact_reader.py#29-33] — `_OS_FAMILY_TO_GROUP_VARS` mapping (arch / debian-family)
- [Source: src/provisioning/src/provisioning/domain/enums.py#8-17] — `Distro` values MUST match group_vars filenames
- [Source: src/provisioning/src/provisioning/cli/main.py#68-86] — `_ANSIBLE_ROOT` + `build_deps()` executor construction
- [Source: src/provisioning/src/provisioning/application/use_cases.py#38-48] — `_seam_extra_vars` (`install_dir`, `os_family`)
- [Source: dotfiles/provisioning/packages.yaml] — logical package set group_vars must cover
- [Source: src/provisioning/.venv/lib/python3.12/site-packages/ansible/config/manager.py#253-313] — `find_ini_config_file` order (ENV > CWD > HOME > /etc)
- [Source: src/provisioning/.venv/lib/python3.12/site-packages/ansible/playbook/role/definition.py#164-188] — role search paths (playbook-basedir `roles/` then configured `roles_path`)
- [Source: _bmad-output/implementation-artifacts/2-1-declarative-manifests.md] — previous story (group_vars consumption contract)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- 2026-08-09: Resolved collection versions via Galaxy API (requires_ansible checked against installed ansible-core 2.21.2): `community.general 13.2.0` (>=2.18.0), `ansible.posix 2.2.2` (>=2.16.0), `kewlfft.aur 0.13.0` (>=2.9.10).
- 2026-08-09: Verified package names live — `pacman -Si` for arch set (ttf-jetbrains-mono-nerd, noto-fonts, noto-fonts-cjk, ttf-nerd-fonts-symbols), Debian archive API for debian-family set (fonts-noto, fonts-noto-cjk, fonts-noto-color-emoji).
- 2026-08-09: Smoke check `ANSIBLE_CONFIG=ansible/ansible.cfg uv run ansible-config dump --only-changed` confirmed `DEFAULT_HOST_LIST` and `DEFAULT_ROLES_PATH` resolve under `src/provisioning/ansible/` — relative paths honored from the cfg file's own directory.
- 2026-08-09: Working tree was dirty (story-creation artifacts) at activation; user chose to commit them (`chore: create story 2.2 ansible scaffold`, eb8898f). Story `baseline_commit` 2e59b7d preserved.

### Completion Notes List

- ✅ Story 2.2 complete: authored the Ansible project scaffold under `src/provisioning/ansible/` (inventory, requirements.yml, ansible.cfg, group_vars/{all,arch,debian-family}.yml) as data-only files — no `.py` under ansible/.
- ✅ Wired `ANSIBLE_CONFIG` end-to-end: added `config_file` param + `_ansible_env()` helper to `AnsibleExecutor`, forwarded `env` to `subprocess.run`; `build_deps()` passes `config_file=_ANSIBLE_ROOT / "ansible.cfg"`. Injected-runner contract (`Callable[[list[str]], CompletedProcess]`) unchanged — all existing executor tests pass unmodified.
- ✅ Distro isolation per AC 5: distro differences live only in `group_vars/{arch,debian-family}.yml`; localhost is NOT statically grouped; filenames match the `IFactReader.os_family()` seam exactly.
- ✅ 14 new tests (10 scaffold real-file + 4 executor). Full suite 208 passed (194 baseline + 14). ruff check/format + mypy strict + layering guard (37 tests) all green.
- ✅ Verified collection versions pinned in requirements.yml compatible with ansible-core 2.21.2.

### File List
- `src/provisioning/ansible/inventory/localhost.yaml` (new)
- `src/provisioning/ansible/requirements.yml` (new)
- `src/provisioning/ansible/ansible.cfg` (new)
- `src/provisioning/ansible/group_vars/all.yml` (new)
- `src/provisioning/ansible/group_vars/arch.yml` (new)
- `src/provisioning/ansible/group_vars/debian-family.yml` (new)
- `src/provisioning/src/provisioning/adapters/ansible_executor.py` (modified: `os` import, `_ansible_env`, `config_file` param, env forwarding)
- `src/provisioning/src/provisioning/cli/main.py` (modified: `build_deps()` passes `config_file`)
- `src/provisioning/tests/unit/test_ansible_scaffold.py` (new)
- `src/provisioning/tests/unit/adapters/test_ansible_executor.py` (modified: `_ansible_env` + config_file regression guard)

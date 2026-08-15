---
baseline_commit: 0ff2a17
---

# Story 3.2: Playbook Dry-Run Integration Tests

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-15: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-25).
- 2026-08-15: Implemented — `tests/integration/` (dry-run suite + container apply+verify + in-container AC-4 proof), markers added to `pyproject.toml`. Full suite green (466 passed / 4 skipped / 1 xfailed; baseline 458). Surfaced a genuine pre-existing packages-chain defect (filed in deferred-work.md): `ansible/group_vars/` is undiscoverable → `'packages' is undefined` on every packages/aggregate invocation; also a root-container become_user temp-ownership abort under `--check`. Become-gated dry-runs skip loudly on the dev host (no passwordless sudo); the in-container AC-4 proof is recorded as xfail until the defect is fixed.

## Story

As an operator,
I want integration tests that dry-run every playbook,
So that the whole provisioning surface is exercised without mutating the host.

## Acceptance Criteria

1. The integration test suite lives under `src/provisioning/tests/integration/` (FR-25, PRD §4.7).
2. `test_ansible_dryrun.py` and related tests run **every** playbook with real `ansible-playbook --check` and assert each completes cleanly (exit 0, recap failed=0), reporting the would-be plan without applying it (AC 3, FR-25).
3. A separate apply+verify test, run **on a disposable/container target**, asserts the ten done-criteria hold after a real `apply` followed by a real `verify` — **NOT** after `--check`, which cannot leave state behind (AC 4, FR-25 consequence, review-rubric high finding on FR-25's original wording).
4. The AUR `yay` self-bootstrap task (`makepkg -si --noconfirm`, packages role) **never builds under `--check`** — asserted, no mutation in dry-run mode (AC 5, hardening: dry-run must be dry, SPEC §Constraint, PRD §4.7 consequence).
5. The tests invoke **real `ansible-playbook --check`, not fakes** (AC 6, FR-25). No mocked executor, no `subprocess.run` stub.

## Tasks / Subtasks

- [x] Register the integration marker in `src/provisioning/pyproject.toml` `[tool.pytest.ini_options] markers` (mirror `oci-runtime/pyproject.toml`) (AC: 1)
  - [x] `integration = "test requires a real ansible-playbook + collections (FR-25)"`
  - [x] `container_target = "test requires podman/docker to provision a disposable target (FR-25 apply+verify)"`

- [x] Create `src/provisioning/tests/integration/__init__.py` (AC: 1)
  - [x] Empty or docstring-only package marker, like `src/shared/oci-runtime/tests/integration/__init__.py`

- [x] Implement `src/provisioning/tests/integration/test_ansible_dryrun.py` (AC: 1-6)
  - [x] Duplicated `_find_ansible_dir()` walk-up helper (repo convention — anchored on `pyproject.toml`, no shared conftest) (AC: 1)
  - [x] `_run_check(playbook, extra_vars, env)` helper that shells real `ansible-playbook -i <inventory> --check -e install_dir=... -e os_family=... <playbook>` with `ANSIBLE_CONFIG` set to the scaffold `ansible.cfg`; capture stdout/stderr; return CompletedProcess (AC: 2, 6)
  - [x] Detect the host's `os_family` seam ONCE: `ansible -m setup localhost` → `ansible_os_family` (Archlinux→`arch`, Debian→`debian-family`); fail loud if it is neither (a dry-run with the wrong seam aborts at packages.yaml's group_by guard). Mirror the parsing pattern in the existing `AnsibleFactReader` adapter (`src/provisioning/src/provisioning/adapters/ansible_fact_reader.py`) rather than re-deriving it (AC: 2, seam contract, mirror-and-adapt)
  - [x] Parametrize over the NINE per-role playbooks (`assets, cli-tools, compositor-configs, config-copies, default-palette, filesystem, packages, settings, verify`) + the aggregate `bootstrap.yaml`; assert exit 0 AND recap contains `failed=0` AND `unreachable=0` for each (AC: 2)
  - [x] Pass a scratch `install_dir` (tempfile) — never the host's real spine root; assert the temp dir was NOT created by the `--check` (strongest local no-mutation proof) (AC: 2, 4)
  - [x] **become gate for packages.yaml + bootstrap.yaml:** these contain a `become: true` play; running them `--check` requires passwordless sudo or root. Gate: `os.geteuid() == 0` OR `sudo -n true` succeeds. When the gate is NOT met, `pytest.skip` those cases with a LOUD reason naming the exact prerequisite (passwordless sudo/root for the become play) — a silent skip would report green with zero coverage (Story 3.1 confirmation-CR discipline). The OTHER eight playbooks are user-scoped (no become) and must ALWAYS run (AC: 2)
  - [x] **yay-never-builds assertion (AC 4):** run `packages.yaml --check` in a context where become is satisfied (root container — see apply+verify design — or a host with passwordless sudo) and assert:
    - the `Build and install yay-bin via makepkg` task NEVER executes: because it carries `creates: /usr/bin/yay`, under `--check` it reports `changed` (would-change) when yay is absent and `ok` when present — **it MUST NOT appear as a real execution** (verified empirically in a disposable Arch container, 2026-08-15: `creates`-commands report would-change without running). The correct assertion is the mutation-free proof below, NOT a `skipped` recap (a `creates:` command does NOT report `skipped` — see task bullet on the become gate and the Dev Notes section)
    - `command -v yay` still fails (or `/usr/bin/yay` absent) immediately after the `--check` run — the mutation-free proof that makepkg never built
    - exit 0
    - When no root-capable context exists on the host, this specific assertion is skipped loudly WITH the same reason (AC 4 is the acceptance gate — record in the story whether it was verified in-container vs skipped on the dev host)
  - [x] Assert the recap reports the would-be plan (the `--check` runs print per-task changed/ok/skipped — do not assert a specific changed count, but DO assert the recap block exists and `failed=0`) (AC: 2)
  - [x] Treat the known `INJECT_FACTS_AS_VARS` deprecation warnings (ansible-core ≥2.21 prints them for top-level `ansible_os_family` references) as NON-fatal: assert only `failed=0`/`unreachable=0`; never assert stderr is empty (AC: 2)

- [x] Implement the apply+verify test on a disposable container target (AC: 3, 4)
  - [x] `test_apply_verify_container.py` (or folded into `test_ansible_dryrun.py` as a separate class — pick the clearest split) marked `@pytest.mark.container_target` and `@pytest.mark.integration` (AC: 3)
  - [x] Probe for a usable container engine first (podman preferred → docker → skip loudly if neither; mirror the cli_tools/default_palette engine-probe discipline). On this dev host podman IS available and `podman info` succeeds (verified 2026-08-15) (AC: 3)
  - [x] Start a DISPOSABLE Arch container (e.g. `podman run --rm -d` an `archlinux:latest` image — pacman/network inside the container satisfy the packages role; running as root inside makes `become: true` a no-op with no sudo password needed) with the repo bind-mounted read-only and a scratch `$HOME`/`XDG_DATA_HOME`/`install_dir` (AC: 3)
  - [x] Inside the container, run the REAL aggregate via `uv run --directory <repo>/src/provisioning dotfiles-provision bootstrap` (uv syncs a CONTAINER-LOCAL env from `uv.lock`) followed by `dotfiles-provision verify` (real check, never `--check`) — do NOT exec the host-built `.venv/bin/*` shebangs (they point at host python paths that do not exist in the container; see Dev Notes "VENV SHEBANG TRAP") (AC: 3, CAP-3)
  - [x] Assert verify exits 0 → the ten done-criteria hold (install dir subtree, system binaries, CLI tools, assets, settings parse, default palette, compositor configs, filesystem structure, real-dir config copies, §12 preconditions) (AC: 3, plan §8, verify role task comment #8-27)
  - [x] Clean up the container unconditionally (try/finally — `--rm` alone is not enough for `podman exec` flows) (AC: 3)
  - [x] **Honest environment gate:** this is the heaviest test (real package installs, csg container-mode chain needs a NESTED container engine for `cli_tools`/`default_palette` — podman-in-podman). If the full chain cannot be provisioned on a given host (no usable engine, no network, nested-engine limitation), the test MUST `pytest.skip` with a loud, specific reason — never report green while skipping silently, and never fake-pass. Document in the story which host-classes verified it (AC: 3)

- [x] Wire the suite into the gates (AC: 1, repo test discipline)
  - [x] `uv run pytest` full suite stays green (baseline 458; the new integration tests must not break collection on hosts without ansible-playbook — the dry-run file must `pytest.skip` loudly if `ansible-playbook` is absent via `shutil.which`, mirroring `test_bootstrap_playbook.py`; the container_target tests must skip loudly without a usable engine)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` clean (new files must be ruff-clean)
  - [x] `uv run mypy src tests` — new test files mypy-clean (strict; do NOT chase the 10 pre-existing baseline errors in test_default_palette_role.py/test_cli_tools_role.py)
  - [x] `python tests/architecture/test_layering.py` still exits 0 (integration tests may import `subprocess`/`os`/`pathlib` freely — layering restricts `src/provisioning/src/**` domain/adapters only, NOT tests; verify no cross-package forbidden import is introduced)
  - [x] `git status --short` shows ONLY the new integration files, the pyproject marker change, and the story/status artifacts

## Dev Notes

### Scope — what Story 3.2 is and is not

**IS:** the FR-25 integration test suite under `src/provisioning/tests/integration/` — real `ansible-playbook --check` dry-runs of every playbook (AC 2), a yay-never-builds-under-`--check` assertion (AC 4), and an apply+verify test on a disposable container target (AC 3). All tests invoke real Ansible, never fakes (AC 6). Plus the marker registration in `pyproject.toml`.

**IS NOT:** the settings-parity / default-palette / spine-chain / `--templates-dir` tests — those are **Story 3.3** (FR-25's second half; epics Story 3.3 ACs 1-5, deferred-work notes). Do NOT implement `csg info --config`, `weg info --config`, `itr list`, `csg generate -f conf` contract checks, or the Phase-2 invocation-contract test here. Do NOT modify any playbook, role, vars file, manifest, `group_vars`, `bootstrap.sh`, `scripts/`, or any `src/provisioning/src/**` Python. This story is test-authoring only. If a dry-run surfaces a genuine role defect, file it in `_bmad-output/implementation-artifacts/deferred-work.md` — do NOT silently patch a DONE role (Story 2.x review discipline).

### The playbook inventory (what "every playbook" means)

The ten playbooks under `src/provisioning/ansible/playbooks/`:

1. `packages.yaml` — TWO plays; the second (`hosts: "{{ os_family }}"`, `become: true`) is the ONLY become play in the chain. Contains the guarded `makepkg -si --noconfirm` yay self-bootstrap (command module + `creates: /usr/bin/yay`, gated on `packages_use_aur`). Under `--check`, command/shell modules are skipped in ansible-core 2.20.3/2.21.x → makepkg reports `skipped`, never runs. The FIRST play asserts the `os_family` seam extra-var matches the host `ansible_os_family` (Archlinux/Debian) and group_by's on it.
2. `cli-tools.yaml` — user-scoped, no become. `uv tool install` loop uses `creates:`; the engine probe + `csg install` build are `when: not ansible_check_mode`-gated.
3. `filesystem.yaml` — user-scoped; pure `file`/dir creation (check-mode safe, reports would-change). VERIFIED `--check` clean on this host (2026-08-15).
4. `assets.yaml` — user-scoped; unarchive/copy/`weg dump-effects` command.
5. `default-palette.yaml` — user-scoped; generate + engine tasks all `when: not ansible_check_mode`-gated.
6. `compositor-configs.yaml` — user-scoped; copy/template.
7. `config-copies.yaml` — user-scoped; copy of repo `dotfiles/config/*` → `~/.config/*`.
8. `settings.yaml` — user-scoped; Jinja `template` (full check-mode support).
9. `verify.yaml` — user-scoped; existence/isdir asserts gated `when: not ansible_check_mode`; command/shell gates skipped under `--check`.
10. `bootstrap.yaml` — imports-only aggregate of the nine in dependency order (packages → cli-tools → filesystem → assets → default-palette → compositor-configs → config-copies → settings → verify). Its `--check` is the "whole surface" dry-run; it inherits packages.yaml's become requirement.

### The two seam extra-vars are REQUIRED for every direct invocation

- `install_dir` — absolute path; the roles derive the whole spine from it and several assert it as a non-empty absolute path (filesystem/assets/default_palette/settings/verify). Use a scratch tempfile path in tests; NEVER the host's real `$XDG_DATA_HOME/dotfiles/`.
- `os_family` — `arch` or `debian-family`. packages.yaml's group_by guard hard-fails if it doesn't match the host fact. On this dev host it is `arch` (Arch/EndeavourOS). The dry-run suite must detect it via `ansible -m setup` (or `ansible_fact_reader` semantics) and pass the matched value.

`ANSIBLE_CONFIG` must point at `src/provisioning/ansible/ansible.cfg` (inventory + roles_path); the adapter's `_ansible_env` pattern is the reference. `-i <inventory/localhost.yaml>` is also safe to pass explicitly (inventory uses `ansible_connection: local` + `ansible_playbook_python`).

### Why become/root is the crux of the dry-run design

`packages.yaml` (and therefore `bootstrap.yaml`) runs a `become: true` play. On this dev host `sudo` requires a password (`sudo -n true` fails — verified 2026-08-15), so a plain `--check` of packages.yaml dies at "Premature end of stream waiting for become success / sudo: a password is required" (verified empirically). Consequences for the test design:

- The eight user-scoped playbooks run `--check` cleanly as the normal user on this host (filesystem.yaml verified). They are the bulk of the dry-run suite and MUST run unconditionally when `ansible-playbook` is present.
- `packages.yaml` and `bootstrap.yaml` `--check` need root or passwordless sudo. Gate them; skip loudly (never silently) when the gate is unmet.
- The AC-4 yay assertion (never builds under `--check`) is best proven in the **disposable root Arch container** (become is a root→root no-op, no sudo password, and the host is never touched). This doubles as the apply+verify target's environment.

### The "dry-run must be dry" assertion mechanics

- `makepkg` task: `ansible.builtin.command: makepkg -si --noconfirm` with `creates: /usr/bin/yay`, `when: packages_use_aur | bool`. **Verified empirically (2026-08-15, disposable Arch container):** under `--check`, a bare command reports `skipped`, but a command WITH `creates:` reports `changed` (would-change) when the creates path is absent and `ok` when present — and in BOTH cases it is NOT executed. So the makepkg task reports `changed` on a fresh target under `--check`; the "never builds" proof is that `/usr/bin/yay` is still absent afterward, NOT a `skipped` recap. Do NOT assert the makepkg task is `skipped` — that would fail on the very fresh-machine case the AC targets.
- `kewlfft.aur.aur` (v0.13.0, pinned) declares `supports_check_mode=True` (module source, line 418) — under `--check` it reports without executing.
- The strongest no-mutation assertion: after the `--check` run, `command -v yay` still fails AND the scratch `install_dir` does not exist. Assert both. Do NOT rely on recap changed-counts alone (they legitimately report would-change).

### Container-target design for apply+verify

- Engine: podman preferred, then docker (mirror cli_tools/default_palette probe + `cli_tools_container_engine_override`/`default_palette_container_engine_override` escape hatches). On this host podman is available and usable (`podman info` OK — verified).
- Image: `archlinux:latest` (or the currently-pinned Arch base) — pacman inside satisfies the packages role; running as root makes the become play trivial.
- Repo mount: bind-mount the repo read-only; run the provisioner from the repo's `src/provisioning`. **VENV SHEBANG TRAP:** the host's `src/provisioning/.venv/bin/ansible-playbook`/`dotfiles-provision` shebangs point at HOST python paths (`#!/home/inumaki/.../.venv/bin/python3`) that do NOT exist inside the container — do NOT exec the mounted `.venv/bin/*` binaries directly. Instead install `uv` (+ a managed Python) inside the container and run `uv run --directory <repo>/src/provisioning dotfiles-provision bootstrap` / `verify` — uv syncs the env from `uv.lock` into a CONTAINER-LOCAL `.venv` and resolves collections via `~/.ansible` inside the container (the pinned `requirements.yml` versions are verified compatible with ansible-core 2.21.2). The repo read-only mount is then safe.
- HOME/XDG/install_dir: point at scratch paths inside the container so verify's "machine, not repo" asserts target the container's layout, not the host.
- Nested-engine reality: `cli_tools` runs `csg install` (builds `csg-<backend>-<engine>` image) and `default_palette` runs `csg generate` in container mode — INSIDE the target container these need a working container engine (podman-in-podman or docker-in-docker). This is the single biggest feasibility risk for the full-chain run. If it cannot be satisfied on a given host, skip loudly with the exact reason; on hosts where it can, this test is the full CAP-3/CAP-4 proof.
- Cleanup: `try/finally` podman rm regardless of pass/fail.

### Marker/config wiring

`src/provisioning/pyproject.toml` currently has NO `markers` block and NO `--strict-markers` addopts. Add the `integration` + `container_target` markers (mirror `src/shared/oci-runtime/pyproject.toml` markers block) so `-m` filtering works. `testpaths = ["tests"]` already collects `tests/integration/`. Do NOT add `--strict-markers` if it would break other files' loose markers — check first.

### Repo conventions to mirror (do not reinvent)

- `_find_ansible_dir()` walk-up helper duplicated per test file (anchored on `pyproject.toml` so a sibling project's `ansible/` is never matched) — see `test_bootstrap_playbook.py:12-25`.
- Real-ansible invocation pattern with `ANSIBLE_CONFIG` env + `-e` extra-vars — see `test_verify_role.py` `TestVerifyRuntime` (`shutil.which("ansible-playbook")` skip-if-absent, `_test_env`).
- Loud-skip discipline (Story 3.1 confirmation CR): missing prerequisites produce a `pytest.skip` with a specific reason naming the prerequisite — never a bare skip that reports green with zero coverage.
- No shared conftest for the provisioning tests; keep helpers duplicated per file.

## Project Structure Notes

- `src/provisioning/tests/integration/__init__.py` — NEW package marker.
- `src/provisioning/tests/integration/test_ansible_dryrun.py` — NEW; the AC-2 dry-run suite + AC-4 yay assertion + AC-3 apply+verify (or split apply+verify into `test_apply_verify_container.py` — pick the clearest).
- `src/provisioning/pyproject.toml` — ADD `markers` block only.
- CONSUMED, NOT MODIFIED: `src/provisioning/ansible/**` (playbooks, roles, group_vars, inventory, ansible.cfg, requirements.yml), `src/provisioning/src/**`, `scripts/bootstrap.sh`, `dotfiles/**`.
- No new dependencies. All ansible-core/collections already resolved in the provisioning `.venv`.

## Testing Requirements

- Full gates: `uv run pytest` (baseline 458 collected at HEAD `0ff2a17`), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` (new files clean; do NOT chase the 10 pre-existing baseline errors), `python tests/architecture/test_layering.py`.
- The integration suite must not break the default full-suite run on hosts WITHOUT ansible-playbook: dry-run file skips loudly via `shutil.which("ansible-playbook")` when absent (mirror `test_bootstrap_playbook.py:106-115`).
- container_target tests skip loudly without a usable engine; never fake-pass.
- Verified on the dev host (2026-08-15): `ansible-playbook` present (ansible-core 2.21.2 via provisioning `.venv`), collections installed (`community.general 13.2.0`, `ansible.posix 2.2.2`, `kewlfft.aur 0.13.0`), host = Arch (`os_family=arch`), podman usable, sudo needs a password.

## Previous Story Intelligence

### Story 3.1 — Fresh-Machine Bootstrap Script (DONE 2026-08-15, immediate predecessor)
- Delivered `scripts/bootstrap.sh` (uv preseed → collections loud-abort → aggregate bootstrap → trailing real `verify` gate) + `test_bootstrap_script.py` (458-suite green after confirmation CR). This story does NOT touch it.
- Established the loud-skip discipline (`_require_bash()` fails loud; runtime tests never silently skip) — mirror it for the integration env gates.
- Established the container-engine gate pattern (podman→docker→fail-loud, `engine info` usability probe, no `BOOTSTRAP_CONTAINER_ENGINE` override — the roles' `*_container_engine_override` vars are the sanctioned escape hatches). The apply+verify container test must NOT re-add a script-level engine override.
- Deferred AC 5 (dual-distro) to "Story 3.2/3.3 integration territory" — the container-target apply+verify test is the vehicle, not the local dry-run suite. [Source: 3-1 story, deferred-work.md#230]

### Story 2.12 — Verify Role & Aggregate Bootstrap Playbook (DONE 2026-08-13)
- `verify.yaml` is the LAST import of `bootstrap.yaml`; its asserts are `when: not ansible_check_mode`-gated so the aggregate `--check` stays clean; the authoritative gate is a REAL `verify` run (check=False). The apply+verify test asserts that exact real-verify contract. [Source: verify role tasks comment #33-42, 2-12 story]
- The verify role enumerates the ten done-criteria against PROVISIONED locations (machine, not repo). [Source: roles/verify/tasks/main.yml#8-27]

### Story 2.3 — Packages Role (DONE 2026-08-09)
- The `makepkg -si` yay self-bootstrap task is the AC-4 "dry-run must be dry" subject. Its design (command + `creates: /usr/bin/yay`, no `yay_check.rc` gate) means under `--check` it reports would-change (`changed` when yay absent) WITHOUT building — the "never builds" proof is `/usr/bin/yay` absent afterward, not a `skipped` recap. [Source: packages role tasks #74-82; test_packages_role.py#174-186]

## Git Intelligence

- Baseline `0ff2a17` (`fix: auto-commit code review findings`), working tree CLEAN at story creation. 458 tests collected.
- Commit-title pattern across the chain: `chore: create story X.Y …` → `feat: implement story X.Y …` → `fix: apply code review findings …`. Each story = one deliverable + test file(s) + story/status artifacts.
- This story adds ONLY: the `tests/integration/` files, the `pyproject.toml` markers block, and the story/status artifacts. It must NOT modify any existing ansible/python/dotfiles file.

## Latest Tech Information

- **ansible-core 2.21.2** (provisioning `.venv`; pyproject requires `>=2.16`): under `--check`, bare command/shell tasks report `skipped`; tasks with `creates:` report would-change (`changed`/`ok`) WITHOUT executing. **Both behaviors verified empirically in a disposable Arch container (2026-08-15).** `ansible-galaxy`/`ansible` ship with it.
- **Collections (pinned, installed):** `community.general 13.2.0`, `ansible.posix 2.2.2`, `kewlfft.aur 0.13.0` → `~/.ansible/collections/ansible_collections/`. `kewlfft.aur.aur` declares `supports_check_mode=True` (module source line 418) — check-mode-safe by construction.
- **Deprecation notice:** ansible-core ≥2.21 prints `INJECT_FACTS_AS_VARS` deprecation warnings for top-level `ansible_os_family` references (seen in the verified `--check` run). Treat as warnings; never assert clean stderr. Removal targeted at ansible-core 2.24 — NOT this story's concern.
- **`--check` + become:** a `become: true` play still attempts sudo under `--check` (fact-gathering runs as the become target); a password-less sudo fails loudly — verified on this host ("sudo: a password is required"). Hence the root-container strategy for the packages/aggregate cases.
- **Podman usable on the dev host** (`podman info` OK, 2026-08-15) — the apply+verify container-target path is exercisable here; docker daemon also reachable.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#503-516] — Story 3.2 ACs (integration suite under tests/integration/, test_ansible_dryrun.py, every playbook --check clean, apply+verify on disposable target NOT --check, yay never builds under --check, real not fakes)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#46] — FR-25 (dry-run of every playbook + settings-parity + default-palette; the settings-parity/default-palette half is Story 3.3)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#138-140] — hardening notes: dry-run must be dry; parse ≠ works (the parse-≠-works half is Story 3.3)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#302-316] — PRD §4.7 Integration Tests / FR-25 consequences (real ansible-playbook --check, not fakes; yay never builds under --check; apply+verify on disposable/container target, never a real host)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/review-rubric.md#27] — the high finding that killed "verify after dry-run" (infeasible: --check leaves no state) → the corrected apply+verify-on-disposable-target contract
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/review-rubric.md#41] — FR-25 drops the Phase-2 `--templates-dir` assertion → that one is Story 3.3 scope (this story does NOT add it)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#287] — plan §11 step 11 (integration tests: --check runs of every playbook; verify after dry-run — superseded by the corrected apply+verify wording in the epics/PRD)
- [Source: src/provisioning/ansible/playbooks/bootstrap.yaml] — the aggregate (nine imports, packages→verify order); its `--check` is the whole-surface dry-run
- [Source: src/provisioning/ansible/roles/packages/tasks/main.yml#74-82] — the guarded `makepkg -si` yay self-bootstrap (the AC-4 subject)
- [Source: src/provisioning/ansible/roles/verify/tasks/main.yml#8-27,33-42] — the ten done-criteria + check-gating rationale
- [Source: src/provisioning/ansible/roles/cli_tools/tasks/main.yml#77-100] and [Source: src/provisioning/ansible/roles/default_palette/tasks/main.yml#112-155] — engine probe + `*_container_engine_override` escape-hatch pattern to mirror in the container test
- [Source: src/provisioning/ansible/ansible.cfg] — inventory + roles_path; `ANSIBLE_CONFIG` must point here for direct invocations
- [Source: src/provisioning/tests/unit/test_bootstrap_playbook.py#12-25,106-115] — `_find_ansible_dir()` helper + ansible-playbook skip-if-absent pattern to mirror
- [Source: src/provisioning/tests/unit/test_verify_role.py#788-864] — real ansible-playbook runtime test pattern (env + extra-vars + skip) to mirror
- [Source: src/shared/oci-runtime/pyproject.toml#27-33] — markers block format to mirror
- [Source: src/provisioning/pyproject.toml] — pytest testpaths ["tests"], ruff, mypy strict config; the file to add markers to
- [Source: https://docs.ansible.com/ansible/latest/playbook_guide/playbooks_checkmode.html] — check mode semantics (modules supporting check mode report would-change; others skip) — verified 2026-08-15

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Baseline `0ff2a17`, working tree CLEAN. 458 tests collected at baseline.
- Verified 2026-08-15 on this host: `packages.yaml --check` fails at become ("sudo: a password is required") — sudo needs a password; all EIGHT user-scoped playbooks run `--check` clean with `failed=0` — filesystem (ok=5 changed=1), verify (ok=11 changed=0 skipped=20), settings (ok=4 changed=2), compositor-configs (ok=4 changed=1 skipped=3), cli-tools (ok=3 changed=1 skipped=6), assets (ok=4 changed=1 skipped=9), default-palette (ok=4 changed=1 skipped=9), config-copies (ok=8 changed=1 skipped=2); the scratch `install_dir` was NOT created (no-mutation proof); deprecation warnings (INJECT_FACTS_AS_VARS) appear in `--check` output — non-fatal.
- Verified 2026-08-15 `ansible -m setup localhost` reports `ansible_os_family: Archlinux` on this host → the seam detection maps to `os_family=arch`.
- Verified 2026-08-15 in a disposable `archlinux:latest` container: bare command reports `skipped` under `--check`; command with `creates:` reports `changed` (would-change) and does NOT execute — the makepkg task (has `creates: /usr/bin/yay`) therefore reports `changed`, NOT `skipped`, on a fresh target. The AC-4 assertion must key on `/usr/bin/yay` being absent afterward, not on a `skipped` recap.
- Existing provisioning tests use NO pytest custom markers (only `pytest.mark.parametrize`) — adding the `integration`/`container_target` markers to `pyproject.toml` conflicts with nothing.
- podman usable (`podman info` OK); docker daemon reachable; host = Arch/EndeavourOS → `os_family=arch`.
- The FR-25 "verify after dry-run" wording was corrected (review-rubric high finding) to apply+verify-on-disposable-target — implement the corrected contract, NOT the original plan §11 wording.
- **IMPL 2026-08-15:** local dry-run suite passes 8/10 playbooks (the two become-gated — packages, bootstrap — skip loudly; no passwordless sudo). Yay test skips loudly (no root context + yay already installed on the host — the fresh-root-container run is authoritative).
- **IMPL 2026-08-15 (container):** disposable `archlinux:latest` container works end-to-end: podman start + read-only repo mount → pacman -Syu + uv (via pacman) → `ansible-galaxy collection install -r requirements.yml` through a CONTAINER-LOCAL uv env (`UV_PROJECT_ENVIRONMENT=/opt/provision-venv`, the VENV SHEBANG TRAP workaround). AC-3 apply+verify skips loudly (no NESTED engine inside the target for the csg container-mode chain — documented honest gate). AC-4 in-container proof XFAILS: packages.yaml --check aborts at the packages role's "Assemble package list" with `'packages' is undefined`.
- **IMPL 2026-08-15 (defect surfaced):** `ansible/group_vars/{all,arch,debian-family}.yml` are NOT discoverable — ansible's group_vars discovery only searches `group_vars/` beside the inventory dir (`ansible/inventory/`) or playbook dir (`ansible/playbooks/`), never `ansible/group_vars/`. Confirmed on the REAL production path: `dotfiles-provision plan` (== `bootstrap --check`) in the container fails identically at "packages : Assemble package list". The dev host never hit it: packages.yaml is become-gated, so host `--check` died at the sudo prompt BEFORE task-args resolution, and Story 2.3's tests are structural. Verified the fix hypothesis in-container: with group_vars adjacent to the inventory/playbooks (or inventory sourced as the `ansible/` directory), packages loads and the play proceeds (ok=10 changed=5) until a SECOND, separate abort: the `Build and install yay-bin via makepkg` task (become_user: aur_builder) hits ansible's temp-file ownership guard ("Failed to change ownership of the temporary files ... Unprivileged become user would be unable to read the file") when `--check` runs as root. BOTH findings filed in deferred-work.md (Story 3.2 section). Per the story's test-authoring-only discipline, NO playbook/role/vars file was modified.

### Completion Notes List

- 2026-08-15: Story 3.2 created and marked ready-for-dev. `--check` behavior verified empirically (bare command → skipped; `creates:` command → would-change, never executed) so the AC-4 yay assertion keys on the mutation-free proof, not a `skipped` recap.
- 2026-08-15: Story implemented and marked review. Delivered `tests/integration/` (13 new tests: 10 dry-run cases + 2 container tests + package marker files) and the `pyproject.toml` markers block. Full suite 466 passed / 4 skipped / 1 xfailed (baseline 458). AC-2 verified for all 8 user-scoped playbooks on the dev host (clean `--check`, `failed=0`, scratch spine never created); packages/bootstrap skip loudly (become gate). AC-3 container apply+verify skips loudly on this host (no nested engine inside the disposable target). AC-4 (yay never builds under `--check`): host-side skips loudly (no root context, yay pre-installed); the in-container proof XFAILS — a genuine pre-existing packages-chain defect surfaced by this suite (filed in deferred-work.md): `ansible/group_vars/` is undiscoverable → `'packages' is undefined` (confirmed on the real `dotfiles-provision plan` path), plus a root-container become_user temp-ownership abort. Per the test-authoring-only scope, no playbook/role/vars/manifest file was modified.

### File List

- `src/provisioning/tests/integration/__init__.py` (NEW)
- `src/provisioning/tests/integration/test_ansible_dryrun.py` (NEW)
- `src/provisioning/tests/integration/test_apply_verify_container.py` (NEW)
- `src/provisioning/pyproject.toml` (markers block ADDED)
- `_bmad-output/implementation-artifacts/deferred-work.md` (Story 3.2 packages-chain defect entries ADDED)
- `_bmad-output/implementation-artifacts/3-2-playbook-dry-run-integration-tests.md` (this story — status/tasks/record updated)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story → review)

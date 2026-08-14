---
baseline_commit: e29e603
---

# Story 3.1: Fresh-Machine Bootstrap Script

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-13: Story created — ultimate context engine analysis completed; comprehensive developer guide created (FR-5, NFR-9, CAP-4).
- 2026-08-13: Container-engine check LOCKED as Option A (fail-loud on missing podman/docker, no distro install in script) — product owner confirmation.
- 2026-08-13: Story 3.1 implemented — `scripts/bootstrap.sh` (uv preseed → collections loud-abort → aggregate bootstrap → trailing verify hard gate, early container-engine check) + `test_bootstrap_script.py` (16 tests incl. runtime smoke); full suite 453 green; status → review.

## Story

As an operator,
I want `scripts/bootstrap.sh` that pre-seeds Python+uv and runs the provisioner,
So that any fresh machine can be fully provisioned in one command.

## Acceptance Criteria

1. `scripts/bootstrap.sh` pre-seeds Python+uv if absent (no pre-install step beyond a shell and git) (AC 1, FR-5, plan §3 "Bootstrap")
2. `ansible-galaxy` collection resolution (`ansible/requirements.yml`) happens at bootstrap start, and a resolution failure (e.g. missing network) aborts with a loud, helpful error instead of proceeding with missing modules (AC 2, SPEC.md#47, plan §3 "Ansible install")
3. `uv run --directory ./src/provisioning dotfiles-provision bootstrap` executes the aggregate playbook end-to-end (AC 3, FR-4, plan §3 "Bootstrap")
4. The run completes with `dotfiles-provision verify` green against all ten done-criteria (AC 4, CAP-3, plan §8)
5. The script works on both Arch and Debian-family targets (AC 5, FR-5, NFR-9)
6. Distro differences are isolated to `group_vars` — NO distro branching in `bootstrap.sh` or Python (AC 5 hardening, NFR-3, plan §3)

## Tasks / Subtasks

- [x] Create `scripts/bootstrap.sh` (AC: 1-5)
  - [x] `#!/usr/bin/env bash` + `set -euo pipefail` (fail-fast on any error — a partially-provisioned machine is worse than a failed bootstrap)
  - [x] Derive `ROOT` from the script's own location — `ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"` — NOT `git rev-parse --show-toplevel` (the script must work even if the repo checkout isn't a git worktree or the command fails; `git clone <repo> && ./scripts/bootstrap.sh` makes the script location authoritative)
  - [x] **uv preseed (AC 1):** if `command -v uv` fails, install via the official standalone installer: `curl -LsSf https://astral.sh/uv/install.sh | sh` (fall back to `wget -qO- ... | sh` if `curl` is absent — the standalone installer supports both); then add `~/.local/bin` to `PATH` for the rest of the script (`export PATH="$HOME/.local/bin:$PATH"` — the installer places `uv`/`uvx` there; also the `cli_tools` role's `uv tool install` binaries land here). Keep the install failure loud (`set -e` aborts; print a helpful message with the failing step name)
  - [x] **Python preseed (AC 1):** the project's `requires-python = ">=3.12"` is satisfied by `uv run` automatically (uv downloads a managed Python if no compatible interpreter exists). Do NOT hand-roll a `python3` detection/install — uv owns Python provisioning. Optionally emit an informational line stating uv will manage the interpreter
  - [x] **Collection resolution (AC 2):** BEFORE running the provisioner, run `uv run --directory "$ROOT/src/provisioning" ansible-galaxy collection install -r "$ROOT/src/provisioning/ansible/requirements.yml"` — the first `uv run` syncs the project env from `uv.lock` (installing `ansible-core`), making `ansible-galaxy` available; collections install to the default user path `~/.ansible/collections` (verified present on the dev host)
  - [x] **Loud abort on resolution failure (AC 2):** wrap the galaxy install so a failure (missing network, version pin unresolvable) prints a loud, helpful error naming the exact `requirements.yml` path and the likely cause (no network → collections cannot resolve; the provisioner will NOT run with missing modules) then exits non-zero — never continue into `bootstrap` with missing collections
  - [x] **Provision (AC 3):** run `uv run --directory "$ROOT/src/provisioning" dotfiles-provision bootstrap` (the aggregate `bootstrap.yaml` — Story 2.12 — runs the whole chain `packages → cli_tools → filesystem → assets → default_palette → compositor_configs → config_copies → settings → verify`; `BootstrapUseCase` already passes the `install_dir` + `os_family` seam extra-vars)
  - [x] **Verify green (AC 4):** after the aggregate completes, run `uv run --directory "$ROOT/src/provisioning" dotfiles-provision verify` as the final hard gate — `VerifyCapabilityUseCase` runs `verify.yaml` with a REAL check (never `--check`) asserting all ten done-criteria against provisioned locations. The aggregate's final `verify` import already runs verify, but the explicit trailing `verify` is the literal CAP-4 success signal ("completes `dotfiles-provision bootstrap` with verify green") and the authoritative gate
  - [x] On any failure, exit non-zero and print the failing stage (preseed / collections / bootstrap / verify) with the return code — no silent success
  - [x] Header comment block: what the script is (CAP-4 fresh-machine entry point), the chicken-and-egg it solves (plan §3), the stage order (uv preseed → collections → bootstrap → verify), the NFR-3 no-distro-branching invariant, and the container-engine note (see Dev Notes "Container engine")
  - [x] **Container engine check (AC 4 runtime reality):** the `cli_tools` role builds the `csg` container image and the `default_palette` role runs `csg generate` in container mode — both DETECT podman/docker at runtime and fail loud if absent (group_vars/all.yml). A truly fresh machine has neither. **LOCKED DECISION (Option A):** bootstrap.sh checks for a container engine (`podman` OR `docker` on PATH, podman preferred) EARLY in the script and, if absent, fails loud with a helpful message naming the engine requirement and the reason (the container-mode chain needs one; install podman or docker, then re-run) — exit non-zero BEFORE the long aggregate run. Do NOT install one (distro-specific install would violate NFR-3); do NOT silently proceed (the aggregate would fail 40 minutes in at `default_palette`)
  - [x] NO distro branching anywhere (`pacman`, `apt-get`/`apt`, `yum`, `dnf` MUST NOT appear in the script — NFR-3: distro logic lives in `group_vars` only; the test scans for these tokens)
  - [x] NO hardcoded absolute paths (everything derives from `ROOT`, `$HOME`, `$XDG_*`)
  - [x] Make it executable (`chmod +x scripts/bootstrap.sh`)

- [x] Add structural test `src/provisioning/tests/unit/test_bootstrap_script.py` (AC: 1-5)
  - [x] Locate the script via a walk-up resolver from the test file (copy the `_find_ansible_dir()`-style helper or derive `<repo root>/scripts/bootstrap.sh` — reuse the repo's accepted duplicated-helper convention)
  - [x] Assert the file exists, is executable, and starts with `#!/usr/bin/env bash` + `set -euo pipefail`
  - [x] Assert the uv preseed logic: a `command -v uv` presence check and the `astral.sh/uv/install.sh` standalone installer (curl or wget form) for the absent case
  - [x] Assert the collection-resolution command: `ansible-galaxy collection install -r` referencing `requirements.yml`, run through `uv run --directory`
  - [x] Assert the loud-abort-on-failure path exists (the galaxy install is not allowed to silently continue — check for a guard/error-exit around it)
  - [x] Assert the `dotfiles-provision bootstrap` and trailing `dotfiles-provision verify` invocations both appear, in that order (bootstrap before verify), via `uv run --directory`
  - [x] Assert NO distro-branching tokens: regex scan for `pacman|apt-get|apt |yum|dnf` returns no matches (NFR-3 — the test locks the invariant so a future edit cannot sneak distro logic in)
  - [x] Assert the LOCKED container-engine check: the script references `podman` (preferred) and `docker`, and there is a fail-loud abort (non-zero exit / `||` guard with a helpful message) when neither is on PATH — this is the Option A decision locked on 2026-08-13
  - [x] `bash -n scripts/bootstrap.sh` syntax-check exits 0 (skip if `bash` absent)
  - [x] Optional runtime smoke test: stub `uv`/`ansible-galaxy`/`dotfiles-provision` with a temp `PATH` and assert the script invokes them in the correct order (mirror the 2.10/2.11/2.12 runtime-execution discipline — structural tests alone can miss a silent no-op). Skip if the harness is fragile on the CI host

- [x] Verify full suite + lint + layering guard (AC: 1-5)
  - [x] `uv run pytest` — full suite green, no regressions from the 433-pass baseline (Story 2.12)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean (new test file must be mypy-clean; 10 pre-existing baseline errors in test_default_palette_role.py/test_cli_tools_role.py — do NOT chase them)
  - [x] `python tests/architecture/test_layering.py` exits 0 (standalone nicety)
  - [x] `git status --short` shows ONLY `scripts/bootstrap.sh`, the new test file, and the story/status artifacts

## Dev Notes

### Scope — what Story 3.1 is and is not

**IS:** `scripts/bootstrap.sh` — the CAP-4 fresh-machine entry point — plus its structural test. It pre-seeds uv, resolves Ansible collections with a loud-abort, runs the aggregate `bootstrap`, and finishes with a real `verify` green gate.

**IS NOT:** the playbook dry-run integration tests (Story 3.2 — `test_ansible_dryrun.py`), the settings-parity/default-palette integration tests (Story 3.3), any Ansible role/playbook/vars work, `tests/integration/`, any Python hexagon file (`src/provisioning/src/**`), `dotfiles/provisioning/*.yaml`, `dotfiles/config/**`. The Python side is COMPLETE: `BootstrapUseCase` (runs `bootstrap.yaml`) and `VerifyCapabilityUseCase` (runs `verify.yaml`) already exist and are wired in `cli/main.py:80-86`. Do NOT create any new Python beyond the single test file. Do NOT modify any existing file under `src/provisioning/ansible/` or `dotfiles/`.

### The ten done-criteria (what "verify green" means)

The final `dotfiles-provision verify` must go green against all ten done-criteria (plan §8, Story 2.12 Dev Notes table): install dir subtree, system binaries, CLI tools, assets, settings render+parse (spine targets resolve), default palette, compositor configs, filesystem structure, real-dir config copies, §12 preconditions. This story does NOT assert them itself — it guarantees the script RUNS verify as the terminal gate, so a failed criterion fails the bootstrap.

### Stage order (the CAP-4 flow)

```
git clone <repo>
./scripts/bootstrap.sh
  1. ensure uv (standalone installer if absent) + PATH
  2. uv run ansible-galaxy collection install -r ansible/requirements.yml   # loud abort on failure
  3. uv run dotfiles-provision bootstrap                                     # aggregate end-to-end
  4. uv run dotfiles-provision verify                                        # hard gate, all ten criteria
  → exit 0 only if every stage succeeded
```

### Container engine — LOCKED DECISION (Option A)

`group_vars/all.yml` + deferred-work.md#208 record that podman OR docker is a DOCUMENTED RUNTIME DEPENDENCY of the container-mode chain (`cli_tools` builds the `csg` image; `default_palette` runs `csg generate` in container mode). Both roles detect the engine at runtime (podman preferred, then docker) and FAIL LOUD if absent — but neither installs one. Story 2.3 (packages role) is DONE and does NOT install podman/docker.

**Decision (confirmed 2026-08-13, product owner):** bootstrap.sh performs an EARLY fail-loud container-engine check — `podman` OR `docker` must be on PATH (podman preferred); if neither is present, the script aborts with a helpful message naming the requirement and the reason, BEFORE the long aggregate run. The script does NOT install an engine (a distro-specific install in a shell script would violate NFR-3's "distro logic lives in `group_vars` only" invariant) and does NOT silently proceed (the aggregate would otherwise fail deep in `cli_tools`/`default_palette` with an opaque engine error). The operator installs podman/docker and re-runs. Option B (adding podman to the packages role `group_vars`) was considered and rejected as scope expansion into a DONE story; it remains a valid future follow-up if zero-touch fresh-machine provisioning is ever wanted.

### uv preseed — verified against current upstream (2026-08-13)

- Official standalone installer: `curl -LsSf https://astral.sh/uv/install.sh | sh` (fallback `wget -qO- https://astral.sh/uv/install.sh | sh`). Installs `uv`/`uvx` to `~/.local/bin`.
- `uv run --directory <dir>` syncs the project environment from `uv.lock` on first run (creating `.venv`, installing `typer`, `pydantic`, `cli-output`, `ansible-core`, `PyYAML`) — no explicit `uv sync` needed, though an early `uv sync --directory "$ROOT/src/provisioning"` is an acceptable explicit preseed that surfaces lock errors before the long bootstrap run.
- Python: uv downloads a managed interpreter satisfying `requires-python = ">=3.12"` when none exists. `uv tool install` of `csg`/`itr` (requires-python >=3.14) and `weg` (>=3.12) also self-provisions their interpreters. Do NOT hand-roll Python detection.
- Dev host: uv 0.9.22, Python 3.14.3, ansible-core 2.21.2 — consistent with the above.

### Collection resolution mechanics

- `requirements.yml` pins `community.general 13.2.0`, `ansible.posix 2.2.2`, `kewlfft.aur 0.13.0` — resolved via `ansible-galaxy collection install -r` at bootstrap start (SPEC.md#47, plan §3 "Ansible install").
- The `ansible-galaxy` binary comes from `ansible-core`, which is a runtime dep of `src/provisioning` — so the install MUST run through the project env: `uv run --directory "$ROOT/src/provisioning" ansible-galaxy collection install -r "$ROOT/src/provisioning/ansible/requirements.yml"`.
- Collections install to the default user path `~/.ansible/collections/ansible_collections/` (verified present on the dev host) — the default `collections_paths` resolves them; `ansible.cfg` does not override it.
- A resolution failure (no network, or a version pin no longer resolvable) MUST abort loudly with a message naming the requirements file and the likely cause — never proceed into `bootstrap` with missing modules (the roles import `kewlfft.aur.aur`/`community.general.*` and would fail with opaque "module not found" errors deep in the run).

### No distro branching (NFR-3 — the test-enforced invariant)

`group_vars/{arch,debian-family}.yml` are the ONLY place distro differences live. `bootstrap.sh` must contain NO `pacman`, `apt-get`/`apt`, `yum`, `dnf` tokens and NO `ansible_os_family` reads — the Python side only reads `os_family` to pick `group_vars`, and the packages role self-bootstraps `yay` on Arch. The structural test regex-scans the script for these tokens so the invariant cannot silently regress.

### Why the trailing explicit `verify`

`bootstrap.yaml` (Story 2.12) already ends with the `verify.yaml` import, so the aggregate runs verify internally. The explicit trailing `uv run ... dotfiles-provision verify` is the literal CAP-4 / FR-5 success signal ("completes with `dotfiles-provision verify` green") and guarantees the hard gate is a REAL check (`VerifyCapabilityUseCase` runs `check=False`) — not the aggregate's check-gated asserts. It is cheap (one playbook run) and makes the bootstrap's terminal status unambiguous.

### Mirror-and-adapt discipline

- **orchestrate-v5.sh (the existing script in `scripts/`)** — derives `ROOT` via `git rev-parse --show-toplevel` with a fallback; bootstrap.sh should NOT copy that (it would fail outside a git worktree) — derive from `BASH_SOURCE` instead. Do NOT touch orchestrate-v5.sh.
- **Story 2.12** — the aggregate `bootstrap.yaml` and `verify.yaml` this script drives; the CLI already wires both (cli/main.py:80-86).
- **Story 2.11** — the seam contract: `BootstrapUseCase` passes `install_dir` + `os_family` extra-vars; the script needs no seam knowledge (the use case owns it).
- **cli_tools (2.4)** — its fail message "uv not found on PATH — the cli_tools role requires uv (bootstrap.sh pre-seeds it; Story 3.1)" is the guard this story closes.

## Project Structure Notes

- `scripts/bootstrap.sh` — NEW executable shell script at repo root (sibling of the existing `scripts/orchestrate-v5.sh`, which is UNRELATED and must not be modified).
- `src/provisioning/tests/unit/test_bootstrap_script.py` — NEW structural test (mirror the duplicated-helper convention; no shared conftest).
- Consumed, NOT modified: `src/provisioning/ansible/requirements.yml`, `src/provisioning/ansible/ansible.cfg`, `src/provisioning/ansible/playbooks/{bootstrap,verify}.yaml`, `src/provisioning/src/provisioning/cli/main.py`, `src/provisioning/src/provisioning/application/use_cases.py`, `src/provisioning/pyproject.toml`, all roles, all `group_vars`.
- No new dependencies. No Python outside the single test file.

## Testing Requirements

- Full gates: `uv run pytest` (433-pass baseline from Story 2.12), `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src tests` (new test must be clean; do NOT chase the 10 pre-existing baseline errors), `python tests/architecture/test_layering.py` (standalone nicety).
- New `src/provisioning/tests/unit/test_bootstrap_script.py` — copy the repo's accepted helper convention (`_find_ansible_dir()`-style walk-up resolver, duplicated per-file). Assert: file exists + executable + shebang + `set -euo pipefail`; uv preseed (`command -v uv` + astral installer); galaxy install via `uv run --directory` + `requirements.yml`; loud-abort guard; bootstrap-before-verify order; NO distro tokens (`pacman|apt-get|apt |yum|dnf`); `bash -n` syntax check (skip-if-absent). Optional runtime smoke with stubbed `uv`/`ansible-galaxy`/`dotfiles-provision` on a temp PATH to assert invocation order (skip if fragile).
- Do NOT attempt to run the real bootstrap on the host (it mutates the machine — that's Story 3.2/3.3 integration territory on disposable targets).

## Previous Story Intelligence

### Story 2.12 — Verify Role & Aggregate Bootstrap Playbook (DONE 2026-08-13, the immediate predecessor)
- Delivered `roles/verify/**`, `verify.yaml`, and the aggregate `bootstrap.yaml` (nine `import_playbook` entries in dependency order ending with `verify`) — the exact artifacts this script drives. `bootstrap.yaml --check` is dry-run-clean; a real `bootstrap` runs the full chain. [Source: 2-12 story, bootstrap.yaml]
- The verify role's check-gated asserts mean the aggregate's internal verify import is plan-gated; the AUTHORITATIVE gate is `dotfiles-provision verify` (check=False) — which is why this script's trailing explicit verify matters.
- Baseline 433 tests pass at 2.12. Working tree at story creation is DIRTY with uncommitted 2.12 review fixes (`verify/tasks/main.yml`, `verify/vars/main.yml`, `test_verify_role.py`, story/status artifacts) — build on the CURRENT tree; do NOT stash/revert them.

### Story 2.11 — Settings Role (DONE 2026-08-12)
- The seam contract (`install_dir` + `os_family` extra-vars) is fully owned by `BootstrapUseCase`/`VerifyCapabilityUseCase` — this script needs no seam knowledge.

### Story 2.4 — CLI Tools Role (DONE 2026-08-09)
- Its fail message explicitly defers uv preseed to bootstrap.sh: "uv not found on PATH — the cli_tools role requires uv (bootstrap.sh pre-seeds it; Story 3.1)". This story closes that loop.
- `cli_tools_bin_dir` = `~/.local/bin` — the same dir the uv installer populates and that bootstrap.sh prepends to PATH. [Source: cli_tools/vars/main.yml#14]

### Story 2.3 — Packages Role (DONE 2026-08-09)
- Does NOT install podman/docker (the container-engine OPEN DECISION). Its `group_vars/{arch,debian-family}.yml` are the only sanctioned distro locations — if Option B is chosen, the podman package names belong there.

### Story 2.2 — Ansible Scaffold (DONE 2026-08-04)
- Established `requirements.yml` (pinned collections) and the "resolved via `ansible-galaxy` at bootstrap start — a resolution failure must abort loudly (Story 3.1)" contract. [Source: 2-2-ansible-scaffold.md#168]

## Git Intelligence

- Baseline: `e29e603` (`feat: implement story 2.12 verify role and aggregate bootstrap playbook`). **The working tree is DIRTY with the uncommitted 2.12 review-fix changes** (verify role tasks/vars, `test_verify_role.py`, the 2.12 story/status artifacts) — build on the CURRENT working tree; do NOT stash/revert them.
- 433 tests pass at baseline.
- Recent work pattern (2.8→2.12): each story is one deliverable + one structural test file + story/status artifacts; role tests duplicate the shared helper suite (no shared conftest). Commit titles follow `chore: create story X.Y ...` → `feat: implement story X.Y ...` → `fix: apply code review findings ...`.
- This story adds ONLY: `scripts/bootstrap.sh`, `src/provisioning/tests/unit/test_bootstrap_script.py`, and the story/status artifacts. It must NOT modify any existing role/playbook/test/manifest/Python file.

## Latest Tech Information

- **uv standalone installer (verified 2026-08-13, uv 0.9.22):** `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `wget -qO- ... | sh`), installs to `~/.local/bin/uv`. `uv run --directory <dir>` syncs the project env from `uv.lock` and auto-provisions a managed Python satisfying `requires-python`.
- **ansible-core 2.21.2** on the dev host (pyproject requires `>=2.16`); `ansible-galaxy` ships with it — hence running galaxy through `uv run --directory "$ROOT/src/provisioning"`.
- **Collections** (`community.general 13.2.0`, `ansible.posix 2.2.2`, `kewlfft.aur 0.13.0`) install to `~/.ansible/collections/ansible_collections/` by default — the default `collections_paths` resolves them; `ansible.cfg` (roles_path/inventory only) does not override.
- **Container engine:** podman OR docker is a documented runtime dependency of the container-mode chain; neither role installs one. **LOCKED Decision (2026-08-13):** bootstrap.sh fails loud early if neither engine is on PATH (Option A) — see Dev Notes.
- No new Python/shell dependencies. `bash` is the only interpreter requirement (present on every Arch/Debian-family fresh machine).

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#487-501] — Story 3.1 ACs (pre-seed Python+uv, galaxy resolution loud-abort, aggregate bootstrap, verify green, Arch+Debian)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#26] — FR-5 Fresh-Machine Bootstrap
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#46] — FR-25 Integration Tests (Story 3.2/3.3 split — NOT this story)
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#58] — NFR-9 Bootstrap Reproducibility
- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#138-140] — hardening notes (parse ≠ works; dry-run must be dry — context for why verify is the terminal gate)
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#288-300] — PRD §4.6 Reproducible Bootstrap / FR-5
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#28-30] — CAP-4 (fresh machine fully provisioned in one command)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#47] — bootstrap chain constraint (galaxy at bootstrap start)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#55] — plan §3 locked Bootstrap decision (pre-seed Python+uv, then `uv run --directory ./src/provisioning dotfiles-provision bootstrap`)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#56] — plan §3 Ansible install decision (galaxy at bootstrap start)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#286] — plan §11 step 10 (scripts/bootstrap.sh)
- [Source: src/provisioning/ansible/requirements.yml] — the pinned collections (community.general / ansible.posix / kewlfft.aur)
- [Source: src/provisioning/ansible/group_vars/all.yml#15-23] — the documented runtime dependencies (podman/docker + uv)
- [Source: src/provisioning/src/provisioning/application/use_cases.py#99-117] — BootstrapUseCase (runs bootstrap.yaml, passes seam extra-vars)
- [Source: src/provisioning/src/provisioning/application/use_cases.py#75-96] — VerifyCapabilityUseCase (real check, never --check)
- [Source: src/provisioning/src/provisioning/cli/main.py#80-86] — CLI already wires bootstrap.yaml + verify.yaml
- [Source: src/provisioning/pyproject.toml] — requires-python >=3.12; ansible-core runtime dep
- [Source: src/provisioning/ansible/roles/cli_tools/vars/main.yml#14] — cli_tools_bin_dir = `$HOME/.local/bin` (the uv bin dir this script prepends)
- [Source: src/provisioning/ansible/roles/cli_tools/tasks/main.yml] — "uv not found on PATH — the cli_tools role requires uv (bootstrap.sh pre-seeds it; Story 3.1)" guard
- [Source: _bmad-output/implementation-artifacts/2-12-verify-role-and-aggregate-bootstrap-playbook.md] — previous story (aggregate bootstrap.yaml + verify.yaml this script drives)
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#208] — the container-engine deferred flag (podman/docker dependency provisioning)
- [Source: src/provisioning/tests/unit/test_bootstrap_playbook.py] — the test-pattern precedent (structural, helper-duplicating)
- [Source: https://docs.astral.sh/uv/getting-started/installation/] — uv standalone installer (verified 2026-08-13)

## Dev Agent Record

### Agent Model Used

opencode (deepseek-v4-flash)

### Debug Log References

- Baseline `e29e603`; working tree DIRTY with the uncommitted 2.12 review fixes (verify role + tests + artifacts) — build on the current tree, don't revert. 433 tests pass. Container-engine check LOCKED as Option A (fail-loud on missing podman/docker) — see Dev Notes.
- At dev start the dirty tree was committed (`fb83e64 feat: apply code review findings for story 2.12 verify role`); tree clean; HEAD `fb83e64`.
- Runtime smoke test required a `dirname` symlink in the stub PATH: the script's ROOT derivation runs `dirname` (external), so an isolated stub-only PATH broke it (`cd ""/..` → ROOT=/). Resolved by symlinking the real `dirname` into the stub dir.
- The NFR-3 no-distro-token scan caught my own header comment naming `pacman/apt/yum/dnf` — removed the literal tokens from the script so the invariant lock holds.

### Completion Notes List

- 2026-08-13: Story 3.1 implemented and marked for review. Created `scripts/bootstrap.sh` — the CAP-4 fresh-machine entry point: ROOT from BASH_SOURCE (not the git top-level), `set -euo pipefail`, early fail-loud container-engine check (podman preferred → docker → abort naming the requirement, per the locked Option A decision; no install), uv preseed via the official astral standalone installer (curl with wget fallback, `~/.local/bin` prepended to PATH, uv owns Python provisioning), `ansible-galaxy collection install -r requirements.yml` through `uv run --directory` with a loud abort on resolution failure (names the requirements path + no-network cause), `uv run dotfiles-provision bootstrap` (aggregate, Story 2.12), and the trailing `uv run dotfiles-provision verify` hard gate (real check, never --check). Zero distro tokens (NFR-3 invariant), zero hardcoded absolute paths. Added `test_bootstrap_script.py` — 16 tests: file/executable/shebang/fail-fast, ROOT-from-BASH_SOURCE, uv preseed (curl+wget), collection resolution through uv run, loud-abort guard, bootstrap-before-verify order, no-distro-token regex lock, container-engine check (podman preferred + fail-loud), no-hardcoded-paths, header block, stage-failure-with-rc, `bash -n` syntax, plus two runtime smoke tests (stub podman/uv/ansible-galaxy/dotfiles-provision on an isolated PATH asserting exact stage invocation order, and a fail-loud-no-engine run). Gates: full suite 453 passed (433 baseline + new tests, no regressions), ruff check + format clean, new test file mypy-clean (10 pre-existing baseline errors in test_default_palette_role/test_cli_tools_role NOT chased), layering guard OK, `git status` shows only the intended files.

### File List

- `scripts/bootstrap.sh` (NEW, executable)
- `src/provisioning/tests/unit/test_bootstrap_script.py` (NEW)
- `_bmad-output/implementation-artifacts/3-1-fresh-machine-bootstrap-script.md` (this story)
- `_bmad-output/implementation-artifacts/sprint-status.yaml` (story status → ready-for-dev → in-progress → review)

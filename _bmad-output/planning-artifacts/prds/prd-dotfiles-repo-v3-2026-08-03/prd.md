---
title: Dotfiles System Phase 1 — Provisioning
status: final
created: 2026-08-03
updated: 2026-08-03
---

# PRD: Dotfiles System Phase 1 — Provisioning

## 0. Document Purpose

This PRD defines Phase 1 of the dotfiles project: a **provisioning layer** (`dotfiles-provision`) that establishes the operational environment a future runtime reconciliation layer (Phase 2+) can assume exists. It is written for the product owner, the downstream architecture/epics/stories workflow, and the developer who will implement it.

This PRD builds on already-locked inputs and does not duplicate them:

- **Canonical contract:** `_bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md` (CAP-1…5, constraints, success signal) + `chaining-spine.md` (install-dir subtree, per-tool settings contract).
- **Architecture:** `docs/99-dotfiles-hexagonal-architecture.md`, `docs/01-dotfiles-provisioning-phase1-plan.md` (approved, 2026-08-03).
- **Decomposition:** `_bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md` (Epics 1–3, stories 1.1–3.3).

**Structure note:** The FR/NFR identifiers used here (FR-1…FR-25, NFR-1…NFR-9) are stable and match the epics document exactly, so downstream artifacts keep identical references. Feature grouping in this PRD is its own organization; it does not change the FR numbering.

## 1. Vision

The dotfiles project is a **Desktop State Reconciliation Engine**, not a wallpaper manager or CLI wrapper collection. The three compute providers (`csg`, `weg`, icon-renderer) and the shared configuration libraries already exist and work; nothing yet orchestrates the machine state those tools run on. Phase 1 closes that gap.

Phase 1 delivers a single command that turns a fresh Arch or Debian-family machine into a **capable** dotfiles host: packages installed, CLI tools on PATH, wallpapers/icon templates/color mappings deployed, filesystem layout and symlinks in place, per-tool settings files rendered, and a first-boot color palette generated from the default wallpaper. It makes the machine *capable* — it does not reconcile the desktop.

The product's value is reproducibility and trust. `git clone && ./scripts/bootstrap.sh` produces a verified, tool-ready machine; `dotfiles-provision plan` shows desired-vs-actual before any mutation; `verify` is a hard gate that future phases may assume. Phase 1 establishes the install spine — the single place the tools read from and write to — so that Phase 2's runtime can invoke any tool with a config file and no per-invocation path flags.

## 2. Target User

### 2.1 Jobs To Be Done

- Reproduce my dotfiles setup on a fresh machine in one command, without remembering a manual install sequence.
- See what provisioning *would* change before it changes anything (`plan`).
- Re-run provisioning safely — idempotently, with no drift on a second run (`apply`).
- Prove a machine is correctly set up before relying on it (`verify`).
- Install and update the `csg`/`weg`/icon-renderer CLIs and their assets without hand-managing symlinks and settings paths.

### 2.2 Non-Users (v1)

- Desktop *runtime* reconcilers — anyone expecting the tool to watch the desktop and react to changes (that is Phase 2, `src/core/`).
- Users of the root `dotfiles` CLI (Phase 2 Task Group F).
- Users wanting a persisted provisioning receipt (`provisioning-state.json`) or content-hash/invalidation tracking — deferred to Phase 2+.

### 2.3 Key User Journeys

This is internal tooling with a single operator role, so journeys are kept light — one per command surface. The SPEC's capabilities (CAP-1…5) are the authoritative intent; journeys below narrate them.

- **UJ-1. Diego provisions a fresh machine with one command.**
  - **Persona + context:** Diego, a solo dotfiles maintainer, has just cloned the repo on a fresh Arch box with only a shell and git.
  - **Entry state:** `git clone` done, no Python/uv, no dotfiles state on the machine.
  - **Path:** run `./scripts/bootstrap.sh` → Python+uv pre-seeded → `dotfiles-provision bootstrap` runs the aggregate playbook → roles install packages, tools, assets, filesystem, symlinks, settings, palette, verify.
  - **Climax:** `dotfiles-provision verify` reports all ten done-criteria green.
  - **Resolution:** Diego runs `csg generate <wallpaper>`, `itr render --config ...` and they read/write through the install spine with no path flags.
  - **Edge case:** a distro other than Arch/Debian-family — the playbook fails with a clear message rather than guessing.
- **UJ-2. Diego previews provisioning before mutating the machine.**
  - `dotfiles-provision plan` runs Ansible's `--check` mode and prints the per-task desired-vs-actual diff (changed/ok); nothing is installed. Reassures him the apply is safe.
- **UJ-3. Diego proves an existing machine is still correctly provisioned.**
  - `dotfiles-provision verify` re-derives state on demand against provisioned locations (not the repo checkout) and reports which of the ten done-criteria hold. Green is the contract Phase 2 may assume.

## 3. Glossary

- **Provisioning** — Establishing the operational environment (packages, CLIs, assets, filesystem, settings, palette) so Phase 2 runtime preconditions hold. Machine state reconciliation, not desktop reconciliation.
- **Install dir / install spine** — `$XDG_DATA_HOME/dotfiles/` (default `~/.local/share/dotfiles/`), the single data-flow glue location. Subtrees: `wallpapers/`, `icon-templates/`, `icon-mappings/`, `csg-templates/`, `weg-effects.yaml`, `generated/{palettes,effects,icons,.weg-tmp}/`.
- **Compute provider** — One of the three CLI tools: `csg` (color-scheme-generator), `weg` (wallpaper-effects-generator), `icon-renderer` (icon-templates-renderer, "itr").
- **Manifest** — A declarative desired-machine-state YAML under `dotfiles/provisioning/` (`packages.yaml`, `assets.yaml`, `filesystem.yaml`, `symlinks.yaml`, `cli-tools.yaml`).
- **Role / Playbook** — Ansible concepts. A role is a reusable task unit; a playbook is a runnable Ansible entrypoint. Phase 1 has one playbook per role plus the aggregate `bootstrap.yaml`.
- **Done-criteria** — The ten conditions `verify` asserts (install dir, system binaries, CLI tools, assets, settings parse, default palette, compositor configs, filesystem structure, symlinks, §12 preconditions).
- **§11 boundary** — The mechanical package rule: `src/provisioning` imports `cli-output` only; never `core`, `infrastructure`, or the CLI-tool packages. Enforced by `tests/architecture/test_layering.py`.
- **§12 preconditions** — The four runtime assumptions Phase 2 relies on: binaries installed, assets placed, filesystem structure exists, settings files parseable.
- **Default palette** — First-boot colors generated at apply time from `default.png` by the `default_palette` role; source of Hyprland `colors.conf` and Waybar `colors.css` fragments.

## 4. Features

### 4.1 dotfiles-provision CLI

**Description:** A Typer CLI exposing four commands — `plan`, `apply`, `verify`, `bootstrap` — that drive the provisioning orchestration and render structured output through `cli-output` (JSON by default). Realizes UJ-1, UJ-2, UJ-3. The `plan`/`apply` pair is the diff-then-execute loop; `verify` is the acceptance gate; `bootstrap` is the aggregate end-to-end run. Distro awareness stays inside Ansible (`group_vars`); the Python side never branches on distro beyond reading `ansible_os_family` to select `group_vars`.

**Functional Requirements:**

#### FR-1: Plan Command

An operator can preview provisioning without mutating the machine. Running `dotfiles-provision plan` loads the desired manifests, reads `ansible_os_family` via `IFactReader`, and runs the playbooks through Ansible's native `--check` mode, printing the per-task changed/ok diff via `cli-output`. Realizes UJ-2.

**Consequences (testable):**
- `dotfiles-provision plan` exits 0, prints a per-task changed/ok plan, and makes no system changes.
- The diff is entirely Ansible's `--check` mode; the Python side never inspects installed packages.
- `--check` under `plan` never executes `makepkg` (the guarded `yay` bootstrap task) and never mutates the host.

**Out of Scope:**
- Any non-Ansible diff engine or Python-side package inspection.

#### FR-2: Apply Command

An operator can provision the machine idempotently and re-runnably. Running `dotfiles-provision apply` executes the playbooks with `check=False`; a re-run produces no drift because Ansible is the state authority. Realizes UJ-1.

**Consequences (testable):**
- `dotfiles-provision apply` exits 0 and a second consecutive run reports no drift.
- No `provisioning-state.json` is persisted in Phase 1; state is re-derived by `verify` on demand.

#### FR-3: Verify Command

An operator can assert the machine satisfies all §12 runtime preconditions and the ten done-criteria. `dotfiles-provision verify` runs `VerifyCapabilityUseCase` against provisioned locations (not the repo checkout). Realizes UJ-3.

**Consequences (testable):**
- `dotfiles-provision verify` is green when all ten done-criteria hold.
- Verification never reaches into provisioning internals; the four §12 preconditions are asserted via `VerifyCapabilityUseCase`.

#### FR-4: Bootstrap Command

An operator can run the full aggregate provisioning in one command. `dotfiles-provision bootstrap` runs `bootstrap.yaml`, which aggregates all role playbooks in dependency order (`packages` → `cli_tools` → `filesystem` → `assets` → `default_palette` → `compositor_configs` → `symlinks` → `settings` → `verify`). Realizes UJ-1.

**Consequences (testable):**
- `dotfiles-provision bootstrap` runs all playbooks end-to-end.
- `dotfiles-provision bootstrap --check` completes cleanly with no mutation.

#### FR-11: CLI Rendering via cli-output

All four commands render through `cli-output` (JSON by default). Each command exits 0 on success and non-zero with a structured error on failure.

**Consequences (testable):**
- CLI tests use Typer `CliRunner` with mock deps on `ctx.obj`.
- Each command exits 0 on success; failures produce a structured, non-zero error.

### 4.2 Provisioning Package and Hexagonal Boundary

**Description:** `src/provisioning` is a standalone uv package with a `dotfiles-provision` entry point, mirroring the `cli-output`/`oci-runtime` structure. Its in-package hexagonal layering (domain ← ports ← adapters ← application ← cli) and its cross-package boundary are enforced mechanically from day one, so the package can never silently import forbidden packages.

**Functional Requirements:**

#### FR-6: Provisioning Package Scaffold

The `src/provisioning` uv package exists with package name `dotfiles-provision`, entry point `dotfiles-provision`, runtime deps `typer`, `pydantic`, `cli-output` (via `uv.sources`), `ansible-core`; dev deps `pytest`, `ruff`, `mypy`.

**Consequences (testable):**
- `pyproject.toml` declares the package and deps; `uv lock` resolves without errors.
- A stub CLI invoking `cli-output` renders a version string and exits 0.

#### FR-24: Architecture Layering Test

A mechanical test (`tests/architecture/test_layering.py`) enforces the in-package dependency order (domain ← ports ← adapters ← application ← cli), the domain stdlib allowlist (bans `subprocess`, `os`, `shutil`, Path FS calls in domain), ports-as-ABCs, and Rule 5: the cross-package forbidden set (`core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`) is never imported. Only `provisioning` and `cli_output` are allowed cross-package. Realizes NFR-4.

**Consequences (testable):**
- A deliberately-violating import fails the test.

### 4.3 Domain, Ports, Adapters, Use Cases

**Description:** The hexagonal core of the orchestrator: pure zero-I/O domain models, explicit port abstractions, concrete adapters, and use cases wiring ports together. This layer is fully testable with fakes — no real `ansible-playbook` invocation in unit tests.

**Functional Requirements:**

#### FR-7: Domain Models and Enums

Pure, zero-I/O domain under `src/provisioning/domain/`: frozen dataclasses `MachineState`, `ProvisionManifest`, `ProvisionResult`, `Spec`; `StrEnum` enums `Distro`, `BinaryCapability`, `AssetKind`.

**Consequences (testable):**
- No domain module imports `os`, `subprocess`, `shutil`, `pathlib`, or any I/O library.
- Unit tests exercise construction, validation, and equality with zero fixtures or temp files. Realizes NFR-5.

#### FR-8: Ports

Explicit port abstractions under `src/provisioning/ports/`: `IProvisionExecutor` (abstracts `ansible-playbook` with a `check: bool` parameter), `IManifestReader` (reads `dotfiles/provisioning/*.yaml`), `IFactReader.os_family()` (thin: selects `group_vars`, never inspects packages).

**Consequences (testable):**
- All three are abstract base classes (Protocol-compatible) raising `NotImplementedError` on unimplemented methods.
- Unit tests verify each port's contract with fakes. Realizes NFR-5.

#### FR-10: Adapters

Concrete adapters under `src/provisioning/adapters/`: `yaml_manifest_reader.py` (parses manifests into domain objects), `ansible_fact_reader.py` (parses `ansible -m setup` for `ansible_os_family`), `ansible_executor.py` (shells to `ansible-playbook` with `-i`, `--tags`, `--check`, `--extra-vars`, surfacing per-task changed/ok).

**Consequences (testable):**
- `AnsibleExecutor` passes exactly the extra-var keys `install_dir` and `os_family` (seam contract pinned by a test).
- All adapters are unit-tested with fakes — no real `ansible-playbook` invocation.

#### FR-9: Use Cases

Application layer under `src/provisioning/application/`: `ProvisionMachineUseCase` (plan = `check: True`, apply = `check: False`; resolves `os_family` via `IFactReader` and the install dir at plan time, passing it via the seam extra-vars), `VerifyCapabilityUseCase` (asserts the four §12 preconditions without reaching into provisioning internals), `BootstrapUseCase` (runs the aggregate `bootstrap.yaml`).

**Consequences (testable):**
- Unit tests verify plan/apply/verify/bootstrap behavior with fake ports. Realizes NFR-7.

### 4.4 Declarative Manifests and Ansible Scaffold

**Description:** Desired machine state is data. `dotfiles/provisioning/*.yaml` manifests describe packages, assets, filesystem layout, symlinks, and CLI-tool installs; the Ansible project scaffold provides the local inventory, collection requirements, and distro-aware `group_vars`. Distro differences are isolated to `group_vars` — never in Python or `bootstrap.sh`.

**Functional Requirements:**

#### FR-12: Declarative Manifests

`dotfiles/provisioning/` contains `packages.yaml`, `assets.yaml`, `filesystem.yaml`, `symlinks.yaml`, and `cli-tools.yaml` describing desired machine state. Every manifest parses with `YamlManifestReader` into domain `ProvisionManifest` objects.

**Consequences (testable):**
- `packages.yaml` lists desired packages per package manager; `assets.yaml` lists wallpapers/icon templates/icon mappings to deploy; `filesystem.yaml` describes the XDG + install-dir subtree; `symlinks.yaml` maps `dotfiles/config/*` → `~/.config/*`; `cli-tools.yaml` specifies csg/weg/itr `uv tool install` targets.

#### FR-13: Ansible Scaffold

The Ansible scaffold exists under `src/provisioning/ansible/`: `inventory/localhost.yaml` (local host), `requirements.yml` (`community.general`, `ansible.posix`, `kewlfft.aur`), `ansible.cfg`, and `group_vars/{all,arch,debian-family}.yml`. The `arch`/`debian-family` filenames match the `IFactReader.os_family()` seam contract. Realizes NFR-3.

**Consequences (testable):**
- Distro differences are isolated to `group_vars` — no distro branching in Python or `bootstrap.sh`.
- External collections resolve via `ansible-galaxy` at bootstrap start.

### 4.5 Machine Provisioning Content (Ansible Roles)

**Description:** The nine roles that actually provision a real machine, each one playbook plus role content. Internal dependency order is locked: `cli_tools` → `assets` → `default_palette` → `compositor_configs` → `settings`. This feature realizes the bulk of UJ-1.

**Functional Requirements:**

#### FR-14: Packages Role

Installs system packages (Hyprland, Hyprpaper, Waybar, fonts) per distro. Arch uses `pacman` and self-bootstraps `yay` (`base-devel`+`git` → guarded `makepkg -si yay-bin`, skipping if `yay` present), then drives AUR installs via `kewlfft.aur`; Debian-family uses `apt`. Distro logic lives in `vars/arch.yml`/`vars/debian.yml` only.

**Consequences (testable):**
- A `--check` run reports would-change without ever executing `makepkg` or mutating the host.
- A re-run reports no drift (idempotent).

#### FR-15: CLI Tools Role

Installs `csg`, `weg`, and icon-renderer via `uv tool install` against the repo package paths; each binary is on PATH after the role completes.

**Consequences (testable):**
- Idempotent — re-run produces no changed state for already-installed tools.
- `--check` reports would-change without installing.

#### FR-16: Filesystem Role

Creates the machine layout: XDG config/state/cache dirs, `~/.config/{hypr,hyprpaper,waybar}/`, and the install-dir subtree (`wallpapers/`, `icon-templates/`, `icon-mappings/`, `csg-templates/`, `weg-effects.yaml` location, `generated/{palettes,effects,icons,.weg-tmp}/`). Dirs are created only where missing. Realizes NFR-8.

**Consequences (testable):**
- Idempotent — a re-run leaves existing dirs unchanged.

#### FR-17: Assets Role

Deploys assets to the spine: unpacks `dotfiles/assets/wallpapers/wallpapers.tar.gz` → `<install>/wallpapers/` (including `default.png`), deploys SVG icon templates → `<install>/icon-templates/`, icon color-mapping YAMLs → `<install>/icon-mappings/`, CSG bundled templates → `<install>/csg-templates/`, and emits the WEG effects catalog via `weg dump-effects --output <install>/weg-effects.yaml`.

**Consequences (testable):**
- Every task is idempotent.
- Replacing `wallpapers.tar.gz` in the repo causes the next `apply` to redeploy.

#### FR-18: Default Palette Role

Generates the default palette at apply time by invoking `csg generate <install>/wallpapers/default.png -f conf` (plus standard formats), writing to `<install>/generated/palettes/`. `overwrite=true` is scoped to that single task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"`; the rendered `~/.config/color-scheme-generator/settings.toml` keeps `overwrite = false`.

**Consequences (testable):**
- The emitted `colors.conf` matches the Hyprland syntax contract (`$accent` equals `$color1`).
- Replacing `wallpapers.tar.gz` causes the next `apply` to regenerate the palette.

#### FR-19: Compositor Configs Role

Places the static Hyprland/Waybar/Hyprpaper skeletons and copies the default-palette color fragments into the user config: `<install>/generated/palettes/colors.conf` → `~/.config/hypr/colors.conf`, and `<install>/generated/palettes/colors.css` → `~/.config/waybar/colors.css`.

**Consequences (testable):**
- The skeleton files never change on re-run; only the fragment files are overwrite candidates.
- All tasks are idempotent.

#### FR-20: Symlinks Role

Creates every entry in `dotfiles/provisioning/symlinks.yaml` as a symlink from repo `dotfiles/config/*` → `~/.config/*`; broken or missing targets are reported as failures.

**Consequences (testable):**
- Re-runs are idempotent — existing symlinks are left unchanged.

#### FR-21: Settings Role

Renders the three per-tool `settings.toml` files from Jinja templates (Ansible `template` module): CSG `output.directory` → `<install>/generated/palettes` (keeps `overwrite = false`); WEG `output.directory` → `<install>/generated/effects` and `processing.temp_dir` → `<install>/generated/.weg-tmp`; ITR `output.output_dir` → `<install>/generated/icons`, `templates.dir` → `<install>/icon-templates`, `color_scheme.path` → `<install>/generated/palettes/colors.yaml`. Absolute install-dir paths come from the `install_dir` seam extra-var, never hardcoded. Realizes NFR-6.

**Consequences (testable):**
- Each rendered file parses via its tool's `--config` gate: `csg info --config <rendered>`, `weg info --config <rendered>`, `itr list <install>/icon-mappings/icons.yaml --config <rendered>` — all exit 0.
- `csg/weg dump-*` commands are not used by provisioning (ITR has no dump command; its file is written directly, 4 keys).

#### FR-22: Verify Role

Asserts all §12 preconditions and the ten done-criteria against provisioned locations. The ITR settings-parse gate uses `itr list <install>/icon-mappings/icons.yaml --config ~/.config/itr/settings.toml` (not `defaults.yaml`, which lacks a `variants` field). Realizes FR-3's content.

**Consequences (testable):**
- `verify.yaml` asserts the install-dir subtree, system binaries on PATH, `csg`/`weg`/icon-renderer on PATH, assets deployed, per-tool settings parse, default palette files present, compositor configs + fragments placed, filesystem structure, symlinks resolved, and §12 preconditions.
- Verification is against provisioned locations, not the repo checkout.

#### FR-23: Compositor Skeleton Configs

The repo contains static skeleton configs: `dotfiles/config/hypr/hyprland.conf` starts with `source = ~/.config/hypr/colors.conf`; `dotfiles/config/waybar/style.css` starts with `@import "colors.css";`; `dotfiles/config/hyprpaper/hyprpaper.conf` is flat static pointing at `<install>/wallpapers/default.png`.

**Consequences (testable):**
- Existing `dotfiles/config/{nvim,starship,wlogout,zsh}/` dirs are unchanged.

### 4.6 Reproducible Bootstrap

**Description:** A fresh machine with only a shell and git can be fully provisioned from `git clone && ./scripts/bootstrap.sh`. This is the CAP-4 entry point and the ultimate proof of the whole system.

**Functional Requirements:**

#### FR-5: Fresh-Machine Bootstrap

`scripts/bootstrap.sh` pre-seeds Python and `uv` if absent, then runs `uv run --directory ./src/provisioning dotfiles-provision bootstrap` (FR-4), completing with `dotfiles-provision verify` green against all ten done-criteria.

**Consequences (testable):**
- Works on both Arch and Debian-family targets.
- No pre-install step beyond a shell and git. Realizes NFR-9.

### 4.7 Integration Tests

**Description:** Integration tests exercise the real provisioning surface without mutating the host — every playbook dry-runs under `--check`, and the settings/palette contract is proven by actually invoking the tools with rendered configs. This is Epic 3, the acceptance gate.

**Functional Requirements:**

#### FR-25: Integration Tests

The integration suite under `src/provisioning/tests/integration/` includes: a dry-run test running every playbook with `--check` and asserting it completes cleanly with no mutation (never executing `makepkg`); a separate apply+verify test (on a disposable/container target) asserting the ten done-criteria hold after a real `apply` followed by `verify` — not after `--check`, which cannot leave state behind; a settings-file-parity test invoking `csg info --config <rendered>`, `weg info --config <rendered>`, `itr list <install>/icon-mappings/icons.yaml --config <rendered>` — each exits 0 and each rendered spine path resolves to an existing directory (parse ≠ works); a default-palette test running `csg generate -f conf` and asserting the output matches the Hyprland syntax contract; a spine-chain test asserting ITR's `color_scheme.path` resolves to a real CSG palette output; and a Phase 2 invocation-contract assertion testing that CSG invoked with `--templates-dir <install>/csg-templates/` renders from the spine templates rather than silently falling back to bundled defaults.

**Consequences (testable):**
- Tests invoke real `ansible-playbook --check`, not fakes.
- The AUR `yay` self-bootstrap task never builds under `--check` (asserted — no mutation in dry-run mode).
- The apply+verify test runs on a disposable/container target, never mutating a real host.
- Realizes NFR-6, CAP-5.

### 4.8 Feature-specific NFRs

None unique to any single feature beyond those already enumerated in §5.

## 5. Cross-Cutting Non-Functional Requirements

**NFR-1: Idempotency.** `apply` is re-runnable with no drift; Ansible is the state authority. Validates FR-2, FR-14, FR-15, FR-16, FR-17, FR-18, FR-19, FR-20, FR-21.

**NFR-2: No Persisted Provisioning State.** No `provisioning-state.json` in Phase 1; `verify` re-derives state on demand. Validates FR-2, FR-3.

**NFR-3: Multi-Distro Support.** Arch (pacman + AUR) and Debian-family (apt) supported; distro differences isolated to `group_vars`; the Python orchestrator never branches on distro. Validates FR-13, FR-14.

**NFR-4: §11 Package Boundary.** `src/provisioning` imports `cli-output` only; never `core`, `infrastructure`, or CLI-tool packages; enforced mechanically by `test_layering.py`. Validates FR-24.

**NFR-5: Testability.** Domain logic is pure with zero I/O; ports are ABCs; adapters testable with fakes; use cases testable with fake ports. Validates FR-7, FR-8, FR-9, FR-10.

**NFR-6: Deterministic Settings.** Rendered settings files parse exactly with absolute install-dir paths; each tool parses its rendered settings via its `--config` gate. Validates FR-21, FR-25.

**NFR-7: Verify-Gate Contract.** The four §12 runtime preconditions are assertable via `VerifyCapabilityUseCase` without reaching into provisioning internals. Validates FR-3, FR-9, FR-22.

**NFR-8: Spine Containment.** The install dir is the single place tools read from and write to; wiping `$XDG_DATA_HOME/dotfiles/` leaves nothing orphaned in the XDG config tree. Validates FR-16, FR-21.

**NFR-9: Bootstrap Reproducibility.** From a fresh Arch or Debian-family machine, `git clone && ./scripts/bootstrap.sh` completes with verify green. Validates FR-5.

## 6. Non-Goals (Explicit)

- **The runtime reconciliation core** — `src/core/` and its infrastructure adapters (`src/infrastructure/`). That is Phase 2.
- **The root `dotfiles` CLI** — architecture doc §28 Task Group F.
- **Persistence of desktop state** — separate from provisioning's state store.
- **A persisted `provisioning-state.json` receipt** — deferred to Phase 2+ only if a drift-history need surfaces.
- **Content hashing, invalidation, and derived-artifact tracking.**
- **Writing derived colors into the Hyprland/Hyprpaper/Waybar templates** provisioning only places (Phase 2 overwrites only the fragment files).
- **An `itr dump-config` command** for parity with csg/weg.
- **Desktop convergence / reactive runtime.**
- **A non-Ansible provisioning backend** — Ansible is locked.

## 7. MVP Scope

### 7.1 In Scope

- `dotfiles-provision {plan, apply, verify, bootstrap}` CLI with `cli-output` rendering.
- `src/provisioning` uv package + hexagonal boundary (`test_layering.py`).
- Domain, ports, adapters, use cases with fakes-based unit tests.
- Declarative manifests + Ansible scaffold + nine roles + aggregate `bootstrap.yaml`.
- Three rendered `settings.toml` files + default palette + compositor skeletons + color fragments.
- `scripts/bootstrap.sh` and integration tests (dry-run, verify, settings-parity, default-palette, spine-chain).
- Multi-distro: Arch (pacman + AUR) and Debian-family (apt).

### 7.2 Out of Scope for MVP

- Phase 2 runtime core and infrastructure adapters. *Deferred to Phase 2.*
- Root `dotfiles` CLI. *Deferred to Phase 2.*
- Content hashing/invalidation. *Deferred to Phase 2+.*
- Persisted provisioning receipts. *Deferred to Phase 2+ only if drift-history need surfaces.*
- `itr dump-config`. *Deferred to Phase 2+ only if needed; provisioning already writes ITR's settings.toml directly.*

## 8. Success Metrics

**Primary**
- **SM-1**: Fresh-machine bootstrap green — from `git clone`, `./scripts/bootstrap.sh` completes with `dotfiles-provision verify` green on a real Arch and a real Debian-family machine. Validates FR-5, FR-25, CAP-4.
- **SM-2**: `dotfiles-provision plan` shows the desired-vs-actual diff and makes no changes on both distros. Validates FR-1, CAP-1.
- **SM-3**: `dotfiles-provision verify` is green after a second consecutive `apply` run (no drift). Validates FR-2, FR-3, NFR-1, CAP-2, CAP-3.

**Secondary**
- **SM-4**: Each of `csg`, `weg`, `itr` invoked with `--config <provisioned-settings>` reads/writes through the install spine with no per-invocation path flags; ITR's `color_scheme.path` chains to CSG's palette output. Validates FR-21, FR-25, CAP-5.
- **SM-5**: `tests/architecture/test_layering.py` passes and a deliberately-violating import fails. Validates FR-24, NFR-4.

**Counter-metrics (do not optimize)**
- **SM-C1**: Do not optimize provisioning *speed* over correctness — a slow, verifiable `bootstrap` is strictly preferred to a fast one that can leave the machine partially provisioned. Counterbalances the natural pull toward skipping `verify` or consolidating roles.
- **SM-C2**: Do not optimize `src/provisioning` size/simplicity to the point of breaking the §11 boundary — importing a forbidden package to "save a few lines" is a hard failure. Counterbalances NFR-5-style convenience.

## 9. Open Questions

The SPEC (`spec-dotfiles-provisioning-phase1`) declares **Open Questions: None**, and the provisioning plan is marked **Approved** with locked decisions applied (2026-08-03). One residual decision surfaced during decomposition (epics story 2.3) is carried forward, not silently assumed resolved:

- **OQ-1: Run-as-user privilege context.** Whether a single run context can satisfy both privileged steps (`makepkg -si`, `pacman`/`apt`) and user-scoped steps (`uv tool install`, `~/.config` symlinks) — or whether the playbook must run under a context that separates them. The playbook run's user must have rights to the privileged steps while user-scoped steps target the intended user; if a single run context cannot satisfy both, this is an open decision for the packages role (FR-14, NFR-1). *Owner: implementation (story 2.3). Revisit condition: before the `packages` role ships.*

## 10. Assumptions Index

No `[ASSUMPTION]` tags were required: every requirement in this PRD is distilled from locked sources (SPEC, chaining-spine, provisioning plan, epics doc), and no new assumptions were added. The SPEC's formal **Assumptions** section (seven items) is inherited as locked — including `default.png` verified present in `wallpapers.tar.gz`, CSG shipping the `conf` (Hyprland) output format, `$XDG_DATA_HOME` defaulting to `~/.local/share` when unset, and the settings-schema facts treated as the contract. These are load-bearing for FR-17/FR-18/FR-19 and the install-dir resolution; readers relying on the PRD should treat them as confirmed, not inferred.

---

### Addendum pointers

Decisions and detail that belong downstream (not in this PRD) are captured in the locked inputs already: the install-dir subtree and per-tool settings contracts live in `chaining-spine.md`; role internals and the repo layout live in `docs/01-dotfiles-provisioning-phase1-plan.md`; architecture rationale lives in `docs/99-dotfiles-hexagonal-architecture.md`; story-level decomposition lives in `epics-dotfiles-provisioning-phase1.md`. This PRD intentionally does not duplicate them.

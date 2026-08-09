---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
inputDocuments:
  - _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md
  - _bmad-output/specs/spec-dotfiles-provisioning-phase1/chaining-spine.md
  - docs/01-dotfiles-provisioning-phase1-plan.md
---

# dotfiles-repo-v3 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for the dotfiles-repo-v3 Phase 1 — Provisioning, decomposing the requirements from the locked SPEC and provisioning plan into implementable stories for a hexagonal Python orchestrator driving Ansible to establish machine state.

## Requirements Inventory

### Functional Requirements

FR-1: Plan Command — `dotfiles-provision plan` diffs desired machine state against actual state before any mutation, making no system changes. The diff is Ansible's native `--check` mode; the Python side reads only `ansible_os_family` via `IFactReader` to select `group_vars/{arch,debian-family}.yml` and never inspects packages itself.
FR-2: Apply Command — `dotfiles-provision apply` runs the Ansible playbooks (check=False) idempotently and re-runnably; a re-run produces no drift. Ansible is the state authority — no `provisioning-state.json` is persisted.
FR-3: Verify Command — `dotfiles-provision verify` asserts all ten done-criteria (install dir, system binaries, CLI tools, assets, settings parse, default palette, compositor configs, filesystem structure, symlinks, §12 preconditions) via `VerifyCapabilityUseCase` without reaching into provisioning internals.
FR-4: Bootstrap Command — `dotfiles-provision bootstrap` runs the aggregate `bootstrap.yaml` end-to-end.
FR-5: Fresh-Machine Bootstrap — `scripts/bootstrap.sh` pre-seeds Python+uv if absent, then runs `uv run --directory ./src/provisioning dotfiles-provision bootstrap`; a fresh Arch or Debian-family machine is fully provisioned from `git clone` + one command (CAP-4).
FR-6: Provisioning Package Scaffold — `src/provisioning` is a standalone uv package with entry point `dotfiles-provision`; deps: `typer`, `pydantic`, `cli-output` (via `uv.sources`), `ansible-core`; dev: `pytest`, `ruff`, `mypy`.
FR-7: Domain Models and Enums — Pure, zero-I/O domain: `MachineState`, `ProvisionManifest`, `ProvisionResult`, `Spec` dataclasses and `Distro`, `Capability`, `CapabilityKind`, `AssetKind` enums.
FR-8: Ports — `IProvisionExecutor` (abstracts `ansible-playbook`, `check: bool`), `IManifestReader`, `IFactReader.os_family()` (thin: selects `group_vars`, never inspects packages).
FR-9: Use Cases — `ProvisionMachineUseCase` (plan=check:True / apply=check:False), `VerifyCapabilityUseCase`, `BootstrapUseCase` wiring ports → use cases.
FR-10: Adapters — `ansible_executor.py` (shells to `ansible-playbook` with `-i`, `--tags`, `--check`, `--extra-vars`; surfaces per-task changed/ok), `yaml_manifest_reader.py` (reads `dotfiles/provisioning/*.yaml`), `ansible_fact_reader.py` (parses `ansible -m setup` for `ansible_os_family`).
FR-11: CLI — Typer app `dotfiles-provision {plan,apply,verify,bootstrap}` in `cli/main.py` + `options.py`, rendering via `cli-output`.
FR-12: Declarative Manifests — `dotfiles/provisioning/{packages,assets,filesystem,symlinks,cli-tools}.yaml` describe desired machine state (packages per manager, assets to deploy, XDG + install-dir subtree, symlink map, csg/weg/itr install specs).
FR-13: Ansible Scaffold — `ansible/inventory/localhost.yaml`, `requirements.yml` (community.general, ansible.posix, kewlfft.aur), `ansible.cfg`, `group_vars/{all,arch,debian-family}.yml`.
FR-14: Packages Role — installs system packages (Hyprland, Hyprpaper, Waybar, fonts) per distro; Arch self-bootstraps `yay` (`base-devel`+`git` → guarded `makepkg -si yay-bin`) then uses `kewlfft.aur.aur` for AUR installs; distro logic stays in `vars/arch.yml`.
FR-15: CLI Tools Role — installs `csg`, `weg`, icon-renderer on PATH via `uv tool install` against repo paths.
FR-16: Filesystem Role — creates XDG config/state/cache dirs, hypr/hyprpaper/waybar dirs, and the full install-dir subtree.
FR-17: Assets Role — unpacks `dotfiles/assets/wallpapers/wallpapers.tar.gz` → `<install>/wallpapers/`, deploys SVG icon templates → `<install>/icon-templates/`, icon color-mapping YAMLs → `<install>/icon-mappings/`, CSG bundled templates → `<install>/csg-templates/`, and emits `weg-effects.yaml` via `weg dump-effects --output`.
FR-18: Default Palette Role — invokes `csg generate <install>/wallpapers/default.png -f conf` (plus standard formats) writing `<install>/generated/palettes/` at apply time; `overwrite=true` scoped to that one task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"`, never written into the rendered settings file.
FR-19: Compositor Configs Role — places Hyprland/Waybar/Hyprpaper static skeletons and copies the default palette color fragments: `colors.conf` (Hyprland) and `colors.css` (Waybar) from the palette dir into `~/.config/{hypr,waybar}/`.
FR-20: Symlinks Role — links every entry in `dotfiles/provisioning/symlinks.yaml` (repo `dotfiles/config/*` → `~/.config/*`).
FR-21: Settings Role — renders the three per-tool `settings.toml` files from Jinja templates pointing at the install dir: CSG `output.directory` → `<install>/generated/palettes`, WEG `output.directory` + `processing.temp_dir`, ITR `output.output_dir` + `templates.dir` + `color_scheme.path`.
FR-22: Verify Role — asserts all §12 preconditions and the ten done-criteria.
FR-23: Compositor Skeleton Configs — adds `dotfiles/config/{hypr,hyprpaper,waybar}/`: Hyprland skeleton starts with `source = ~/.config/hypr/colors.conf`; Waybar `style.css` starts with `@import "colors.css";`; Hyprpaper flat static pointing at `<install>/wallpapers/default.png`.
FR-24: Architecture Layering Test — `tests/architecture/test_layering.py` enforces the in-package hexagon (domain ← ports ← adapters ← application ← cli; domain stdlib allowlist; banned `subprocess`/`os`/`shutil` in domain; ports as ABCs; no Path FS calls in domain) plus Rule 5 cross-package forbidden set (`core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`); only `provisioning` + `cli_output` allowed.
FR-25: Integration Tests — `--check` dry-run of every playbook; verify test that all done-criteria hold after a dry-run bootstrap; settings-file-parity test invoking each tool with `--config <rendered>` asserting it parses; default-palette test asserting `csg generate -f conf` output matches the Hyprland syntax contract.

### NonFunctional Requirements

NFR-1: Idempotency — `apply` is re-runnable with no drift; Ansible is the state authority.
NFR-2: No Persisted Provisioning State — no `provisioning-state.json` in Phase 1; `verify` re-derives state on demand.
NFR-3: Multi-Distro Support — Arch (pacman + AUR) and Debian-family (apt) supported; distro differences isolated to `group_vars/{arch,debian-family}.yml`; the Python orchestrator never branches on distro.
NFR-4: §11 Package Boundary — `src/provisioning` imports `cli-output` only; never `core`, `infrastructure`, or CLI-tool packages; enforced mechanically by `test_layering.py`.
NFR-5: Testability — domain logic is pure with zero I/O; ports are ABCs; adapters testable with fakes; use cases testable with fake ports.
NFR-6: Deterministic Settings — rendered settings files parse exactly with absolute paths baked into the install dir; each tool parses its rendered settings via its `--config` gate.
NFR-7: Verify-Gate Contract — the four §12 runtime preconditions (binaries installed, assets placed, filesystem structure exists, settings files parseable) assertable via `VerifyCapabilityUseCase` without reaching into provisioning internals.
NFR-8: Spine Containment — the install dir is the single place tools read from; wiping `$XDG_DATA_HOME/dotfiles/` leaves nothing orphaned in the XDG config tree.
NFR-9: Bootstrap Reproducibility — from a fresh Arch or Debian-family machine, `git clone && ./scripts/bootstrap.sh` completes with verify green.

### Additional Requirements

- Hexagonal in-package architecture mirroring the `oci-runtime` hexagon.
- Ansible (`ansible-core`) is a runtime dependency of `src/provisioning`, resolved by `uv` from the lockfile — no system-wide Ansible install.
- External collections (`community.general`, `ansible.posix`, `kewlfft.aur`) declared in `ansible/requirements.yml`, resolved via `ansible-galaxy` at bootstrap start.
- Install dir is `$XDG_DATA_HOME/dotfiles/` (default `~/.local/share/dotfiles/`), resolved at plan time.
- AUR strategy: `packages` role self-bootstraps `yay` then uses `kewlfft.aur`; distro logic stays in `vars/arch.yml`.
- CSG templates dir is NOT a settings field — provisioning deploys bundled templates to `<install>/csg-templates/`; Phase 2 runtime invokes CSG with `--templates-dir <install>/csg-templates/`.
- WEG effects catalog is a deployed file: emitted via `weg dump-effects --output <install>/weg-effects.yaml`; WEG effects chain points at it.
- Settings authoring via Ansible `template` module; `csg/weg dump-*` commands are NOT used by provisioning (user-facing conveniences only).
- ITR has no dump command — provisioning writes its `settings.toml` directly (4 keys).
- The rendered settings files keep `overwrite = false`; the default-palette role scopes `overwrite=true` to one task via per-process env override.
- Verify gate pins `icons.yaml`: `itr list <install>/icon-mappings/icons.yaml --config ~/.config/itr/settings.toml` (not `defaults.yaml`, which lacks a `variants` field).
- Wallpaper input to CSG/WEG is a positional CLI arg, never a settings field.
- CSG ships a 9th `conf` (Hyprland) format — provisioning emits `colors.conf` directly via `csg generate -f conf`.

### FR Coverage Map

FR-1: Epic 1 — plan command (Ansible `--check` diff)
FR-2: Epic 1 — apply command (idempotent, re-runnable)
FR-3: Epic 1 — verify command (ten done-criteria)
FR-4: Epic 1 — bootstrap command (aggregate playbook)
FR-5: Epic 3 — scripts/bootstrap.sh fresh-machine flow
FR-6: Epic 1 — provisioning package scaffold
FR-7: Epic 1 — domain models/enums
FR-8: Epic 1 — ports (executor/manifest/fact readers)
FR-9: Epic 1 — use cases
FR-10: Epic 1 — adapters
FR-11: Epic 1 — Typer CLI
FR-12: Epic 2 — declarative manifests
FR-13: Epic 2 — ansible scaffold (inventory/requirements/group_vars)
FR-14: Epic 2 — packages role
FR-15: Epic 2 — cli_tools role
FR-16: Epic 2 — filesystem role
FR-17: Epic 2 — assets role
FR-18: Epic 2 — default_palette role
FR-19: Epic 2 — compositor_configs role
FR-20: Epic 2 — symlinks role
FR-21: Epic 2 — settings role
FR-22: Epic 2 — verify role
FR-23: Epic 2 — compositor skeleton configs
FR-24: Epic 1 — architecture layering test
FR-25: Epic 3 — integration tests

## Epic List

### Epic 1: Provisioning Orchestrator

You can run `dotfiles-provision {plan, apply, verify, bootstrap}` as a hexagonal Python CLI that renders structured output and diffs desired-vs-actual state (Ansible `--check`) before any mutation — testable in isolation with zero I/O.

**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-24

### Epic 2: Machine Provisioning Content

You can provision a real machine: distro-aware packages (incl. AUR via self-bootstrapped `yay`), `csg`/`weg`/`itr` CLI installs, filesystem + install spine, assets (wallpapers, icon templates/mappings, CSG templates, WEG effects), default palette, compositor skeletons + color fragments, symlinks, and the three rendered `settings.toml` files.

**FRs covered:** FR-12, FR-13, FR-14, FR-15, FR-16, FR-17, FR-18, FR-19, FR-20, FR-21, FR-22, FR-23

**Internal story dependency order:** `cli_tools` → `assets` → `default_palette` → `compositor_configs` → `settings` (FR-18 needs FR-15 + FR-17; FR-21 needs the install-dir seam resolved by the orchestrator). All roles live in the `src/provisioning/ansible/` + `dotfiles/provisioning/` trees, so this stays a single epic with ordered stories — no cross-epic file churn.

### Epic 3: Reproducible Bootstrap & Verified Install

You can reproduce any machine from scratch: `git clone && ./scripts/bootstrap.sh` completes with `verify` green, and integration tests lock the ten done-criteria as a contract Phase 2 may assume.

**FRs covered:** FR-5, FR-25

### Cross-Epic Contracts

Load-bearing seams between epics, resolved by the orchestrator (Epic 1) and consumed by the Ansible content (Epic 2):

- **Install-dir seam:** the orchestrator resolves `$XDG_DATA_HOME/dotfiles/` at plan time and passes it to `ansible-playbook` via `--extra-vars` (in `ansible_executor`). Epic 2's `settings` templates and `default_palette`/`compositor_configs` roles consume that value to bake absolute paths into rendered files.
- **OS-family seam:** `IFactReader.os_family()` (Epic 1) selects `group_vars/{arch,debian-family}.yml` (Epic 2). The `group_vars` filename naming is a shared contract both sides must honor.
- **Verify-gate dependency:** Epic 3's integration tests and verify gate require Epic 2's rendered settings + deployed icon-mappings. This is intentional — Epic 3 is the acceptance gate, not a functional prerequisite for Epic 1 or 2.

### Hardening Notes (from inversion analysis)

Failure paths identified and the mitigations to carry into story creation:

- **Seam contract lock:** Epic 1 must carry a test pinning the exact `--extra-vars` names (`install_dir`, `os_family`) passed by `ansible_executor`, so Epic 2 templates can never silently diverge from the seam.
- **Parse ≠ works:** Epic 3's settings-parity test must assert rendered spine paths *resolve to existing directories*, not merely that the settings file parses. Verify must check the *target* of each path, not just parseability.
- **Dry-run must be dry:** Epic 2's AUR `yay` self-bootstrap task and Epic 3's dry-run integration test need an explicit "no mutation in `--check` mode" acceptance criterion — the guarded `makepkg -si yay-bin` must never build under `--check`.
- **Machine, not repo:** `verify.yaml` must assert against provisioned locations (`~/.config/...`, install dir), not the repo checkout, so the gate cannot go green while the machine is unprovisioned.
- **Story size budget:** Epic 2 (12 FRs, 9 roles, 10 playbooks, 3 templates, 3 skeleton configs) must be cut into stories small enough for a single dev-agent context.

<!-- Repeat for each epic in epics_list (N = 1, 2, 3...) -->

## Epic 1: Provisioning Orchestrator

You can run `dotfiles-provision {plan, apply, verify, bootstrap}` as a hexagonal Python CLI that renders structured output and diffs desired-vs-actual state (Ansible `--check`) before any mutation — testable in isolation with zero I/O.

**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11, FR-24

### Story 1.1: Scaffold the Provisioning Package

As an operator,
I want a `src/provisioning` uv package with a `dotfiles-provision` entry point,
So that the provisioning tool can be built, installed, and extended incrementally.

**Acceptance Criteria:**

**Given** the repository working tree
**When** I create the `src/provisioning` uv package scaffold
**Then** `pyproject.toml` exists with package name `dotfiles-provision`, entry point `dotfiles-provision`, and dependencies `typer`, `pydantic`, `cli-output` (via `uv.sources`), `ansible-core`
**And** dev dependencies include `pytest`, `ruff`, `mypy`
**And** a stub CLI invoking `cli-output` renders a version string and exits 0
**And** the package layout mirrors `src/shared/cli-output/` structure with `src/provisioning/`, `tests/`, and `pyproject.toml`
**And** `uv lock` resolves without errors (FR-6)

### Story 1.2: Domain Models and Enums

As an operator,
I want pure, zero-I/O domain models representing machine state,
So that provisioning logic is testable in isolation without touching the filesystem.

**Acceptance Criteria:**

**Given** the domain module under `src/provisioning/domain/`
**When** I implement `models.py` and `enums.py`
**Then** `MachineState`, `ProvisionManifest`, `ProvisionResult`, and `Spec` are defined as frozen dataclasses with typed fields
**And** `Distro`, `Capability`, `CapabilityKind`, and `AssetKind` are defined as `StrEnum` enums
**And** no domain module imports `os`, `subprocess`, `shutil`, `pathlib`, or any I/O library
**And** unit tests exercise construction, validation, and equality with zero fixtures or temp files (FR-7, NFR-5)

### Story 1.3: Hexagonal Boundary Lock

As an architect,
I want a mechanical test enforcing the provisioning package boundary,
So that `src/provisioning` can never silently import forbidden packages.

**Acceptance Criteria:**

**Given** the approved §11 boundary
**When** I implement `tests/architecture/test_layering.py`
**Then** the test asserts the in-package dependency order: domain ← ports ← adapters ← application ← cli
**And** the test asserts the domain stdlib allowlist and bans `subprocess`, `os`, `shutil`, and Path FS calls in domain
**And** the test asserts ports are ABCs
**And** the test asserts the Rule 5 cross-package forbidden set (`core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`) is never imported
**And** only `provisioning` and `cli_output` are allowed cross-package
**And** a deliberately-violating import fails the test (FR-24, NFR-4)

### Story 1.4: Ports

As an operator,
I want explicit port abstractions for provisioning execution,
So that adapters and use cases stay decoupled and testable.

**Acceptance Criteria:**

**Given** the port module under `src/provisioning/ports/`
**When** I implement `IProvisionExecutor`, `IManifestReader`, and `IFactReader`
**Then** `IProvisionExecutor` abstracts `ansible-playbook` with a `check: bool` parameter
**And** `IManifestReader` reads `dotfiles/provisioning/*.yaml` manifests
**And** `IFactReader` exposes `os_family() -> str` selecting `group_vars` without inspecting packages
**And** all three are abstract base classes (Protocol-compatible) that raise `NotImplementedError` on unimplemented methods
**And** unit tests verify each port's interface contract with fakes (FR-8, NFR-5)

### Story 1.5: Adapters

As an operator,
I want concrete adapters implementing the provisioning ports,
So that the orchestrator can read manifests, detect OS family, and drive `ansible-playbook`.

**Acceptance Criteria:**

**Given** the adapter module under `src/provisioning/adapters/`
**When** I implement `yaml_manifest_reader.py`, `ansible_fact_reader.py`, and `ansible_executor.py`
**Then** `YamlManifestReader` parses `dotfiles/provisioning/*.yaml` into domain `ProvisionManifest` objects
**And** `AnsibleFactReader` parses `ansible -m setup` output for `ansible_os_family`
**And** `AnsibleExecutor` shells to `ansible-playbook` with `-i`, `--tags`, `--check`, and `--extra-vars`, surfacing per-task changed/ok results
**And** a seam contract test asserts `AnsibleExecutor` passes exactly the extra-var keys `install_dir` and `os_family` (values from the resolved install dir and `IFactReader`)
**And** an unknown/unexpected `os_family` value fails loudly with a clear error rather than defaulting silently (no silent fallback)
**And** all adapters are unit-tested with fakes — no real `ansible-playbook` invocation (FR-10, hardening: seam contract lock)

### Story 1.6: Provision Use Case

As an operator,
I want a `ProvisionMachineUseCase` that plans or applies machine state,
So that I can diff desired-vs-actual state before mutating the machine.

**Acceptance Criteria:**

**Given** the application module under `src/provisioning/application/`
**When** I implement `ProvisionMachineUseCase`
**Then** running it with `check=True` executes the executor in plan mode and makes no system changes
**And** running it with `check=False` executes the executor in apply mode
**And** the use case resolves `os_family` via `IFactReader` to select `group_vars/{arch,debian-family}.yml`
**And** it resolves the install dir (`$XDG_DATA_HOME/dotfiles/`, default `~/.local/share/dotfiles/`) at plan time and passes it via the seam extra-vars
**And** unit tests verify plan/apply behavior with fake ports (FR-9, FR-1, FR-2, NFR-1)

### Story 1.7: Verify and Bootstrap Use Cases

As an operator,
I want `VerifyCapabilityUseCase` and `BootstrapUseCase`,
So that I can assert runtime preconditions and run the full aggregate provisioning.

**Acceptance Criteria:**

**Given** the application module under `src/provisioning/application/`
**When** I implement `VerifyCapabilityUseCase` and `BootstrapUseCase`
**Then** `VerifyCapabilityUseCase` asserts the four §12 runtime preconditions (binaries installed, assets placed, filesystem structure exists, settings files parseable) without reaching into provisioning internals
**And** `BootstrapUseCase` runs the aggregate `bootstrap.yaml` end-to-end
**And** unit tests verify each use case with fake ports (FR-9, FR-3, FR-4, NFR-7)

### Story 1.8: Typer CLI

As an operator,
I want a `dotfiles-provision` CLI exposing `plan`, `apply`, `verify`, and `bootstrap`,
So that I can drive provisioning from a terminal with structured output.

**Acceptance Criteria:**

**Given** the CLI module under `src/provisioning/cli/`
**When** I implement `main.py` (Typer app) and `options.py`
**Then** `dotfiles-provision plan` runs `ProvisionMachineUseCase` with `check=True`
**And** `dotfiles-provision apply` runs `ProvisionMachineUseCase` with `check=False`
**And** `dotfiles-provision verify` runs `VerifyCapabilityUseCase`
**And** `dotfiles-provision bootstrap` runs `BootstrapUseCase`
**And** all commands render output through `cli-output` (JSON by default)
**And** CLI tests use Typer `CliRunner` with mock deps on `ctx.obj`, and each command exits 0 on success and non-zero with a structured error on failure (FR-11, FR-1, FR-2, FR-3, FR-4, NFR-2)

## Epic 2: Machine Provisioning Content

You can provision a real machine: distro-aware packages (incl. AUR via self-bootstrapped `yay`), `csg`/`weg`/`itr` CLI installs, filesystem + install spine, assets (wallpapers, icon templates/mappings, CSG templates, WEG effects), default palette, compositor skeletons + color fragments, symlinks, and the three rendered `settings.toml` files.

**FRs covered:** FR-12, FR-13, FR-14, FR-15, FR-16, FR-17, FR-18, FR-19, FR-20, FR-21, FR-22, FR-23

### Story 2.1: Declarative Manifests

As an operator,
I want `dotfiles/provisioning/*.yaml` manifests describing desired machine state,
So that provisioning is data-driven and the orchestrator can read desired state from the repo.

**Acceptance Criteria:**

**Given** the `dotfiles/provisioning/` directory
**When** I author `packages.yaml`, `assets.yaml`, `filesystem.yaml`, `symlinks.yaml`, and `cli-tools.yaml`
**Then** `packages.yaml` lists the verified logical package set (`hyprland`, `hyprpaper`, `waybar`, `fonts`) — per-manager names resolve in Ansible `group_vars` (Story 2.2/2.3), per NFR-3 (interpretation ratified 2026-08-08)
**And** `assets.yaml` lists wallpapers + icon templates + icon mappings to deploy
**And** `filesystem.yaml` describes the XDG + install-dir subtree layout
**And** `symlinks.yaml` maps repo `dotfiles/config/*` to `~/.config/*`
**And** `cli-tools.yaml` specifies csg/weg/itr install specs (`uv tool install` targets)
**And** every manifest parses with `YamlManifestReader` (Story 1.5) into domain `ProvisionManifest` objects
**And** manifest content matches the verified package set and existing assets from the plan (§4/§6) — no empty or typo'd package/asset lists (FR-12)

### Story 2.2: Ansible Scaffold

As an operator,
I want the Ansible project scaffold in place,
So that playbooks can run against the local host with distro-aware group variables.

**Acceptance Criteria:**

**Given** the `src/provisioning/ansible/` directory
**When** I create the scaffold
**Then** `inventory/localhost.yaml` targets the local host
**And** `requirements.yml` declares `community.general`, `ansible.posix`, and `kewlfft.aur`
**And** `ansible.cfg` configures inventory and roles paths
**And** `group_vars/all.yml`, `group_vars/arch.yml`, and `group_vars/debian-family.yml` exist with per-distro package settings (the `arch`/`debian-family` filenames matching the `IFactReader.os_family()` seam contract)
**And** distro differences are isolated to `group_vars` — no distro branching in Python or `bootstrap.sh` (FR-13, NFR-3)

### Story 2.3: Packages Role

As an operator,
I want a `packages` role that installs system packages per distro,
So that Hyprland, Hyprpaper, Waybar, and fonts are present on the machine.

**Acceptance Criteria:**

**Given** the `roles/packages/` role
**When** I implement `tasks/main.yml` and `vars/{main,arch,debian}.yml`
**Then** Arch uses `pacman` and self-bootstraps `yay` (`base-devel`+`git` → guarded `makepkg -si yay-bin`, skipping if `yay` present) then drives AUR installs via `kewlfft.aur`
**And** Debian-family uses `apt` for the same package set
**And** distro logic lives in `vars/arch.yml`/`vars/debian.yml` only
**And** a `--check` run reports would-change without ever executing `makepkg` or mutating the host (hardening: dry-run must be dry)
**And** the role is idempotent — a re-run reports no drift
**And** the privilege context is explicitly defined: the playbook run's user has the rights to run `makepkg -si` and `pacman`/`apt`, while user-scoped steps (`uv tool install`, `~/.config` symlinks) target the intended user — or, if a single run context cannot satisfy both, this is recorded as an open question for the run-as-user decision (FR-14, NFR-1)

### Story 2.4: CLI Tools Role

As an operator,
I want a `cli_tools` role that installs the dotfiles CLIs,
So that `csg`, `weg`, and icon-renderer are available on PATH.

**Acceptance Criteria:**

**Given** the `roles/cli_tools/` role
**When** I implement `tasks/main.yml`
**Then** `csg`, `weg`, and icon-renderer are installed via `uv tool install` against the repo package paths
**And** each installed binary is on PATH after the role completes
**And** the role is idempotent (re-run produces no changed state for already-installed tools)
**And** `--check` reports would-change without installing (FR-15)

### Story 2.5: Filesystem Role

As an operator,
I want a `filesystem` role that creates the machine layout,
So that XDG dirs and the install-spine subtree exist before assets land.

**Acceptance Criteria:**

**Given** the `roles/filesystem/` role
**When** I implement `tasks/main.yml`
**Then** XDG config/state/cache dirs are created
**And** `~/.config/{hypr,hyprpaper,waybar}/` dirs are created
**And** the install-dir subtree exists: `wallpapers/`, `icon-templates/`, `icon-mappings/`, `csg-templates/`, `weg-effects.yaml` location, and `generated/{palettes,effects,icons,.weg-tmp}/`
**And** dirs are created only where missing (idempotent) (FR-16, NFR-8)

### Story 2.6: Assets Role

As an operator,
I want an `assets` role that deploys wallpaper, icon, template, and effect-catalog assets,
So that the tools have everything they need to read from the install spine.

**Acceptance Criteria:**

**Given** the `roles/assets/` role
**When** I implement `tasks/main.yml`
**Then** `dotfiles/assets/wallpapers/wallpapers.tar.gz` unpacks to `<install>/wallpapers/` (including `default.png`)
**And** SVG icon templates deploy to `<install>/icon-templates/`
**And** icon color-mapping YAMLs deploy to `<install>/icon-mappings/`
**And** CSG bundled templates deploy to `<install>/csg-templates/`
**And** `weg dump-effects --output <install>/weg-effects.yaml` emits the effects catalog
**And** every task is idempotent (FR-17)

### Story 2.7: Default Palette Role

As an operator,
I want a `default_palette` role that generates the default palette at apply time,
So that first-boot colors exist and regenerate when the default wallpaper changes.

**Acceptance Criteria:**

**Given** the `roles/default_palette/` role
**When** I implement `tasks/main.yml`
**Then** it invokes `csg generate <install>/wallpapers/default.png -f conf` (plus standard formats) writing to `<install>/generated/palettes/`
**And** `overwrite=true` is scoped to that single task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"`
**And** the rendered `~/.config/color-scheme-generator/settings.toml` keeps `overwrite = false`
**And** the emitted `colors.conf` matches the Hyprland syntax contract (verified by the default-palette test)
**And** `default.png` presence is asserted after the wallpaper unpack (Story 2.6) — the task fails loudly if the tarball regresses
**And** replacing `wallpapers.tar.gz` in the repo causes the next `apply` to regenerate (FR-18)

### Story 2.8: Compositor Skeleton Configs

As an operator,
I want static skeleton compositor configs in the repo,
So that the compositor_configs role has source files to place.

**Acceptance Criteria:**

**Given** the `dotfiles/config/{hypr,hyprpaper,waybar}/` directories
**When** I author the skeleton configs
**Then** `dotfiles/config/hypr/hyprland.conf` starts with `source = ~/.config/hypr/colors.conf`
**And** `dotfiles/config/waybar/style.css` starts with `@import "colors.css";`
**And** `dotfiles/config/hyprpaper/hyprpaper.conf` is flat static pointing at `<install>/wallpapers/default.png`
**And** existing `dotfiles/config/{nvim,starship,wlogout,zsh}/` dirs are unchanged (FR-23)

### Story 2.9: Compositor Configs Role

As an operator,
I want a `compositor_configs` role that places skeletons and color fragments,
So that Hyprland/Waybar render with first-boot colors.

**Acceptance Criteria:**

**Given** the `roles/compositor_configs/` role
**When** I implement `tasks/main.yml`
**Then** it copies `dotfiles/config/{hypr,hyprpaper,waybar}/` skeletons to `~/.config/{hypr,hyprpaper,waybar}/`
**And** it copies `<install>/generated/palettes/colors.conf` → `~/.config/hypr/colors.conf`
**And** it copies `<install>/generated/palettes/colors.css` → `~/.config/waybar/colors.css`
**And** the skeleton files themselves never change on re-run (only the fragment files are overwrite candidates)
**And** all tasks are idempotent
**And** the "skeletons never change; fragments are the Phase 2 overwrite target" invariant is documented as load-bearing for Phase 2 (FR-19)

### Story 2.10: Symlinks Role

As an operator,
I want a `symlinks` role that links repo configs into `~/.config/`,
So that my dotfiles live in the repo and are referenced by the machine.

**Acceptance Criteria:**

**Given** the `roles/symlinks/` role
**When** I implement `tasks/main.yml`
**Then** every entry in `dotfiles/provisioning/symlinks.yaml` is created as a symlink from repo `dotfiles/config/*` to `~/.config/*`
**And** broken or missing targets are reported as failures
**And** re-runs are idempotent (existing symlinks are left unchanged) (FR-20)

### Story 2.11: Settings Role

As an operator,
I want a `settings` role that renders the three `settings.toml` files,
So that each tool reads from and writes to the install spine with no per-invocation path flags.

**Acceptance Criteria:**

**Given** the `roles/settings/` role with `templates/{csg,weg,itr}-settings.toml.j2` and `vars/main.yml`
**When** I implement the role
**Then** CSG settings render `output.directory` → `<install>/generated/palettes` and keep `overwrite = false`
**And** WEG settings render `output.directory` → `<install>/generated/effects` and `processing.temp_dir` → `<install>/generated/.weg-tmp`
**And** ITR settings render `output.output_dir` → `<install>/generated/icons`, `templates.dir` → `<install>/icon-templates`, and `color_scheme.path` → `<install>/generated/palettes/colors.yaml`
**And** absolute install-dir paths come from the orchestrator seam extra-var (`install_dir`), never hardcoded
**And** an undefined/empty `install_dir` fails loudly during render (Jinja undefined handling or pre-render validation) — no `None/generated/...` or empty-path settings files
**And** the templates are Jinja-rendered by Ansible's `template` module — `csg/weg dump-*` commands are not used
**And** each rendered file parses via its tool's `--config` gate (CSG `info`, WEG `info`, ITR `list`) (FR-21, NFR-6, NFR-8)

### Story 2.12: Verify Role and Aggregate Bootstrap Playbook

As an operator,
I want a `verify` role plus the aggregate `bootstrap.yaml`,
So that all preconditions and done-criteria are assertable in one run.

**Acceptance Criteria:**

**Given** the `roles/verify/` role and playbooks
**When** I implement `tasks/main.yml`, `verify.yaml`, and the aggregate `bootstrap.yaml`
**Then** `verify.yaml` asserts the ten done-criteria including: install-dir subtree, system binaries on PATH, `csg`/`weg`/icon-renderer on PATH, assets deployed, per-tool settings parse, default palette files present, compositor configs + fragments placed, filesystem structure, symlinks resolved, and §12 preconditions
**And** verification asserts against provisioned locations (`~/.config/...`, install dir), not the repo checkout (hardening: machine, not repo)
**And** the ITR settings-parse gate uses `itr list <install>/icon-mappings/icons.yaml --config ~/.config/itr/settings.toml` (not `defaults.yaml`)
**And** `bootstrap.yaml` aggregates all role playbooks in dependency order (`packages` → `cli_tools` → `filesystem` → `assets` → `default_palette` → `compositor_configs` → `symlinks` → `settings` → `verify`)
**And** `bootstrap.yaml --check` completes cleanly without mutation (FR-22, FR-3, hardening: dry-run must be dry)

## Epic 3: Reproducible Bootstrap & Verified Install

You can reproduce any machine from scratch: `git clone && ./scripts/bootstrap.sh` completes with `verify` green, and integration tests lock the ten done-criteria as a contract Phase 2 may assume.

**FRs covered:** FR-5, FR-25

### Story 3.1: Fresh-Machine Bootstrap Script

As an operator,
I want `scripts/bootstrap.sh` that pre-seeds Python+uv and runs the provisioner,
So that any fresh machine can be fully provisioned in one command.

**Acceptance Criteria:**

**Given** a fresh machine with only a shell and git
**When** I run `git clone <repo> && ./scripts/bootstrap.sh`
**Then** Python and `uv` are pre-seeded if absent (no pre-install step)
**And** `ansible-galaxy` collection resolution (`requirements.yml`) happens at bootstrap start, and a resolution failure (e.g. missing network) aborts with a loud, helpful error instead of proceeding with missing modules
**And** `uv run --directory ./src/provisioning dotfiles-provision bootstrap` executes the aggregate playbook end-to-end
**And** the run completes with `dotfiles-provision verify` green against all ten done-criteria
**And** the script works on both Arch and Debian-family targets (FR-5, NFR-9)

### Story 3.2: Playbook Dry-Run Integration Tests

As an operator,
I want integration tests that dry-run every playbook,
So that the whole provisioning surface is exercised without mutating the host.

**Acceptance Criteria:**

**Given** the integration test suite under `src/provisioning/tests/integration/`
**When** I implement `test_ansible_dryrun.py` and related tests
**Then** every playbook runs with `--check` and completes cleanly, and the run reports the would-be plan without applying it
**And** a separate apply+verify test (on a disposable/container target) asserts the ten done-criteria hold after a real `apply` followed by `verify` — not after `--check`, which cannot leave state behind
**And** the AUR `yay` self-bootstrap task never builds under `--check` (asserted — no mutation in dry-run mode) (hardening: dry-run must be dry)
**And** the tests invoke real `ansible-playbook --check`, not fakes (FR-25)

### Story 3.3: Settings-Parity and Default-Palette Integration Tests

As an operator,
I want integration tests that prove the rendered settings and palette contract,
So that the install spine truly works — not merely that files parse.

**Acceptance Criteria:**

**Given** the integration test suite
**When** I implement the settings-parity and default-palette tests
**Then** a settings-file-parity test invokes `csg info --config <rendered>`, `weg info --config <rendered>`, and `itr list <install>/icon-mappings/icons.yaml --config <rendered>` and each exits 0
**And** the parity test asserts each rendered spine path *resolves to an existing directory*, not merely that the settings file parses (hardening: parse ≠ works)
**And** a default-palette test runs `csg generate -f conf` and asserts the output matches the Hyprland `colors.conf` syntax contract and `$accent` equals `$color1`
**And** a spine-chain test asserts ITR's `color_scheme.path` resolves to a real CSG palette output
**And** a Phase 2 invocation-contract assertion tests that CSG invoked with `--templates-dir <install>/csg-templates/` renders from the spine templates, so the Phase 2 per-invocation contract is testable rather than silently falling back to bundled defaults (FR-25, NFR-6, CAP-5)

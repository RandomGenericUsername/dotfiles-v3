# `dotfiles-repo-v3`
# Architecture & System Design Reference

> **State note (2026-08-16):** this document is the dual-domain architecture
> vision. **Domain 1 (Machine Provisioning) is IMPLEMENTED** — see
> `docs/01-dotfiles-provisioning-phase1-plan.md` and
> `docs/02-config-in-spine-pattern.md` for the concrete provisioning design.
> **Domain 2 (Runtime Desktop Reconciliation) is PLANNED, not built** — the
> sections below describing the runtime core (state model, hashing,
> reconciliation, persistence, reactive runtime, phases 2–6) are the roadmap
> for Phase 2+; `src/core/` and `src/infrastructure/` do not exist yet.

---

# 1. Project Overview

`dotfiles-repo-v3` is a desktop orchestration platform for Linux environments.

The system manages, derives, reconciles, and applies desktop state across:

- wallpapers
- generated color schemes
- icon rendering
- compositor configuration
- status bar theming
- desktop visual effects
- derived configuration artifacts

The project integrates multiple standalone CLI tools and coordinates them through a centralized orchestration model.

The architecture intentionally treats the desktop as a coherent stateful system rather than a collection of unrelated scripts.

---

# 2. Core Philosophy

The project is based on a foundational idea:

> Desktop configuration should be deterministic, reproducible, and state-aware.

Traditional dotfiles systems usually evolve into:

- shell script collections
- ad-hoc hooks
- implicit orchestration
- duplicated logic
- fragile dependency chains

Example:

```text
set wallpaper
    ↓
run pywal
    ↓
rewrite configs
    ↓
reload waybar
    ↓
regenerate icons
```

This works initially but eventually introduces:

| Problem | Consequence |
|---|---|
| No state tracking | Impossible to know what is outdated |
| No dependency graph | Excessive recomputation |
| No invalidation strategy | Stale assets |
| Tight coupling | Difficult extensibility |
| Script sprawl | Poor maintainability |
| Implicit orchestration | Fragile execution |
| Side-effect execution | Hard debugging |

The purpose of this architecture is to replace implicit orchestration with explicit reconciliation.

---

# 3. The Most Important Architectural Insight

The project is NOT fundamentally:

```text
a wallpaper manager
```

or:

```text
a CLI wrapper collection
```

The project is fundamentally:

# A Desktop State Reconciliation Engine

The wallpaper is not the final product.

The wallpaper is an input signal that causes:

- derived assets to become invalid
- themes to require regeneration
- configs to require rewriting
- desktop applications to require reload
- runtime state to require convergence

This means the architecture is conceptually closer to:

- Nix
- Terraform
- Bazel
- Kubernetes reconciliation loops
- build systems

than to a traditional CRUD application.

---

# 4. Dual-Domain Architecture

One of the most important architectural findings is that the project actually contains TWO distinct orchestration domains.

---

# Domain 1 — Machine Provisioning

Responsible for:

- package installation
- binary installation
- asset deployment
- filesystem setup
- symlink creation
- environment preparation
- runtime dependency setup
- desktop package provisioning

Examples:

- install Hyprland
- install Waybar
- install fonts
- install CLI tools
- place wallpapers
- place icon themes
- create filesystem structure

This domain is responsible for:

```text
Machine State Reconciliation
```

> **IMPLEMENTED (Domain 1):** `src/provisioning` — a hexagonal Python
> orchestrator (`dotfiles-provision`) driving Ansible. Concrete roles:
> packages, cli_tools, filesystem, assets, default_palette,
> compositor_configs, config_copies, settings, config_links (config-in-spine
> symlinks), icons (`itr render`), verify. Entry points:
> `scripts/bootstrap.sh` (fresh machine) and `dotfiles-provision
> {plan,apply,verify,bootstrap}`.

---

# Domain 2 — Runtime Desktop Reconciliation

Responsible for:

- wallpaper transitions
- cache invalidation
- artifact generation
- config regeneration
- desktop convergence
- runtime orchestration
- derived state reconciliation

This domain is responsible for:

```text
Desktop Runtime State Reconciliation
```

---

# 5. Why The Domain Separation Matters

This separation is critically important.

Provisioning and runtime orchestration evolve differently.

They solve different problems.

They have different lifecycles.

---

# Provisioning Concerns

Provisioning concerns include:

- apt
- pacman
- yay
- package installation
- symlink management
- asset copying
- system services
- filesystem ownership

These are machine-level concerns.

---

# Runtime Concerns

Runtime concerns include:

- wallpaper state
- derived artifacts
- invalidation
- reconciliation
- regeneration
- desktop convergence

These are runtime orchestration concerns.

---

# Critical Rule

The runtime orchestration core must NEVER become responsible for:

- package installation
- binary provisioning
- system bootstrap
- distro setup
- filesystem provisioning

Those concerns belong to provisioning.

---

# 6. Layered System Architecture

The project therefore becomes a layered architecture.

```text
┌────────────────────────────────┐
│  Provisioning Layer            │
│  (Machine Reconciliation)      │
│                                │
│  - packages                    │
│  - binaries                    │
│  - assets                      │
│  - filesystem                  │
│  - symlinks                    │
│  - dependencies                │
└────────────────────────────────┘
                ↓
┌────────────────────────────────┐
│  Runtime Reconciliation Layer  │
│                                │
│  - desktop state               │
│  - invalidation                │
│  - derivation                  │
│  - regeneration                │
│  - convergence                 │
└────────────────────────────────┘
                ↓
┌────────────────────────────────┐
│  Desktop Environment           │
└────────────────────────────────┘
```

---

# 7. Provisioning Enables Runtime

This becomes a foundational principle.

```text
Provisioning
    ↓
creates operational environment
    ↓
Runtime orchestration
    ↓
converges desktop state
```

The runtime system assumes the operational environment already exists.

This is a VALID architectural assumption because provisioning guarantees it.

> **Implemented guarantee:** `dotfiles-provision verify` (Ansible `verify`
> role) asserts the eleven done-criteria against **provisioned locations only**
> — never the repo — so "the environment exists" is a mechanically-checked
> contract, not a hope. The runtime may assume `verify` green.

---

# 8. Architectural Style

The runtime orchestration system uses:

# Hexagonal Architecture (Ports & Adapters)

---

# 8.0 Note: the implemented hexagon is in PROVISIONING

The v2 plan assigned hexagonal architecture to the runtime core. As built, the
hexagon lives in **`src/provisioning/src/provisioning/`** — domain/ports/
adapters/application/cli with the in-package layering enforced mechanically by
`tests/architecture/test_layering.py` (domain stdlib allowlist, banned
`subprocess`/`os`/`shutil` in domain, ports as ABCs, no Path FS calls in
domain, cross-package forbidden set). The runtime core (Domain 2) is intended
to follow the same style when Phase 2 starts.

---

# 8.1 Core Principle

Dependencies point inward.

```text
Infrastructure → Core
```

never:

```text
Core → Infrastructure
```

---

# 8.2 The Core Owns

The core owns:

- desktop state
- invalidation
- orchestration
- reconciliation
- execution planning
- domain rules

---

# 8.3 Infrastructure Owns

Infrastructure owns:

- subprocess execution
- filesystem access
- desktop integrations
- external CLI invocation
- persistence backends

---

# 9. Repository Structure

```text
dotfiles-repo-v3/
│
├── src/
│   │
│   ├── provisioning/            ← Machine provisioning domain (IMPLEMENTED)
│   │   ├── src/provisioning/    ← Hexagonal Python orchestrator
│   │   │   ├── domain/          ←   pure dataclasses/enums (MachineState, ProvisionResult, ...)
│   │   │   ├── ports/           ←   IProvisionExecutor, IFactReader (ABCs)
│   │   │   ├── adapters/        ←   ansible_executor, ansible_fact_reader, yaml_manifest_reader
│   │   │   ├── application/     ←   use cases: plan/apply/verify/bootstrap
│   │   │   └── cli/             ←   Typer app `dotfiles-provision {plan,apply,verify,bootstrap,version}`
│   │   ├── ansible/             ← the state authority provisioning drives
│   │   │   ├── playbooks/       ←   11 per-role playbooks + aggregate bootstrap.yaml
│   │   │   ├── roles/           ←   packages, cli_tools, filesystem, assets, default_palette,
│   │   │   │                        compositor_configs, config_copies, settings, config_links,
│   │   │   │                        icons, verify
│   │   │   ├── inventory/       ←   localhost.yaml
│   │   │   ├── group_vars/      ←   {all,arch,debian-family}.yml (distro isolation)
│   │   │   ├── ansible.cfg
│   │   │   └── requirements.yml
│   │   ├── tests/               ←   unit + architecture-layering tests
│   │   └── pyproject.toml       ←   uv package `dotfiles-provision`
│   │
│   ├── cli-tools/               ← Standalone compute providers (IMPLEMENTED)
│   │   ├── color-scheme-generator/    (csg)
│   │   ├── wallpaper-effects-generator/ (weg)
│   │   └── icon-templates-renderer/   (itr)
│   │
│   └── shared/                  ← Shared libraries (IMPLEMENTED)
│       ├── cli-output/
│       ├── config-assembler-engine/
│       └── oci-runtime/
│
├── dotfiles/                    ← declarative manifests + config + assets sources
├── docs/
└── (runtime core/ and infrastructure/ are Phase 2+ — NOT yet present)
```

> **Drift from v2 plan:** the original plan had `core/`, `infrastructure/`,
> and a flat `provisioning/{packages,assets,filesystem,bootstrap}`. The
> implemented provisioning domain is a **hexagonal Python package driving
> Ansible** (the hexagon lives in provisioning, not runtime); `cli-tools` uses
> the actual tool names; a `shared/` layer exists for cross-tool libraries.
> `src/core/` and `src/infrastructure/` (runtime) remain future work.

---

# 10. Why `provisioning/` Instead of `installer/`

The term:

```text
installer
```

sounds procedural.

The term:

```text
provisioning
```

better communicates:

```text
machine state reconciliation
```

which is what the system is actually doing.

This terminology more accurately reflects the architecture.

---

# 11. Bounded Context Separation

Provisioning and runtime orchestration should be treated as separate bounded contexts.

---

# Provisioning Context

Responsible for:

- machine capabilities
- package state
- filesystem layout
- runtime prerequisites

---

# Runtime Context

Responsible for:

- desktop convergence
- runtime state
- derivation
- invalidation
- reconciliation

---

# Critical Architectural Boundary

Provisioning should NOT know:

- wallpaper invalidation rules
- desktop reconciliation logic
- runtime cache policies

Runtime orchestration should NOT know:

- apt
- pacman
- package installation
- symlink provisioning
- filesystem bootstrap

This separation must remain strict.

---

# 12. Runtime Assumptions

The runtime orchestration layer assumes:

- binaries are installed
- wallpapers exist
- assets exist
- filesystem structure exists
- config directories exist
- dependencies are available

Provisioning guarantees these assumptions.

This dramatically simplifies runtime orchestration complexity.

---

# 13. Core Runtime Model

The runtime system revolves around:

- desktop state
- derived artifacts
- invalidation
- reconciliation
- execution planning

NOT around:

- subprocesses
- shell commands
- tools

---

# 14. Desktop State Model

```python
@dataclass
class DesktopState:
    wallpaper: WallpaperState
    theme: ThemeState
    artifacts: list[DerivedArtifact]
```

---

# 14.1 Wallpaper State

```python
@dataclass
class WallpaperState:
    path: Path
    content_hash: str
    applied_at: datetime
```

---

# 14.2 Theme State

```python
@dataclass
class ThemeState:
    palette_hash: str
    generated_at: datetime
```

---

# 14.3 Derived Artifact

```python
@dataclass
class DerivedArtifact:
    kind: ArtifactKind
    source_hash: str
    artifact_hash: str
    generated_at: datetime
```

This becomes the foundation for:

- invalidation
- caching
- reconciliation
- reuse

---

# 15. Content Hashing Strategy

The system should use content-addressed derivation.

Hash:

- wallpaper contents
- templates
- tool configs
- generator inputs
- derived artifacts

NOT filenames.

---

# Correct

```text
wallpaper content changed
    → invalidate palette
```

---

# Incorrect

```text
wallpaper filename changed
```

---

# 16. Derived Artifact Model

Generated outputs are treated as derived artifacts.

Examples:

| Artifact | Derived From |
|---|---|
| Color palette | Wallpaper |
| Waybar theme | Palette |
| Icon theme | Theme state |
| Blur effects | Wallpaper |
| Config files | Multiple inputs |

---

# 17. Runtime Reconciliation Model

The architecture should evolve toward reconciliation-based orchestration.

---

# Desired State

Represents what the desktop SHOULD look like.

---

# Actual State

Represents what currently exists.

---

# Reconciliation

Computes differences.

---

# Execution Plan

Determines required work.

---

# High-Level Runtime Flow

```text
Desired State
    ↓
Load Actual State
    ↓
Compute Diff
    ↓
Generate Execution Plan
    ↓
Execute Plan
    ↓
Persist New State
```

---

# 18. Runtime Use Cases

Use cases should express orchestration intent.

---

# Recommended Use Cases

```text
ApplyWallpaperUseCase
ReconcileDesktopStateUseCase
GenerateDerivedArtifactsUseCase
ApplyDesktopConfigurationUseCase
InvalidateArtifactsUseCase
```

---

# Avoid Overly Granular Use Cases

Avoid:

```text
RunColorGeneratorUseCase
RunEffectsToolUseCase
```

These describe execution mechanics rather than orchestration semantics.

---

# 19. Ports

Ports define domain capabilities.

---

# Good Port Design

```python
class IColorSchemeGenerator(Protocol):
    def generate(
        self,
        wallpaper: WallpaperState
    ) -> Palette:
        ...
```

---

```python
class IDesktopConfigWriter(Protocol):
    def write(
        self,
        state: DesktopState
    ) -> None:
        ...
```

---

# Bad Port Design

```python
class ICommandRunner
```

Too low-level.

Ports should express domain intent.

---

# 20. Infrastructure Adapters

Infrastructure adapters implement ports.

Examples:

| Port | Adapter |
|---|---|
| `IWallpaperBackend` | Hyprpaper adapter |
| `IColorSchemeGenerator` | CLI wrapper adapter |
| `IIconRenderer` | Icon renderer adapter |
| `IStateRepository` | SQLite repository |
| `IDesktopReloader` | Hyprland reload adapter |

---

# 21. CLI Tool Integration Strategy

CLI tools remain independent systems.

They are treated as:

```text
Compute Providers
```

The orchestration layer coordinates them.

It does not absorb them.

---

# Responsibilities of CLI Tools

CLI tools should:

- accept deterministic inputs
- produce deterministic outputs
- remain standalone
- avoid runtime core dependencies

---

# Responsibilities of Runtime Core

The runtime core determines:

- WHAT is invalid
- WHAT must regenerate
- WHEN execution is required

---

# 22. Initial Runtime Execution Model

The initial runtime should remain synchronous.

Avoid initially:

- daemons
- async orchestration
- event buses
- distributed execution

---

# Initial Runtime Flow

```text
dotfiles wallpaper set image.png
    ↓
ApplyWallpaperUseCase
    ↓
Update Desired State
    ↓
ReconcileDesktopStateUseCase
    ↓
Generate Missing Artifacts
    ↓
Write Configs
    ↓
Reload Desktop
    ↓
Persist Resulting State
```

---

# 23. Persistence Strategy

Initially:

- SQLite
or
- JSON snapshots

are sufficient.

---

# Example Snapshot

```json
{
  "wallpaper_hash": "...",
  "palette_hash": "...",
  "generated_at": "..."
}
```

---

# 24. Caching & Invalidation

Caching should be deterministic.

Example:

```python
if existing.source_hash == wallpaper_hash:
    reuse_palette()
else:
    regenerate_palette()
```

---

# Invalidations Must Be Explicit

| Change | Invalidates |
|---|---|
| Wallpaper change | Palette |
| Palette change | Themes |
| Theme change | Icons |
| Template change | Config files |

---

# 25. Provisioning Execution Model

Provisioning operates independently from runtime orchestration.

---

# Provisioning Responsibilities

Provisioning is responsible for (all IMPLEMENTED):

- package installation (Ansible `packages` role: pacman/apt + AUR yay bootstrap)
- filesystem bootstrap (Ansible `filesystem` role: XDG dirs + install spine)
- asset placement (Ansible `assets` role: wallpapers, icon-templates, icon-mappings, csg templates, weg effects)
- CLI installation (Ansible `cli_tools` role: `uv tool install` csg/weg/itr + container image builds)
- default palette generation (Ansible `default_palette` role: `csg generate` in container mode)
- compositor configs (Ansible `compositor_configs`: skeletons + palette fragments)
- config copies (Ansible `config_copies`: repo dotfiles/config → spine)
- per-tool settings (Ansible `settings`: renders csg/weg/itr settings.toml)
- config-in-spine symlinks (Ansible `config_links`: `~/.config/<name>` → spine, with backup guard)
- icon rendering (Ansible `icons`: `itr render` resolved SVGs)
- environment preparation
- verification (Ansible `verify`: the eleven done-criteria)

---

# Example Provisioning Flow

```text
scripts/bootstrap.sh            ← fresh-machine one-shot (uv preseed → collections → bootstrap → verify)
    ↓
dotfiles-provision plan         ← Ansible --check dry-run (no mutation)
dotfiles-provision apply        ← aggregate bootstrap.yaml, 11 roles in dependency order
    ↓
packages → cli_tools → filesystem → assets → default_palette →
compositor_configs → config_copies → settings → config_links → icons → verify
    ↓
dotfiles-provision verify       ← asserts the eleven done-criteria against provisioned locations
```

---

# Important Provisioning Principle

Provisioning should establish:

```text
Operational Capability
```

NOT runtime reconciliation.

---

# Drift from v2 plan (good drift)

The v2 plan listed "symlink management" as a provisioning concern; the
implemented pattern is **config-in-spine** (`docs/02-config-in-spine-pattern.md`):
all managed configs live under `<install>/config/` and `~/.config/<name>` is a
symlink into it. This keeps the spine the single home for config + data while
satisfying each tool's native XDG discovery. A backup/migration guard preserves
pre-existing user configs before any symlink replaces them.

---

# 26. What NOT To Build Initially

Avoid initially:

| Avoid | Reason |
|---|---|
| Event bus | Complexity without payoff |
| Async runtime | Workflow is bounded |
| Plugin systems | Premature abstraction |
| Distributed execution | Unnecessary |
| Multi-backend persistence | SQLite sufficient |
| Generic workflow engines | Premature generalization |
| Runtime package installation | Belongs to provisioning |

---

# 27. Recommended Development Phases

---

# Phase 1 — Provisioning Foundation (DONE, 2026-08-16)

## Goal

Establish operational environment.

---

## Deliverables

- [x] package installation
- [x] CLI installation
- [x] asset deployment
- [x] filesystem setup
- [x] config-in-spine symlink management
- [x] per-tool settings rendering
- [x] icon rendering (`itr render` at apply time)
- [x] verify gate (eleven done-criteria)

> Implemented as `src/provisioning` (hexagonal Python driving Ansible) +
> `scripts/bootstrap.sh`; see `docs/01` and `docs/02`.

---

# Phase 2 — Foundational Runtime Orchestration

## Goal

Prove deterministic runtime orchestration.

---

## Deliverables

- wallpaper command
- orchestration pipeline
- color generation
- config writing
- desktop reload
- persisted state

---

# Phase 3 — State Awareness

## Goal

Introduce invalidation and reuse.

---

## Deliverables

- content hashing
- artifact metadata
- cache validation
- selective regeneration

---

# Phase 4 — Reconciliation Engine

## Goal

Move from imperative execution to declarative convergence.

---

## Deliverables

- desired state
- actual state
- diff engine
- execution planning

---

# Phase 5 — Reactive Runtime

## Goal

Introduce continuous reconciliation.

---

## Deliverables

- filesystem watchers
- daemon
- reactive updates
- runtime reconciliation

---

# Phase 6 — Advanced Runtime

## Goal

Improve scalability.

---

## Deliverables

- parallel execution
- plugin interfaces
- incremental dependency graph
- distributed cache

---

# 28. Immediate Recommended Tasks

---

# Task Group A — Provisioning (DONE)

- [x] Create provisioning architecture (hexagonal Python + Ansible)
- [x] Define package installation model (Ansible packages role, distro-isolated group_vars)
- [x] Define filesystem layout (XDG dirs + install spine)
- [x] Implement asset deployment (wallpapers, icon-templates, icon-mappings, csg templates, weg effects)
- [x] Implement symlink management (config-in-spine: `~/.config/<name>` → spine, backup guard)
- [x] Implement CLI installation (uv tool install csg/weg/itr + container images)
- [x] Implement bootstrap workflow (`scripts/bootstrap.sh` + `dotfiles-provision bootstrap`)

---

# Task Group B — Core Runtime Domain

- [ ] Define `WallpaperState`
- [ ] Define `ThemeState`
- [ ] Define `DerivedArtifact`
- [ ] Define invalidation rules
- [ ] Define reconciliation model

---

# Task Group C — Runtime Persistence

- [ ] Implement `IStateRepository`
- [ ] Persist desktop snapshots
- [ ] Persist artifact metadata
- [ ] Implement state loading

---

# Task Group D — Runtime Orchestration

- [ ] Implement `ApplyWallpaperUseCase`
- [ ] Implement `ReconcileDesktopStateUseCase`
- [ ] Implement execution ordering
- [ ] Implement failure handling

---

# Task Group E — Runtime Infrastructure

- [ ] Wallpaper backend adapter
- [ ] Color scheme adapter
- [ ] Effects adapter
- [ ] Config writer adapter
- [ ] Desktop reload adapter

---

# Task Group F — CLI Integration

- [ ] Implement root `dotfiles` CLI
- [ ] Implement wallpaper commands
- [ ] Implement runtime inspection commands
- [ ] Implement debug commands

---

# 29. Current Project Status

# Overall Completion

```text
[████████████████████░░] ~55%   ← provisioning complete; runtime not started
```

---

# Provisioning Layer (DONE)

- [x] Provisioning architecture (hexagonal Python + Ansible)
- [x] Package management (Ansible packages role; pacman/apt + AUR yay)
- [x] CLI installation (csg/weg/itr via uv tool install + container images)
- [x] Asset deployment (wallpapers, icon-templates, icon-mappings, csg templates, weg effects)
- [x] Filesystem bootstrap (XDG dirs + install spine)
- [x] Config-in-spine symlink management (backup guard)
- [x] Per-tool settings rendering
- [x] Icon rendering (`itr render`)
- [x] Verify gate (eleven done-criteria)

---

# Runtime Core (NOT STARTED — Phase 2+)

- [ ] Domain entities
- [ ] Port definitions
- [ ] Use case implementations
- [ ] Reconciliation engine

---

# Runtime Persistence

- [ ] State repository
- [ ] Snapshot persistence
- [ ] Artifact tracking

---

# Runtime Infrastructure

- [ ] Wallpaper adapter
- [ ] Color generation adapter
- [ ] Effects adapter
- [ ] Desktop reload adapter

---

# CLI Integration

- [ ] Root CLI
- [ ] Wallpaper commands
- [ ] State inspection commands
- [ ] Debug commands

---

# Reactive Runtime

- [ ] Filesystem watchers
- [ ] Daemon
- [ ] Reactive reconciliation

---

# Advanced Runtime

- [ ] Parallel execution
- [ ] Plugin interfaces
- [ ] Distributed cache
- [ ] Incremental dependency graph

---

# 30. Long-Term Evolution

The architecture should eventually evolve into:

```text
Provisioning Layer
    ↓
Runtime Reconciliation Layer
    ↓
Reactive Automation Layer
```

---

# Provisioning Layer

Ensures:

```text
machine is capable of operation
```

---

# Runtime Layer

Ensures:

```text
desktop state converges
```

---

# Reactive Layer

Ensures:

```text
changes trigger reconciliation automatically
```

---

# 31. Final Guiding Principle

The project does NOT exist to:

```text
run desktop tools
```

The project exists to:

```text
converge the desktop toward a deterministic desired state
```

Provisioning establishes the operational environment.

Runtime orchestration maintains desktop convergence.

Reactive systems automate reconciliation.

Everything else is implementation detail.

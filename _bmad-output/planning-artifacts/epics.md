---
stepsCompleted:
  - step-01-validate-prerequisites
  - step-02-design-epics
  - step-03-create-stories
  - step-04-final-validation
inputDocuments:
  - _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-07-03/prd.md
  - _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-07-03/reconcile-architecture-plan.md
  - _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-07-03/addendum.md
  - _bmad-output/specs/spec-wallpaper-effects-generator-v3/SPEC.md
---

# dotfiles-repo-v3 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for dotfiles-repo-v3, decomposing the requirements from the PRD, UX Design if it exists, and Architecture requirements into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: Users can run process commands in `local` or `container` Runtime Mode without changing command intent.
FR2: The system returns structured fields for operation success/failure, rendered command, stdout/stderr, return code, and duration.
FR3: The system supports process subcommands for effect, composite, and preset targets with consistent argument semantics.
FR4: Users can run batch processing over effects, composites, presets, or all.
FR5: The system returns a structured `BatchResult` containing total/succeeded/failed and per-item outcomes.
FR6: Output paths follow explicit `flat` and `explicit_output` behavior rules.
FR7: Users can select strict/non-strict and parallel/sequential execution controls for batch operations.
FR8: The system resolves file source using precedence `CLI path > ENV path > traversal/XDG > package default`.
FR9: Only declared settings fields are overridable through ENV/CLI override rules.
FR10: Effects definitions are resolved by file source only and are not content-overridden by ENV/CLI scalar rules.
FR11: The CLI supports `--output-format json|rich|plain` with JSON as default.
FR12: Install/uninstall/info/show/dump commands execute locally and expose config/catalog/runtime attribution and image lifecycle operations.
FR13: Container runs consume host-resolved settings and resolved effects artifacts through explicit mounts.
FR14: Container execution does not depend on host ENV forwarding for configuration parity.
FR15: Container execution uses validated OCI runtime APIs with explicit error mapping.

### NonFunctional Requirements

NFR1: Equivalent commands under equivalent resolved settings/effects inputs must produce equivalent result contracts across Runtime Modes.
NFR2: Batch completion must always return a final structured summary even when one or more items fail.
NFR3: Result and error payloads must expose enough structured detail for CI/pipeline decisioning without parsing styled terminal text.
NFR4: Resolution source paths and effective runtime mode must be inspectable from operational commands.
NFR5: Runtime mode and container engine controls remain orthogonal.
NFR6: Container mount model must avoid implicit host-environment leakage, use explicit host-to-container mounts only, and enforce writable output permission strategy for container user execution.

### Additional Requirements

- Preserve a hexagonal architecture with pure domain logic and side-effecting adapters.
- Preserve the `EffectProcessorPort` processing abstraction (do not replace with CLI interception/proxy behavior).
- Enforce deterministic single-file settings/effects resolution and source attribution.
- Preserve effects content immutability (file-source only, no scalar ENV override channel).
- Preserve host pre-resolution and explicit container handoff via mounted settings/effects artifacts.
- Keep runtime mode and container engine orthogonal in command behavior and implementation.
- Preserve JSON-first output default with multi-format adapter support.
- Preserve explicit runtime/image error mapping and local-only operational command posture.
- Add an explicit dry-run execution contract with pre-flight validation and rendered local/container command plans.
- Add explicit schema-based `--param key=value` type coercion behavior.
- Clarify and codify operational command decisions: `--show-config` dropped in favor of `info`; keep `install --dump-config/--dump-effects` bootstrap behavior with overwrite semantics.
- Mandate `config-assembler-engine` (from `src/shared/config-assembler-engine/`) as the single resolution engine for all settings/effects config — single-file resolution only, no multi-file merge.
- Maintain dependency baseline compatibility for `oci-runtime >= 0.3.0`.

### UX Design Requirements

- None provided for this run (no UX design contract files were selected).

### FR Coverage Map

FR1 (local mode): Epic 1 - Runtime parity for process commands (local)
FR1 (container mode): Epic 2 - Runtime parity for process commands (container)
FR2: Epic 1 - Stable single-operation result contract
FR3: Epic 1 - Typed processing scope support
FR4: Epic 3 - Batch scope coverage
FR5: Epic 3 - Stable batch result contract
FR6: Epic 3 - Output path determinism
FR7: Epic 3 - Strict/parallel control behavior
FR8: Epic 1 - Precedence-ordered settings/effects resolution
FR9: Epic 1 - Explicit override model for settings
FR10: Epic 1 - Effects source immutability
FR11: Epic 1 - JSON-first multi-format output
FR12: Epic 1 - Local-only operational command surface
FR13: Epic 2 - Pre-resolved host config handoff
FR14: Epic 2 - No ENV forwarding dependency
FR15: Epic 2 - Explicit runtime API validation

## Epic List

### Epic 1: Core Processing Engine & Configuration Resolution
Users can process single wallpapers locally with deterministic config resolution (via config-assembler-engine), typed processing scopes, and structured JSON/rich/plain output. Operational commands provide runtime and config diagnostics.
**FRs covered:** FR1 (local), FR2, FR3, FR8, FR9, FR10, FR11, FR12
**Implementation Notes:** The `EffectProcessorPort` must be designed as runtime-agnostic (not local-coupled) so Epic 2's container adapter can implement the same port without a refactor. The `OutputPort` design must anticipate batch output path rules (flat/explicit_output semantics from FR6) to avoid port redesign in Epic 3.

### Epic 2: Container Execution Contract
Users run the same process commands in containers with pre-resolved host config handoff, explicit OCI runtime validation, and no ENV forwarding dependency.
**FRs covered:** FR1 (container), FR13, FR14, FR15

### Epic 3: Batch Processing & Automation
Users can batch process effects/composites/presets/all with deterministic output paths, strict/parallel controls, and structured BatchResult contracts for pipeline consumption.
**FRs covered:** FR4, FR5, FR6, FR7

## Epic 1: Core Processing Engine & Configuration Resolution

Users can process single wallpapers locally with deterministic config resolution (via config-assembler-engine), typed processing scopes, and structured JSON/rich/plain output. Operational commands provide runtime and config diagnostics.

### Story 1.1: Domain Models & Resolution Contracts

As a developer,
I want the domain models, ports, and config-assembler-engine integration defined,
So that all downstream processing, output, and resolution logic has stable contracts to build on.

**Acceptance Criteria:**

**Given** a clean project state
**When** the settings schema is defined
**Then** it is a Pydantic `BaseModel` with declared fields matching the PRD requirements
**And** override rules are defined for settings (ENV + CLI sources) but not for effects (file-source only)

**Given** a defined `ResolutionPolicy` with an env prefix
**When** config-assembler-engine `execute()` is called with `explicit_path`
**Then** it resolves the config file using the priority chain: CLI path > ENV path > traversal > XDG > default
**And** returns an `AssemblyResult` with validated model, resolved path, and applied overrides

**Given** an `EffectProcessorPort` protocol
**When** the port interface is defined
**Then** it supports `process()` accepting an input path, processing scope, and resolved config
**And** returns a `ProcessingResult` with status, command, stdout/stderr, return code, and duration
**And** the port is designed runtime-agnostic (no local/container assumptions in the interface)

**Given** a `config-assembler-engine` dependency declaration
**When** the project is built
**Then** `config-assembler-engine>=0.1.0` is declared in the project's dependency list

### Story 1.2: Config Resolution & CLI Wiring

As a developer,
I want the full settings and effects resolution chain wired via CLI,
So that config file discovery, override application, and source attribution work from the command line.

**Acceptance Criteria:**

**Given** a settings file at a default path
**When** the CLI runs without `--config` or env overrides
**Then** it resolves settings via traversal/XDG/default strategy
**And** `info` shows the resolved source path and attribution

**Given** a `--config /path/to/custom.yaml` CLI flag
**When** the CLI runs
**Then** the explicit path wins resolution over all other strategies
**And** the resolved source attribution reports `CLI_PATH`

**Given** an ENV var `WEG_CONFIG_FILE_PATH=/env/path/config.yaml`
**When** the CLI runs without `--config`
**Then** the ENV path wins over traversal/XDG/default
**And** the resolved source attribution reports `ENV_PATH`

**Given** an effects file at a resolved path
**When** effects are loaded
**Then** the content matches the file exactly (no ENV/CLI scalar overrides applied)
**And** `dump-effects` outputs the resolved effects catalog

**Given** an override rule declared for `settings.timeout`
**When** `WEG__SETTINGS__TIMEOUT=60` is set
**Then** the ENV override is applied and coerced to `int`
**And** the final config has `timeout=60`

**Given** an override rule declared for `settings.timeout`
**When** `--param settings.timeout=30` is passed via CLI
**Then** the CLI override is applied and takes precedence over any ENV value for the same field

### Story 1.3: Local Processing Engine

As a developer,
I want to process wallpaper inputs locally as effects, composites, or presets,
So that I get a structured `ProcessingResult` with predictable output.

**Acceptance Criteria:**

**Given** the CLI is installed
**When** I run `process effect <input> --effect <name>` with a valid input and effect
**Then** ImageMagick is invoked via the local runtime
**And** a `ProcessingResult` is returned with status, rendered command, stdout/stderr, return code, and duration

**Given** a valid composite definition in the effects catalog
**When** I run `process composite <input> --composite <name>`
**Then** the composite layers are applied in order
**And** a `ProcessingResult` is returned with success status

**Given** a valid preset in the effects catalog
**When** I run `process preset <input> --preset <name>`
**Then** all effects and composites in the preset are applied
**And** a `ProcessingResult` is returned

**Given** an invalid effect name
**When** I run `process effect <input> --effect nonexistent`
**Then** the system returns a `ProcessingResult` with failure status
**And** the error maps to an explicit catalog/domain error category

**Given** a successful processing run
**When** the command completes
**Then** the output file is written to the default output location
**And** the `ProcessingResult` includes the output path

**Given** the `EffectProcessorPort`
**When** `LocalProcessor` is the active implementation
**Then** it fulfills the same port contract that `ContainerProcessor` will later implement (runtime-agnostic interface)

### Story 1.4: Multi-Format Output Adapters

As a developer,
I want structured output in JSON, rich, and plain formats,
So that automation consumers can parse results and humans get readable feedback.

**Acceptance Criteria:**

**Given** no `--output-format` flag
**When** any process or operational command runs
**Then** output is rendered as JSON by default

**Given** `--output-format json`
**When** a process command completes successfully
**Then** the output is a valid JSON `ProcessingResult` with fields: status, command, stdout, stderr, return_code, duration, output_path

**Given** `--output-format json`
**When** a process command fails
**Then** the output is a valid JSON `ProcessingResult` with failure status and structured error info (no terminal-only formatting)

**Given** `--output-format rich`
**When** a process command completes
**Then** the output is formatted for terminal readability with colors and structure

**Given** `--output-format plain`
**When** a process command completes
**Then** the output is plain text with no formatting or color codes

**Given** the `OutputPort` interface
**When** a new output format adapter is added
**Then** it implements the existing `OutputPort` protocol without modifying domain logic

### Story 1.5: Operational Commands

As a developer,
I want `info`, `show`, `dump-config`, `dump-effects`, and `version` commands,
So that I can inspect runtime state, config/catalog attribution, and tool version without running processing.

**Acceptance Criteria:**

**Given** the CLI is installed
**When** I run `info`
**Then** it displays the resolved config source path, effective runtime mode, container engine, and resolved effects source

**Given** effects are defined in the catalog
**When** I run `show effects` / `show composites` / `show presets` / `show all`
**Then** it displays the catalog entries with their definitions (filtered by scope)

**Given** a resolved config
**When** I run `dump-config`
**Then** it outputs the full resolved config as JSON, including applied overrides and source attribution

**Given** a resolved effects catalog
**When** I run `dump-effects`
**Then** it outputs the full effects catalog as JSON

**Given** the CLI
**When** I run `version`
**Then** it displays the current version string

**Given** any operational command
**When** it runs
**Then** it does not invoke ImageMagick or any processing runtime
**And** it supports `--output-format json|rich|plain`

**Given** `--show-config` is attempted as a process flag
**When** a process command runs
**Then** it is not supported; config/runtime attribution is provided through `info`

## Epic 2: Container Execution Contract

Users run the same process commands in containers with pre-resolved host config handoff, explicit OCI runtime validation, and no ENV forwarding dependency.

### Story 2.1: OCI Runtime Integration & Image Management

As a developer,
I want OCI runtime integration with image lifecycle commands,
So that container execution is backed by validated runtime APIs and managed images.

**Acceptance Criteria:**

**Given** the CLI is installed
**When** I run `install`
**Then** it pulls or builds the managed container image
**And** the image is available for container execution
**And** optional `--dump-config` / `--dump-effects` bootstrap the default config/effects files with overwrite semantics

**Given** a managed container image exists
**When** I run `uninstall`
**Then** the managed container image is removed
**And** image lifecycle errors map to explicit domain error categories

**Given** the container runtime (docker/podman) is not installed
**When** any container operation is attempted
**Then** an explicit `RuntimeNotFoundError` is raised with diagnostic guidance

**Given** the container runtime is installed but the managed image is missing
**When** a container process command runs without prior `install`
**Then** an explicit `ImageNotFoundError` is raised

**Given** `oci-runtime >= 0.3.0`
**When** a run configuration is built
**Then** it uses the typed `RunConfig` API with explicit tuple mounts and exception mapping

### Story 2.2: Container Processing via Pre-Resolved Host Config

As a developer,
I want to process wallpapers in container mode with host-resolved config,
So that container execution has consistent behavior without in-container re-resolution.

**Acceptance Criteria:**

**Given** a resolved settings config and effects catalog on the host
**When** a process command runs with `--runtime container`
**Then** the host pre-resolves settings and effects before container invocation
**And** resolved settings are serialized to a temp TOML file
**And** the temp settings TOML is mounted as `/weg-config/settings.toml` (RO)
**And** the resolved effects file is mounted as `/weg-effects/effects.yaml` (RO)
**And** the input parent directory is mounted as `/input` (RO)
**And** the output directory is mounted as `/output` (RW)

**Given** a container process command without explicit `--output`
**When** it completes
**Then** the output files are written to the mounted `/output` directory
**And** visible on the host in the specified output path

**Given** equivalent input, config, and effects
**When** `process effect` runs in local mode and container mode
**Then** both return the same `ProcessingResult` contract shape (same fields, same structure)
**And** any differences are surfaced only through explicit runtime errors (not silent contract divergence)

**Given** a container process run
**When** it completes
**Then** temp settings artifacts are cleaned up from the host

### Story 2.3: Runtime Mode Selection & Error Mapping

As a developer,
I want explicit runtime mode and container engine selection with clear error categories,
So that I can switch between local/container and docker/podman with predictable behavior.

**Acceptance Criteria:**

**Given** the CLI
**When** I run any process command
**Then** it accepts `--runtime local|container` and `--container-engine docker|podman`
**And** the flags are orthogonal: changing one does not affect the other's available values

**Given** `--runtime local`
**When** a process command runs
**Then** it uses host ImageMagick binary directly (no containerization)

**Given** `--runtime container` with `--container-engine docker`
**When** a process command runs
**Then** it executes via the docker runtime using the managed container image

**Given** `--runtime container` with `--container-engine podman`
**When** a process command runs
**Then** it executes via the podman runtime using the managed container image

**Given** an unsupported container engine value
**When** passed to `--container-engine`
**Then** an explicit validation error is returned with supported values

**Given** a container process command that times out
**When** execution exceeds the configured timeout
**Then** an explicit `ContainerTimeoutError` is raised

**Given** a container process with a pre-flight check failure (missing binary, missing image)
**When** the command is invoked
**Then** the error maps to the appropriate domain error category before any execution attempt

## Epic 3: Batch Processing & Automation

Users can batch process effects/composites/presets/all with deterministic output paths, strict/parallel controls, and structured BatchResult contracts for pipeline consumption.

### Story 3.1: Batch Scope & Result Contract

As a developer,
I want to batch process effects, composites, presets, or all at once,
So that I get a structured `BatchResult` with aggregate and per-item outcomes.

**Acceptance Criteria:**

**Given** an input file and a populated effects catalog
**When** I run `batch effects --input <file>`
**Then** all effects from the catalog are enumerated and applied sequentially
**And** a `BatchResult` is returned with `total`, `succeeded`, `failed` counts and per-item `ProcessingResult` entries

**Given** an input file and populated composites/presets
**When** I run `batch composites --input <file>` / `batch presets --input <file>`
**Then** the corresponding scope is enumerated and processed

**Given** multiple scope types
**When** I run `batch all --input <file>`
**Then** effects, composites, and presets are all processed

**Given** some items fail during batch
**When** the batch completes
**Then** the `BatchResult` includes both succeeded and failed per-item outcomes
**And** the envelope shape (total/succeeded/failed) is consistent regardless of success/failure mix

**Given** all items fail during batch
**When** the batch completes
**Then** a `BatchResult` is still returned with `total > 0` and `succeeded = 0`
**And** the envelope shape is identical to a successful batch

**Given** `--output-format json`
**When** a batch command completes
**Then** the output is a valid JSON `BatchResult` with structured per-item details

### Story 3.2: Deterministic Output Path Semantics

As a developer,
I want predictable batch output paths via `flat` and `explicit_output` behavior,
So that automation pipelines can reliably locate generated files.

**Acceptance Criteria:**

**Given** `--flat true --explicit-output true`
**When** a batch command runs
**Then** each item output is written directly in the requested output directory: `output_dir/item_name.ext`

**Given** `--flat true --explicit-output false`
**When** a batch command runs
**Then** each item output is written under `output_dir/input_stem/item_name.ext`

**Given** `--flat false` (default)
**When** a batch command runs
**Then** each item output is written under `output_dir/input_stem/type_subdir/item_name.ext` (e.g. `effects/`, `composites/`, `presets/`)

**Given** a computed output path that already exists
**When** the batch processes an item writing to that path
**Then** the backend follows the configured overwrite/error behavior
**And** the outcome is surfaced via the per-item `ProcessingResult` status

**Given** `--output json`
**When** a batch command completes
**Then** each per-item result includes the `output_path` field showing where the file was written

### Story 3.3: Strict & Parallel Execution Controls

As a developer,
I want strict/non-strict and parallel/sequential batch execution modes,
So that I control whether the batch stops on failure and whether items run concurrently.

**Acceptance Criteria:**

**Given** `--strict` mode
**When** an item fails during batch processing
**Then** the batch stops immediately on the first failure
**And** the `BatchResult` includes completed-item outcomes up to the failure point
**And** the batch result status reflects the failure

**Given** `--non-strict` mode (default)
**When** items fail during batch processing
**Then** the batch continues processing remaining items
**And** the final `BatchResult` includes outcomes for all items (both succeeded and failed)

**Given** `--parallel` mode
**When** a batch command runs
**Then** multiple items are executed concurrently
**And** the final `BatchResult` is reported deterministically after all items complete

**Given** `--sequential` mode (default)
**When** a batch command runs
**Then** items are executed one at a time in order
**And** each item's result is available before the next begins

**Given** `--strict --parallel`
**When** an item fails
**Then** remaining in-flight items may complete but no new items are started
**And** the batch result includes outcomes for all completed items

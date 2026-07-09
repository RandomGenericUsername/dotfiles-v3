---
title: Wallpaper Effects Generator v3 PRD
status: final
created: 2026-07-03
updated: 2026-07-05
---

# PRD: Wallpaper Effects Generator v3

## 0. Document Purpose
This PRD defines the product requirements for the v3 redesign of `wallpaper-effects-generator` so downstream architecture, implementation, and testing can execute against stable, user-centered requirements. It captures required capabilities, non-goals, MVP boundaries, and measurable success criteria while keeping implementation mechanics out of the core narrative.

This document is based on:
- `_bmad-output/specs/spec-wallpaper-effects-generator-v3/SPEC.md`
- `src/cli-tools/wallpaper-effects-generator/docs/ARCHITECTURE_PLAN.md`

Technical mechanism depth and architecture-level detail extracted from those sources is preserved in `addendum.md` in the same workspace.

## 1. Vision
Wallpaper Effects Generator v3 is a deterministic CLI for applying image effects, composites, and presets across local and container runtimes with consistent behavior and structured output for both humans and automation.

The product exists to remove ambiguity and runtime divergence: configuration resolution is explicit and deterministic, processing semantics are stable regardless of runtime, and output payloads are reliably machine-consumable by default.

Success means teams can run the same processing workflows in development and automated environments with predictable results, explicit error mapping, and no reliance on terminal-only presentation.

## 2. Target User

### 2.1 Jobs To Be Done
- As a developer, I need to run single-item and batch wallpaper processing with repeatable outcomes.
- As an automation author, I need structured result and error payloads that can be parsed without scraping terminal formatting.
- As an operator, I need explicit visibility into resolved config/effects sources and runtime/image state so failures are diagnosable.
- As a maintainer, I need runtime behavior and configuration precedence that are auditable and deterministic.

### 2.2 Non-Users (v1)
- End users needing a GUI workflow for image editing.
- Users needing a generic container command proxy for arbitrary tooling.
- Teams expecting multi-file layered settings merge behavior from legacy versions.

### 2.3 Key User Journeys
- **UJ-1. Morgan processes a single wallpaper with the same semantics in local and container modes.**
  - **Persona + context:** Morgan is a developer validating parity between local and CI container execution.
  - **Entry state:** CLI installed; input file available; settings/effects resolvable.
  - **Path:** Morgan runs `process effect ... --runtime local`, then reruns with `--runtime container` and equivalent arguments.
  - **Climax:** Both executions return the same result shape and predictable output location semantics.
  - **Resolution:** Morgan trusts runtime switching does not require command rewrites.

- **UJ-2. Riley runs batch generation for automation and consumes JSON results.**
  - **Persona + context:** Riley owns a pipeline that needs deterministic batch behavior and machine-readable outputs.
  - **Entry state:** Riley has an input, output dir, and selected batch scope.
  - **Path:** Riley runs `batch ... --output json` and consumes the final result payload.
  - **Climax:** Riley receives `total/succeeded/failed` and per-item outcomes with stable output path behavior.
  - **Resolution:** The pipeline can gate, retry, or alert based on structured fields.

- **UJ-3. Avery diagnoses configuration and runtime readiness before execution.**
  - **Persona + context:** Avery is troubleshooting environment drift.
  - **Entry state:** Avery has access to CLI commands but not full implementation internals.
  - **Path:** Avery runs `info`, `dump-config`, `dump-effects`, and `show` commands.
  - **Climax:** Avery sees resolved config/effects source attribution and runtime/image state.
  - **Resolution:** Avery can correct environment issues without starting processing runs.

## 3. Glossary
- **ProcessingResult** — Structured result for single processing operations including status, command, outputs, return code, and duration.
- **BatchResult** — Structured result for batch operations including aggregate counts and per-item outcomes.
- **Runtime Mode** — Processing execution location selector (`local` or `container`).
- **Container Engine** — OCI backend selector (`docker` or `podman`) independent from Runtime Mode.
- **Single-file resolution** — Config strategy where one settings source is resolved by precedence, then explicit overrides are applied.
- **OutputPort** — Output abstraction that renders domain results into JSON, rich, or plain formats.
- **Effects Catalog** — Definitions of effects, composites, and presets used by processing commands.
- **Explicit output mode** — Output path behavior flag controlling stem/subdirectory handling in batch output generation.

## 4. Features

### 4.1 Deterministic Processing Runtime
**Description:** Users can process an input as an effect, composite, or preset in either Runtime Mode while preserving command semantics and structured result contracts. Realizes UJ-1.

**Functional Requirements:**

#### FR-1: Runtime parity for process commands
Users can run process commands in `local` or `container` Runtime Mode without changing command intent.
[ASSUMPTION: ImageMagick execution path is available either via host binary detection in local mode or managed container image in container mode.]

**Consequences (testable):**
- Equivalent local/container process invocations return the same result contract type (`ProcessingResult`).
- Runtime differences are surfaced only through explicit, mapped runtime errors.

#### FR-2: Stable single-operation result contract
The system returns structured fields for operation success/failure, rendered command, stdout/stderr, return code, and duration.

**Consequences (testable):**
- Successful and failed process operations emit the same envelope shape.
- Duration and command fields are always present when execution is attempted.

#### FR-3: Typed processing scope support
The system supports process subcommands for effect, composite, and preset targets with consistent argument semantics.

**Consequences (testable):**
- Each supported process scope executes through the same request/result model.
- Unknown scope targets map to explicit catalog/domain errors.

### 4.2 Deterministic Batch Orchestration
**Description:** Users can batch process effects/composites/presets/all with deterministic output path semantics and strict/parallel controls. Realizes UJ-2.

**Functional Requirements:**

#### FR-4: Batch scope coverage
Users can run batch processing over effects, composites, presets, or all.

**Consequences (testable):**
- Batch mode enumerates and executes the selected scope only.
- Aggregate totals match enumerated item count.

#### FR-5: Stable batch result contract
The system returns a structured `BatchResult` containing total/succeeded/failed and per-item outcomes.

**Consequences (testable):**
- Batch completion emits one final structured result payload.
- Result fields are consistent across success, partial failure, and full failure.

#### FR-6: Output path determinism
Output paths follow explicit `flat` and `explicit_output` behavior rules.

**Consequences (testable):**
- `flat=true` + `explicit_output=true` writes item output directly in requested output dir.
- `flat=true` + `explicit_output=false` writes output under `output_dir/input_stem/item_name.ext`.
- `flat=false` writes output under `output_dir/input_stem/type_subdir/item_name.ext`.
- If computed output path already exists, the run follows backend overwrite/error behavior and surfaces outcome via structured result/error payload.

#### FR-7: Strict/parallel control behavior
Users can select strict/non-strict and parallel/sequential execution controls for batch operations.

**Consequences (testable):**
- Strict mode stops on first item failure and returns a failed batch result with completed-item outcomes preserved.
- Parallel mode executes multiple items while preserving deterministic final result reporting.

### 4.3 Configuration and Resolution Integrity
**Description:** Settings and effects config resolution is deterministic and source-attributed, with explicit override precedence. Realizes UJ-3.

**Functional Requirements:**

#### FR-8: Precedence-ordered settings/effects resolution
The system resolves file source using precedence `CLI path > ENV path > traversal/XDG > package default`.

**Consequences (testable):**
- Resolution path attribution indicates which source won for each run.
- CLI explicit path always overrides lower-precedence sources.

#### FR-9: Explicit override model for settings
Only declared settings fields are overridable through ENV/CLI override rules.

**Consequences (testable):**
- Undeclared fields are not mutated by ENV/CLI injection.
- Declared fields are coerced to target types and validated.

#### FR-10: Effects source immutability by override channel
Effects definitions are resolved by file source only and are not content-overridden by ENV/CLI scalar rules.

**Consequences (testable):**
- Effects runtime content matches the resolved effects file.
- Effects override attempts outside file replacement are rejected or ignored by design.

### 4.4 Output and Operational Surface
**Description:** The CLI supports machine-first output and non-processing operational commands for lifecycle and diagnostics. Realizes UJ-2 and UJ-3.

**Functional Requirements:**

#### FR-11: JSON-first multi-format output
The CLI supports `--output json|rich|plain` with JSON as default.  
[ASSUMPTION: Default JSON behavior remains non-negotiable for v3 automation-first usage.]

**Consequences (testable):**
- No output mode flag yields JSON output.
- Error/process/batch payloads are structured when in JSON mode.

#### FR-12: Local-only operational command surface
Install/uninstall/info/show/dump commands execute locally and expose config/catalog/runtime attribution and image lifecycle operations.

**Consequences (testable):**
- Operational commands do not require processing runtime execution paths.
- Image lifecycle and runtime availability errors map to explicit domain error categories.
- `--show-config` is not supported as a process-level flag; runtime/config attribution is provided through `info`.
- `install` supports optional config/effects bootstrap dump behavior as part of local image lifecycle workflows.

### 4.5 Container Execution Contract
**Description:** Container processing executes from host-resolved configuration and mounted artifacts rather than in-container re-resolution. Realizes UJ-1 and UJ-3.

**Functional Requirements:**

#### FR-13: Pre-resolved host config handoff
Container runs consume host-resolved settings and resolved effects artifacts through explicit mounts.

**Consequences (testable):**
- Settings consumed by container reflect post-resolution and override application from host.
- Effects consumed by container are sourced from the resolved effects file path.

#### FR-14: No ENV forwarding dependency
Container execution does not depend on host ENV forwarding for configuration parity.

**Consequences (testable):**
- Container processing succeeds with equivalent behavior without forwarding host ENV settings state.
- Divergence caused by host/container ENV differences is eliminated for supported settings path.

#### FR-15: Explicit runtime API validation
Container execution uses validated OCI runtime APIs with explicit error mapping.

**Consequences (testable):**
- Missing runtime/image and timeout categories map to dedicated error families.
- Run configuration objects are validated before invocation.

## 5. Cross-Cutting NFRs
- **NFR-1 (Determinism):** Equivalent commands under equivalent resolved settings/effects inputs must produce equivalent result contracts across Runtime Modes.
- **NFR-2 (Reliability):** Batch completion must always return a final structured summary even when one or more items fail.
- **NFR-3 (Observability):** Result and error payloads must expose enough structured detail for CI/pipeline decisioning without parsing styled terminal text.
- **NFR-4 (Configurability):** Resolution source paths and effective runtime mode must be inspectable from operational commands.
- **NFR-5 (Compatibility):** Runtime mode and container engine controls remain orthogonal.
- **NFR-6 (Security baseline):** Container mount model must avoid implicit host-environment leakage, use explicit host-to-container mounts only, and enforce writable output permission strategy for container user execution. Additional hardening requirements remain tracked for launch policy closure.

## 6. Constraints and Guardrails

### 6.1 Constraints
- Domain logic stays pure; side effects remain in adapters.
- Domain models and domain services remain immutable/pure (frozen dataclass semantics in implementation, zero I/O in domain layer).
- Multi-file merge behavior is out of scope for config.
- Processing abstraction is a dedicated port, not a CLI interception proxy.
- Runtime Mode selection and Container Engine selection remain independent.

### 6.2 Guardrails
- Do not introduce generic arbitrary command execution inside containers.
- Do not introduce output-mode-specific behavioral semantics; only rendering should vary by output mode.
- Do not weaken deterministic source precedence and override rules.

## 7. Why Now
The previous architecture coupled command transport concerns with routing and created ambiguity in configuration/debugging behavior. This redesign addresses immediate correctness and operability risks for automation-driven usage while preserving a clear migration path from the legacy behavior model.

## 8. Non-Goals (Explicit)
- Generic “run any CLI command in a container” proxy behavior.
- Reintroduction of layered multi-file settings merge.
- Incremental/streaming JSON progress events for batch operations in v1 scope.
- GUI or interactive TUI product surfaces.

## 9. MVP Scope

### 9.1 In Scope
- Process and batch commands across effect/composite/preset scopes with deterministic result contracts.
- Deterministic settings/effects resolution with explicit precedence and source attribution.
- Container execution via pre-resolved host config/effects artifact mounts.
- Output adapters with JSON default plus rich/plain alternatives.
- Local operational command set (install/uninstall/info/show/dump/version).

### 9.2 Out of Scope for MVP
- Runtime-agnostic arbitrary container command execution.
- Multi-file merge/resolution compatibility layers from prior architecture.
- Streaming JSON progress protocol.
- Expanded mount-permission hardening beyond current baseline. [NOTE FOR PM: Define security baseline target before launch hardening.]

## 10. Success Metrics
**Primary**
- **SM-1:** 100% of supported process/batch command classes produce schema-valid JSON output by default. Validates FR-2, FR-5, FR-11.
- **SM-2:** Local and container executions of parity test scenarios show no contract-shape divergence. Validates FR-1, FR-13, FR-14.

**Secondary**
- **SM-3:** Configuration source attribution is available for all runs where settings/effects are resolved. Validates FR-8, FR-9, FR-10.
- **SM-4:** Operational command suite covers runtime/image and source-diagnostic tasks without invoking processing. Validates FR-12.
- **SM-5:** Batch processing meets MVP performance baseline under representative workload: p95 <= 1.0s per item, failure rate < 0.2%, and peak memory <= 256MB. Validates FR-5, FR-7.

**Counter-metrics (do not optimize)**
- **SM-C1:** Raw processing speed at the expense of deterministic behavior or structured output fidelity. Counterbalances SM-1 and SM-2.
- **SM-C2:** Feature breadth that reintroduces ambiguous configuration pathways. Counterbalances SM-3.

## 11. Open Questions
1. What migration and cutover criteria will be used to retire prior implementation safely? [NOTE FOR PM: Owner=PM; revisit before rollout planning sign-off.]
2. What security constraints are required for container mount permissions beyond the current baseline strategy? [NOTE FOR PM: Owner=Security/Platform; revisit before launch hardening gate.]

## 12. Assumptions Index
- **§4.1 / FR-1:** [ASSUMPTION] ImageMagick execution path is available via host binary detection (local) or managed image (container).
- **§4.4 / FR-11:** [ASSUMPTION] JSON remains the default output mode for v3.

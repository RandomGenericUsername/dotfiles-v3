---
id: SPEC-wallpaper-effects-generator-v3
companions:
  - ../../../src/cli-tools/wallpaper-effects-generator/docs/ARCHITECTURE_PLAN.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Wallpaper Effects Generator v3

## Why

This work realizes a deliberate redesign of the wallpaper-effects CLI into a hexagonal architecture so effect processing is deterministic, container execution matches host behavior, and automation consumers can rely on structured outputs. The change matters now because the previous design mixed transport/runtime concerns into command routing and made configuration/debugging behavior harder to reason about.

## Capabilities

- **CAP-1**
  - **intent:** User can process a wallpaper input as an effect, composite, or preset in local or container runtime without changing command semantics.
  - **success:** For any valid process command, both runtimes return a `ProcessingResult` with success status, rendered command, stderr/stdout, return code, and measurable duration.

- **CAP-2**
  - **intent:** User can run batch processing over effects/composites/presets/all with deterministic output paths and strict/parallel controls.
  - **success:** Batch commands produce a `BatchResult` reporting total/succeeded/failed and per-item results, and output paths follow the explicit `flat` and `explicit_output` rules.

- **CAP-3**
  - **intent:** System resolves settings and effects config deterministically through single-file resolution with explicit override precedence.
  - **success:** Resolution follows `CLI path > ENV path > traversal/XDG > package default`, then applies only declared override rules, and reports resolved source paths.

- **CAP-4**
  - **intent:** Container processing runs from pre-resolved host configuration with explicit mounts instead of in-container re-resolution.
  - **success:** Container runs receive mounted temp settings TOML and mounted resolved effects YAML, use no ENV forwarding, and complete using validated OCI runtime APIs.

- **CAP-5**
  - **intent:** CLI output can be consumed by humans or automation with JSON as the default presentation.
  - **success:** `--output json|rich|plain` is supported, JSON remains default, and error/process/batch payloads are structured from domain objects via `OutputPort`.

- **CAP-6**
  - **intent:** User can manage and inspect runtime state through install/uninstall/info/show/dump commands without requiring processing runtime execution.
  - **success:** Non-processing commands run locally, expose config/catalog/runtime attribution, and support image lifecycle flows with explicit error mapping.

## Constraints

- Domain models and services stay pure (frozen dataclasses, zero I/O); I/O lives in adapters.
- Configuration uses `config-assembler-engine` single-file resolution only; multi-file merge behavior is out.
- Runtime selection (`runtime.mode`) and engine selection (`container.engine`) remain orthogonal settings.
- Container adapter uses `oci-runtime >= 0.3.0` typed API (`RunConfig`, tuple mounts, explicit exceptions).
- Processing abstraction is an explicit domain port (`EffectProcessorPort`), not a CLI command proxy/interceptor.
- Container mode must mount host-resolved config/effects artifacts and never depend on host ENV forwarding.

## Non-goals

- Provide a generic "run arbitrary CLI command in container" proxy path.
- Reintroduce layered multi-file config merging from prior architecture.
- Stream incremental JSON progress events during batch execution (final JSON result only).

## Success signal

- A demonstration can run equivalent process and batch scenarios in local and container modes with consistent behavior, expected outputs, and mapped error types while preserving the same config intent.
- Automation clients can parse default JSON output from success and failure paths without terminal-format dependencies.

## Assumptions

- The architecture plan remains the controlling source for unresolved implementation details carried in the adopted companion.
- The workspace provides compatible `oci-runtime` and `config-assembler-engine` versions as declared by the plan.
- ImageMagick execution is available either through host binary detection or the managed container image path.

## Open Questions

- What acceptance thresholds (performance, throughput, memory) define "production-ready" for batch-heavy workloads?
- What migration/cutover criteria will be used to retire the prior implementation safely?
- What security constraints are required for container mount permissions beyond the current chmod strategy?

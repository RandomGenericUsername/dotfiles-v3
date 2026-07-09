# Addendum: Wallpaper Effects Generator v3 (Technical Detail Extract)

This addendum captures implementation-level detail extracted from:
- `_bmad-output/specs/spec-wallpaper-effects-generator-v3/SPEC.md`
- `src/cli-tools/wallpaper-effects-generator/docs/ARCHITECTURE_PLAN.md`

The PRD (`prd.md`) remains capability-first; this file preserves technical depth for architecture and implementation handoff.

## A. Architectural Spine
- Hexagonal architecture with pure domain layer and I/O-constrained adapters.
- Processing abstraction through `EffectProcessorPort` with local/container implementations.
- Deterministic single-file config resolution with explicit override rules.
- Pre-resolved host configuration handoff to container execution path.
- JSON-first output design through `OutputPort`.

## B. Core Capability-to-Mechanism Mapping
- **Processing parity:** `LocalProcessor` and `ContainerProcessor` implement the same processing port surface and return shared result models.
- **Batch determinism:** Batch request/result contracts include deterministic path semantics with `flat` and `explicit_output` behavior.
- **Resolution determinism:** Settings/effects each use separate assembler instances and source precedence order.
- **Container reliability:** OCI runtime integration uses typed config and explicit exception mapping.
- **Automation output:** JSON default output adapter emits structured payloads for success/error paths.

## C. Key ADR Extract (from Architecture Plan)
1. Single-file config resolution only; no merge strategy.
2. Domain port for processing (not CLI proxy/interception).
3. Pre-resolved config mounted into container.
4. Effects file mounted from resolved path as-is.
5. Container command surface is explicit and typed.
6. Runtime mode and container engine are orthogonal controls.
7. JSON-first output as default behavior.
8. `oci-runtime >= 0.3.0` as container foundation.

## D. Domain and Port Inventory (Condensed)
- Domain models: effects/composites/presets catalog, processing and batch request/result contracts, runtime/output/config models.
- Domain services: command substitution, parameter resolution, output path computation, catalog validation.
- Ports: loaders/resolvers/runners, processor, image manager, output, serializers.

## E. Container Execution Contract (Condensed)
Host flow:
1. Resolve settings and effects on host.
2. For container mode, validate runtime and image availability.
3. Serialize resolved settings to temp TOML.
4. Mount input/output/settings/effects paths explicitly.
5. Execute typed OCI run config.
6. Clean temporary artifacts.

Mount model:
- Input parent directory -> `/input` (RO)
- Output directory -> `/output` (RW)
- Temp settings TOML -> `/weg-config/settings.toml` (RO)
- Resolved effects directory/file -> `/weg-effects/effects.yaml` (RO)

## F. Command Surface Snapshot
- `process effect|composite|preset`
- `batch effects|composites|presets|all`
- `show effects|composites|presets|all`
- `install`, `uninstall`, `dump-config`, `dump-effects`, `info`, `version`
- Globals include output format, config/effects paths, runtime mode, verbosity controls
- `--show-config` is intentionally dropped in favor of `info`
- `install` keeps optional `--dump-config` / `--dump-effects` bootstrap semantics

## F.1 Dry-run and Parameter Coercion Contracts
- Dry-run behavior is a first-class execution contract via dedicated dry-run processing/running adapters.
- Dry-run validates input existence, binary/runtime availability, image presence, and catalog lookup before reporting.
- Dry-run returns rendered local/container command plans and mount mappings without executing side effects.
- CLI `--param key=value` values are coerced using schema-defined parameter types to preserve deterministic behavior and parity with settings override coercion.

## G. Dependency Snapshot
- `config-assembler-engine`
- `oci-runtime >= 0.3.0`
- `pydantic >= 2.0`
- `pyyaml >= 6.0`
- `typer[all] >= 0.9.0`
- `rich >= 13.0`
- `tomli-w >= 1.0`

## H. Deferred Clarifications
- Production readiness thresholds (performance/throughput/memory) for batch-heavy use.
- Legacy migration/cutover criteria.
- Container mount-permission hardening policy beyond current baseline.

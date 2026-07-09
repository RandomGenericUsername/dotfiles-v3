# Reconciliation — ARCHITECTURE_PLAN.md
## Summary
PRD + addendum preserve the main architectural spine: hexagonal boundaries, deterministic config/effects resolution, runtime/engine orthogonality, JSON-first output, and host-pre-resolved container execution. Most ADR-level intent from the source remains visible for downstream delivery. The remaining gaps are concentrated around explicit dry-run behavior and a few command-surface decisions that were resolved in the source architecture plan but are not currently carried forward.

## Gaps (if any)
- [medium] **Dry-run execution contract is not preserved as an explicit commitment.** Source defines a dedicated `DryRunProcessor`/`DryRunCommandRunner` with pre-flight validation (input/binary/catalog/runtime/image checks) plus rendered local/container command plans. PRD/addendum mention command surface but do not retain this behavior as a required architecture-level contract.
- [medium] **`--param` type-coercion contract is dropped.** Source commits that CLI `--param key=value` values are coerced using schema-defined parameter types (via shared coercion logic), which is key to deterministic processing and parity with config override coercion. PRD/addendum keep typed params conceptually but omit this mechanism-level requirement.
- [low] **Operational command decision details are partially dropped.** Source explicitly resolves `--show-config` as dropped in favor of `info`, and keeps `install --dump-config/--dump-effects` post-build bootstrap behavior (with overwrite semantics). These command commitments are not clearly retained in PRD/addendum.

## Alignment Confirmed
- Hexagonal architecture with pure domain + adapter side-effects separation is preserved.
- Processing abstraction remains a dedicated `EffectProcessorPort` model (not CLI interception/proxy behavior).
- Runtime parity intent for local/container processing and shared result contracts is preserved.
- Batch deterministic contract (`BatchResult`, strict/parallel controls, deterministic output path semantics including `flat`/`explicit_output`) is preserved.
- Deterministic single-file settings/effects resolution and precedence ordering are preserved.
- Effects content immutability (file-source only, no scalar ENV override channel) is preserved.
- Host pre-resolution and container handoff via mounted settings/effects artifacts is preserved.
- Runtime mode and container engine orthogonality is preserved.
- JSON-first output default and multi-format adapter model are preserved.
- Local-only operational command posture and explicit runtime/image error mapping are preserved.
- Key dependency baseline (`oci-runtime >= 0.3.0` and supporting stack) remains visible.

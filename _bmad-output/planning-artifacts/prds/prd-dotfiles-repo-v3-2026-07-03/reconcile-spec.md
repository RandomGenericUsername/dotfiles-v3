# Reconciliation — SPEC.md
## Summary
The PRD and addendum preserve nearly all core contract intent from `SPEC.md`, including deterministic runtime parity, batch/result contracts, single-file resolution precedence, container mount-based handoff, and JSON-first output behavior. Non-goals and the primary open questions are carried forward with high fidelity. The main deltas are not feature omissions but slight dilution of a few contract-level constraints and assumptions. No high-severity functional gaps were found.

## Gaps (if any)
- [medium] The strict purity constraint is softened: SPEC requires domain models/services to be pure with **frozen dataclasses** and zero I/O, while PRD language keeps purity but does not explicitly retain the frozen-model invariant.
- [medium] A key operational assumption is dropped: SPEC explicitly assumes ImageMagick execution is available via host binary detection or managed container image path; PRD/addendum do not clearly restate this prerequisite.
- [low] Security open-question specificity is reduced: SPEC references mount-permission constraints beyond the current **chmod strategy**, while PRD generalizes this to a broader baseline without preserving the concrete chmod framing.

## Alignment Confirmed
- Runtime parity intent and shared `ProcessingResult` contract across local/container execution are preserved.
- Batch scope coverage and `BatchResult` structure (`total/succeeded/failed` + per-item outcomes) are preserved.
- Deterministic output path rules (`flat` and `explicit_output`) and strict/parallel controls are preserved.
- Settings/effects resolution precedence (`CLI > ENV > traversal/XDG > package default`) and source attribution are preserved.
- Container execution uses host-pre-resolved settings/effects via explicit mounts and avoids ENV-forwarding dependency.
- JSON-first output with `--output json|rich|plain` and machine-consumable structured payloads is preserved.
- Operational non-processing commands (install/uninstall/info/show/dump) remain local and include lifecycle/diagnostic intent.
- Core non-goals are preserved (no generic container command proxy, no multi-file merge return, no streaming batch JSON progress).
- Primary open questions from SPEC (performance thresholds, migration/cutover, mount-permission hardening) are preserved.

## Context

~20 string literals for OCI subcommands are scattered across all four manager adapters. The codebase already enums `RuntimeKind`, `ContainerState`, etc. in `domain/enums.py`.

## Goals / Non-Goals

**Goals:** Typo-safe enum for subcommands; adapter-internal only.
**Non-Goals:** Public API re-export (external callers constructing their own command lists use raw strings; not our problem).

## Decisions

`Subcommand(str, Enum)` — inherits from `str` so `Subcommand.RUN == "run"` is True (back-compat for any string-comparison paths). Managers call `cmd.append(Subcommand.RUN.value)`. Migration is one manager per commit to keep diffs reviewable.

## Risks / Trade-offs

- Every manager call site changes — medium diff size. Risk mitigated by per-manager-commit migration.
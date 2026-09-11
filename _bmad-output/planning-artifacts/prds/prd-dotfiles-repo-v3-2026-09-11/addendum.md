# Addendum: Phase 4 Reconciliation-Engine Decision Handoff

This addendum preserves the user-approved technical depth behind the two locked
Phase 4 decisions. The PRD remains capability-first; this file carries the
rejected alternatives, precedence rules, and implementation implications.

## A. AD-30 — Hybrid prune policy

### Approved configuration

- Policy precedence, lowest to highest:
  1. Code default: keep the last 5 entries per layer.
  2. Desired-state declaration: overrides the code default for automatic runs.
  3. Explicit CLI flags: override both for a manual run.
- Automatic prune obeys a non-negotiable protected floor:
  - active entries referenced by `current.json`;
  - last-N entries per layer;
  - seed-pinned entries;
  - undated/unclassifiable entries.
- Manual `prune` may be intentionally aggressive, including `--keep 0` and
  `--prune-pinned` — but the maximum is everything except active + undated
  entries: whole-cache deletion is NOT offered, and `active` (live desktop)
  plus `undated` (unclassifiable) survive every flag combination.
- Automatic prune uses the B2 preview/execute contract:
  - `reconcile --plan` shows the exact delete set without executing it;
  - `reconcile` executes the reviewed deletes and logs them;
  - no interactive confirmation prompt, preserving future Phase 5 daemon use.
- Every real prune execution appends exactly one `history.jsonl` line with
  `trigger="prune"` carrying the counts (dry-run appends nothing).

### Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| Planner-only automatic prune | Could delete wanted cache without a separate human decision. |
| Explicit-prune-only Phase 4 | Leaves disk growth unaddressed; the user explicitly wants safe automation. |
| Interactive confirmation before auto-delete | Breaks unattended and future daemon-driven reconciliation. |
| Manual prune obeying the same conservative policy as auto-prune | Removes the operator's deliberate escape hatch for aggressive cleanup. |

### Implementation implications

- The planner may emit `delete` steps only for candidates outside the protected floor.
- Keep/policy inputs must be visible in both `--plan` and execution output.
- The exact desired-state filename/schema remains a Phase 4 PRD/architecture detail; do not hard-code an invented filename as a contract here.
- Future favorites can join the protected floor as desired-state data without changing AD-30.

## B. AD-31 — history.jsonl writer file locking

### Approved configuration

- All writers of `history.jsonl` serialize through a single OS-level file lock.
- Append-only behavior is unchanged.
- The lock prevents torn-line interleaving from concurrent writers.
- Exact lock primitive and filesystem behavior: scoped to local POSIX;
  lock-acquire/hold/release failures surface as typed errors (never raw
  platform errors, never silent skips). NFS/synced-filesystem behavior is
  explicitly out of scope until portability evidence appears.

### Rejected alternatives

| Alternative | Reason rejected |
|---|---|
| Keep history locking deferred indefinitely | Leaves the known concurrent-writer torn-line failure mode open. |
| Prompt or manual repair instead of locking | Adds operator friction without closing the race. |
| A database or alternate history store | Out of scope; violates the inherited append-only JSONL contract. |

### Open implementation detail

- Select the portable OS file-lock primitive during Phase 4 implementation.
- Preserve behavior on the operator's actual filesystem; revisit only if NFS/synced-filesystem evidence changes the choice.

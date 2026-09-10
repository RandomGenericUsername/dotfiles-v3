# Gate 2 Review — p3-3-3 Prune CLI

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
~20 findings (overlapping). Zero files changed — all proposals.

Files: `prune_source.py` = `src/runtime/src/runtime/adapters/prune_source.py`;
`prune.py` = `src/runtime/src/runtime/application/prune.py`;
`main.py` = `src/runtime/src/runtime/cli/main.py`;
tests = `src/runtime/tests/unit/test_prune_cli.py`.

**E is Medium (fail-open).**

---

## APPLY A — `remove_entry` race + delete the named inode (Edge #1, #2, Blind #? )

**Situation.** (1) An entry deleted/replaced between `exists()` and `rmtree`
raises `FileNotFoundError`/`NotADirectoryError`, aborting the prune. (2)
`resolve()` follows symlinks, so a symlink swapped in after the `is_symlink`
check that points at another real same-layer entry passes the parent check and
`rmtree(resolved)` deletes the WRONG (unplanned) entry.

**Proposal.**
```python
# BEFORE (prune_source remove_entry tail)
    if not resolved.is_dir():
        return False  # non-dir squatter is not a prunable entry
    shutil.rmtree(resolved)
    logger.info(...)
    return True
# AFTER
    if resolved.name != entry_hash:
        raise ValueError(f"entry resolves to a different name: {target} -> {resolved}")
    if not resolved.is_dir():
        return False  # non-dir squatter is not a prunable entry
    if target.is_symlink():
        return False  # swapped to a symlink mid-race: refuse
    try:
        shutil.rmtree(target)  # delete the NAMED inode, not a resolved target
    except (FileNotFoundError, NotADirectoryError):
        return False  # vanished/replaced mid-race: idempotent no-op
    logger.info("prune: removed cache/%s/%s", layer, entry_hash)
    return True
```

## APPLY B — dry-run must not take the mutex (Blind #1, Edge #5)

**Situation.** `--dry-run` acquires the blocking exclusive mutex, whose
`_acquire` does `mkdir(parents=True)` + `O_CREAT .seed.lock` — a "safe" dry run
creates state dirs/files. The snapshot test hides it by excluding `.seed.lock`.

**Proposal.** Dry-run skips the lock entirely (read-only plan).
```python
# AFTER (_run_prune)
    if dry_run:
        plan = PruneUseCase(...).run(prune_pinned=prune_pinned)
        return plan, 0
    mutex = FlockSeedMutex(state_root / ".seed.lock")
    with mutex.hold(blocking=True):
        plan = PruneUseCase(...).run(prune_pinned=prune_pinned)
        removed = 0
        ...
```

## APPLY C — report partial prune instead of aborting silently (Blind #2, Edge #3, Auditor #6)

**Situation.** One `remove_entry` failure aborts mid-loop after earlier
deletions; the error path discards `removed`, so the user is never told what
was actually deleted and a half-deleted dir is left (undated → protected).

**Proposal.** Accumulate failures, then raise a summary AFTER the loop:
```python
        removed = 0
        failed: list[str] = []
        if not dry_run:
            for layer, hashes in plan.removals.items():
                for entry_hash in hashes:
                    try:
                        if remove_entry(state_root, layer, entry_hash):
                            removed += 1
                    except OSError as exc:
                        failed.append(f"{layer}/{entry_hash}")
                        logger.error("prune: failed cache/%s/%s: %s", layer, entry_hash, exc)
        if failed:
            raise RuntimeError(f"prune removed {removed}, failed {len(failed)}: {', '.join(failed)}")
```

## APPLY D — `removed_count` key + list removed hashes (Auditor #1, #2)

**Situation.** Story specifies `removed_count`; the object has only `removed`.
"Every removal is logged" isn't observable (INFO dropped — CLI never configures
logging).

**Proposal.** Add `removed_count` and `removed_hashes` to the object; list the
hashes in plain output; and configure root logging at INFO when unset in
`main_callback` so the adapter's per-removal log is visible.

## APPLY E — seed pins fail CLOSED on mid-file corruption (Edge #8, MEDIUM)

**Situation.** `seed_pins` returns an empty set on mid-file `history.jsonl`
corruption; prune reads "no pins" and REMOVES protection from seed-pinned
entries — fail-open. Story 3.2's "no pins (safe degradation)" is unsafe for a
destructive command.

**Proposal.** Raise on mid-file corruption (torn trailing line still tolerated):
```python
        except json.JSONDecodeError:
            if i == last_index and not raw.endswith("\n"):
                break
            raise ValueError(
                f"history.jsonl line {i + 1}: not valid JSON; refusing to compute seed pins"
            )
```
Update `test_corrupt_first_seed_line_yields_no_pins` → expects `ValueError`
(prune then exits 1, nothing deleted).

## APPLY F — `--keep` min bound (Edge #6)

**Situation.** Negative `--keep` is rejected inside the use case (exit 1,
generic error) rather than as a usage error.

**Proposal.** `typer.Option(5, "--keep", min=0, ...)` + a test.

## APPLY G — refuse to prune when `current.json` is absent (Auditor #7)

**Situation.** Absent state → empty active set; with `--keep 0` prune can
delete entries still referenced by `current/` symlinks. Fail-open.

**Proposal.** In `_run_prune` (CLI), `load_current()` — if `None`, raise
`ValueError("no runtime state recorded; refusing to prune")` before planning.
The use case stays general (its absent-state behavior is unchanged).

## APPLY H — `prune_source` module docstring (Auditor #3)

Update the header from "Read-only ... never writes or deletes" to describe the
Story 3.3 validated removal seam.

## APPLY I — tests + story hygiene (Blind #4, Edge #4, Auditor #4/#5)

Add: `remove_entry` on symlinked layer / file squatter / name-mismatch escape /
`rmtree` failure; dry-run exact side-effect set (only reads); removed_count 0
on noop; invalid `--keep` exit; absent-state refusal; `prune_pinned` CLI;
noop `removed_count`. Tick story boxes + record.

---

## DISMISS X1 — add a top-level `cache` alias to satisfy the epics' `cache prune`

The existing tree nests cache under inspect (`inspect cache list`, Story 3.1
contract); the story documents the `inspect cache prune` path. Mounting the
same Typer twice is fragile and the nesting is the established convention.

---

## Item-to-finding index

| Item | Findings |
|------|----------|
| A | Edge #1, #2 |
| B | Blind #1, Edge #5 |
| C | Blind #2, Edge #3, Auditor #6 |
| D | Auditor #1, #2 |
| E | Edge #8 |
| F | Edge #6 |
| G | Auditor #7 |
| H | Auditor #3 |
| I | Blind #4, Edge #4, Auditor #4/#5 |
| Dismiss X1 | Edge #7, Auditor (command-path note) |

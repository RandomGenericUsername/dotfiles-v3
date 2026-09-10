# Gate 2 Review — p3-3-2 Prune Keep-Policy Core

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
~16 findings (overlapping). Zero files changed — all proposals.

Files: `prune.py` = `src/runtime/src/runtime/application/prune.py`;
`prune_source.py` = `src/runtime/src/runtime/adapters/prune_source.py`;
tests = `src/runtime/tests/unit/test_prune.py`.

**A is HIGH (wrong eviction order).**

---

## APPLY A — canonicalize timestamps in the adapter (Blind #3, Edge #1, HIGH)

**Situation.** Recency is compared lexicographically, but the repo's
`_now_iso_z()` emits variable-width fractional seconds (`…:56Z` vs
`…:56.900000Z`) and the adapter accepts offsets/non-ISO strings, so
lexicographic ≠ chronological: a newer entry sorts older and is evicted first.
Reproduced with `keep=1`.

**Proposal.** Normalize in `prune_source._read_timestamp` to a fixed-width
UTC form, so the use case's lexicographic sort stays correct and pure.
```python
# BEFORE
    value = meta.get(_timestamp_key(layer))
    return value if isinstance(value, str) and value else None
# AFTER
    value = meta.get(_timestamp_key(layer))
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)  # accepts 'Z' + offsets (3.11+)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
```
(+ `from datetime import UTC, datetime`). Update the adapter test expectation to
the canonical form.

## APPLY B — seed pins: torn-tail-only tolerance (Blind #4, Edge #2, Auditor #4)

**Situation.** `seed_pins` skips ANY corrupt line, so a corrupt first line lets
a LATER seed line be treated as "oldest" — pinning the wrong generation and
leaving the real first-run defaults evictable (fails unsafe).

**Proposal.** Mirror the reader policy: only a torn TRAILING line is tolerated;
mid-file corruption → no pins (safe degradation).
```python
# BEFORE
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue  # torn/corrupt line — skip, never crash
# AFTER
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            if i == last_index and not raw.endswith("\n"):
                break  # torn trailing line only
            return pins  # mid-file corruption: oldest seed unknowable → no pins
```
(compute `lines`, `last_index = max non-blank index` before the loop)

## APPLY C — refuse a symlinked `cache/` root (Blind #1)

**Situation.** `entries_for` guards a symlinked layer dir but not `cache/`
itself, unlike `InspectCacheUseCase`; a `cache -> /elsewhere` link plans
deletion of out-of-tree entries.

**Proposal.** Early `if (state_root / "cache").is_symlink(): return []`.

## APPLY D — symlinked `meta.json` → undated/protected (Blind #2, Edge #3)

**Situation.** `_read_timestamp` follows a symlinked `meta.json`, reading an
arbitrary file's JSON for recency.

**Proposal.** `if meta_path.is_symlink(): return None` at the top of
`_read_timestamp`.

## APPLY E — history read via `O_NOFOLLOW` (Edge #4)

**Situation.** `is_symlink()` then `read_text()` is a TOCTOU; the rest of the
codebase opens history with `O_NOFOLLOW`.

**Proposal.** `os.open(history_path, os.O_RDONLY | os.O_NOFOLLOW)` + `fdopen`.

## APPLY F — protect per-monitor wallpaper hashes (Auditor #3)

**Situation.** `_active_hashes` protects only `state.wallpaper.content_hash`,
ignoring `MonitorWallpaperConfig.source_hash`.

**Proposal.** `active["wallpapers"].update(cfg.source_hash for cfg in state.monitors.values())`.

## APPLY G — tests (Blind #5, Edge #5, Auditor #6)

Add: symlinked `cache/` root, symlinked layer dir, symlinked entry dir,
symlinked `meta.json`; equal-timestamp tie determinism; undated does not
consume a keep slot; corrupt FIRST seed line → no pins; fractional-second vs
whole-second ordering; per-monitor active protection.

## APPLY H — story hygiene (Auditor #2, #7)

Rename the story field `kept_layer_count` → `kept` (matches code); amend AC4
per-removal-reason wording (reasons are surfaced by Story 3.3 logging);
tick boxes; append the Gate 2 record.

---

## DISMISS X1 — extract `_is_entry_name` to a shared domain helper (Auditor #5)

Duplication is 3 lines and stable; `cache.py` already has its own private
`_is_hex64`, and adapters can't import `application/` (AD-25). Consolidating
all three predicates is a cross-cutting refactor out of this story's scope.

## DISMISS X2 — per-removal reason field in `PrunePlan` (Auditor #1)

The plan's single documented policy (unreferenced ∧ outside last-N ∧
not-seed-pinned) is one reason for every candidate; per-item reason strings
belong to the removal/logging step (Story 3.3). AC4 is amended accordingly.

---

## Item-to-finding index

| Item | Findings |
|------|----------|
| A | Blind #3, Edge #1 (HIGH) |
| B | Blind #4, Edge #2, Auditor #4 |
| C | Blind #1 |
| D | Blind #2, Edge #3 |
| E | Edge #4 |
| F | Auditor #3 |
| G | Blind #5, Edge #5, Auditor #6 |
| H | Auditor #2, Auditor #7 |
| Dismiss X1 | Auditor #5 |
| Dismiss X2 | Auditor #1 |

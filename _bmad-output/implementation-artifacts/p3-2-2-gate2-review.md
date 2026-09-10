# Gate 2 Review — p3-2-2 Doctor Repair

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
22 findings (overlapping). Zero files changed — all items below are proposals.

Files: `doctor.py` = `src/runtime/src/runtime/application/doctor.py`;
`cache.py` = `src/runtime/src/runtime/adapters/cache.py`;
`seeder.py` = `src/runtime/src/runtime/adapters/seeder.py`;
`main.py` = `src/runtime/src/runtime/cli/main.py`;
tests = `src/runtime/tests/unit/test_doctor_repair.py`.

Severity: **A and B are blockers; D is major.**

---

## APPLY A — detect artifact-hash mismatch in `check()` (Auditor #1, BLOCKER)

**Situation.** `_check_entries` verifies existence/parse/presence but never
re-hashes artifacts. An artifact tampered in place with `meta.json` unchanged
classifies `ok`, so `repair()` short-circuits clean and AC2 ("corrupt-by-digest
entries quarantine + repopulate") is unimplementable. The only "digest" test
actually deletes the file (absence, not mismatch).

**Proposal.** Add a hash leg over each recorded pair (application may import
`adapters.hashing` — allowlisted). `content_hash`-only wallpaper metas have no
`artifact_hashes` and are skipped (wallpaper integrity is reconcile's
`_ensure_wallpaper_entry` job).
```python
# BEFORE (doctor.py _check_entries, artifact loop)
                if not (entry_dir / rel).is_file():
                    items.append(_item("diverged", f"artifact absent: {rel}"))
                    break
# AFTER
                if not (entry_dir / rel).is_file():
                    items.append(_item("diverged", f"artifact absent: {rel}"))
                    break
                try:
                    actual = hash_file(entry_dir / rel)
                except OSError:
                    items.append(_item("diverged", f"artifact unhashable: {rel}"))
                    break
                if actual != recorded[rel]:
                    items.append(_item("diverged", f"artifact digest mismatch: {rel}"))
                    break
```
(+ `from runtime.adapters.hashing import hash_file`)
**Boundary note:** this evolves 2.1's "structural only" AC4 — doctor is the
diagnostic/integrity command; Story 3.1's `cache list --verify` remains a
separate command. Ratified in the story record.

## APPLY B — palette canonical-artifact enforcement (Blind #1/#4 + Edge none, BLOCKER)

**Situation.** (1) `check` only validates keys present in `meta["artifact_hashes"]`,
so deleting one canonical key from meta (files present) reads `ok`, repair
no-ops, yet reconcile's `ensure_palette_entry_complete` calls
`shutil.rmtree` on it — the never-delete violation (BLOCKER). (2) A palette
meta with an absent map passes as legacy-ok, but reconcile then reads meta,
finds no `artifact_hashes`, and rmtrees it. Repair must flag every entry
reconcile would evict so it is **quarantined** first (rename-aside, never rm).

**Proposal.** Palettes require the canonical 6 names (present in meta AND on
disk with matching digests); absent/malformed map for palettes → `diverged`.
```python
# BEFORE
            recorded = meta.get("artifact_hashes")
            if recorded is None:
                pass  # legacy shape: nothing recorded (Story 3.1 annotates on read)
            elif not isinstance(recorded, dict) or not all(
                isinstance(key, str) for key in recorded
            ):
                items.append(_item("diverged", "meta.json artifact_hashes malformed"))
                continue
            else:
                listed.extend(recorded)
# AFTER
            recorded = meta.get("artifact_hashes")
            if recorded is None:
                if layer == "palettes":
                    # canonical set required; absence is incomplete (reconcile would evict)
                    items.append(_item("diverged", "palette meta.json lacks artifact_hashes"))
                    continue
                # effects/icons legacy shape: nothing recorded (3.1 annotates on read)
            elif not isinstance(recorded, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in recorded.items()
            ):
                items.append(_item("diverged", "meta.json artifact_hashes malformed"))
                continue
            else:
                listed.extend(recorded)
            if layer == "palettes":
                listed.extend(PALETTE_LINK_NAMES)  # canonical required names
```
This also folds in Apply H (value-type validation). The artifact loop then
checks presence + digest for the union (canonical ∪ recorded).
**Effect:** any palette reconcile would evict is now `diverged` → quarantined
by repair → reconcile sees it absent → rebuilds via staging (no `rmtree`).

## APPLY C — quarantine non-dir entries (file/symlink squat) (Blind #3 + Edge #1/#2, major)

**Situation.** `quarantine_entry` returns `None` for a non-dir at the entry
path; doctor flags it `missing`, reconcile's `.exists()` sees it present →
repair exits 0 with a history line while `check` stays unclean, and spams one
line per run.

**Proposal.**
```python
# BEFORE (cache.py quarantine_entry)
    entry_dir = state_root / "cache" / layer / entry_hash.lower()
    if not entry_dir.is_dir():
        return None
# AFTER
    entry_dir = state_root / "cache" / layer / entry_hash.lower()
    if not entry_dir.exists() and not entry_dir.is_symlink():
        return None  # absent: nothing to move
```
Moving the squatter aside lets reconcile rebuild the (now-absent) entry.

## APPLY D — roll back quarantine if reconcile fails (Blind #2, major)

**Situation.** Entries are moved aside before reconcile; if reconcile raises
(e.g. seeded machine: `source_path=""` → `_ensure_wallpaper_entry` raises),
moved entries are never restored and the machine is strictly worse.

**Proposal.** `DoctorRepairUseCase` gains `state_root: Path`; on reconcile
failure, restore each quarantined dir (best-effort) then re-raise.
```python
# BEFORE (doctor.py repair())
        reconciled = self._reconcile.run(trigger="doctor")
# AFTER
        try:
            reconciled = self._reconcile.run(trigger="doctor")
        except BaseException:
            for moved in reversed(quarantined):
                layer = moved.parent.name
                entry_hash = moved.name.split("-", 1)[0]
                restore = self._state_root / "cache" / layer / entry_hash
                if not restore.exists() and not restore.is_symlink():
                    try:
                        os.rename(moved, restore)
                    except OSError:
                        logger.exception("doctor repair: could not restore %s", moved)
            raise
```
(+ `import os`, `import logging`, `logger`, ctor `state_root`.)

## APPLY E — quarantine rename race → None (Edge #3)

**Situation.** Quarantine runs outside the mutex; a concurrent repair's
`os.rename` raises `FileNotFoundError` (uncaught OSError → exit 1).

**Proposal.**
```python
# BEFORE
    os.rename(entry_dir, target)
    return target
# AFTER
    try:
        os.rename(entry_dir, target)
    except FileNotFoundError:
        return None  # concurrent repair already moved it
    return target
```

## APPLY F — quarantine collision loop (Blind #6)

**Situation.** Single `if target.exists()` check then one uuid; rename onto an
existing empty dir can silently replace it.

**Proposal.** `while target.exists(): target = ... uuid ...`.

## APPLY G — `_entry_dir` lowercases (Edge #5)

**Situation.** `cache_entry_path`/`quarantine_entry` lowercase; `_entry_dir`
does not, so an uppercase hash in state is permanently unr epairable.

**Proposal.** `return self._state_root / "cache" / layer / entry_hash.lower()`.

## APPLY I — `append_history` newline guard (Edge #4)

**Situation.** A torn trailing line (no final newline) gets concatenated with
the next appended line → an unparseable MIDDLE line; a healing `doctor
--repair` corrupts the must-not-lose log. (2.3 will add reader tolerance +
`--repair` truncation, but the writer shouldn't create new damage.)

**Proposal.** Prefix `"\n"` when the file is non-empty and does not end in a
newline (computed after `history_path`).

## APPLY J — test hardening (Blind #7/#8 + Auditor #3/#4)

Add: whole-entry byte-identity of the quarantined dir; digest-mismatch
(tamper bytes, keep meta) → quarantined+repopulated; incomplete-palette (drop
a canonical key) → diverged+quarantined; file-squat entry heal; seeded
`source_path=""` + missing wallpaper → rollback (state not worse); multi-entry
corruption → exactly ONE `doctor` history line; spine snapshot comparing
removed/changed (not just added).

## APPLY K — story hygiene + AD-22 ratification (Auditor #5/#6/#7)

Tick boxes; fix the ctor text to the shipped/updated signature; record the
`DoctorUseCase`/`DoctorRepairUseCase` split as the ratified AD-22 reading and
the 2.1-AC4 boundary amendment (digest leg added in 2.2).

---

## DISMISS X1 — hold the mutex across check+quarantine+reconcile

**Claim (Edge #3 part 2):** concurrent repairs can quarantine a freshly
regenerated good entry. **Rebuttal:** `doctor --repair` is an explicit,
operator-run command, not a hot path; Apply E removes the crash symptom and
Apply D makes any damage recoverable. Full mutual exclusion would require
threading the seed mutex through the repair use case and serializing a
potentially long reconcile behind interactive runs — deferred, documented.

## DISMISS X2 — reconcile `.exists()` → `.is_dir()` for effects/icons

**Claim (Edge #2):** a squatter file is "present" to reconcile but "missing"
to doctor. **Rebuttal:** Apply C moves the squatter aside before reconcile, so
reconcile sees it absent and rebuilds — no Phase-2 behavior churn. The broader
`.exists()`→`.is_dir()` change would alter seed/apply/reconcile semantics for
an input repair already normalizes; recorded as a follow-up note only.

---

## Item-to-finding index

| Item | Findings |
|------|----------|
| A | Auditor #1 (blocker) |
| B | Blind #1, Blind #4, Edge none (blocker) |
| C | Blind #3, Edge #1, Edge #2 |
| D | Blind #2 |
| E | Edge #3 |
| F | Blind #6 |
| G | Edge #5 |
| H | Blind #5 (folded into B) |
| I | Edge #4 |
| J | Blind #7, Blind #8, Auditor #3, Auditor #4 |
| K | Auditor #5, Auditor #6, Auditor #7 |
| Dismiss X1 | Edge #3 (concurrency) |
| Dismiss X2 | Edge #2 (reconcile semantics) |

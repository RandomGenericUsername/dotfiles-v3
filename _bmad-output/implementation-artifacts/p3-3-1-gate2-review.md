# Gate 2 Review — p3-3-1 `cache list --verify` Per-Entry Health

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
~20 findings (overlapping). Zero files changed — all proposals.

Files: `cache.py` = `src/runtime/src/runtime/adapters/cache.py`;
`verify_cache.py` = `src/runtime/src/runtime/application/verify_cache.py`;
`main.py` = `src/runtime/src/runtime/cli/main.py`;
tests = `src/runtime/tests/unit/test_verify_cache.py`.

**A is major (security/containment).**

---

## APPLY A — symlink containment in verify_entry + annotation (Blind #2, Edge #1, Auditor #2)

**Situation.** The read path joins `entry_dir / rel` and hashes it without
resolving/containment-checking, unlike `verify_staging` (which uses
`resolve()` + `is_relative_to`). A recorded artifact that is a symlink to a
file outside the entry is hashed and reported `ok`; `_annotate_legacy` would
persist hashes of external files. A symlinked `meta.json` is likewise followed.

**Proposal.**
```python
# BEFORE (cache.py verify_entry)
        target = entry_dir / rel
        if not target.is_file():
            return EntryHealth("missing", f"artifact absent: {rel}")
        try:
            actual = hash_file(target)
# AFTER
        try:
            entry_resolved = entry_dir.resolve()
            resolved = (entry_dir / rel).resolve()
        except (OSError, ValueError) as exc:
            return EntryHealth("corrupt", f"unresolvable artifact {rel}: {exc}")
        if not resolved.is_relative_to(entry_resolved):
            return EntryHealth("corrupt", f"artifact escapes entry: {rel}")
        if not resolved.is_file():
            return EntryHealth("missing", f"artifact absent: {rel}")
        try:
            actual = hash_file(resolved)
```
plus at the top: `if entry_dir.is_symlink() or meta_path.is_symlink(): return EntryHealth("corrupt", "symlinked entry/meta refused")`, and in `_annotate_legacy` skip escaping symlinks (mirror `canonical_hash_dir`'s external-target sentinel).

## APPLY B — annotation write failure → verdict, not crash (Blind #1, Edge #2)

**Situation.** `open`/`json.dump`/`fsync`/`os.replace` OSError escapes
`_annotate_legacy`, so one unwritable legacy entry aborts the whole verify run,
violating the documented "never hard-failed" contract.

**Proposal.**
```python
# BEFORE
        os.replace(tmp, meta_path)
    finally:
# AFTER
        os.replace(tmp, meta_path)
    except OSError as exc:
        return EntryHealth("corrupt", f"legacy annotation failed: {exc}")
    finally:
```

## APPLY C — empty map = legacy; validate hash_algorithm (Blind #3/#4, Edge #5, Auditor #4)

**Situation.** `artifact_hashes: {}` is treated as "verified" (files unhashed),
while `None` is correctly annotated; and a non-sha256 `hash_algorithm` passes.

**Proposal.**
```python
# BEFORE
    recorded = meta.get("artifact_hashes")
    if recorded is None:
        if not annotate:
            return EntryHealth("ok", "legacy entry (unverified)")
        return _annotate_legacy(entry_dir, meta, meta_path)
# AFTER
    alg = meta.get("hash_algorithm")
    if alg is not None and alg != HASH_ALGORITHM:
        return EntryHealth("corrupt", f"hash_algorithm={alg!r} != {HASH_ALGORITHM!r}")
    recorded = meta.get("artifact_hashes")
    if not recorded:  # None OR {} → nothing recorded (legacy)
        if not annotate:
            return EntryHealth("ok", "legacy entry (unverified)")
        return _annotate_legacy(entry_dir, meta, meta_path)
```

## APPLY D — annotation temp hygiene + mode preservation (Blind #5, Edge #3/#4)

**Situation.** A leftover `.meta.json.tmp.*` from a crash gets hashed and
permanently recorded as an artifact; the tmp-replace loses the original
`meta.json` mode.

**Proposal.** In the walk skip `rel == "meta.json" or path.name.startswith(".meta.json.tmp.")`; before `os.replace`, `shutil.copymode(meta_path, tmp)` (guarded).

## APPLY E — use `cache_entry_path` in verify_cache (Auditor #5)

**Situation.** The use case re-derives `state_root / "cache" / layer / hash`
instead of the validated `cache_entry_path`, duplicating the layout contract.

**Proposal.** Import `cache_entry_path` from `runtime.adapters.cache`
(application may import adapters) and use it.

## APPLY F — unrecorded-extra detection (Blind #3, Edge #6)

**Situation.** A recorded map that omits an on-disk artifact (or a stray file)
verifies `ok`, unlike `verify_staging` which rejects unrecorded files.

**Proposal.** After the recorded loop, walk `entry_dir.rglob("*")` and return
`corrupt` for any non-dir file (except root `meta.json` / `.meta.json.tmp.*`)
not in `recorded`.

## APPLY G — tests (Blind #6, Edge #7, Auditor #3)

Add: symlink-escape recorded artifact → corrupt; `..` key → corrupt; `{}` map
with files → annotated; annotation write failure (monkeypatched `os.replace`)
→ corrupt not raise; `missing` entry → CLI exit 1; a golden snapshot of the
default `inspect cache list` plain + JSON output; fix the lister spy return
annotation (`-> InspectCacheResult`, `# type: ignore[assignment, method-assign]`).

## APPLY H — story/docs (Auditor #1, #6, #7)

Fix AC5 "meta absent → `corrupt`" → `missing` (matches code/task/test); add the
exit-non-zero-on-unhealthy AC; note the annotation walk as a sanctioned one-time
`1 + N` path outside NFR-4's steady-state single walk; tick boxes + record.

---

## DISMISS — none proposed

All findings are applied (F is the strict-parity option; if leniency is
preferred for unrecorded files, say so and F becomes a dismissal).

---

## Item-to-finding index

| Item | Findings |
|------|----------|
| A | Blind #2, Edge #1, Auditor #2 |
| B | Blind #1, Edge #2 |
| C | Blind #3, Blind #4, Edge #5, Auditor #4 |
| D | Blind #5, Edge #3, Edge #4 |
| E | Auditor #5 |
| F | Blind #3, Edge #6 |
| G | Blind #6, Edge #7, Auditor #3 |
| H | Auditor #1, Auditor #6, Auditor #7 |

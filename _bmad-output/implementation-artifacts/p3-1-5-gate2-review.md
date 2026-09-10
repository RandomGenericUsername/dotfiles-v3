# Gate 2 Review — p3-1-5 Digest Enforcement at Populate Time

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
16 findings (several overlapping). Zero files changed — all items below are proposals.

Files: `cache.py` = `src/runtime/src/runtime/adapters/cache.py`;
`models.py` = `src/runtime/src/runtime/domain/models.py`;
tests = `src/runtime/tests/unit/test_populate_enforcement.py`;
story = `_bmad-output/implementation-artifacts/p3-1-5-digest-enforcement-at-populate.md`.

---

## APPLY A — catch UnicodeDecodeError on meta read (Blind #1)

**Situation.** `meta_path.read_text(encoding="utf-8")` on binary-garbage bytes
raises `UnicodeDecodeError` — a `ValueError`, not `OSError` — escaping the
`except OSError` as a raw crash, violating the zero-crash contract the whole
function otherwise honors.

**Proposal.**
```python
# BEFORE (cache.py, verify_staging)
    try:
        raw = meta_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorruptCacheError(f"cannot read staging meta.json in {staging}: {exc}") from exc
# AFTER
    try:
        raw = meta_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise CorruptCacheError(f"cannot read staging meta.json in {staging}: {exc}") from exc
```
**Alignment.** Precise catch (decode errors only, not broad `ValueError`);
every read path in the function now terminates in `CorruptCacheError`.

## APPLY B — algorithm check precedes the absent-map return (Blind #2)

**Situation.** `hash_algorithm` is verified only AFTER the `artifact_hashes is
None → return` early exit, so a map-absent entry declaring `md5` (or no
algorithm) publishes unchecked — inconsistent: a declared non-sha256 is writer
corruption whether or not digests are listed.

**Proposal.** Move the algorithm check above the absent-return:
```python
# BEFORE
    recorded = meta.get("artifact_hashes")
    if recorded is None:
        return  # heterogeneous/legacy shape ...
    if not isinstance(recorded, dict) or ...:
        raise CorruptCacheError(...)
    if meta.get("hash_algorithm") != HASH_ALGORITHM:
        raise CorruptCacheError(...)
# AFTER
    if meta.get("hash_algorithm") != HASH_ALGORITHM:
        raise CorruptCacheError(
            f"staging meta.json declares hash_algorithm={meta.get('hash_algorithm')!r} "
            f"(expected {HASH_ALGORITHM!r}) in {staging}"
        )
    recorded = meta.get("artifact_hashes")
    if recorded is None:
        return  # heterogeneous/legacy shape: nothing recorded, nothing to verify
    if not isinstance(recorded, dict) or ...:
        raise CorruptCacheError(...)
```
**Alignment.** Strictest coherent rule: algorithm is universal (pinned
everywhere), the MAP's presence opts into per-artifact enforcement. No legit
writer declares a non-sha256 algorithm.

## APPLY C — up-front relpath validation (Blind #3 + Blind #4 + Edge #2, merged)

**Situation.** Three related gaps: (1) a NUL byte in a recorded relpath makes
`resolve()` raise `ValueError`, uncaught (only `OSError` is caught) → raw
crash; (2) unnormalized keys (`"a/../b"`, `"./x"`, absolute, `""`, `"."`,
`"meta.json"`) either false-positive as unrecorded or fail misleadingly
(`""` reports "missing" since `staging/""` is the dir; `"meta.json"` is an
unmatchable self-reference).

**Proposal.** Validate every key BEFORE hashing (fail loud with a clear
message), and harden the resolve catch:
```python
# BEFORE (top of the recorded loop)
    for relpath, expected in recorded.items():
        candidate = staging_resolved / relpath
        try:
            resolved = candidate.resolve()
        except OSError as exc:
            raise CorruptCacheError(...) from exc
# AFTER
    for relpath, expected in recorded.items():
        if (
            not relpath
            or relpath in (".", "meta.json")
            or relpath.startswith("/")
            or "\x00" in relpath
            or ".." in Path(relpath).parts
        ):
            raise CorruptCacheError(f"malformed artifact relpath: {relpath!r} in {staging}")
        candidate = staging_resolved / relpath
        try:
            resolved = candidate.resolve()
        except (OSError, ValueError) as exc:
            raise CorruptCacheError(...) from exc
```
**Alignment.** One validation choke point with an honest error; the
`(OSError, ValueError)` catch stays as defense-in-depth. Real generators emit
clean relative posix paths, so no legit writer is affected.

## APPLY D — guard the extras walk (Blind #5 + Edge #1, merged)

**Situation.** `for path in staging.rglob("*")` has no `OSError` guard (unlike
`hashing.py:205`, which wraps traversal errors): a transient mid-walk error
(EACCES on a subdir, symlink race on `relative_to`) escapes raw.

**Proposal.**
```python
# BEFORE
    recorded_set = set(recorded)
    for path in staging.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            continue
        rel = path.relative_to(staging).as_posix()
# AFTER
    recorded_set = set(recorded)
    try:
        walk = list(staging.rglob("*"))
    except OSError as exc:
        raise CorruptCacheError(f"cannot enumerate staging dir {staging}: {exc}") from exc
    for path in walk:
        if path.is_dir() and not path.is_symlink():
            continue
        try:
            rel = path.relative_to(staging).as_posix()
        except (OSError, ValueError) as exc:
            raise CorruptCacheError(f"cannot inspect staged entry in {staging}: {exc}") from exc
```
**Alignment.** Same zero-crash discipline as the rest of the function;
materializing the walk first also freezes the enumeration against races.

## APPLY E — document the verify→rename assumption (Blind #6, modified to doc-only)

**Situation.** TOCTOU window between verification and `os.rename`: staging
files could be swapped post-check. The reviewer proposed `mkdir(mode=0o700)`;
that changes behavior for ALL populate paths (umask interplay, mode-assertion
risk in existing tests) for a same-user threat model the codebase accepts
elsewhere.

**Proposal (doc-only).** Append to `verify_staging`'s docstring: assumes no
concurrent writer to the PID-namespaced staging dir between verification and
rename; PID-namespacing + same-user threat model make the window acceptable
(documented, not mitigated).

**Alignment.** Honest about the residual risk without behavior churn on a
mechanism 9 existing tests pin down.

## APPLY F — test hardening: orphans + hostile keys (Blind #7 + Edge #4, merged)

**Situation.** Corruption tests assert "target absent" but mostly omit the
orphan assertion; no test covers traversal keys, bad-UTF-8 meta, nested
`meta.json`, or absent-map-plus-wrong-algorithm (which pins Apply B).

**Proposal.** Add `assert _staging_orphans(tmp_path) == []` to every
`CorruptCacheError` test, plus:
- `test_traversal_and_absolute_keys_rejected`: `{"/etc/passwd": h}`,
  `{"a/../../x": h}`, `{"": h}`, `{"meta.json": h}` → each `CorruptCacheError`,
  target absent, no orphans.
- `test_bad_utf8_meta_raises`: raw non-UTF-8 bytes as meta → `CorruptCacheError`
  (pins Apply A).
- `test_nested_meta_json_must_be_recorded`: `staging/sub/meta.json` unrecorded
  → `CorruptCacheError` (pins the root-only exclusion).
- `test_absent_map_wrong_algorithm_raises`: map absent + `md5` → `CorruptCacheError`
  (pins Apply B's reorder).

## APPLY G — story :41 rewritten to absent→skip (Auditor #1)

**Situation.** Tasks still prescribe absent→error while the deviation note,
implementation, and test all implement absent→skip — the story contradicts
itself.

**Proposal.** Rewrite :41: "require `artifact_hashes` to be a `str→str` map
when PRESENT (malformed → `CorruptCacheError`); ABSENT → return without
verification per deviation above (heterogeneous/legacy shape; Story 3.1
annotates on read)". No code impact.

## APPLY H — narrow AC3 to placeability (Auditor #2)

**Situation.** AC3's second clause ("`application/` surfaces the error as
data") has zero evidence: no application changes exist, catching is deferred
to 2.2.

**Proposal.** Narrow AC3 to what this story proves: "error type lives in
`domain/` so `application/` CAN catch it without importing `adapters/`
(surfacing/quarantine deferred to Story 2.2)". Honest scoping, no code impact.

## APPLY I — append AC5 layering (Auditor #3)

**Situation.** Epics Story 1.5 carries a 5th AC (layering green); the story
dropped it.

**Proposal.** Append AC5: "`tests/architecture/test_layering.py` passes
unchanged (AR-6)". Epics→story mapping back to 1:1. No code impact.

## APPLY J — delta frontmatter to adopted (Auditor #4)

**Situation.** Frontmatter still `status: proposed` while the adopted line and
both `[ADOPTED]` markers claim adoption — half-applied flip.

**Proposal.** Frontmatter → `status: adopted` (keep the `adopted:` line). No code impact.

---

## DISMISS 1 — meta.json-as-directory → CorruptCacheError (Edge #3)

**Claim.** Directory-named-meta hits the `is_file()` guard as `RuntimeError`
(programmer-error) instead of `CorruptCacheError` (corruption).

**Rebuttal.** Verified: derive has no broad `except` — both types propagate
loudly with identical staging cleanup, so the distinction is log-cosmetic.
The guard's programmer-error semantics are deliberate (only `populate_fn`
writes staging; a dir-named-meta is a generator bug, and the guard exists to
say exactly that). Doctor-2.2 classification applies to PUBLISHED entries,
never to staging. No change.

---

## Item-to-finding index

| Item | Reviewer findings |
|------|-------------------|
| A | Blind #1 |
| B | Blind #2 |
| C | Blind #3 + Blind #4 + Edge #2 |
| D | Blind #5 + Edge #1 |
| E | Blind #6 (modified: doc-only, no chmod) |
| F | Blind #7 + Edge #4 |
| G | Auditor #1 |
| H | Auditor #2 |
| I | Auditor #3 |
| J | Auditor #4 |
| Dismiss 1 | Edge #3 (rebutted: identical loudness/cleanup; guard semantics stand) |

# Gate 2 Review — p3-1-4 Selective Regeneration + Cascade + Reconverge

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
18 findings (several overlapping). Zero files changed — all items below are proposals.

Conventions: `regenerate.py` = `src/runtime/src/runtime/application/regenerate.py`;
`main.py` = `src/runtime/src/runtime/cli/main.py`; tests =
`src/runtime/tests/unit/test_regenerate_stale.py`.

---

## APPLY A — CAS compares the derivation projection, not just wallpaper (BH #1 + EH #3, modified)

**Situation.** `_save_guarded` compares only `wallpaper.content_hash`. A concurrent
writer that changed derived entries under the SAME wallpaper (second regen,
`wallpaper set` re-derivation edge) is silently clobbered — save overwrites
newer entries with older ones.

**Proposal (modified from both reviewers).** Reviewers proposed full-dataclass
equality (`current != observed`). That over-triggers: `applied_at`/monitors
churn (a concurrent plain `reconcile` refresh) would abort regen spuriously,
wasting a minutes-long derive. Compare the derivation-relevant projection
instead — wallpaper hash + the three entry hashes (the exact inputs `save`
overwrites). Timestamp churn never aborts; semantic drift always does:
```python
# BEFORE (regenerate.py, _save_guarded)
            if (
                current is None
                or current.wallpaper.content_hash != observed.wallpaper.content_hash
            ):
# AFTER
            if current is None or _projection(current) != _projection(observed):
# ...with helper:
def _projection(state: DesktopState) -> tuple[str | None, ...]:
    """Derivation-relevant identity: what save() overwrites."""
    return (
        state.wallpaper.content_hash,
        state.palette.entry_hash if state.palette else None,
        state.effects.entry_hash if state.effects else None,
        state.icons.entry_hash if state.icons else None,
    )
```
**Alignment.** Fails loud only on semantic drift (never clobbers, never wastes
derives on timestamp churn); keeps the no-long-lock split (derive unlocked,
CAS window is one re-load).

## APPLY B — unknown stale tokens raise (BH #2 + EH #2)

**Situation.** A stale set containing an unknown token (e.g. `{"wallpapers"}`
from a future/buggy check) is non-empty, so it skips the no-op, saves an
identical state, and appends a spurious `regenerate` history line via
reconcile — a full desktop reload for nothing.

**Proposal.**
```python
# BEFORE (regenerate.py run(), after the empty-stale no-op return)
        if not stale:
            return RegenerateResult(regenerated=frozenset(), state=state)
# AFTER
        if not stale:
            return RegenerateResult(regenerated=frozenset(), state=state)
        unknown = set(stale) - {"palettes", "effects", "icons"}
        if unknown:
            raise ValueError(f"unknown stale layers: {sorted(unknown)}")
```
**Alignment.** Fail-loud parity with p3-1-1/p3-1-2 unknown-layer rules; the
check path can never smuggle no-op work into a mutating pipeline again.

## APPLY C — stale-but-absent palette/effects heal instead of raising (EH #1, modified)

**Situation.** `palettes ∈ stale` with `state.palette is None` raises
`RuntimeError` — but `ensure_palette` needs only wallpaper bytes, so a
degraded (healable) state hard-errors instead of healing. (1.3 marks missing
layers stale precisely so they get rebuilt.)

**Proposal.** Drop the two guards; derive unconditionally when stale:
```python
# BEFORE
        if "palettes" in stale:
            if state.palette is None:
                raise RuntimeError("palette layer stale but no palette entry recorded")
            new_palette, _ = self._pipeline.ensure_palette(wallpaper_path, wallpaper_hash)
# AFTER
        if "palettes" in stale:
            new_palette, _ = self._pipeline.ensure_palette(wallpaper_path, wallpaper_hash)
```
(same for effects). KEEP the icons guard (`new_palette is None → RuntimeError`):
icons needs a palette hash and the guard is now defensive-dead code — palette
is either present (recorded) or just rebuilt — which is exactly what a
defensive invariant should be.

**Alignment.** Regen heals degraded states (its job); the icons guard stays as
an assertion-style tripwire, not a reachable path.

## APPLY D — no-op still validates wallpaper bytes (BH #5)

**Situation.** The no-op path returns before `_wallpaper_bytes()`: a fresh
check with missing cached `wallpaper.png` succeeds quietly, hiding latent
corruption (hyprpaper would fail at reload).

**Proposal.**
```python
# BEFORE
        if not stale:
            return RegenerateResult(regenerated=frozenset(), state=state)
# AFTER
        if not stale:
            self._wallpaper_bytes(state)  # fail loud on missing cache bytes even when fresh
            return RegenerateResult(regenerated=frozenset(), state=state)
```
**Alignment.** One `is_file` probe; a `regenerate` that reports "converged"
while bytes are missing is a lie — fail loud, doctor repopulates.

## APPLY E — seeder.py trigger docstring (BH #6)

**Situation.** `adapters/seeder.py` docstring pins the 4-value trigger enum
while reconcile/inspect validators accept 5 — docs drift on first regen.

**Proposal.** One-liner: ``seed|set|reconcile|force`` → 
``seed|set|reconcile|force|regenerate`` at seeder.py:712-713. Doc-only.

## APPLY F — absent test exercises the load-None branch (BH #7)

**Situation.** The current absent test scripts the CHECK to raise, so
`run()` never reaches the `state is None` branch — the loud-absent path is
untested.

**Proposal.** Script check success + `state=None`: `stale_script=[frozenset({"palettes"})]`,
repo returns `None` → expect `ValueError match="no runtime state recorded yet"`,
zero pipeline/reconcile touches.

## APPLY G — JSON object gains state hashes (BH #8)

**Situation.** The `--regenerate-stale` JSON object exposes only
`regenerated/repointed/reload_failures`, unlike the reconcile/check paths
that expose state hashes for scripting.

**Proposal.** Add `wallpaper` (content hash) + `palette`/`effects`/`icons`
(entry hashes or null) to the object. Cheap, scripting parity.

## APPLY H — docstring repair-path note (EH #4)

**Situation.** Save-then-reconcile leaves a documented-nowhere divergence
window (new `current.json`, old symlinks, no history) if `reconcile.run()`
raises.

**Proposal.** Append to the module concurrency contract: if `reconcile.run()`
raises after the guarded save, the next plain `reconcile` (recovery + repoint)
repairs it — re-run, do not hand-edit state. Doc-only.

## APPLY I — e2e asserts the repoint (AA #1)

**Situation.** The e2e proves save/history/reload but never asserts
`current/` repoint — AC2's "repointed current/" is exercised only indirectly.

**Proposal.** Assert `result.repointed` non-empty and that a `current/`
symlink target resolves into the NEW-hash cache entry post-run.

## APPLY J — reload-failure passthrough test (AA #2)

**Situation.** `_FakeReconcile` always returns empty `reload_failures`, so
use-case-level R5 passthrough has no test despite the story requiring it.

**Proposal.** Fake-reconcile test with `reload_failures=("hyprland",)`:
assert `run().reload_failures == ("hyprland",)` AND the save is not rolled
back (no rollback semantics — failures surface, state stands).

## APPLY K — no-fallback proof with a VALID source file (AA #3)

**Situation.** The missing-wallpaper test uses a dummy never-created
`source_path`, so it proves loud failure but not the load-bearing "no
`source_path` fallback" semantic.

**Proposal.** Build the state with `source_path` pointing at a REAL tmp file
while omitting only the cached `wallpaper.png`; assert `ValueError` still
raises with zero pipeline calls.

## APPLY L — story boxes + contract line (AA #4)

**Situation.** Boxes unchecked at review; line 25 specs
`RegenerateResult(regenerated, state: DesktopState | None)` while the code is
`(regenerated, state: DesktopState, repointed=(), reload_failures=())` —
absent raises instead of returning `None`.

**Proposal.** Tick boxes; update line 25 to the landed contract. No code impact.

---

## DISMISS 1 — skip icons rebuild on same-hash palette (BH #3)

**Claim.** Cascade fires on `palettes in rebuilt` even when the rebuilt hash is
unchanged, forcing a needless rebuild.

**Rebuttal.** Impossible modulo SHA-256 collision: `palettes ∈ stale` means
recorded inputs ≠ recomputed inputs, and the new hash is computed from the
recomputed inputs — so it NECESSARILY differs from the recorded hash. The
icons miss is always genuine. No change.

## DISMISS 2 — reorder check/load (BH #4)

**Claim.** Stale set may describe a different revision than the mutated one.

**Rebuttal.** Both loads are unlocked either way; ordering changes nothing.
Apply A makes the guards revision-precise (projection compare). Churn with
zero semantic effect. No change.

---

## Item-to-finding index

| Item | Reviewer findings |
|------|-------------------|
| A | Blind #1, Edge #3 (modified: projection, not full equality) |
| B | Blind #2, Edge #2 |
| C | Edge #1 (modified: keep icons guard) |
| D | Blind #5 |
| E | Blind #6 |
| F | Blind #7 |
| G | Blind #8 |
| H | Edge #4 |
| I | Auditor #1 |
| J | Auditor #2 |
| K | Auditor #3 |
| L | Auditor #4 |
| Dismiss 1 | Blind #3 (rebutted: cryptographic necessity) |
| Dismiss 2 | Blind #4 (rebutted: no semantic effect post-A) |

# Gate 2 Review — p3-2-1 Doctor Three-Way Check

Date: 2026-09-10. Reviewers: Blind Hunter / Edge Case Hunter / Acceptance Auditor (parallel).
18 findings (several overlapping). Zero files changed — all items below are proposals.

Files: `doctor.py` = `src/runtime/src/runtime/application/doctor.py`;
`main.py` = `src/runtime/src/runtime/cli/main.py`;
tests = `src/runtime/tests/unit/test_doctor_check.py`.

---

## APPLY A — UnicodeDecodeError → diverged (Blind #1 + Edge #1-blocker)

**Situation.** `meta_path.read_text(encoding="utf-8")` on non-UTF-8 bytes raises
`UnicodeDecodeError` — a `ValueError`, not `OSError` — escaping `check()` as a
raw crash. Same bug class as p3-1-5 Apply A (already fixed there); the reader
here needs the same catch.

**Proposal.**
```python
# BEFORE (doctor.py, _check_entries)
            try:
                raw = meta_path.read_text(encoding="utf-8")
            except OSError:
                items.append(DriftItem(name, "entry", "diverged", f"{meta_path} unreadable"))
# AFTER
            try:
                raw = meta_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                items.append(DriftItem(name, "entry", "diverged", f"{meta_path} unreadable"))
```
**Alignment.** Zero-crash invariant: every read path terminates in a verdict,
never an exception. Precise catch (decode errors only).

## APPLY B — seed guard via typer context, kill argv parsing (Blind #3)

**Situation.** The guard strips dash-flags but not their values:
`doctor --format json` yields `argv[:1] == ["json"]` → first-run seeding
WRITES (cache/current.json/history!) before the read-only check. This breaks
AC3 in exactly the `--format json` case the story's own tests use — and the
bug is pre-existing for reconcile/inspect, now inherited by doctor.

**Proposal.** Stop parsing `sys.argv`; use the command typer already resolved:
```python
# BEFORE (main.py, main_callback)
    argv = [a for a in sys.argv[1:] if not a.startswith("-")]
    if argv[:1] in (["reconcile"], ["inspect"], ["doctor"]):
        return
# AFTER
def main_callback(
    ctx: typer.Context,
    output_format: OutputFormat = typer.Option(...),
) -> None:
    ...
    if ctx.invoked_subcommand in ("reconcile", "inspect", "doctor"):
        return
```
(Exact `typer.Option(...)` block unchanged; only the guard lines + `ctx` param.)
**Alignment.** Kills the whole bug class (operands named `reconcile`,
flag values, flag-first order) instead of patching one instance. `ctx`
is typer's documented callback context; CliRunner drives it identically, so
existing seed-guard tests keep passing (verified post-apply). Touches shared
`main_callback` minimally and justifiably: the story extended the guard, so
the guard's correctness is this story's business.

## APPLY C — artifact-key traversal validation (Blind #4 + Edge #5)

**Situation.** Recorded keys are joined unchecked: absolute (`/etc/x`) or
`..` keys escape `entry_dir` (`Path("/a") / "/etc/x" == Path("/etc/x")`),
probing/validating outside the state root and yielding false-`ok`.

**Proposal** (read path → verdicts, not exceptions):
```python
# BEFORE (doctor.py, _check_entries loop tail)
            for rel in listed:
                if not (entry_dir / rel).is_file():
# AFTER
            for rel in listed:
                if (
                    not rel
                    or rel in (".", "meta.json")
                    or rel.startswith("/")
                    or ".." in Path(rel).parts
                ):
                    items.append(
                        DriftItem(name, "entry", "diverged", f"unsafe artifact key: {rel}")
                    )
                    break
                if not (entry_dir / rel).is_file():
```
**Alignment.** Same validation doctrine as p3-1-5 Apply C, adapted to a
classifying (not raising) context. Real metas carry clean relpaths.

## APPLY D — resolve() catches RuntimeError (Blind #5 + Edge #6)

**Situation.** Symlink loops raise `RuntimeError` from `resolve()`, uncaught
(only `OSError`) → raw crash instead of `dangling`.

**Proposal.** Both resolve blocks: `except OSError:` → `except (OSError,
RuntimeError):` (actual link + expected-target fallback). Improves on
inspect's identical latent gap without touching inspect (out of scope).

## APPLY E — mirror the DEFAULT_MONITOR fallback (Edge #2)

**Situation.** Empty `state.monitors` yields zero wallpaper-link checks, but
reconcile/apply/inspect all default to `DP-1` (`reconcile.py:222`,
`inspect.py:299`, `models.py:162`) — production MANAGES those links, so a
degraded state reports clean while managed links go unchecked.

**Proposal** (mirror inspect line-for-line, incl. alias rule):
```python
# BEFORE (doctor.py, _check_links)
        for monitor in state.monitors:
            expected[f"wallpaper-{monitor}.png"] = wallpaper_target
        if state.monitors:
            expected["wallpaper.png"] = wallpaper_target
# AFTER
        from runtime.domain.models import DEFAULT_MONITOR
        monitor_names = list(state.monitors) or [DEFAULT_MONITOR]
        for monitor_name in monitor_names:
            expected[f"wallpaper-{monitor_name}.png"] = wallpaper_target
        expected["wallpaper.png"] = wallpaper_target
```
plus the name validation from Apply F (folded here — same loop). Docstring
notes the twin logic in `inspect.py` (future unification candidate, not this
story).

## APPLY F — monitor-name validation (Edge #3)

**Situation.** Names interpolate into link filenames with no guard, unlike
`inspect.py:301-309` (`/`, `\`, `..`, padded → `ValueError`).

**Proposal** (inside the Apply E loop, before building the key):
```python
            if (
                "/" in monitor_name
                or "\\" in monitor_name
                or ".." in monitor_name
                or monitor_name.strip() != monitor_name
            ):
                raise ValueError(
                    f"monitor name must not contain path separators, got {monitor_name!r}"
                )
```
**Alignment.** Identical rule to inspect; corrupt store fails loud instead of
checking phantom paths.

## APPLY G — malformed map → diverged, absent map → ok (Edge #4)

**Situation.** Present-but-malformed `artifact_hashes` (list/str/num) fails
the `isinstance dict` test and is silently SKIPPED — leg reports `ok` —
while `cache.py` treats it as corrupt. Absent map (`None`, legacy) correctly
stays `ok` per the 3.1 boundary.

**Proposal.**
```python
# BEFORE
            recorded = meta.get("artifact_hashes")
            if isinstance(recorded, dict):
                listed.extend(key for key in recorded if isinstance(key, str))
# AFTER
            recorded = meta.get("artifact_hashes")
            if recorded is None:
                pass  # legacy shape: nothing recorded (Story 3.1 annotates on read)
            elif not isinstance(recorded, dict) or not all(
                isinstance(key, str) for key in recorded
            ):
                items.append(
                    DriftItem(name, "entry", "diverged", "meta.json artifact_hashes malformed")
                )
                continue
            else:
                listed.extend(recorded)
```
**Alignment.** Three-way distinction the codebase uses everywhere:
absent→legacy-ok, malformed→diverged, well-formed→verified.

## APPLY H — exact double-leg assertions (Blind #8-test-half)

**Situation.** Breakage tests assert one item while two legs fire (e.g.
deleting an artifact yields entry-`diverged` + link-`dangling`); clean-math
and double-report behavior unpinned.

**Proposal.** Strengthen to exact full-map assertions, e.g.:
```python
by = _by_name(report)
assert by["current/colors.gtk.css"] == "dangling"
assert by[f"cache/palettes/{PH[:12]}"] == "diverged"
```
for the artifact-deletion case (and symmetric exactness where deterministic).

## APPLY I — hostile-meta + vocabulary tests (Blind #8-tests + Edge tests)

**Situation.** No tests for non-UTF-8 meta, file-instead-of-symlink, or the
pinned extra-file invisibility (Blind#6-dismiss decision needs a code pin or
it will be "rediscovered").

**Proposal.**
- non-UTF-8 `meta.json` bytes → entry `diverged`, no raise (pins Apply A).
- regular file at a link name → `missing` (pins the inspect-identical vocabulary against Blind#2).
- extra file in `current/` → report clean stays `True` (pins the Blind#6-dismiss decision in code).
- malformed-map meta → `diverged`; absent-map meta → `ok` (pins Apply G).

## APPLY J — diverged-e2e snapshot pin (Auditor #1)

**Situation.** The diverged CLI run asserts exit/report but no FS snapshot —
AC3 lacks CLI-layer diverged mutation evidence.

**Proposal.** Capture `_snapshot(state_root)` before the diverged invoke and
assert equality after (mirrors the clean e2e).

## APPLY K — boxes + review record (Auditor #2)

Flip all `- [ ]` → `- [x]`; append this Gate 2 record. No code impact.

---

## DISMISS 1 — file-instead-of-symlink → diverged (Blind #2)

**Claim.** Regular file squatting on a link name should be `diverged`, not `missing`.

**Rebuttal.** The story pins inspect-identical vocabulary (`_link_status`
returns `missing` for non-symlinks), and consistency of the shared 4-way
language across commands outweighs one arguable label — the item is still
non-`ok`, so drift is always detected, and 2.2's repoint (unlink + symlink)
repairs both cases identically. Pinned by Apply I's vocabulary test instead.

## DISMISS 2 — flag extra current/ files (Blind #6)

**Claim.** Unexpected files in `current/` should break `clean`.

**Rebuttal.** Every non-`ok` must be repairable by `--repair`, but repair can
never delete user state — flagging extras creates unactionable drift (doctor
could never go clean). Extras are inert (all consumers read fixed names, never
directory listings). Pinned as intentionally-ignored by Apply I's test.

## DISMISS 3 — conditional palette-link expectation (Blind #7)

**Claim.** Expect palette links only when targets exist (seeder skips absent).

**Rebuttal.** The seeder's skip is bootstrap tolerance; doctor reports
steady-state truth — a missing managed link IS drift (its entry leg already
fires for the absent artifact; both statements are true). Conditional
expectation would couple the checker to seeder internals. No change.

---

## Item-to-finding index

| Item | Reviewer findings |
|------|-------------------|
| A | Blind #1, Edge #1 (blocker) |
| B | Blind #3 |
| C | Blind #4, Edge #5 |
| D | Blind #5, Edge #6 |
| E | Edge #2 |
| F | Edge #3 |
| G | Edge #4 |
| H | Blind #8 (assertions) |
| I | Blind #8 (tests) + Blind #2-vocab + Blind #6-invisibility pins |
| J | Auditor #1 |
| K | Auditor #2 |
| Dismiss 1 | Blind #2 (rebutted: shared vocabulary consistency) |
| Dismiss 2 | Blind #6 (rebutted: unactionable verdicts) |
| Dismiss 3 | Blind #7 (rebutted: steady-state truth vs bootstrap tolerance) |

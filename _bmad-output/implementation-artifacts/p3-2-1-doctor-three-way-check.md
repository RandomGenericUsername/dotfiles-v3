# Story 2.1: Doctor Three-Way Check with Machine-Readable Report

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 2 — Doctor Drift Detection + Repair (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 2.1)

## Story

As a user,
I want `dotfiles-runtime doctor` to check `current.json` vs `current/` symlink targets vs `cache/<layer>/<hash>/` existence+health,
so that drift shows as ok/missing/diverged/dangling with a proper exit code.

## Acceptance Criteria

1. On a consistent machine (warm cache, aligned symlinks, valid `current.json`), `doctor` exits 0 and reports clean (AC 1, FR-3)
2. On a diverged machine (stray symlink, missing entry, corrupt `meta.json`, artifact-hash mismatch... precisely: missing entry, unparseable meta, absent listed artifact), it exits non-zero with a machine-readable report classifying each item ok/missing/diverged/dangling (AC 2, FR-3)
3. The check path performs zero mutations (AC 3)
4. Health depth is structural (existence + parse + presence) — artifact-hash RECHECK belongs to Story 3.1, not here (AC 4, boundary)

## Tasks / Subtasks

- [x] Create `src/runtime/src/runtime/application/doctor.py` (AC: 1, 2, 4)
  - [x] Reuse the `LinkStatusKind` vocabulary (`"ok" | "missing" | "diverged" | "dangling"`) from `application/inspect.py` (same layer import — allowed; identical semantics to `inspect._link_status`: missing = absent, dangling = points nowhere, diverged = points elsewhere / present-but-wrong, ok = matches)
  - [x] Frozen dataclasses `DriftItem(name: str, kind: str, status: LinkStatusKind, detail: str)` and `DoctorReport(items: tuple[DriftItem, ...], clean: bool)` (`clean` = every item ok)
  - [x] Class `DoctorUseCase(state_repo: IStateRepository, state_root: Path)` with `check() -> DoctorReport`. Read-only `Path` reads only (mirror `inspect.py`'s read-only invariant — established application-layer pattern, no new port). NO seeder/mutex/adapters in ctor. (Story 2.2 adds `repair()` to this same class; keep it import-clean for that.)
  - [x] `check()`:
    1. `load_current()` → `None` raises `ValueError` (absent loud, consistent with check-inputs/inspect-status; never seeds behind a read).
    2. Leg 1 — store→cache entries: for each ACTIVE entry (palette/effects/icons non-`None`, wallpaper always): expected dir `cache/<layer>/<hash>` exists → else `missing`; `meta.json` parses → else `diverged`; every file listed in `artifact_hashes` present → else `diverged`; else `ok`. NO cryptographic recheck (AC 4 — Story 3.1 owns it). Inactive layers (entry `None`) contribute nothing.
    3. Leg 2 — store→`current/` symlinks: expected link set computed from `current.json` (mirror `seeder.repoint_current_symlinks` inventory: `wallpaper-<monitor>.png` per monitor + `wallpaper.png` alias when monitors exist + 6 palette artifacts when palette active + `effects`/`icons` dir links when active), each classified missing/dangling/ok/diverged against its expected cache target with `inspect`-identical semantics (resolve both sides before comparing, as `_link_status` does).
    4. `clean = all(item.status == "ok")`.
  - [x] Out of scope (documented, not implemented): R2 consumer-pointer links stay `inspect`'s domain (three legs only, per CAP-3/FR-3); `history.jsonl` is never read here (torn-tail tolerance belongs to Story 2.3); repair belongs to Story 2.2
- [x] Wire the `doctor` command in `src/runtime/src/runtime/cli/main.py` (AC: 1, 2)
  - [x] New top-level `@app.command("doctor")` (like `reconcile`, NOT a sub-app — Story 2.2 adds `--repair` to this same command; shape it forward-compatibly)
  - [x] Composition helper `_run_doctor_check()` mirroring `_run_inspect_status` wiring: `state_root` absolute + `JsonStateRepository` only (no seeder, mutex, derivation adapters, reloaders)
  - [x] Render via `cli-output`: plain summary (`desktop clean: N item(s) checked` / `drift detected: <counts by status>`) + machine-readable object `{clean: bool, items: [{name, kind, status, detail}]}`; exit 0 when clean, exit 1 on drift; absent state → `ErrorView` + exit 1
  - [x] Confirm the `main_callback` seed guard covers `doctor` (argv-positional check from Story 1.3/1.4 work: `argv[:1] == ["doctor"]` skips seeding) — extend the positional list, pin with a test
- [x] Create `src/runtime/tests/unit/test_doctor_check.py` (AC: 1, 2, 3)
  - [x] Fixtures mirror `test_reconcile.py` `_apply_state` (REAL `ApplyWallpaperUseCase` with contract-honest fake tools seeds warm state), then BREAK it per case: deleted cache entry dir → `missing`; corrupt (unparseable) `meta.json` → `diverged`; stray symlink repointed elsewhere → `diverged`; target deleted → `dangling`; link removed → `missing`; listed artifact file deleted → `diverged`
  - [x] Clean fixture → `clean is True`, exit 0
  - [x] CLI shape tests (monkeypatched `_run_doctor_check`, mirroring 1.3): exit codes, plain + `--format json` object shape, absent-state exit 1, seed-guard (no seeding behind the read)
  - [x] Zero-mutation pin: FS snapshot (reuse the v2 snapshot helper pattern from 1.3: links + dirs + modes + mtimes + hashes) byte-identical before/after every check run, including the diverged cases
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_doctor_check.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — this story is the CHECK ONLY

Story 2.1 builds the three-way drift check. It does **NOT** implement:
- Repair: quarantine, repopulate, repoint, `trigger: doctor` history line (Story 2.2 — extends `DoctorUseCase` with `repair()`)
- Torn-history-tail tolerance (Story 2.3)
- `cache list --verify` / prune (Stories 3.1–3.3)
- Any mutation surface: no seeder, no mutex, no derivation adapters, no reloaders anywhere in this story's code

### Layering (AD-25, locked)

- New use case in `application/`; imports `domain` + `ports` + same-layer `application/inspect.py` (types only); read-only `pathlib` use mirrors `inspect.py` precedent
- CLI change is composition-root only (new command + helper + rendering)
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. `LinkStatusKind` 4-way semantics identical to inspect (missing/dangling/diverged/ok).
2. `current/` inventory mirrors `seeder.repoint_current_symlinks` (per-monitor wallpapers + alias + 6 palette artifacts + effects/icons dir links, conditional on active entries).
3. Stale-vs-corrupt boundary: corrupt `meta.json` here classifies `diverged` (structural); cryptographic verdicts belong to 3.1; quarantine/repopulate belong to 2.2.
4. Exit 0 clean / exit 1 drift / exit 1 absent (ErrorView); staleness-vs-drift exit semantics stay with their owners (1.3 informational, 2.1 drift).

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-2-1-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; 18 findings). Operator verdicts
per-item ballot: apply A–K, dismiss X1–X3 confirmed.

Applied:
- A: `UnicodeDecodeError` caught as `diverged` (zero-crash).
- B: seed guard via `ctx.invoked_subcommand` (kills argv value/operand bug class; shared with reconcile/inspect).
- C: unsafe artifact keys (absolute/`..`/empty) → `diverged`.
- D: `resolve()` catches `RuntimeError` → `dangling`.
- E: mirror `DEFAULT_MONITOR` fallback.
- F: monitor-name validation mirrored from inspect.
- G: malformed map → `diverged`; absent map stays legacy-`ok`.
- H: exact double-leg assertions.
- I: hostile-meta + vocabulary + invisibility pin tests.
- J: diverged e2e snapshot pin.
- K: boxes checked; this record.

Dismissed:
- X1 file-squat classified `missing` — inspect-identical vocabulary; still non-ok; repair identical.
- X2 extra `current/` files ignored — fixed-name consumers; flagging would be unrepairable.
- X3 conditional palette-link expectation — doctor reports steady-state truth; seeder skip is bootstrap tolerance.

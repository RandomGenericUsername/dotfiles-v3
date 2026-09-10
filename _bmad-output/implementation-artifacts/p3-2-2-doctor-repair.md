# Story 2.2: Doctor Repair — Quarantine, Repopulate, Repoint, Record

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 2 — Doctor Drift Detection + Repair (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 2.2)

## Story

As a user,
I want `dotfiles-runtime doctor --repair` to heal drift without ever deleting user state,
so that a corrupted `meta.json` (or missing entry/stray symlink) heals and the desktop reconverges.

## Acceptance Criteria

1. Bad cache entries (status missing/diverged) are **quarantined by rename-aside** to `state_root/cache/.quarantine/<layer>/<hash>-<utc>-<pid>`, then repopulated via the Phase 2 pipeline (reconcile's `_ensure_entries`); **never `rm -rf`** — no user/derived state is destroyed (AC 1, FR-4)
2. Corrupt-by-digest entries (artifact-hash mismatch per Story 1.5) quarantine + repopulate identically to corrupt-`meta.json` entries — **one repair path for all corruption classes** (AC 2, FR-8)
3. Stray symlinks are repointed to last-good `current.json` state; `current.json` is saved (tmp+rename) and `history.jsonl` gains **exactly one line with `trigger: doctor`** (O_APPEND) (AC 3, FR-4)
4. Re-running `doctor --repair` on a healthy machine is a **no-op success** (idempotent; zero quarantine, zero reconcile, zero history) (AC 4, NFR-3)
5. Repair never writes under the install spine except the AD-11 R2 consumer symlink (NFR-2)

## Tasks / Subtasks

- [x] Add `quarantine_entry(state_root, layer, entry_hash) -> Path | None` to `src/runtime/src/runtime/adapters/cache.py` (AC: 1, 5)
  - [x] `os.rename(entry_dir, quarantine_dir/<hash>-<UTCstamp>-<pid>)` — atomic same-filesystem rename; create `<layer>` parent first
  - [x] Entry dir absent → return `None` (nothing to quarantine — reconcile rebuilds the missing entry in place)
  - [x] Collision-safe: if the timestamped target exists, append a short uuid; **never overwrite**, **never `rm`**
  - [x] Validate `layer ∈ CACHE_LAYERS` and `entry_hash` is 64-hex (reuse existing validators)
  - [x] Docstring: rename-aside is the only destructive-looking step and it MOVES bytes (forensics preserved); eviction is Story 3.x's domain, not repair's
- [x] Extend `DriftItem` + add `DoctorRepairUseCase` in `src/runtime/src/runtime/application/doctor.py` (AC: 1–4)
  - [x] `DriftItem` gains structured `layer: str | None = None` and `entry_hash: str | None = None` (populated for `kind == "entry"` items; `None` for symlink items) — additive, 2.1 tests unaffected
  - [x] Frozen `RepairResult(quarantined: tuple[Path, ...], repopulated: tuple[str, ...], history_trigger: str | None, reload_failures: tuple[str, ...])`
  - [x] `DoctorRepairUseCase(doctor: DoctorUseCase, quarantine: Callable[[str, str], Path | None], reconcile: ReconcileDesktopStateUseCase, state_root: Path)` — writers ONLY here; `DoctorUseCase.check()` stays read-only (separate class, documented deviation from "same class": AD-22's principle — the doctor module owns three-way repair — is satisfied while preserving 2.1's tight read-only ctor; Gate 2 ratified in the Review Record)
  - [x] `repair()`:
    1. `report = self._doctor.check()`; if `report.clean` → return no-op `RepairResult((), (), None, ())` — no reconcile, no history, no writes (AC 4)
    2. For each `kind == "entry"` item with `status in ("missing","diverged")` and a non-null `(layer, entry_hash)`: `quarantine(layer, entry_hash)`; collect non-None paths. (Missing dirs → `None` → skipped; reconcile rebuilds them.)
    3. `reconciled = self._reconcile.run(trigger="doctor")` — reconcile's `_ensure_entries` repopulates every quarantined/missing entry via the Phase 2 pipeline (same inputs → same hash), `_ensure_wallpaper_entry` re-imports the wallpaper from `source_path` if its entry was missing, `_revert_stale_symlinks` reverts strays to last-good `current.json`, then swap+save+**one** history line `trigger="doctor"`+reload (AC 1–3, 5)
    4. Return `RepairResult(quarantined, tuple(reconciled.cache_regenerated), "doctor", tuple(reconciled.reload_failures))`
  - [x] Import-clean for tests: constructor-injected `quarantine` callable keeps the adapter behind a seam (no adapter import in `application/`)
- [x] Wire `doctor --repair` in `src/runtime/src/runtime/cli/main.py` (AC: 1–4)
  - [x] Add `repair: bool = typer.Option(False, "--repair", help=...)` to the existing `doctor` command (check remains the default read path)
  - [x] New `_run_doctor_repair()` composition mirroring `_run_regenerate_stale`'s shared-instance discipline: `state_root` absolute; `JsonStateRepository`; `CacheSeeder`; `FlockSeedMutex`; `CsgAdapter`/`WegAdapter`/`ItrAdapter`; `DerivationPipeline`; `ReconcileDesktopStateUseCase` with `_build_reloaders(state_root)`; `DoctorUseCase`; `DoctorRepairUseCase(quarantine=lambda l,h: quarantine_entry(state_root,l,h))`
  - [x] Render via `cli-output`: plain (`repaired: quarantined N, regenerated <layers>` / `already clean: nothing to repair`) + machine-readable object `{quarantined: [...], repopulated: [...], history_trigger, reload_failures: [...]}`; reload failures surface per-consumer + exit non-zero (R5); absent state → `ErrorView` + exit 1
  - [x] `--repair` is a mutation path: confirm the `main_callback` seed guard still skips seeding for `doctor` (ctx-based, Story 2.1) — repair must not depend on prior auto-seed
- [x] Create `src/runtime/tests/unit/test_doctor_repair.py` (AC: 1–4)
  - [x] Build a warm state (reuse `test_doctor_check.py::_seed_state` helper pattern), BREAK it, `repair()`, assert healed:
    - corrupt `meta.json` → quarantined (bytes present under `.quarantine/<layer>/…`), entry repopulated, `check().clean is True` after
    - absent listed artifact (digest-integrity sibling) → same quarantine+repopulate path
    - deleted entry dir → repopulated with **no** quarantine entry (nothing to move)
    - stray symlink only (entries intact) → repointed, exactly one `trigger: doctor` history line
    - wallpaper entry deleted but `source_path` valid → re-imported; wallpaper entry deleted + source gone → loud `RuntimeError`
  - [x] **Idempotency**: second `repair()` on the healed state → `quarantined == ()`, `history_trigger is None`, zero new history lines, zero tool invocations (counting fakes)
  - [x] History: exactly one new line per repair, `trigger == "doctor"`; line count +1 (never rewritten)
  - [x] Never-delete pin: quarantined bytes byte-identical to the pre-repair entry (hash compare)
  - [x] No-spine-write pin: `install_spine` FS snapshot unchanged except the R2 consumer symlink targets
  - [x] CLI shape (monkeypatched `_run_doctor_repair`): clean → exit 0 + "already clean"; repaired → exit 0 + report; reload failure → exit 1; absent state → exit 1
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_doctor_repair.py tests/unit/test_doctor_check.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — this story is REPAIR ONLY

Story 2.2 heals drift. It does **NOT** implement:
- Torn-history-tail tolerance (Story 2.3)
- `cache list --verify` / prune (Stories 3.1–3.3) — quarantine is NOT eviction; `.quarantine/` growth/cleanup is explicitly out of scope (documented as a Story 3.x follow-up)
- Any new derivation/hash logic — repopulation is reconcile's existing `_ensure_entries` (Phase 2 pipeline), untouched
- The check semantics themselves (Story 2.1, read-only, unchanged except additive `DriftItem` fields)

### Layering (AD-25, locked)

- `quarantine_entry` in `adapters/cache.py` (I/O); `DoctorRepairUseCase` in `application/doctor.py` importing same-layer `ReconcileDesktopStateUseCase` + ports + the injected `quarantine` callable; CLI composition wires everything
- `DoctorUseCase.check()` ctor stays `(state_repo, state_root)` — the repair writers live on the separate `DoctorRepairUseCase`
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. Reconcile IS the Phase 2 pipeline orchestrator: repopulate/repoint/save/history/reload already exist there — repair only quarantines first so "present-but-diverged" dirs register as misses.
2. History trigger enum `seed|set|reconcile|force|regenerate|doctor` — add `doctor` to BOTH validator sets (`reconcile._VALID_TRIGGERS`, `inspect._VALID_HISTORY_TRIGGERS`) and the docstrings, symmetric with the `regenerate` addition in Story 1.4.
3. Rename-aside layout under `state_root/cache/.quarantine/` (runtime-owned; never the install spine).
4. Idempotency = check-clean short-circuits before any write.

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-2-2-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; 22 findings). Operator verdicts
per-item ballot: apply A–K, dismiss X1–X2 confirmed.

Applied:
- A (blocker): artifact-hash recheck added to `DoctorUseCase.check()` — digest-mismatch (tampered in place, meta unchanged) now classifies `diverged`, so repair quarantines + repopulates (AC2).
- B (blocker): palettes require the canonical 6 artifacts (meta + disk + digest); absent/incomplete palette meta → `diverged`. This makes repair quarantine every entry reconcile's `ensure_palette_entry_complete` would otherwise `rmtree` — closing the never-delete violation.
- C: `quarantine_entry` moves non-dir entries (file/symlink squat) aside.
- D: reconcile failure now rolls quarantined entries back (state never worse).
- E: quarantine rename race → `None`.
- F: quarantine collision `while` loop.
- G: `_entry_dir` lowercases.
- H: `artifact_hashes` values validated `str→str`.
- I: `append_history` torn-tail newline guard.
- J: hardening tests (digest, incomplete-palette, squat, rollback, byte-identity, multi-entry single line, spine removed/changed).
- K: boxes, ctor text, this record.

Boundary amendment ratified: 2.1's "structural only" check gains a digest leg
here (2.2's AC2 requires corrupt-by-digest repair, which requires detection);
Story 3.1's `cache list --verify` stays a separate command.

AD-22 ratification: repair is split into `DoctorRepairUseCase` (writers) while
`DoctorUseCase.check()` remains read-only with its tight ctor — the doctor
module owns three-way repair as AD-22 requires; the read path's surface is not
widened.

Dismissed:
- X1 full mutex-held repair — explicit operator command; E removes the crash symptom, D makes it recoverable. Deferred.
- X2 reconcile `.exists()`→`.is_dir()` — B+C normalize first; avoids Phase-2 semantics churn. Follow-up note.

Verification: 678 unit/architecture + 68 integration passed, ruff + format
clean (only pre-existing B008), mypy strict clean on doctor.py + cache.py.

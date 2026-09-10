# Story 3.1: `cache list --verify` Per-Entry Health

Status: done

baseline_commit: 5f0609f

Epic: Phase 3 Epic 3 — Cache Verify + Prune (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase3.md`, Story 3.1; PRD v2 FR-5 + FR-9; AD-27)

## Story

As a user,
I want `inspect cache list --verify` to add per-entry health (artifact-hash recheck, `meta.json` validity),
so that corrupt entries are visible without changing the default list, and legacy entries are annotated instead of failed.

## Acceptance Criteria

1. `inspect cache list` with NO flag is byte-identical to today's output — same layers, same ordering, same counts (AC 1, FR-5)
2. With `--verify`, each entry carries a health verdict `ok | corrupt | missing` from a SINGLE bounded cache walk (reuse `InspectCacheUseCase`'s listing — no second directory scan) (AC 2, NFR-4)
3. Legacy entries (no `artifact_hashes` map, pre-FR-8) are lazily annotated in place on first `--verify` (all files under the entry except `meta.json` hashed and recorded, preserving other meta keys, atomic tmp+replace) and reported `ok` — never hard-failed, no migration pass (AC 3, FR-9/AR-11/AD-27)
4. `--verify` performs zero mutations EXCEPT the legacy annotation write; a healthy annotated entry is never rewritten on a second run (idempotent) (AC 4, NFR-3)
5. Corruption taxonomy: meta ABSENT → `missing`; meta unparseable/not-object/malformed map/unsafe key/non-sha256 algorithm → `corrupt`; recorded artifact file absent (or escaping symlink) → `missing`/`corrupt`; digest mismatch → `corrupt`; unrecorded on-disk file → `corrupt` (AC 5)
6. `--verify` exits non-zero when any entry is `corrupt`/`missing`, zero when all `ok`; the default list command stays exit 0 (AC 6)

## Tasks / Subtasks

- [x] Add `verify_entry(entry_dir: Path, *, annotate: bool) -> EntryHealth` to `src/runtime/src/runtime/adapters/cache.py` (AC: 2, 3, 5)
  - [x] `EntryHealth` dataclass: `status: Literal["ok","corrupt","missing"]`, `detail: str`, `annotated: bool`
  - [x] meta absent → `missing`; unparseable/not-object/malformed `artifact_hashes`/unsafe key → `corrupt`
  - [x] recorded map present: each `(rel, hash)` must resolve inside `entry_dir` (traversal guard, reuse the p3-1-5 doctrine), exist (`missing` if absent), and `hash_file == recorded` (`corrupt` if mismatch)
  - [x] absent map + `annotate=True`: hash every file under `entry_dir` except root `meta.json` (recursive — WEG nested layouts), write them into `meta.json["artifact_hashes"]` via atomic tmp+replace, preserving `hash_algorithm`/other keys → `ok, annotated=True`
  - [x] absent map + `annotate=False`: `ok, annotated=False` (nothing to check — legacy tolerated)
  - [x] Read-only otherwise: no deletes, no cache-layout change (AD-21)
- [x] Create `src/runtime/src/runtime/application/verify_cache.py` (AC: 1, 2, 4)
  - [x] `VerifyCacheResult(layers: dict[str, tuple[EntryHealth, ...]], counts, total, unhealthy: int)`; per-layer entries align 1:1 with `InspectCacheUseCase`'s sorted hashes
  - [x] `VerifyCacheUseCase(state_root, lister: InspectCacheUseCase, verify_entry_fn)` — ctor takes the listing use case (single walk) + the adapter seam (no adapter import in `application/`); `run()` lists once, verifies each entry via the injected `verify_entry` callable (passing the composed entry dir + annotate=True), aggregates
  - [x] Idempotent: annotation only fires when the map is absent; a second run reports `ok` with no write
- [x] Wire `cache list --verify` in `src/runtime/src/runtime/cli/main.py` (AC: 1, 2)
  - [x] Add `verify: bool = typer.Option(False, "--verify", ...)` to the existing `inspect_cache_list` command; default branch unchanged (byte-identical)
  - [x] New `_run_verify_cache()` composition: `InspectCacheUseCase(state_root)` + `verify_entry` seam (pass `annotate=True`)
  - [x] Render: default list untouched; `--verify` prints per-entry `hash [status]` and a summary; machine-readable object carries `health` + `unhealthy`; exit 1 when any entry is `corrupt`/`missing`, else 0 (verify is a gate; plain list stays exit 0)
- [x] Create `src/runtime/tests/unit/test_verify_cache.py` (AC: 1–5)
  - [x] Default list output unchanged (regression: same bytes as before this story)
  - [x] healthy → `ok`; corrupt meta → `corrupt`; non-object meta → `corrupt`; malformed map → `corrupt`; unsafe key → `corrupt`; absent recorded artifact → `missing`; digest mismatch → `corrupt`
  - [x] legacy absent map → annotated: `meta.json` gains `artifact_hashes` with every non-meta file; reported `ok`; original keys preserved; second verify → `ok`, no rewrite
  - [x] zero-mutation pin: healthy entries' `meta.json` bytes+mtime unchanged across verify (only legacy annotation writes)
  - [x] single-walk: verify reuses the lister (assert the lister is called once / not re-scanned)
  - [x] CLI shape: no flag byte-identical; `--verify` health rendering; exit 1 on corruption, exit 0 healthy
- [x] Run `uv run --directory src/runtime pytest tests/unit/test_verify_cache.py tests/unit/test_inspect_cache.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — verify only

- No eviction/prune (Stories 3.2/3.3)
- No repair/quarantine (doctor owns it) — `--verify` only REPORTS (annotation is the sole sanctioned write, AD-27)
- `InspectCacheUseCase` stays byte-identical in behavior; verify lives in a sibling use case

### Layering (AD-25, locked)

- `verify_entry` I/O in `adapters/cache.py`; `VerifyCacheUseCase` in `application/` takes the lister + the injected adapter callable (no direct adapter import); CLI composes
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed

1. The listing walk (`InspectCacheUseCase`) is the single scan source; verify decorates its result (NFR-4).
2. Annotation doctrine mirrors `verify_staging` (p3-1-5): all files except root `meta.json`, recursive, traversal-guarded, atomic write.
3. Verdict vocabulary `ok/corrupt/missing` matches doctor's drift classes where shared.
4. NFR-4 walk budget: the steady-state `--verify` is a single listing walk; a first run over a legacy entry additionally performs one `rglob` per annotated entry (the sanctioned one-time AD-27 annotation path), not a repeated scan.

## Review Record (Gate 2, 2026-09-10)

Full detail: `p3-3-1-gate2-review.md` (reviewers: Blind Hunter / Edge Case
Hunter / Acceptance Auditor, parallel; ~20 findings). Operator verdicts
per-item ballot: apply A–H (all applied).

Applied:
- A (major): symlink containment on the read path — `resolve()` + `is_relative_to` for recorded artifacts (mirrors `verify_staging`), symlinked entry/`meta.json` refused, escaping symlinks rejected in the annotation walk.
- B: annotation write `OSError` → `corrupt` verdict, never a run-abort.
- C: `artifact_hashes: {}` treated as legacy (annotated); `hash_algorithm` validated when present.
- D: annotation walk skips `.meta.json.tmp.*` leftovers; tmp preserves the original meta mode via `copymode`.
- E: `verify_cache` uses `cache_entry_path` (single layout contract).
- F: strict parity with `verify_staging` — unrecorded on-disk file → `corrupt`.
- G: tests — symlink escape, `..` key, `{}` annotate, write-failure verdict, missing-meta exit 1, default JSON golden, spy typing.
- H: AC5 corrected (meta absent → `missing`); exit-code AC added; NFR-4 annotation-walk note; boxes + this record.

Verification: 719 unit/architecture + 68 integration passed, ruff + format
clean (only pre-existing B008), mypy strict clean on cache.py + verify_cache.py.

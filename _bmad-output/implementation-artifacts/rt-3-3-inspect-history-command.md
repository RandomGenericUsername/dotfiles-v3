---
baseline_commit: c9daae75e59fdc96ddc2e9836514abdf081c96a8
---

# Story rt-3.3: inspect history command

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to view the append-only desktop history,
So that I can review past state transitions.

## Scope Reality (READ FIRST)

**This is a GREENFIELD reader on top of a HARDENED writer.** The `history.jsonl`
writer already exists, is tested, and is pinned: `CacheSeeder.append_history`
(`src/runtime/src/runtime/adapters/seeder.py:567-626`, O_APPEND + full-write
loop + fsync + O_NOFOLLOW), called from exactly 2 call sites / 3 flows
(`seed_cache.py:231-239` with `trigger="seed"`, `reconcile.py:265-273` with
`trigger` param, `wallpaper set` reaching history only via
`ReconcileDesktopStateUseCase.run(trigger="set")` at `cli/main.py:264`).
Story rt-3.1 verified + hardened it (5 new tests, crash-window verdict in
`deferred-work.md`, 7-field schema pin, torn-tail/concurrency/`os.write==0`
items explicitly deferred). Do NOT rebuild, move, or rewrite the writer.

There is NO history reader anywhere in `src/runtime` (verified by grep —
zero matches for `load_history`/`read_history`; `IStateRepository` exposes
only `load_current`/`save` per `ports/state_repository.py:8-15`, and rt-3.1
pinned that history stays on the `CacheSeeder` adapter, NOT promoted to the
port). `InspectStateUseCase` exists ONLY as the status projector
(`application/inspect.py`, rt-3.2, read-only `current.json` + live `current/`
symlink reflection). Story 3.3 builds the SECOND Epic-3 inspection command:
`dotfiles-runtime inspect history`.

**Scope boundary — do NOT build the other Epic-3 command.** Story 3.4
(`inspect cache list`) adds cache listing. That lands later. This story
touches ONLY the history path: `InspectHistoryUseCase` (history.jsonl reader,
newest-first, limit, empty-clean), the `inspect history` CLI surface, tests,
and docs. No cache listing, no `IStateRepository.load_history`, no writer
changes, no seed/reconcile behavior changes.

## Acceptance Criteria

1. **History output, newest-first, pinned schema** — Given
   `dotfiles-runtime inspect history` runs on a machine with recorded
   history, Then it prints the transition log from `history.jsonl`,
   **newest-first**, each entry using the pinned 7-field line schema
   (`ts`, `trigger`, `wallpaper`, `palette`, `effects`, `icons`,
   `source_path` — NO `schema_version`) (FR-7, CAP-7, AR-3, AR-9).
2. **Paging / limit for large histories** — The command pages/limits output
   for large histories: a `--limit/-n` option caps the number of entries
   returned (newest N). Default is bounded (see Dev Notes); `--limit 0`
   means no limit (all entries, still newest-first).
3. **Empty history is clean, exit 0** — Given `history.jsonl` is absent
   (never seeded) or present-but-empty, When the command runs, Then it
   reports cleanly (e.g. "no history recorded yet") and exits **0** with an
   empty entry list in JSON. No traceback, no non-zero exit, no fabricated
   entries. (Deliberate contrast with `inspect status` AC 3, which exits
   non-zero on absent `current.json` — an empty history is NOT an error
   state.)
4. **Read-only + format parity** — The command MUTATES NOTHING: no
   `history.jsonl` append, no `current.json` write, no `current/` repoint,
   no seed side-effects, no `.seed.lock` acquisition. Supports
   `--format plain|json|rich` (`OutputFormat`) like every other command;
   JSON object is structured and deterministic (`entries` newest-first +
   `count` + `truncated`).
5. **Corrupt history is loud, torn tail is tolerated** — A non-trailing
   corrupt (non-JSON / schema-violating) line raises `ValueError` loudly
   (CLI maps to `ErrorView` + exit 1). A trailing partial line (the real
   torn-write crash artifact deferred in rt-3.1) is tolerated: skipped with
   a `logger.warning`, parseable prefix still returned newest-first. Never
   crash with an unhandled exception, never silently drop a middle line.
6. **Zero regressions** — full suite passes (`pytest`,
   `ruff check src`, `ruff format --check src`, `mypy --strict src`,
   layering tests) with ZERO new violations; existing
   seeding/apply/reconcile/status behavior unchanged (no guard change
   needed — `inspect` already skips auto-seed; pin it with a test).

## Tasks / Subtasks

- [x] Task 1: `InspectHistoryUseCase` (AC: 1, 2, 3, 5)
  - [x] Extend `src/runtime/src/runtime/application/inspect.py` (do NOT
    create a new module — keeps history+status cohesion; the layering
    module case for `inspect.py` already exists): frozen
    `HistoryRecord` dataclass (7 fields: `ts`, `trigger`, `wallpaper`,
    `palette`, `effects`, `icons`, `source_path`; `str | None` for the
    three nullable hashes) + `InspectHistoryUseCase(state_root: Path)`
  - [x] `run(limit: int = 20) -> list[HistoryRecord]`:
    read `state_root / "history.jsonl"`; absent file → `[]` (AC 3);
    if the path is a symlink → raise `ValueError` (mirror the writer's
    O_NOFOLLOW hardening — never follow a symlinked history file);
    parse line-by-line streaming (`open`, never `read_text` into one
    giant string — large histories must not OOM); skip blank lines;
    validate each object has EXACTLY the 7 pinned keys with `trigger` in
    `seed|set|reconcile|force` (else `ValueError` with line number, AC 5);
    hashes and `ts` are surfaced verbatim — never hex-validate or
    reformat them; trailing-line `json.JSONDecodeError` → warn + skip
    that line only; non-trailing decode error → `ValueError`; return
    newest-first (reverse of file order — file is oldest-first, newest
    on last line per contract); apply `limit` (newest N; `0` = all);
    negative `limit` → `ValueError`
  - [x] Read-only: only `Path` reads (`is_file`/`is_symlink`/`open`);
    never `os.open(..., O_APPEND)`, never `save()`, never seeder/mutex
    construction. Constructor takes ONLY `state_root` — no
    `state_repo`, no adapters (history is a flat file, not the
    `current.json` index; rt-3.1 reserved port extension for Phase 3).
    Do NOT call `load_current()` and do NOT require `current.json` —
    history works (including `[]`) even when `current.json` is absent.
- [x] Task 2: CLI `inspect history` (AC: 1, 2, 4)
  - [x] `@inspect_app.command("history")` in `cli/main.py` (precedent:
    `inspect_status` at main.py:518-575); function `inspect_history`
    with `--limit/-n int = 20` option (`0` = all; negative → `ValueError`
    + exit 1) + shared `_OUTPUT_FORMAT_OPTION`
  - [x] `_run_inspect_history(limit: int)` composition helper
    mirroring `_run_inspect_status` (main.py:498-515): `_resolve_state_root()`
    + `InspectHistoryUseCase(state_root)` only — no seeder, mutex,
    derivation adapters, reloaders, or `state_repo` (AC 4)
  - [x] Error mapping: `ValueError`/`RuntimeError`/`OSError` →
    `ErrorView` + `typer.Exit(1)` (mirror main.py:535-547); catch-all
    `Exception` → `UnexpectedError`. Empty history → success path with
    the clean message (exit 0, AC 3), NOT the error path
  - [x] Render success via `CustomView(plain=..., object={...}, rich=...)`;
    `plain`: one line per entry
    (`<ts> <trigger> <wallpaper[:12]> ...`) or the empty message when
    `[]`;     `object`: `{"entries": [...newest-first full 7-field dicts...],
    "count": <returned>, "total": <parseable on-disk lines, torn trailing
    line excluded>, "truncated": bool,
    "limit": <applied>}`; `rich`: same as plain
  - [x] **No auto-seed guard change:** `main_callback` (main.py:168-183)
    already returns early when `"inspect" in sys.argv` (rt-3.2). Verify
    it covers the new subcommand (it does — argv contains `"inspect"`
    for `inspect history`) and PIN with a guard test; do NOT touch the
    guard
- [x] Task 3: Tests (AC: 1-6)
  - [x] `tests/unit/test_inspect_history.py`: use-case level — newest-first
    ordering from multi-line fixture; `limit` newest-N + `0` = all;
    negative `limit` → `ValueError`; absent file → `[]` (even with
    `current.json` absent — no `state_repo` involved); symlinked
    `history.jsonl` → `ValueError`; empty file / blank-lines-only → `[]`;
    7-field shape pin (incl. `schema_version` absent); invalid trigger →
    `ValueError`; middle corrupt line → `ValueError` with line number;
    torn tail (valid lines + partial last line) → prefix returned +
    warning (torn line excluded from counts); nullable hashes (`None`)
    round-trip; `ts`/hashes surfaced verbatim (no reformat); read-only (no
    `history.jsonl` creation when absent, no `current.json`/`current/`
    mutations, file bytes identical before/after)
  - [x] `tests/unit/test_cli_inspect_history.py`: mirrors
    `test_cli_inspect_status.py` — exit codes, plain summary text,
    `--format json` object shape (`entries`/`count`/`total`/`truncated`/
    `limit`), `--limit/-n` flag wiring (incl. `0` = all, negative →
    exit 1), empty → exit 0 + clean message (NOT `ErrorView`), corrupt
    middle → exit 1 + `ErrorView` (monkeypatch `_run_inspect_history`,
    not the whole app; `DOTFILES_INSTALL_SPINE` + `XDG_STATE_HOME`
    fixtures as in `test_cli_reconcile.py:88-95`)
  - [x] `tests/integration/test_inspect_history_integration.py`: real
    `CacheSeeder.append_history` writes N lines (all 4 triggers incl.
    `None` hashes) then a FRESH `InspectHistoryUseCase` on the same
    `state_root` reads newest-first (restart-survival realism, rt-3.1
    lesson); large-history limit (`--limit` newest-N + `truncated`
    flags); diverged `current/` tree does not affect history output
  - [x] Guard test: `inspect history` never seeds (seed-tripwire: pre-create
    install-spine `generated/default.png` + assert no `current.json` /
    no `history.jsonl` mutation from the CLI path); other commands still
    seed (extend existing seed-hook CLI tests if needed)
- [x] Task 4: Quality gates (AC: 6)
  - [x] `uv run --directory src/runtime pytest`
  - [x] `uv run --directory src/runtime ruff check src` — zero NEW
    (baseline: exactly 3 — cli/main.py:166, cli/main.py:271,
    domain/models.py:35; re-verify live at start, line numbers may have
    shifted after rt-3.2). Do NOT run bare `ruff check`
  - [x] `uv run --directory src/runtime ruff format --check src` — clean
    (src scope; unscoped run reports pre-existing test-file violations,
    do not count them)
  - [x] `uv run --directory src/runtime mypy --strict src` — zero NEW
    (baseline: exactly 4; re-verify live). Bare `mypy --strict` errors
    out ("Missing target module")
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v`
  - [x] Confirm `git status --short` contains ONLY this story's new files +
    the story/status artifacts (`application/inspect.py`, `cli/main.py`,
    3 test files, `sprint-status.yaml`, this story file)

## Dev Notes

### Pinned sources (cite in References)

- PRD/epic: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` —
  Epic 3 (lines 430-435), **Story 3.3 ACs verbatim** (lines 464-475),
  FR-7, CAP-7, R1 note (line 102).
- Architecture: `ARCHITECTURE-SPINE.md` — application layer list line 27
  (`InspectStateUseCase`), `cli` spine line 28, AD-19 line 146 (operations
  are `wallpaper/status/history/cache` CLI commands), AD-3/NFR-3
  (filesystem authority) lines 46-51, AD-4 (must-not-lose) lines 52-57,
  AD-5 state_root line 62, AD-12 (synchronous) line 106.
- Data contract: `shared-data-contract.md` (same folder) —
  `history.jsonl` schema (lines 40-50: newest-on-last-line, 7 fields, NO
  version field, append-BEFORE-reload, immutable lines), swap sequence
  (lines 133-148: history is step 4 of 5).
- Prior stories: `rt-3-1-history-jsonl-persistence.md` (writer mechanics,
  7-field pin, trigger enum, `ts` `...Z` format, call sites, crash-window
  verdict, deferred torn-tail/concurrency items) and
  `rt-3-2-inspect-status-command.md` (epic `inspect` group naming wins over
  SPEC.md:76 / AD-20 flat list; `_run_*` composition + monkeypatch
  pattern; `CustomView`/`ErrorView` mapping; auto-seed guard;
  read-only negative-test style; quality-gate baselines; commit style).

### Command-naming decision (do not re-litigate, inherited from rt-3.2)

The EPIC pins `dotfiles-runtime inspect status` / `inspect history` /
`inspect cache list`. **Use the `inspect` group with subcommands.**
Do NOT create a top-level `history` command and do NOT follow SPEC.md:76
("`dotfiles status`") or AD-20's flat `{wallpaper,status,history,cache}`
list — those are earlier, coarser namings. rt-3.2 already flagged this
drift once; this story implements `inspect history` under the same group.

### Data sources (as-built — the reader contract)

- `history.jsonl` line schema (AR-9 — read EXACTLY, 7 fields, no extras)
  `[Source: shared-data-contract.md#history.jsonl]`:
  ```json
  {"ts": "<ISO-8601-UTC>", "trigger": "seed|set|reconcile|force", "wallpaper": "<sha256-hex>", "palette": "<sha256-hex|null>", "effects": "<sha256-hex|null>", "icons": "<sha256-hex|null>", "source_path": "<abs-or-empty>"}
  ```
  - **NO `schema_version`** — version lives only in `current.json`
    (`schema_version: 2`). rt-3.1 pins this with
    `test_append_line_has_exactly_seven_fields_no_schema_version`.
  - `ts` as-built: `datetime.now(UTC).isoformat().replace("+00:00", "Z")`
    (opaque string to the reader — surface verbatim, never reformat).
  - `trigger` enum `seed|set|reconcile|force` — NEVER `"apply"`.
    Validation lives in `ReconcileDesktopStateUseCase.run(trigger=...)`
    (reconcile.py:148-150); `append_history` is trigger-agnostic.
    The READER validates (unknown trigger → `ValueError`, AC 5).
  - File order is oldest-first (append-only); newest is the LAST line.
    The reader reverses → newest-first (AC 1).
- Writer mechanics (do not touch, but know what you read):
  `CacheSeeder.append_history` (seeder.py:567-626): `_O_APPEND =
  os.O_APPEND | os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW`, mode 0o644,
  full-write `memoryview` loop, `os.fsync`, `os.close` in `finally`.
  Callers: `seed_cache.py:231-239` (`trigger="seed"`, `source_path=""`),
  `reconcile.py:265-273` (`trigger` param, `source_path=saved.wallpaper.source_path`).
  `ApplyWallpaperUseCase` does NOT append (apply_wallpaper.py:174-176).
- `IStateRepository` stays minimal (`load_current`/`save` only,
  ports/state_repository.py:8-15). Do NOT add `load_history` — rt-3.1
  reserved history methods for Epic-3 inspection use cases via the adapter
  seam; the history file is read directly by the new use case from
  `state_root` (same layering privilege `InspectStateUseCase` already uses
  for `current/` symlink reads). The history path never touches
  `current.json`: do NOT inject `state_repo`, do NOT call `load_current()`.

### `--limit` default decision (do not re-litigate without epic change)

Epic AC 2 requires paging/limits but pins no number. This story pins:
**`--limit/-n: int = 20`, `0` = all, negative → `ValueError`.** Rationale: 20 covers the recent
working set in one screen; `0`-means-all avoids a second `--all` flag;
`total` (parseable on-disk lines, torn trailing line excluded) +
`truncated` in the JSON payload let callers page
deterministically (`--limit 20` then `--limit 0` for the rest). Tests pin
the default (CLI default renders ≤20, JSON `truncated` true when
parseable > returned). The use-case signature mirrors the CLI:
`run(limit: int = 20)`. A future pager (`--page`/`--offset`) is out of scope.

### Empty vs absent (AC 3 — exit 0, explicit)

- Absent `history.jsonl` → `[]` (missing file is not an error; first-run
  machines may have `current.json` seeded but the seed line lost per the
  rt-3.1 seed-window verdict — still `[]`, still exit 0).
- Empty / blank-lines-only file → `[]`, same clean path.
- Clean message (plain + rich): `no history recorded yet` (keep the exact
  string; tests assert it). JSON: `{"entries": [], "count": 0, "total": 0,
  "truncated": false, "limit": <applied>}`. No `ErrorView` on this path.

### Corrupt-line policy (AC 5 — closes the rt-3.1 torn-tail item reader-side)

rt-3.1 deferred three writer-side items (torn partial line, per-write
O_APPEND interleaving under concurrency, `os.write==0` spin) to
`deferred-work.md`. This story resolves the READER side for the first:
- **Trailing partial line** (last line fails `json.loads`): skip it,
  `logger.warning("history: skipping torn trailing line <n>")`, return the
  parseable prefix newest-first (the skipped line counts toward neither
  `total` nor `count`). Pin with a test that appends a valid
  prefix + a truncated tail.
- **Any other corrupt line** (non-JSON in the middle, valid JSON with
  wrong keys / bad trigger): raise `ValueError("history.jsonl line <n>:
  ...")` — CLI maps to `ErrorView` + exit 1. Pin with tests asserting the
  line number appears. Never silently drop a middle line.
- **Symlinked file** (`history.jsonl` is a symlink): raise `ValueError`
  (mirror the writer's O_NOFOLLOW hardening in seeder.py:43) — never
  follow it. Pin with a test.
- Concurrency interleaving remains deferred (writer-side, pre-existing).

### Composition root + CLI patterns to mirror (from rt-3.2)

- Build `_run_inspect_history(limit)` in `cli/main.py` and monkeypatch IT
  in CLI tests (exact precedent: `_run_reconcile` main.py:391-424 +
  `test_cli_reconcile.py:97-102` `_fake_composition`; `_run_inspect_status`
  main.py:498-515).
- Wrap ALL expected domain errors: `(ValueError, RuntimeError, OSError)` →
  `logger.error` + `renderer.error(ErrorView(kind=..., message=...))` +
  `raise typer.Exit(code=1)`; plus catch-all `Exception` →
  `UnexpectedError`. Mirror main.py:535-547 verbatim style.
- Output: `renderer.custom(CustomView(plain=..., object={...}, rich=...))`.
  The `object` is the `--format json` payload — `entries` are FULL 7-field
  dicts newest-first (assert VALUES — hashes, triggers, `source_path` —
  not key presence; rt-3.1/3.2 review style).
- **No guard change:** `main_callback` (main.py:168-183) already skips
  seeding when `"inspect" in sys.argv`, which covers `inspect history`
  (`sys.argv` contains the literal `"inspect"`). Touching it risks
  re-seeding regressions — verify + pin only.

### Read-only invariant (AC 4 — negative tests required, mirror rt-3.2 §Read-only)

`inspect history` must create/write NOTHING: no `history.jsonl` creation
(when absent) or append, no `current.json` write, no `current/` symlink
creation/repoint, no `.staging-*` dirs, no `.seed.lock`. Tests must assert
the absence of these side-effects (e.g. `state_root` snapshot
before/after incl. file bytes; `history.jsonl` still absent after an
absent-file run; `save()` tripwire never fires). "A story implementation
must leave the system working end-to-end" — history must be safe to run
anytime (including mid-swap; the swap never holds a lock the reader
needs).

### Test conventions (pass review or get bounced — inherited from rt-3.1/3.2)

- Runner: `uv run --directory src/runtime pytest`; class-based grouping
  with AC/AD-citing docstrings (e.g. `class TestInspectHistoryUseCase:`
  "(AC 1, AR-9)"). No conftest.py.
- Deterministic fixtures: `"a"*64`-style hashes, fixed `ts` strings
  (`2026-01-01T00:00:00Z` style), `tmp_path` as `state_root` via
  constructor injection; history fixtures built with
  `CacheSeeder.append_history` in integration tests (writer realism) and
  hand-written JSONL in unit tests (corrupt/torn cases).
- CLI unit tests: monkeypatch the composition helper
  (`_fake_composition` pattern), `DOTFILES_INSTALL_SPINE` +
  `XDG_STATE_HOME` fixtures (mirror `test_cli_reconcile.py:88-95`).
- Pin TRANSIENT observables (caplog for the torn-tail warning) not just
  final state; assert VALUES (hashes, order, counts) not key presence;
  JSON payload asserts assert exact shape incl. `truncated`/`total`.
- Integration: write via the REAL writer (`CacheSeeder`), read via a
  FRESH `InspectHistoryUseCase` — restart-survival-style realism (rt-3.1
  lesson). Large-history test: 25+ lines, default limit returns newest 20
  with `truncated: true`, `--limit 0` returns all.

### Commit flow

`feat(rt-3-3): inspect history command ...` for the implementation;
`docs(bmm): add story rt-3-3 ...` carrying this story `.md` +
`sprint-status.yaml`. (Precedent: rt-3-1/rt-3-2 commits.)

### Project Structure Notes

- All new code under existing layers: extend
  `src/runtime/src/runtime/application/inspect.py` (new `HistoryRecord` +
  `InspectHistoryUseCase`) and `cli/main.py` (history subcommand +
  `_run_inspect_history` helper). Layering: application →
  domain/ports/adapters/application ONLY (test_layering.py:9,64); cli is
  the composition root (imports everything in-runtime). The extended
  `application/inspect.py` must import only `runtime.domain.*`,
  `runtime.ports.*`, `runtime.adapters.*` (if needed), and stdlib
  (`json`, `logging`, `dataclasses`, `pathlib`) — NEVER `runtime.cli`.
  New `HistoryRecord` is a frozen slots dataclass
  (`@dataclass(frozen=True, slots=True)` with
  `from __future__ import annotations`, mirroring `LinkStatus` /
  `InspectStatusResult`) holding the 7 history fields verbatim
  (domain-purity style, even though it lives in application).
  Read the file streaming (`open` line-by-line); never `read_text()` a
  whole multi-MB history into memory at once.
- Tests land at `tests/unit/test_inspect_history.py`,
  `tests/unit/test_cli_inspect_history.py`,
  `tests/integration/test_inspect_history_integration.py` — naming matches
  the rt-3.2 `test_inspect*` / layer split. No conftest.py.
- Package facts: `dotfiles-runtime` at `src/runtime/` (nested src
  layout), Python >= 3.14, hatchling, typer>=0.12, cli-output (editable
  sibling), ruff line-length 100 double-quotes, mypy strict, target py314.

### References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md#Story 3.3: inspect history command] (ACs verbatim; Epic 3 lines 430-435; R1 line 102)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md#Layer mapping] / [#AD-3 — JSON / dict-like store; filesystem is authority] / [#AD-4 — history.jsonl is must-not-lose] / [#AD-5 — state_root] / [#AD-12 — Synchronous imperative Phase 2] / [#AD-19 — Operational envelope]
- [Source: same folder shared-data-contract.md#history.jsonl (append-only, must-not-lose)] / [#Swap sequence (AD-6 ownership)]
- [Source: _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md#CAP-7]
- [Source: src/runtime/src/runtime/adapters/seeder.py:567-626 `CacheSeeder.append_history`] / [:43 O_NOFOLLOW] / [application/seed_cache.py:231-239 seed call site] / [application/reconcile.py:265-273 reconcile call site] / [application/reconcile.py:148-150 trigger validation] / [application/apply_wallpaper.py:174-176 apply never appends]
- [Source: src/runtime/src/runtime/ports/state_repository.py:8-15 `IStateRepository` minimal]
- [Source: src/runtime/src/runtime/application/inspect.py `InspectStateUseCase`] (status precedent: read-only style, error taxonomy, DEFAULT_MONITOR fallback — history reuses the module, not the class)
- [Source: src/runtime/src/runtime/cli/main.py:168-183 `main_callback` auto-seed guard] / [:498-515 `_run_inspect_status`] / [:518-575 `inspect_status`] / [:264 `trigger="set"` wiring]
- [Source: _bmad-output/implementation-artifacts/rt-3-1-history-jsonl-persistence.md#Dev Notes] — writer mechanics, 7-field pin, trigger enum, crash-window verdict, deferred items
- [Source: _bmad-output/implementation-artifacts/rt-3-2-inspect-status-command.md#Dev Notes] — inspect-group naming win, composition/test/guard/read-only patterns, quality-gate baselines, commit style
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — rt-2-1 crash-window + rt-3.1 torn-tail/concurrency deferrals (AC 5 context)

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Use-case smoke test: absent → [], empty → [], 2-line fixture newest-first, limit=1/0 verified via ad-hoc python before CLI wiring.
- CLI smoke test: empty state → exit 0 + "no history recorded yet", JSON shape {entries,count,total,truncated,limit} verified.
- New-test run: 52 passed (24 use-case + 21 CLI + 7 integration).
- Full suite: 511 passed, 2 skipped (pre-existing skips) — zero regressions.
- Ruff check src: exactly 3 (baseline preserved; B008 lines shifted 166→170, 271→278 from added TYPE_CHECKING import; E501 models.py:35 unchanged). Zero new.
- Ruff format --check src: 1 nit in new inspect.py code → ran `ruff format` on touched files → 37 files clean.
- Mypy --strict src: exactly 4 (baseline preserved). Zero new.
- Layering: 57 passed.
- Guard-test fix: CliRunner does not populate sys.argv, so the end-to-end seed-tripwire patches sys.argv (same pattern as rt-3.2 tests).

### Completion Notes List

- ✅ Task 1: `HistoryRecord` (frozen slots, 7 fields, `to_dict` in pinned order) + `InspectHistoryUseCase(state_root)` in `application/inspect.py`; streaming `open` iteration, blank skip, exact-7-keys + trigger-enum validation with line numbers, torn-tail warn+skip via non-blank-tail lookahead, symlink refusal, limit 20/0/negative semantics, read-only (is_symlink/exists/open only).
- ✅ Task 2: `inspect history` command + `_run_inspect_history(limit) -> (entries, total)` helper (double-read only when len==limit candidate-truncated); `--limit/-n` via module-level `_HISTORY_LIMIT_OPTION` (no new B008); CustomView plain/rich per-entry lines, JSON {entries,count,total,truncated,limit}; empty → exit 0 "no history recorded yet"; guard untouched + pinned.
- ✅ Task 3: 3 test files, 52 tests, all passing; CLI tests monkeypatch `_run_inspect_history`; integration uses real `CacheSeeder.append_history` + fresh reader incl. diverged-current isolation.
- ✅ Task 4: all gates green (see Debug Log); git status contains only story artifacts.
- ✅ Resolved review finding: none (fresh implementation, no prior review section).

### File List

- src/runtime/src/runtime/application/inspect.py (extended: HistoryRecord, InspectHistoryUseCase)
- src/runtime/src/runtime/cli/main.py (extended: _HISTORY_LIMIT_OPTION, _run_inspect_history, inspect_history)
- src/runtime/tests/unit/test_inspect_history.py (new, 24 tests)
- src/runtime/tests/unit/test_cli_inspect_history.py (new, 21 tests)
- src/runtime/tests/integration/test_inspect_history_integration.py (new, 7 tests)
- _bmad-output/implementation-artifacts/sprint-status.yaml (rt-3-3 → review)
- _bmad-output/implementation-artifacts/rt-3-3-inspect-history-command.md (this story file)

### Review Findings

Code review 2026-09-03 (baseline `c9daae7`..HEAD): 3 layers (blind, edge-case, acceptance) + code read. Acceptance Auditor: no violations in runtime code — AC 1-6, 7-field schema, limit 20/0/negative, empty-exit-0, read-only, torn-tail policy all match spec. Battery.tsx hunk in range is NOT this story (`git show --stat`: story commits `75632de` docs-only + `a013c0c` runtime-only; battery.tsx only in `f40b176`) — same false-positive as rt-3.2, dismissed with sub-issues.

- [x] [Review][Patch] Corrupt middle masked by blank-only tail [src/runtime/src/runtime/application/inspect.py:338-344] — corrupt line followed only by blanks misclassified as torn tail, silently dropped instead of ValueError with line number (violates AC 5 never-drop-middle)
- [x] [Review][Patch] TOCTOU symlink check-then-open [src/runtime/src/runtime/application/inspect.py:323-332] — is_symlink() then open() without O_NOFOLLOW; swap between check and open follows attacker symlink
- [x] [Review][Patch] Unhashable trigger escapes as TypeError [src/runtime/src/runtime/application/inspect.py:378-379] — trigger list/dict raises TypeError, bypasses ValueError/ErrorView contract into UnexpectedError
- [x] [Review][Patch] Mid-file UnicodeDecodeError truncated as torn tail [src/runtime/src/runtime/application/inspect.py:346-350] — invalid UTF-8 mid-file warns and returns partial prefix instead of loud ValueError
- [x] [Review][Patch] Unbounded memory despite limit [src/runtime/src/runtime/application/inspect.py:330-354] — full list + reverse + slice is O(N) RAM; limit=1 on large log still parses everything
- [x] [Review][Patch] Double full scan on truncated read [src/runtime/src/runtime/cli/main.py:597-603] — run(limit) then run(0) doubles I/O; exact-fit total==limit does redundant 2x parse + TOCTOU total
- [x] [Review][Patch] exists() masks permission errors as empty [src/runtime/src/runtime/application/inspect.py:327-328] — unreadable history returns [] + exit 0 instead of OSError exit 1; also delete-between-check races to FileNotFoundError
- [x] [Review][Patch] Dead HistoryTrigger alias [src/runtime/src/runtime/application/inspect.py:51,79] — Literal defined but HistoryRecord.trigger typed str, loses static guarantee
- [x] [Review][Defer] Concurrent writer interleave torn lines [src/runtime/src/runtime/adapters/seeder.py:620-623] — deferred, pre-existing writer-side (rt-3.1 deferred-work), reader has no lock/snapshot contract
- [x] [Review][Defer] Brittle argv substring guard [src/runtime/src/runtime/cli/main.py:181] — deferred, pre-existing rt-3.2, spec says do NOT touch guard
- [x] [Review][Defer] FIFO/directory/BOM at history path [src/runtime/src/runtime/application/inspect.py:332] — deferred, out-of-scope hardening; writer never emits BOM, FIFO blocks on open

### Change Log

- 2026-09-03: Implemented `inspect history` (use case + CLI + 52 tests); all quality gates green; story → review.

- 2026-09-03: Code review applied — 8 patches fixed (torn-tail strictness, O_NOFOLLOW, trigger guard, UTF-8 loud, deque bound, single-scan total, lstat absent, HistoryTrigger type); 3 deferred; story → done.

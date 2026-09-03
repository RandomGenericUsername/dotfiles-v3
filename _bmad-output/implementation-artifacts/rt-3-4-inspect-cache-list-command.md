---
baseline_commit: 810910b3409ab54a4a322d23f9e6d88e74415d2b
---

# Story rt-3.4: inspect cache list command

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want to inspect the layered cache,
So that I can see what derived artifacts are cached (and by hash).

## Scope Reality (READ FIRST)

**This is a GREENFIELD reader on top of a HARDENED writer.** The layered
content-addressed cache writer already exists, is tested, and is pinned:
`populate_via_staging` + `cache_entry_path` + `hardlink_or_copy`
(`src/runtime/src/runtime/adapters/cache.py`, AD-2/AD-8/AD-9/AD-16),
with canonical input sets in `shared-data-contract.md#Derivation-input hashing`
and per-entry `meta.json` schemas (wallpaper/palette/effects/icons).
Do NOT rebuild, move, or rewrite the writer, the staging pattern, or the
hashing module.

There is NO cache reader anywhere in `src/runtime` (verified — `rg`
shows only `cache_entry_path` consumers in `inspect.py` for expected-target
computation, plus `test_layering.py`; no `InspectCache*`, no `list_cache`,
no `cache list` CLI). `InspectStateUseCase` (rt-3.2, status projector) and
`InspectHistoryUseCase` (rt-3.3, history reader) both live in
`application/inspect.py`. Story 3.4 builds the THIRD Epic-3 inspection
command: `dotfiles-runtime inspect cache list`.

**Scope boundary — list ONLY, no eviction.** AR-10 + NFR-3 pin Phase 2 as
list-only; prune/eviction is a future-phase stub. This story touches ONLY
the cache-list path: `InspectCacheUseCase` (cache/ directory reader,
per-layer entry hashes, empty-clean), the `inspect cache list` CLI surface,
tests, and docs. No `prune` command, no `--prune` flag, no cache mutation
(no creation, no deletion, no staging reaping, no meta.json rewrite), no
`IStateRepository` extension, no writer changes, no seed/reconcile behavior
changes.

## Acceptance Criteria

1. **Cache listing, per layer by hash** — Given
   `dotfiles-runtime inspect cache list` runs on a machine with populated
   cache, Then it lists each cache layer (`wallpapers/palettes/effects/icons`)
   and its entries by hash (FR-7, AR-2, CAP-7). Entries are the `64-char
   lowercase hex` entry-dir names under `state_root/cache/<layer>/`
   (AD-2/AD-8); output is deterministic in canonical pipeline order
   `wallpapers → palettes → effects → icons` (NOT alphabetical), with
   hashes sorted lexicographically within each layer.
2. **List-only, no eviction** — Prune/eviction are NOT implemented in Phase 2:
   no `prune` subcommand, no `--prune`/`--evict`/`--clear` flag, no deletion
   path anywhere in the new code. Listing a cache with extra/stale entries
   still succeeds (AR-10, NFR-3).
3. **Empty cache is clean, exit 0** — Given `state_root/cache/` is absent,
   or present with zero entries in every layer, When the command runs, Then
   it reports cleanly (e.g. `no cache entries recorded yet`) and exits **0**
   with empty per-layer lists in JSON. No traceback, no non-zero exit, no
   fabricated entries. (Deliberate contrast with `inspect status` AC 3,
   which exits non-zero on absent `current.json` — an empty cache is NOT an
   error state. Mirrors `inspect history` AC 3.)
4. **Read-only + format parity** — The command MUTATES NOTHING: no cache
   population, no `current.json` write, no `current/` repoint, no
   `history.jsonl` append, no seed side-effects, no `.seed.lock`
   acquisition, no `.staging-*` creation or reaping. Supports
   `--format plain|json|rich` (`OutputFormat`) like every other command;
   JSON object is structured and deterministic in canonical layer order
   (per-layer `entries` sorted + `counts` + `total`). This story adds NO
   `--limit`/`--layer` filter flags — full listing only; filters are out
   of scope (prevent scope creep).
5. **Staging + non-entry noise is tolerated, never loud** — `cache/`
   transient noise is skipped, never crashes the listing: `cache/.staging-*`
   dirs (AD-9 in-flight populators) are ignored; plain files squatting in
   `cache/` or inside a layer dir are ignored; non-`64-hex` dir names are
   ignored with `logger.warning("cache: skipping non-entry dir %s/%s", layer, name)`
   (not a `ValueError` — a cache listing is a diagnostic, unlike
   `history.jsonl` where a middle corrupt line is loud per rt-3.3 AC 5).
   If `state_root/cache` itself is a symlink → raise `ValueError`
   (refusing to follow, mirror rt-3.3 O_NOFOLLOW). Symlinked layer/entry
   paths are never followed (`is_symlink()` check first, then
   `is_dir(follow_symlinks=False)` — mirror the rt-3.3 O_NOFOLLOW
   hardening); a symlinked entry is skipped, never traversed. Never crash
   with an unhandled exception on any of these.
6. **Zero regressions** — full suite passes (`pytest`,
   `ruff check src`, `ruff format --check src`, `mypy --strict src`,
   layering tests) with ZERO new violations; existing
   seeding/apply/reconcile/status/history behavior unchanged (no guard
   change needed — `inspect` already skips auto-seed; pin it with a test).

## Tasks / Subtasks

- [x] Task 1: `InspectCacheUseCase` (AC: 1, 3, 5)
  - [x] Extend `src/runtime/src/runtime/application/inspect.py` (do NOT
    create a new module — keeps status+history+cache cohesion; the layering
    module case for `inspect.py` already exists): frozen `CacheLayerListing`
    dataclass (`layer: str`, `entries: tuple[str, ...]` sorted) and/or
    frozen `InspectCacheResult` (`layers: dict[str, tuple[str, ...]]`,
    `counts: dict[str, int]`, `total: int`) + `InspectCacheUseCase(state_root: Path)`
  - [x] `run() -> InspectCacheResult`: read `state_root / "cache"`; if the
    cache path itself `is_symlink()` → raise `ValueError` (never follow);
    absent cache dir → all four layers `()` (AC 3); absent layer dir → `()`
    for that layer (do NOT create dirs — read-only). Iterate layers in
    canonical order `("wallpapers", "palettes", "effects", "icons")` —
    import `CACHE_LAYERS` from `runtime.adapters.cache` for validation
    rather than re-declaring (application→adapters is allowed per
    `test_layering.py:64`; do NOT copy-paste a divergent literal), but
    ORDER output by the canonical tuple, never `sorted(CACHE_LAYERS)`
    (alphabetical would yield effects/icons/palettes/wallpapers):
    iterate entries with `os.scandir` or `Path.iterdir` WITHOUT following
    symlinks; skip anything where `is_symlink()` is true; skip plain files;
    skip `.staging-*` prefix names silently (AD-9 transient); skip
    non-`64-hex` dir names with
    `logger.warning("cache: skipping non-entry dir %s/%s", layer, name)`
    (AC 5, never `ValueError`); collect valid dir names lowercased,
    sorted. Never `read_text` a whole directory tree into memory at once;
    never open `meta.json` (hash listing needs dir names only — do NOT
    parse meta.json in this story).
  - [x] Read-only: only `Path` reads (`exists`/`is_dir`/`is_symlink`/
    `iterdir`/`scandir`); never `mkdir`, never `os.rename`, never `save()`,
    never seeder/mutex/populator construction, never staging reap.
    Constructor takes ONLY `state_root` — no `state_repo`, no adapters
    (cache is a flat FS tree, not the `current.json` index; same precedent
    as `InspectHistoryUseCase`). Do NOT call `load_current()` and do NOT
    require `current.json` — cache listing works (including empty) even
    when `current.json` is absent.
- [x] Task 2: CLI `inspect cache list` (AC: 1, 2, 4)
  - [x] Nesting: `inspect` is already a `typer.Typer` group (`inspect_app`,
    main.py:39-40). Add a `cache` subgroup (`cache_app = typer.Typer(...)`)
    under it (`inspect_app.add_typer(cache_app, name="cache")`, precedent:
    `wallpaper_app` at main.py:35-36 + `app.add_typer(inspect_app,
    name="inspect")` at main.py:40) with a `list` command
    (`@cache_app.command("list")`, function `inspect_cache_list`). Result:
    `dotfiles-runtime inspect cache list`. Do NOT create a top-level
    `cache` command and do NOT name it `cache-list`/`cache_list` — the epic
    pins the three-token form. Note `list` shadows the builtin inside the
    function scope only — acceptable (same as Typer conventions); never
    `from builtins import list` workarounds.
  - [x] `_run_inspect_cache_list()` composition helper mirroring
    `_run_inspect_status` (main.py:501-519) and `_run_inspect_history`
    (main.py:581-603): `_resolve_state_root()` + `InspectCacheUseCase(state_root)`
    only — no seeder, mutex, derivation adapters, reloaders, or
    `state_repo` (AC 4). Return the `InspectCacheResult` (or
    `(layers, counts, total)` tuple — pick one, document it; single-scan so
    `total` never needs a second read, rt-3.3 double-scan lesson).
  - [x] Error mapping: `ValueError`/`RuntimeError`/`OSError` →
    `ErrorView` + `typer.Exit(1)` (mirror main.py:537-547 and 622-634);
    catch-all `Exception` → `UnexpectedError`. Empty cache → success path
    with the clean message (exit 0, AC 3), NOT the error path.
  - [x] Render success via `CustomView(plain=..., object={...}, rich=...)`;
    `plain` (pinned exact format — tests assert it verbatim): one section
    per layer in canonical order, `"<layer> (<count>):"` header then one
    truncated hash per line indented two spaces (`"<hash[:12]>"`, history
    precedent: plain truncated, JSON full), e.g.
    `wallpapers (2):\n  aaaaaaaaaaaa\n  bbbbbbbbbbbb`; or the single line
    `no cache entries recorded yet` when `total == 0`;
    `object`: `{"layers": {wallpapers: [...sorted FULL 64-char hashes...],
    palettes: [...], effects: [...], icons: [...]}, "counts": {...},
    "total": <int>}` in canonical layer order; `rich`: same as plain.
    No `--limit`/`--layer` options on this command (full listing only).
  - [x] **AC 2 pin:** no prune surface anywhere — `rg "prune|evict|clear"`
    over the new/changed CLI + use-case files must return zero hits
    (excluding the AC-2 comment itself). Assert in review, not in a unit test.
  - [x] **No auto-seed guard change:** `main_callback` (main.py:178-183)
    already returns early when `"inspect" in sys.argv` (rt-3.2). Verify it
    covers the new subcommand (it does — argv contains `"inspect"` for
    `inspect cache list`) and PIN with a guard test; do NOT touch the guard.
- [x] Task 3: Tests (AC: 1-6)
  - [x] `tests/unit/test_inspect_cache.py`: use-case level — multi-layer
    fixture (hand-made `cache/<layer>/<64hex>/` dirs, `"a"*64`-style hashes)
    listed in canonical layer order with hashes sorted per layer; absent
    `cache/` → all empty (even with `current.json` absent — no `state_repo`
    involved); absent single layer → that layer empty, others intact;
    symlinked `cache/` root → `ValueError` (never followed);
    `.staging-<pid>-<uuid>` dirs ignored silently; plain files (in `cache/`
    and inside layers) ignored; non-hex dir names ignored + exact warning
    `cache: skipping non-entry dir <layer>/<name>` asserted via `caplog`;
    symlinked layer dir and symlinked entry dir skipped, never followed;
    `meta.json` never required (entry without meta.json still listed);
    read-only (no dirs created when absent, no files mutated, tree bytes
    identical before/after); result deterministic (canonical order).
  - [x] `tests/unit/test_cli_inspect_cache_list.py`: mirrors
    `test_cli_inspect_status.py` / `test_cli_inspect_history.py` — exit
    codes, plain summary text, `--format json` object shape
    (`layers`/`counts`/`total`), empty → exit 0 + clean message (NOT
    `ErrorView`) (monkeypatch `_run_inspect_cache_list`, not the whole
    app; `DOTFILES_INSTALL_SPINE` + `XDG_STATE_HOME` fixtures as in
    `test_cli_reconcile.py:88-95`).
  - [x] `tests/integration/test_inspect_cache_list_integration.py`: real
    `populate_via_staging` writes N entries across all 4 layers (minimal
    `populate_fn` creating one artifact + valid `meta.json` with
    `hash_algorithm: sha256`) then a FRESH `InspectCacheUseCase` on the
    same `state_root` reads them (restart-survival realism, rt-3.1/3.3
    lesson); diverged `current/` tree does not affect cache output;
    `current.json` absent does not affect cache output.
  - [x] Guard test: `inspect cache list` never seeds (seed-tripwire:
    pre-create install-spine `generated/default.png` + assert no
    `current.json` / no `history.jsonl` / no `cache/` mutation from the CLI
    path); other commands still seed (extend existing seed-hook CLI tests
    if needed).
- [x] Task 4: Quality gates (AC: 6)
  - [x] `uv run --directory src/runtime pytest`
  - [x] `uv run --directory src/runtime ruff check src` — zero NEW
    (baseline at rt-3.3: exactly 3 — cli/main.py B008×2, domain/models.py
    E501×1; RE-VERIFY LIVE at start, line numbers shift with each story).
    Do NOT run bare `ruff check`.
  - [x] `uv run --directory src/runtime ruff format --check src` — clean
    (src scope; unscoped run reports pre-existing test-file violations,
    do not count them)
  - [x] `uv run --directory src/runtime mypy --strict src` — zero NEW
    (baseline at rt-3.3: exactly 4; re-verify live). Bare `mypy --strict`
    errors out ("Missing target module")
  - [x] `uv run --directory src/runtime pytest tests/architecture/test_layering.py -v`
  - [x] Confirm `git status --short` contains ONLY this story's new files +
    the story/status artifacts (`application/inspect.py`, `cli/main.py`,
    3 test files, `sprint-status.yaml`, this story file). Unrelated hunks
    (e.g. the recurring `battery.tsx` review-range noise seen in rt-3.2/3.3
    — verify with `git show --stat` that story commits never touched it)
    are out of scope.

## Dev Notes

### Pinned sources (cite in References)

- PRD/epic: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` —
  Epic 3 (lines 430-435), **Story 3.4 ACs verbatim** (lines 477-487),
  FR-7, CAP-7, AR-2 (layered cache), AR-10 (list-only, no eviction),
  R1 note (line 102).
- Architecture: `ARCHITECTURE-SPINE.md` — application layer list line 27
  (`InspectStateUseCase`; this story adds the cache-list sibling in the same
  module), `cli` spine line 28, AD-2 lines 40-44 (four layers), AD-3/NFR-3
  (filesystem authority) lines 46-51, AD-5 state_root line 62, AD-8
  (SHA-256, hex dir names) lines 76-80, AD-9 (staging sibling
  `cache/.staging-<pid>-<uuid>`) lines 82-86, AD-12 (synchronous) line 106,
  AD-19 line 146 (operations are `wallpaper/status/history/cache` CLI
  commands), AD-20 line 152.
- Data contract: `shared-data-contract.md` (same folder) —
  `cache/` layout via structural-seed (wallpapers/palettes/effects/icons +
  `meta.json` per entry, `hash_algorithm: sha256`), derivation-input
  hashing table (lines 109-120: entry_hash = hash of ALL inputs), swap
  sequence (lines 133-148).
- Prior stories: `rt-3-1-history-jsonl-persistence.md` (writer mechanics,
  trigger enum, crash-window verdict), `rt-3-2-inspect-status-command.md`
  (epic `inspect` group naming wins over SPEC.md:76 / AD-20 flat list;
  `_run_*` composition + monkeypatch pattern; `CustomView`/`ErrorView`
  mapping; auto-seed guard `inspect in sys.argv`; read-only negative-test
  style; quality-gate baselines; commit style) and
  `rt-3-3-inspect-history-command.md` (second-command precedent: extend
  `application/inspect.py` + `cli/main.py`; `--limit` default rationale;
  torn-tail reader policy; O_NOFOLLOW symlink refusal; single-scan total to
  avoid double-I/O TOCTOU; `deque` bound for large logs; guard-test
  `sys.argv` patching because `CliRunner` does not populate it).

### Command-naming decision (do not re-litigate, inherited from rt-3.2/3.3)

The EPIC pins `dotfiles-runtime inspect status` / `inspect history` /
`inspect cache list`. **Use the `inspect` group with a `cache` subgroup
carrying a `list` command.** Do NOT create a top-level `cache` command, a
flat `cache-list` command, or follow SPEC.md:76 / AD-20's flat
`{wallpaper,status,history,cache}` list — those are earlier, coarser
namings. rt-3.2 already flagged this drift once; rt-3.3 extended the same
`inspect_app` group; this story nests one level deeper
(`inspect_app.add_typer(cache_app, name="cache")` + `@cache_app.command("list")`).

### Data sources (as-built — the reader contract)

- `cache/` layout (AR-2/AR-9 — read dir names ONLY)
  `[Source: shared-data-contract.md#Derivation-input hashing + ARCHITECTURE-SPINE.md#Structural Seed]`:
  ```
  state_root/cache/wallpapers/<wh>/wallpaper.png + meta.json
  state_root/cache/palettes/<ph>/colors.yaml + colors.conf + colors.gtk.css + meta.json
  state_root/cache/effects/<eh>/*.png + meta.json
  state_root/cache/icons/<ih>/*.svg + meta.json
  ```
  - Entry identity = dir name, `64-char lowercase hex sha256`
    (`cache.py:_is_hex64`, `cache_entry_path` validation). The reader
    MUST NOT re-hash contents and MUST NOT parse `meta.json` — dir names
    are the listing.
  - Staging dirs are SIBLINGS of layers: `cache/.staging-<pid>-<uuid>`
    (`cache.py:_staging_dir_for`, `CACHE_STAGING_PREFIX = ".staging-"`).
    They are never inside a layer dir — ignore by prefix at the `cache/`
    level; a layer dir never legitimately starts with `.`.
  - `CACHE_LAYERS = frozenset({"wallpapers","palettes","effects","icons"})`
    (`cache.py:50`). Import it; do not re-declare.
- Writer mechanics (do not touch, but know what you read):
  `populate_via_staging(target, populate_fn)` (`cache.py:172-263`):
  validates `.../cache/<layer>/<64hex>`, fast-path `False` if target
  exists (never overwrites), generates into sibling staging, `os.rename`
  (atomic same-filesystem), `FileExistsError`/`ENOTEMPTY`/`EEXIST`/`EISDIR`
  → discard staging + `False`. Orphan sweep skips live-PID stagings with a
  900s mtime grace (`STAGING_REAP_GRACE_SECONDS`). The reader MUST NOT
  replicate the sweep — no reaping, no `rmtree`, read-only.
- `IStateRepository` stays minimal (`load_current`/`save` only,
  `ports/state_repository.py:8-15`). Do NOT add `load_cache`/`list_cache` —
  rt-3.1 reserved history methods for Epic-3 inspection use cases via the
  adapter seam; the cache tree is read directly by the new use case from
  `state_root` (same layering privilege `InspectStateUseCase` already uses
  for `current/` symlink reads). The cache path never touches
  `current.json`: do NOT inject `state_repo`, do NOT call `load_current()`.

### Empty vs absent (AC 3 — exit 0, explicit)

- Absent `state_root/cache/` → all layers `[]` (missing cache is not an
  error; first-run machines may have nothing derived yet).
- Present-but-empty (no layer dirs, or layer dirs with zero valid entries)
  → same clean path.
- Clean message (plain + rich): `no cache entries recorded yet` (keep the
  exact string; tests assert it). JSON:
  `{"layers": {wallpapers: [], palettes: [], effects: [], icons: []},
  "counts": {wallpapers: 0, ...}, "total": 0}`. No `ErrorView` on this path.

### Noise-tolerance policy (AC 5 — diagnostic, not a validator)

rt-3.3 made history corruption LOUD (middle corrupt line → `ValueError`)
because history is a must-not-lose log. Cache listing is the opposite: a
diagnostic over a directory tree that legitimately contains transients
(in-flight `.staging-*`, half-written layer dirs, stray files). Policy:

- **Staging dirs** (`cache/.staging-*`): skip silently, no warning (hot
  path — a concurrent `wallpaper set` mid-populate must not spam the listing).
- **Plain files** anywhere under `cache/` or inside a layer dir: skip
  silently (squatting files are not entries).
- **Non-hex dir names** inside a layer: skip with
  `logger.warning("cache: skipping non-entry dir <layer>/<name>")` (visible
  in logs for debugging, but exit 0 — never `ValueError`).
- **Symlinks** (layer path or entry path with `is_symlink()` true): skip,
  never follow (mirror the writer's O_NOFOLLOW hardening in
  `seeder.py:43` + rt-3.3 `O_NOFOLLOW` open). Use
  `is_symlink()`-first checks and `is_dir(follow_symlinks=False)` so a
  symlink-to-dir is never descended. Pin with tests.
- Never raise on any of the above; only genuine I/O failures (`OSError`
  on `scandir`/`stat`, permission denied) propagate → CLI maps to
  `ErrorView` + exit 1.

### Composition root + CLI patterns to mirror (from rt-3.2/3.3)

- Build `_run_inspect_cache_list()` in `cli/main.py` and monkeypatch IT
  in CLI tests (exact precedent: `_run_reconcile` main.py:391-424 +
  `test_cli_reconcile.py:97-102` `_fake_composition`; `_run_inspect_status`
  main.py:501-519; `_run_inspect_history` main.py:581-603 with the
  single-scan total lesson).
- Wrap ALL expected domain errors: `(ValueError, RuntimeError, OSError)` →
  `logger.error` + `renderer.error(ErrorView(kind=..., message=...))` +
  `raise typer.Exit(code=1)`; plus catch-all `Exception` →
  `UnexpectedError`. Mirror main.py:537-547 / 622-634 verbatim style.
- Output: `renderer.custom(CustomView(plain=..., object={...}, rich=...))`.
  The `object` is the `--format json` payload — `layers` are FULL 64-char
  hashes sorted (assert VALUES — hashes, counts, total — not key presence;
  rt-3.1/3.2/3.3 review style).
- **No guard change:** `main_callback` (main.py:178-183) already skips
  seeding when `"inspect" in sys.argv`, which covers `inspect cache list`
  (`sys.argv` contains the literal `"inspect"`). Touching it risks
  re-seeding regressions — verify + pin only. Note: `CliRunner` does not
  populate `sys.argv`, so the end-to-end seed-tripwire must patch
  `sys.argv` (rt-3.3 Debug Log lesson).

### Read-only invariant (AC 4 — negative tests required, mirror rt-3.2 §Read-only + rt-3.3 §Read-only)

`inspect cache list` must create/write NOTHING: no `cache/` or layer dir
creation (when absent), no `current.json` write, no `current/` symlink
creation/repoint, no `history.jsonl` creation or append, no `.staging-*`
creation or reaping, no `.seed.lock`. Tests must assert the absence of
these side-effects (e.g. `state_root` snapshot before/after incl. dir
listings + file bytes; `cache/` still absent after an absent-cache run;
`save()`/`append_history()` tripwires never fire). "A story implementation
must leave the system working end-to-end" — cache listing must be safe to
run anytime (including mid-populate; the populator never holds a lock the
reader needs, and the reader never reaps the populator's staging).

### Test conventions (pass review or get bounced — inherited from rt-3.1/3.2/3.3)

- Runner: `uv run --directory src/runtime pytest`; class-based grouping
  with AC/AD-citing docstrings (e.g. `class TestInspectCacheUseCase:`
  "(AC 1, AR-2)"). No conftest.py.
- Deterministic fixtures: `"a"*64`-style hashes, `tmp_path` as `state_root`
  via constructor injection; cache fixtures hand-made with `mkdir` in unit
  tests (noise-tolerance cases) and built with the REAL
  `populate_via_staging` in integration tests (writer realism).
- CLI unit tests: monkeypatch the composition helper
  (`_fake_composition` pattern), `DOTFILES_INSTALL_SPINE` +
  `XDG_STATE_HOME` fixtures (mirror `test_cli_reconcile.py:88-95`).
- Pin TRANSIENT observables (caplog for the non-hex warning) not just
  final state; assert VALUES (hashes, order, counts) not key presence;
  JSON payload asserts assert exact shape incl. `counts`/`total`.
- Integration: write via the REAL writer (`populate_via_staging`), read
  via a FRESH `InspectCacheUseCase` — restart-survival-style realism
  (rt-3.1 lesson). Multi-layer test: entries in all 4 layers, default
  listing returns all sorted with correct `counts`/`total`.
- `rg "prune|evict"` over new/changed source files returns zero hits
  (AC 2) — verify manually, not via a unit test.

### Commit flow

`feat(rt-3-4): inspect cache list command ...` for the implementation;
`docs(bmm): add story rt-3-4 ...` carrying this story `.md` +
`sprint-status.yaml`. (Precedent: rt-3-2/rt-3-3 commits.)

### Project Structure Notes

- All new code under existing layers: extend
  `src/runtime/src/runtime/application/inspect.py` (new `CacheLayerListing` /
  `InspectCacheResult` + `InspectCacheUseCase`) and `cli/main.py`
  (`cache_app` subgroup + `list` command + `_run_inspect_cache_list`
  helper). Layering: application → domain/ports/adapters/application ONLY
  (test_layering.py:9,64); cli is the composition root (imports everything
  in-runtime). The extended `application/inspect.py` must import only
  `runtime.domain.*`, `runtime.ports.*`, `runtime.adapters.*` (for
  `CACHE_LAYERS` — allowed), and stdlib (`os`, `logging`, `dataclasses`,
  `pathlib`) — NEVER `runtime.cli`. New result types are frozen slots
  dataclasses (`@dataclass(frozen=True, slots=True)` with
  `from __future__ import annotations`, mirroring `LinkStatus` /
  `HistoryRecord` / `InspectStatusResult`).
  Read dirs with `os.scandir`/`Path.iterdir` + `is_symlink`-first guards;
  never `shutil.rmtree`, never `os.rename`, never `mkdir`.
- Tests land at `tests/unit/test_inspect_cache.py`,
  `tests/unit/test_cli_inspect_cache_list.py`,
  `tests/integration/test_inspect_cache_list_integration.py` — naming matches
  the rt-3.2/3.3 `test_inspect*` / layer split. No conftest.py.
- Package facts: `dotfiles-runtime` at `src/runtime/` (nested src
  layout), Python >= 3.14, hatchling, typer>=0.12, cli-output (editable
  sibling), ruff line-length 100 double-quotes, mypy strict, target py314.

### References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md#Story 3.4: inspect cache list command] (ACs verbatim; Epic 3 lines 430-435; R1 line 102)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md#Layer mapping] / [#AD-2 — Layered content-addressed cache] / [#AD-3 — JSON / dict-like store; filesystem is authority] / [#AD-5 — state_root] / [#AD-8 — SHA-256 hashing, versioned] / [#AD-9 — Staging-dir cache population] / [#AD-12 — Synchronous imperative Phase 2] / [#AD-19 — Operational envelope] / [#AD-20 — Separate dotfiles-runtime binary] / [Structural Seed cache layout]
- [Source: same folder shared-data-contract.md#Derivation-input hashing (cache keys)] / [#meta.json (one per cache entry)] / [#Swap sequence (AD-6 ownership)]
- [Source: _bmad-output/specs/spec-dotfiles-runtime-phase2/SPEC.md#CAP-7]
- [Source: src/runtime/src/runtime/adapters/cache.py:50 `CACHE_LAYERS`] / [:80-104 `_is_hex64` + `_validate_target`] / [:107-135 `cache_entry_path`] / [:172-263 `populate_via_staging`] / [:54 `STAGING_REAP_GRACE_SECONDS`]
- [Source: src/runtime/src/runtime/adapters/seeder.py:43 O_NOFOLLOW] (symlink hardening precedent)
- [Source: src/runtime/src/runtime/ports/state_repository.py:8-15 `IStateRepository` minimal]
- [Source: src/runtime/src/runtime/application/inspect.py `InspectStateUseCase` + `InspectHistoryUseCase`] (module cohesion, frozen-slots style, read-only + O_NOFOLLOW + single-scan lessons)
- [Source: src/runtime/src/runtime/cli/main.py:39-40 `inspect_app`] / [:178-183 `main_callback` auto-seed guard] / [:501-519 `_run_inspect_status`] / [:581-603 `_run_inspect_history`] / [:606-665 `inspect_history` CustomView/ErrorView]
- [Source: _bmad-output/implementation-artifacts/rt-3-1-history-jsonl-persistence.md#Dev Notes] — writer mechanics, crash-window verdict, deferred items
- [Source: _bmad-output/implementation-artifacts/rt-3-2-inspect-status-command.md#Dev Notes] — inspect-group naming win, composition/test/guard/read-only patterns, quality-gate baselines, commit style
- [Source: _bmad-output/implementation-artifacts/rt-3-3-inspect-history-command.md#Dev Notes] — history reader contract, limit default, torn-tail policy, guard-test sys.argv patching, review-range battery.tsx false-positive
- [Source: _bmad-output/implementation-artifacts/deferred-work.md] — rt-3.1 torn-tail/concurrency deferrals (cache-list tolerance context)

## Dev Agent Record

### Agent Model Used

OpenCode powered by Meta Muse Spark (muse-spark-1.3-contributor-free)

### Debug Log References

- Baseline `rt-3.3` gates re-verified live at start: `ruff check src` = 3
  (cli/main.py B008×2, domain/models.py E501×1), `mypy --strict src` = 4,
  `ruff format --check src` clean.
- `application/inspect.py` mypy strict initially flagged empty-dict
  invariant (`dict[str, tuple[()]]` vs `dict[str, tuple[str, ...]]`);
  fixed with explicit annotation on `_empty_result`.
- `ruff format` reformatted both source files after edits; re-checked clean.
- New suites: 35 tests pass
  (`test_inspect_cache.py` + `test_cli_inspect_cache_list.py` +
  `test_inspect_cache_list_integration.py`).
- Full suite: 546 passed, 2 skipped (zero regressions).
- Post-change gates: `ruff check src` = 3 (baseline unchanged, zero new),
  `ruff format --check src` clean, `mypy --strict src` = 4 (baseline
  unchanged, zero new), `test_layering.py` 57 passed.
- AC-2 pin: `rg -i "prune|evict|clear"` over the 5 new/changed files
  returns only the `eviction surface (AC 2)` docstring comment (excluded
  per spec) — zero functional hits.
- `git status --short` contains only this story's files
  (`application/inspect.py`, `cli/main.py`, 3 test files,
  `sprint-status.yaml`, this story file).

### Completion Notes List

- ✅ Task 1: `InspectCacheUseCase` + `CacheLayerListing`/`InspectCacheResult`
  (frozen slots) in `application/inspect.py`; canonical order validated
  against `CACHE_LAYERS`; `os.scandir` with symlink-first guards;
  staging/files silently skipped, non-hex warns exact message, symlinked
  cache root raises `ValueError`; never reads `meta.json`/`current.json`.
- ✅ Task 2: `cache_app` subgroup + `inspect cache list` command in
  `cli/main.py`; `_run_inspect_cache_list()` returns single-scan
  `InspectCacheResult`; `ValueError/RuntimeError/OSError → ErrorView+Exit1`,
  catch-all `UnexpectedError`; empty → exit 0 `no cache entries recorded yet`;
  plain per-layer `<layer> (<count>):` + indented truncated hashes, JSON
  full hashes + `counts`/`total`, rich = plain; guard untouched + pinned.
- ✅ Task 3: 3 test files (use-case incl. caplog/read-only/symlink cases;
  CLI incl. canonical-order/plain-truncation/JSON-values/error-mapping/
  seed-tripwire; integration via real `populate_via_staging` + isolation).
- ✅ Task 4: all quality gates pass with zero new violations (see Debug Log).

### File List

- src/runtime/src/runtime/application/inspect.py (modified — Task 1)
- src/runtime/src/runtime/cli/main.py (modified — Task 2)
- src/runtime/tests/unit/test_inspect_cache.py (new — Task 3)
- src/runtime/tests/unit/test_cli_inspect_cache_list.py (new — Task 3)
- src/runtime/tests/integration/test_inspect_cache_list_integration.py (new — Task 3)

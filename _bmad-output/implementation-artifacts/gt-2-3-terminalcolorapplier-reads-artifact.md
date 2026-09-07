---
baseline_commit: 07ea6fd
---

# Story 2.3: TerminalColorApplier reads the artifact

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a user,
I want the terminal palette applied from the pinned `current/colors.sequences` artifact,
So that the OSC bytes have a single source of truth shared with new shells.

## Acceptance Criteria

### Verbatim contract (epics-gtk-theming.md, Story 2.3)

**Given** `current/colors.sequences` exists as a cache artifact
**When** `TerminalColorApplier.reload()` runs
**Then** it reads the artifact bytes and writes them to `/dev/tty` once (behavior-identical payload to the re-derived bytes)
**And** the colors.yaml parser path is retired (or kept only as fallback documented as deprecated — pick one and pin it)
**And** vacuous/missing/dangling precedence (AC-4-before-AC-3) is preserved; unit + integration tests updated

### Operational sub-ACs (dev contract — derived from the verbatim block + the pinned artifact byte shape)

1. **Given** `src/runtime/src/runtime/adapters/terminal_color_applier.py`, **When** `reload()` runs on a seeded state, **Then** the guarded consumer entry is `current/colors.sequences` (NOT `current/colors.yaml`): the applier reads `link.read_bytes()` (raw bytes, NO text decode) and writes those bytes UNMODIFIED to `/dev/tty` (the injected `tty_path` seam is preserved for tests) exactly once per `reload()`, then flushes — `TerminalColorApplier(state_root=state_root, tty_path=...)` constructor signature unchanged, so the `_build_reloaders` wiring in `cli/main.py:228` needs NO source change (AC: verbatim "Then it reads the artifact bytes and writes them to `/dev/tty` once").

2. **Given** the artifact's exact byte shape (verified against csg source; Dev Notes "Artifact byte-shape spec"), **When** the payload is written, **Then** the bytes are the `colors.sequences` artifact VERBATIM — including the per-OSC trailing LF after each ST terminator (`\x1b\\`) that the pinned `colors.sequences.j2` template + `JinjaTemplateRenderer` binary post-processing produce. "Behavior-identical payload to the re-derived bytes" is pinned as LF-augmented identity: `artifact_bytes` and the old `_build_payload` output carry the same 19 OSC sequences in the same order; the artifact additionally carries the 19 per-line LFs (the old code deliberately omitted them). The parity test pins the exact relation (AC: verbatim "(behavior-identical payload to the re-derived bytes)" — interpretation pinned in Dev Notes Decision C).

3. **Given** the epics' retire-or-deprecate choice, **When** the switch lands, **Then** the colors.yaml parser path is RETIRED entirely: `_parse_colors_yaml`, `_build_payload`, and the six parser pins (`_HEX_PATTERN`, `_SCALAR_RE`, `_EXTRA_SCALAR_RE`, `_COLORS_HEADER_RE`, `_LIST_ITEM_RE`, `_EXPECTED_COLOR_COUNT`) are DELETED, the `re` import is removed, and NO deprecated fallback remains. In its place a MINIMAL corrupt-artifact guard preserves the R5 fail-loud class: the payload must be non-empty AND start with `\x1b]`, else warning + `False` (no TTY write). Decision + rationale pinned in Dev Notes Decisions A/B (AC: verbatim "And the colors.yaml parser path is retired … pick one and pin it").

4. **Given** the family invariant (AC-4-before-AC-3, same guard order as `hyprpaper_reloader.py`), **When** `reload()` runs, **Then** precedence is preserved with the entry name switched to `colors.sequences`:
   (a) `current/` dir absent → `True` (debug log, no TTY touch);
   (b) `current/colors.sequences` absent (`not exists() and not is_symlink()`) → `True` WITHOUT touching the TTY — the vacuous state wins over a missing/broken TTY (dedicated test kept);
   (c) dangling symlink (`is_symlink()` and not `exists()`) → `False` + warning;
   (d) `read_bytes()` raises `OSError` → `False` + warning;
   (e) corrupt artifact (empty, or not starting with `\x1b]`) → `False` + warning, no TTY write;
   (f) `/dev/tty` open/write failure (`FileNotFoundError`, `PermissionError`, `OSError`, `ValueError`) → `False` + warning;
   success → debug log with the byte count. Log messages keep the existing shapes with the entry name updated (`colors.yaml` → `colors.sequences` / "consumer entry") (AC: verbatim "And vacuous/missing/dangling precedence (AC-4-before-AC-3) is preserved").

5. **Given** the unit tests (`tests/unit/test_terminal_color_applier.py`), **When** updated, **Then**: the fixture family switches to `current/colors.sequences` (a canonical 19-sequence bytes fixture + `_make_sequences` seeding symlink-to-real-file, mirroring today's `_make_colors_yaml`); the byte-read tests assert the sink receives the artifact bytes VERBATIM (LFs included); the 8-case malformed-YAML parametrize is RETIRED and replaced by byte-corruption cases (empty file; non-OSC garbage such as `b"junk\n"`; non-UTF8 garbage) all asserting `False` + no sink write; dangling-symlink, unreadable-file, regular-file-traversed, TTY open/write failure, vacuous family (incl. `test_vacuous_true_wins_without_tty` and `test_missing_consumer_no_write_attempted`), interface, and state-root tests are kept with the new fixture; the CRLF test is retired (no text parsing remains); a NEW parity test pins Decision C's relation using BOTH derivations kept in fixtures (canonical colors.yaml text + old-payload helper) (AC: verbatim "unit + integration tests updated").

6. **Given** the integration tests (`tests/integration/test_terminal_color_applier_integration.py`), **When** updated, **Then**: `_FakeCsg` writes a REALISTIC full 19-sequence `colors.sequences` (current stub is a single-sequence placeholder — it must match the real artifact shape so `current/colors.sequences` is honest); the expected payload is computed INDEPENDENTLY from the palette constants (never by calling the adapter, never by re-reading the seeded artifact); the seeded-apply test asserts `sink.read_bytes() == expected` (LF-inclusive); the unwritable-sink surfaced-failure and vacuous-state tests keep their contracts (vacuous test's docstring updated to the new entry name); a NEW test seeds `current/`, then breaks `current/colors.sequences` into a dangling symlink → `ReconcileDesktopStateUseCase.run()` surfaces `"TerminalColorApplier"` in `reload_failures` (AC: verbatim "unit + integration tests updated").

7. **Given** the module docstring (lines 1-91) references `colors.yaml`, the strict-parser coupling, and the re-derivation rationale, **When** rewritten, **Then** it states the artifact-read contract: the applier reads `current/colors.sequences` bytes and writes them verbatim to `/dev/tty` once; the OSC bytes have a SINGLE source of truth shared with new shells (the same artifact `.zshrc` cats — its repoint to the runtime state root is gt-3-2, currently still provisioning-rendered); the pinned `colors.sequences.j2` template + `JinjaTemplateRenderer` binary post-processing remain the spec of record (no invented OSC codes, LFs written verbatim per csg's own `terminal_applier._emit_to_terminal` precedent); the re-derivation rationale and Story-2.3-transitional note are REMOVED; the AD-15 no-import note, AC-4-before-AC-3 precedence, and R5 headless decision are preserved with the new entry name; the `reload()` and class docstrings are updated to match (AC: derived — the module docstring must not outlive its own rationale).

8. **Given** `shared-data-contract.md` swap step 5 says "Terminal palette applied once from `current/colors.yaml`.", **When** this story lands, **Then** that ONE line is updated to `current/colors.sequences` — a minimal, precise edit owned HERE (the phrase is this story's behavior contract). All other doc reconciliation (ConsumerPointer table wording, cache-model, consumer-wiring.md, ARCHITECTURE-SPINE, docs/99) remains gt-4.2 scope (AC: derived — the epics' FR-6 ties this phrase to this story; deviation from the gt-2-1/gt-2-2 docs-deferred precedent justified in Dev Notes Decision E).

9. **Given** the gate contract, **When** the story lands, **Then** `tests/architecture/test_layering.py` passes with zero edits (no port/domain change; all I/O stays in the adapter); the `TerminalColorApplier` wiring assertions in `test_cli_reconcile.py` / `test_cli_wallpaper_set.py` (type list + `_state_root` wiring) and the stub-based tests in `test_cli_crash_recovery.py` / `test_wallpaper_set_capstone_integration.py` stay green UNCHANGED (they never assert palette bytes); `ReconcileResult.reload_failures` semantics unchanged; full gate suite green at the documented baseline; AR-3 untouched (history schema, `inspect cache list`, swap order — the applier is one reloader among four, invoked in the same position) (AC: verbatim "unit + integration tests updated" — non-regression bound).

## Tasks / Subtasks

- [x] Task 1 — Adapter: byte-read switch (AC: 1, 2, 3, 4)
  - [x] `src/runtime/src/runtime/adapters/terminal_color_applier.py`:
    - DELETE `_parse_colors_yaml`, `_build_payload`, `_HEX_PATTERN`, `_SCALAR_RE`, `_EXTRA_SCALAR_RE`, `_COLORS_HEADER_RE`, `_LIST_ITEM_RE`, `_EXPECTED_COLOR_COUNT`; remove the `re` import (`os` and `pathlib` stay; `_resolve_state_root` untouched).
    - `reload()`: entry becomes `link = current_dir / "colors.sequences"`; keep the guard order EXACTLY as today (sub-AC 4a→f): `current/` dir check → entry-absent vacuous check (`not link.exists() and not link.is_symlink()`) → dangling check (`link.is_symlink() and not link.exists()`) → `link.read_bytes()` in `try/except OSError` (the `UnicodeDecodeError` catch is dropped — no decode happens) → NEW minimal shape guard (`if not payload or not payload.startswith(b"\x1b]"): warning + return False`) → TTY write/flush in the unchanged exception tuple.
    - Log messages: same shapes, entry name updated (`"no colors.sequences entry in %s; nothing to apply"`, `"TerminalColorApplier reload failed: colors.sequences is corrupt (not OSC sequences): %s"` for the shape guard, etc.). Constructor, `_resolve_state_root`, and the `tty_path` seam are untouched.
  - [x] Rewrite the module docstring (sub-AC 7), the class docstring (`Reads state_root/current/colors.yaml (FS authority, NFR-3 …)` → colors.sequences artifact-read), and the `reload()` docstring (True/False semantics list updated: no parse-failure case, corrupt-bytes case added; precedence paragraph updated to the new entry name).

- [x] Task 2 — Contract phrase (AC: 8)
  - [x] `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md`: swap step 5 line → "Terminal palette applied once from `current/colors.sequences`." (ONE line; nothing else in the file — the full doc reconciliation is gt-4.2).

- [x] Task 3 — Docstring-only pin (AC: 7)
  - [x] `src/runtime/src/runtime/cli/main.py` `_build_reloaders` docstring (line 217): "terminal palette (OSC from ``current/colors.yaml``)" → "``current/colors.sequences``". No source-behavior change in this file (the `TerminalColorApplier(state_root=state_root)` construction at line 228 is signature-stable).

- [x] Task 4 — Unit tests (AC: 5)
  - [x] `tests/unit/test_terminal_color_applier.py`:
    - Fixture family: keep `_COLORS`; ADD `_canonical_sequences() -> bytes` building the full 19-sequence artifact bytes (each OSC + ST + trailing `\n`, foreground/background/cursor from the same constants — the exact Dev Notes artifact spec); replace `_make_colors_yaml` with `_make_sequences(tmp_path)` (symlink `current/colors.sequences` → real file with those bytes); `_make_dangling` targets `colors.sequences`.
    - KEEP the old colors.yaml fixtures (`_canonical()`, `_expected_payload()`) for the ONE parity test: assert `sink_bytes == artifact_bytes` (already covered) AND `artifact_bytes.replace(b"\x1b\\\n", b"\x1b\\") == _expected_payload()` — the LF-augmented identity relation of Decision C (a comment pins WHY raw equality is intentionally not asserted).
    - `TestTerminalColorApplierParseAndSequence` → byte-read tests: sink bytes == `_canonical_sequences()` VERBATIM (LFs included); hex pass-through test rebuilt on bytes (uppercase/lowercase mix passes through verbatim — no parsing normalizes anything).
    - `TestTerminalColorApplierVacuous`: keep all four tests, fixture-switched (`test_missing_colors_yaml_returns_true` → sequences; `test_vacuous_true_wins_without_tty` with an unreachable TTY; `test_missing_consumer_no_write_attempted`).
    - `TestTerminalColorApplierFailure`: dangling symlink kept; malformed parametrize RETIRED → NEW byte-corruption cases (empty file, `b"junk\n"`, `b"\xff\xfe\x00garbage"` — each `False` + no sink write, caplog-asserted at WARNING); unreadable file (`chmod 0`) kept; CRLF + BOM tests RETIRED (no text decoding remains); `test_regular_file_entry_is_traversed` kept on bytes; TTY open/write failure tests kept (fixture-switched; the single sanctioned `builtins.open` patch stays).
    - `TestTerminalColorApplierInterface` / `TestTerminalColorApplierStateRoot` / `_FakeCsg` / `_FakeWeg` / `_FakeItr` / reconcile helper classes: keep UNCHANGED (the `_FakeCsg` sequences stub bytes are never byte-asserted in the reconcile tests).
  - [x] VERIFY ONLY (no edit expected — they assert wiring/stubs, never palette bytes): `tests/unit/test_cli_reconcile.py`, `tests/unit/test_cli_wallpaper_set.py`, `tests/unit/test_cli_crash_recovery.py`.

- [x] Task 5 — Integration tests (AC: 6)
  - [x] `tests/integration/test_terminal_color_applier_integration.py`:
    - `_FakeCsg.generate` writes a REALISTIC `colors.sequences`: the full 19-sequence LF-terminated byte payload built from the same palette constants as `_pinned_colors_yaml()` (replace the current single-sequence stub `b"\x1b]4;0;#1a1b26\x1b\\"`).
    - Replace `_expected_payload_from_colors_yaml` with `_expected_sequences_bytes() -> bytes` computed INDEPENDENTLY from those constants (template semantics re-stated in the helper, never by calling the adapter or re-reading the seeded artifact).
    - Test 1 (seeded apply): assert `result.reload_failures == []` and `sink.read_bytes() == expected` (LF-inclusive).
    - Test 2 (unwritable sink → surfaced): unchanged.
    - Test 3 (vacuous state): guard entry renamed in docstring + fixture (`ApplyWallpaperUseCase` still does not repoint `current/`, so the vacuous path holds); assertions unchanged.
    - NEW test: seed → apply, then REPLACE `current/colors.sequences` with a dangling symlink → run reconcile with the applier → `"TerminalColorApplier" in result.reload_failures` (dangling is surfaced False through the use-case boundary, R5).
  - [x] VERIFY ONLY: `tests/integration/test_wallpaper_set_capstone_integration.py` (stub-based), `test_apply_wallpaper_integration.py` (no applier bytes).

- [x] Task 6 — Full green (AC: 9)
  - [x] Run and require green (no test runs are part of story CREATION — this task list is for the dev agent):
    ```bash
    uv run --directory src/runtime pytest -q
    uv run --directory src/runtime pytest tests/architecture/test_layering.py -v
    uv run --directory src/runtime ruff check .
    uv run --directory src/runtime ruff format --check .
    uv run --directory src/runtime mypy --strict src/runtime
    ```
  - [x] Record gate results at baseline FIRST (the gt-2-1/2-2 `git stash` procedure): ruff check = 104 pre-existing errors in tests, ruff format --check = 26 pre-existing files, mypy --strict = 4 pre-existing errors. Post-implementation must be EXACTLY at baseline — zero new violations, never `# type: ignore`. Expect a NET test-count DROP (retired malformed/CRLF parametrize ≈ 10 cases) partially offset by new byte-corruption/parity/dangling tests — document the delta in the story record.
  - [x] AR-3 byte-compat guard: history 7-field schema, `inspect cache list` output, swap order, `current/` name sets, and the four-reloader invocation order are unchanged; only the applier's READ source changed.

## Dev Notes

### Scope boundary — this story is the APPLIER ARTIFACT SWITCH only

Story gt-2-3 flips `TerminalColorApplier` from re-deriving OSC bytes out of `current/colors.yaml` to reading `current/colors.sequences` bytes verbatim. It does **NOT** implement:

- **zshrc repoint** — `.zshrc.j2:30` still cats `{{COLOR_SCHEME_OUTPUT_DIR}}/colors.sequences` (provisioning-rendered); repointing it to `$XDG_STATE_HOME/dotfiles/current/colors.sequences` is **gt-3-2**. Until then the "single source of truth shared with new shells" is realized on the runtime side only (the applier now reads the same artifact new shells WILL read).
- **GTK spine dirs / config_links** — gt-3-1. The applier touches nothing under the install spine (AD-5/AD-11: it only reads `current/` and writes `/dev/tty`).
- **AGS/icme polish, ConsumerPointer table wording, cache-model, consumer-wiring.md, ARCHITECTURE-SPINE, docs/99** — gt-4-1/gt-4-2. The ONLY doc edit here is the one-line swap-step-5 phrase (Decision E).
- **Any csg change** — the template, renderer, and `terminal_applier.py` are read as SPEC ONLY. `src/cli-tools/color-scheme-generator/**` is untouched.
- **Any hash, cache-layout, domain, or port change** — no domain model, port, seeder, derive, reconcile, or inspect source is modified; `adapters/hashing.py` untouched (NFR-4).

### colors.yaml is NOT orphaned by this story (scope-investigation pin)

Retiring the applier's parser does NOT orphan `current/colors.yaml`: the icon renderer chains the palette through it (`adapters/itr_adapter.py:394-458` resolves and passes the cache's `colors.yaml` to ITR via `ICON_RENDERER__COLOR_SCHEME__PATH`), and the ITR settings template points at `current/colors.yaml` as a static string (seeder.py:615 docstring). colors.yaml stays a first-class artifact in the 5-name set, consumed by ITR; only the applier's READ source moves. No `current/` name, seeder loop, or expected-target tuple changes in this story.

### Decision A (PINNED) — retire the parser + `_build_payload` entirely; no deprecated fallback

The epics offer retire-or-deprecate. **Retire** is pinned, rationale:

1. **The parser exists ONLY to support re-derivation.** Its own docstring admits the transitional status ("the sequence bytes are re-derived from `current/colors.yaml` because the applier's artifact switch … is Story 2.3"). Once the applier reads the artifact, a parser is dead code by construction.
2. **A "deprecated fallback" has no reachable, correct trigger.** `current/colors.sequences` and `current/colors.yaml` are repointed together by the SAME 5-name loop in `repoint_current_symlinks` (seeder.py:545-557) — they exist or fail together. The only divergence case is a broken cache entry, which fail-loud handling (dangling → False; hit-completeness guard from gt-2-1 → evict+regenerate) already covers. A fallback would keep TWO derivation paths alive forever — the exact opposite of the story's "single source of truth" purpose (FR-6) and a permanent second place the OSC byte shape could drift.
3. **colors.yaml keeps a real consumer** (ITR, above), so nothing must be kept alive "for compatibility".
4. Net effect is simplification: ~90 lines of parser + builder + 8 failure-mode mutations collapse to a byte-read with a two-clause shape guard.

### Decision B (PINNED) — minimal corrupt-artifact guard replaces strict parsing

The old parser made ANY malformed content a surfaced `False` (R5 fail-loud). Byte-read alone would silently write garbage from a corrupt/tampered cache artifact. Pinned guard: `payload` must be non-empty AND start with `\x1b]` (the template's first byte by construction). This preserves the observable failure class at one branch cost WITHOUT re-implementing the grammar (full hex/sequence validation would be re-derivation logic in disguise). Artifact content integrity beyond this is the cache's domain: entries are hash-addressed and produced by the pinned template (gt-2-1's hit-completeness guard evicts incomplete entries). The `#rrggbb`-hex validation disappears — csg's `Color.hex` is validated at the producer (`^#[0-9a-fA-F]{6}$`, csg `domain/models.py:15`), and the runtime no longer re-validates producer output it no longer parses.

### Decision C (PINNED) — payload = artifact bytes VERBATIM; "behavior-identical" = LF-augmented identity

Verified byte shape (see spec below): the artifact carries a trailing LF after EACH of the 19 ST-terminated OSC sequences (including the last — the template file ends with `\n`). The old `_build_payload` omitted the LFs (its docstring called this "functionally equivalent"). The new contract writes the artifact bytes VERBATIM because:
- csg's own live-apply precedent (`terminal_applier._emit_to_terminal`) reads the file bytes and writes them unmodified to `/dev/tty` — the runtime adapter has mirrored those mechanics by design;
- the zshrc path cats the same file — verbatim bytes make "one source of truth" literal rather than byte-adjacent;
- the template is the spec of record; the LFs are part of what the spec produces.

"Behavior-identical payload to the re-derived bytes" (epics) is therefore pinned as: **same 19 OSC sequences, same order, same ST terminators; the artifact additionally carries the 19 per-line LFs**. The parity test pins the exact relation — `artifact_bytes.replace(b"\x1b\\\n", b"\x1b\\") == old_derived_payload` — which is safe because the OSC payloads (slot indices + `#rrggbb` hex) contain no ESC or backslash bytes, so every `ST+LF` occurrence is a sequence boundary. Raw byte equality between old payload and artifact is intentionally NOT asserted.

#### Artifact byte-shape spec (verified against csg source at this worktree's HEAD)

- Template `defaults/templates/colors.sequences.j2`: 19 lines `]4;{i};{{ colors[i].hex }}\` (i = 0-15), then `]10;{{ foreground.hex }}\`, `]11;{{ background.hex }}\`, `]12;{{ cursor.hex }}\` — each line ends `\` + LF; the FILE ends with LF (od-verified).
- `JinjaTemplateRenderer.render` (jinja_template_renderer.py:75-77): for `*.sequences.j2` → `rendered.replace("]", "\x1b]").replace("\\", "\x1b\\")` then `write_bytes` — ESC/ST substitution only; newlines preserved.
- csg writes the artifact as `colors.sequences` (`terminal_applier._SEQUENCES_FILENAME`; `CsgAdapter`'s post-run verification loop and hash map already use that name — gt-2-1).
- Resulting artifact bytes for palette (bg/fg/cursor/colors16):

  ```
  b"".join(f"\x1b]4;{i};{hex}\x1b\\\n" for i, hex in enumerate(colors16))
  + f"\x1b]10;{fg}\x1b\\\n" + f"\x1b]11;{bg}\x1b\\\n" + f"\x1b]12;{cursor}\x1b\\\n"
  ```

- The runtime's `current/colors.sequences` is a SYMLINK to `cache/palettes/<ph>/colors.sequences` (gt-2-1) — `read_bytes()` follows it; the exists/is_symlink/dangling guard order already handles the link states.

### Decision D — the guarded `current/` entry is now colors.sequences

Every guard and log that referenced `colors.yaml` switches to `colors.sequences`. The precedence ORDER is untouched (AC-4-before-AC-3: vacuous entry first, TTY checks only after a consumer entry exists — a missing consumer entry wins over a missing TTY). The vacuous definition (`not exists() and not is_symlink()`) and the dangling definition (`is_symlink() and not exists()`) are kept verbatim. The `UnicodeDecodeError` catch is dropped (bytes are never decoded); `OSError` from `read_bytes()` keeps its warning + `False`.

### Decision E — one-line shared-data-contract.md edit here (deviation from the docs-deferred precedent)

gt-2-1/gt-2-2 amended runtime behavior and deferred ALL doc reconciliation to gt-4.2. This story nevertheless makes the ONE-LINE swap-step-5 edit because the phrase IS this story's contract ("Terminal palette applied once from `current/colors.yaml`" describes the applier's read source that this story changes — leaving it stale would make the contract assert a retired behavior). Everything else in the doc (artifact set enumeration, ConsumerPointer table, cache layout) stays for gt-4.2, consistent with precedent. If review prefers full deferral, moving the line into gt-4.2's inventory is a one-word scope change — but the default is pinned: edit the line here.

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/runtime/src/runtime/adapters/terminal_color_applier.py` | **UPDATE** | Byte-read switch; parser/_build_payload DELETED; minimal shape guard; module/class/reload docstring rewrite |
| `src/runtime/src/runtime/cli/main.py` | **UPDATE (docstring only)** | `_build_reloaders` docstring line 217; construction at line 228 untouched |
| `_bmad-output/planning-artifacts/architecture/.../shared-data-contract.md` | **UPDATE (one line)** | Swap step 5 phrase (Decision E) |
| `src/runtime/tests/unit/test_terminal_color_applier.py` | **UPDATE** | Byte fixtures, corruption tests, parity test, vacuous/TTY family switched |
| `src/runtime/tests/integration/test_terminal_color_applier_integration.py` | **UPDATE** | Realistic `_FakeCsg` sequences, independent expected-bytes helper, dangling test |
| `tests/unit/test_cli_reconcile.py`, `test_cli_wallpaper_set.py`, `test_cli_crash_recovery.py`, `tests/integration/test_wallpaper_set_capstone_integration.py` | **VERIFY ONLY** | Wiring/stub-based; never assert palette bytes |
| `src/cli-tools/color-scheme-generator/**` | **LEAVE ALONE** | Template + renderer are SPEC ONLY (read, never modified) |
| `domain/`, `ports/`, `application/` (seed_cache, reconcile, derive, inspect), `seeder.py`, `hashing.py` | **LEAVE ALONE** | Zero changes (grep-verified blast radius at 07ea6fd: `_parse_colors_yaml`/`_build_payload` referenced ONLY inside the applier module) |
| All other docs (consumer-wiring.md, cache-model.md, ARCHITECTURE-SPINE.md, docs/99) | **DO NOT TOUCH** | gt-4.2 scope |

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest` (`testpaths=["tests"]`, `pythonpath=["src","."]`, py314); fast path `pytest -k "not integration"`.
- Lint/type: `ruff check` + `ruff format --check` (line 100, double quotes) + `mypy --strict` — the deletion shrinks the strict surface (no new types introduced); record baseline counts BEFORE coding and require EXACT baseline after (gt-2-1/2-2 procedure). Expect a test-count delta from the parametrize retirement/replacement — document it, never chase the old count.
- `tests/architecture/test_layering.py` must stay green with ZERO edits (no port/domain surface changes; adapter I/O only).
- Deterministic fixtures only; the TTY seam (`tty_path` injection) remains the only sanctioned mechanism — the real `/dev/tty` is never opened in tests; the single `builtins.open` patch stays confined to the write-failure test.
- Every failure path is asserted BOTH on return value AND on no-sink-write, with `caplog` at WARNING for the surfaced-failure paths (mirror the existing pattern).
- The integration expected-bytes helper must stay INDEPENDENT of the adapter (computed from palette constants with the template semantics re-stated) — never assert `sink == artifact_read_via_adapter_code_path` (circularity).

### Architecture extraction — what this story must respect

| Decision | Relevance |
|----------|-----------|
| AD-1/AD-14 (hexagonal, domain purity) | Pure adapter change — no domain/port/application surface; I/O (`read_bytes`, TTY write) stays in the adapter |
| AD-5/AD-15 (§11 boundary, no csg imports) | STRENGTHENED: the last re-derivation coupling to csg's rendered shapes goes away; the applier imports nothing new and touches nothing under the install spine |
| AD-6/NFR-3 (atomic swap, idempotent) | Untouched — the applier is a post-swap reloader; it reads whatever `current/` points at and is re-runnable |
| AD-17 + NFR-5 (consumer wiring, relaunch pickup) | The applier stays the live-terminal consumer, invoked once per reconcile in position 4 of the fixed reloader list; no daemon |
| R5 (surfaced failure) | Preserved: no `isatty()` precondition; TTY/corrupt/read failures are `False` + warning → `ReconcileResult.reload_failures`; the minimal shape guard keeps corrupt ARTIFACTS surfaced, not just TTY faults |
| NFR-4 | No hash formula, no cache-layout change — the applier is a new READER of an existing artifact |
| AR-3 | Byte-compat where not in scope: swap order, history schema, `inspect cache list`, reloader list order all unchanged |

### Previous story intelligence (gt-2-1 + gt-2-2) + git intelligence

- gt-2-1 (commits 90d59c8 + review fix 47d23cb, DONE) made `current/colors.sequences` real in seed AND reconcile paths, with the hit-completeness guard (`ensure_palette_entry_complete`) evicting incomplete entries — the artifact the applier now reads is guaranteed to exist and be complete whenever `current/` is healthy.
- gt-2-2 (commits dedeeb7 + 68d70ca + review 07ea6fd, DONE) generalized consumer pointers; the seeder/inspect surfaces are stable — this story touches none of them. The applier is deliberately NOT a ConsumerPointer (it writes `/dev/tty`, not a spine symlink) — do not fold it into the spec table.
- The unit test file's `_FakeCsg`/`_FakeItr`/reconcile scaffolding was hardened by gt-fix-1 (never spawn the real desktop from tests) — keep those patterns intact.
- Baseline-gate procedure (stash → count → compare at exactly baseline) is established twice; repeat it (104 ruff / 26 format / 4 mypy pre-existing at 07ea6fd — re-verify at implementation time).
- Repo convention: story commits are `feat(runtime): ...` with `baseline_commit` frontmatter (this story: `07ea6fd`); review fixes follow as separate commits.
- Sprint-status `story_location` still points at the MAIN repo (stale, correction pending) — this story's file lives in the WORKTREE `_bmad-output/implementation-artifacts/` per the gt-1-1/gt-2-1/gt-2-2 precedent.
- Environment caveat (gt-2-1, still open): host `csg` binary predates gt-1-1. Irrelevant here — no real-csg test is touched; all applier fixtures are fake-csg based. Do NOT refresh csg as part of gt-2-3.

### Project Structure Notes

- Blast radius is exactly the applier module + 2 test files + 1 CLI docstring line + 1 contract line (grep-verified at 07ea6fd: `_parse_colors_yaml|_build_payload` have zero references outside `terminal_color_applier.py`; `TerminalColorApplier` appears in `cli/main.py` (wiring) and 7 test files, of which only the two applier test files assert behavior).
- The `re` import removal leaves the module with `logging`, `os`, `pathlib`, and the port import only — a strictly smaller import surface.
- `current/colors.sequences` is created by the seeder's 5-name loop (gt-2-1) in seed AND reconcile — the applier's guard is a pure reader of that state; it must never create, repoint, or delete anything under `current/` (grep-verify: no write calls other than the TTY).
- No new files. No new dependencies (runtime deps stay exactly `typer` + `cli-output`).

### References

- Epics: `_bmad-output/planning-artifacts/epics-gtk-theming.md` — Story 2.3 (verbatim AC block), FR-5, FR-6, NFR-1/3, AR-3
- Investigation: `_bmad-output/planning-artifacts/gtk-theming-investigation.md` — terminal chain (consumer-wiring §: live-terminal OSC + zshrc cat), §4 contract change list
- Contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — Swap sequence step 5 (the one-line edit, line 148)
- Wiring spec: `_bmad-output/specs/spec-dotfiles-runtime-phase2/consumer-wiring.md` — terminal colors chain (R5 channel decision, line 34 area)
- Done predecessors: `_bmad-output/implementation-artifacts/gt-2-1-palette-artifact-set-growth.md` (5-artifact set, `current/colors.sequences` real, hit-completeness guard, baseline-gate procedure), `gt-2-2-iconsumerpathspec-declarative-pointers.md` (spec loop stable; story-file structure mirrored here)
- csg spec sources (READ ONLY): `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.sequences.j2`, `adapters/jinja_template_renderer.py:75-77` (binary post-processing), `adapters/terminal_applier.py` (`_emit_to_terminal` verbatim-byte precedent, `_SEQUENCES_FILENAME`)
- Runtime code: `src/runtime/src/runtime/adapters/terminal_color_applier.py` (whole module), `cli/main.py:217,228` (`_build_reloaders`), `application/reconcile.py:292-307` (`reload_failures` collection), `adapters/itr_adapter.py:394-458` (colors.yaml's REMAINING consumer — ITR), `seeder.py:545-557` (5-name `current/` loop that creates the artifact link), `adapters/terminal_applier.py` mechanics mirrored by AD-15 note
- Tests: `tests/unit/test_terminal_color_applier.py`, `tests/integration/test_terminal_color_applier_integration.py` (both rewritten); `tests/unit/test_cli_reconcile.py:160-186`, `test_cli_wallpaper_set.py:280-315`, `test_cli_crash_recovery.py:164-267`, `tests/integration/test_wallpaper_set_capstone_integration.py:613-701` (VERIFY ONLY wiring/stub coverage)

## Dev Agent Record

### Agent Model Used

opencode-go/glm-5.3-flash (bmad-dev-story, fresh context)

### Debug Log References

- Gate baseline recorded BEFORE coding at 07ea6fd (verified in a throwaway temp worktree at that SHA, main worktree untouched): `pytest` 597 passed + 4 skipped (601 collected); `ruff check` 104 errors; `ruff format --check` 26 files; `mypy --strict` 4 errors — all matching the story's documented baseline.
- Red-green: rewrote adapter + tests, ran the two applier test files (25 passed), then full suite.
- One transient drift fixed during gates: (1) E501 on the corrupt-guard warning line (106 > 100) → split string literal, message text unchanged; (2) `ruff format` drifted on my 2 rewritten test files (28 vs 26) → formatted ONLY those two files, baseline restored exactly.
- Final gates (all at EXACT baseline): `pytest` 591 passed + 4 skipped; `ruff check` 104 errors; `ruff format --check` 26 files (60 formatted); `mypy --strict` 4 errors; `pytest tests/architecture/test_layering.py` 59 passed, ZERO edits to the file.

### Completion Notes List

- **Task 1 (ACs 1-4)**: `TerminalColorApplier.reload()` now guards `current/colors.sequences`, reads `link.read_bytes()` (no decode; `UnicodeDecodeError` catch dropped, `OSError` kept), applies Decision B's minimal shape guard (`not payload or not payload.startswith(b"\x1b]")` → warning + False, no TTY write), and writes the bytes VERBATIM to the `tty_path` seam once + flush. Guard order preserved EXACTLY (dir-absent → entry-absent vacuous → dangling → read → corrupt → TTY), constructor/`_resolve_state_root`/seam untouched. `_parse_colors_yaml`, `_build_payload`, all 6 parser pins, and the `re` import deleted (grep-verified: zero references anywhere else). Module/class/`reload()` docstrings rewritten per sub-AC 7 (artifact-read contract, single-source-of-truth with zshrc note + gt-3-2 pointer, re-derivation rationale and transitional note removed, AD-15/AC-4-before-AC-3/R5 preserved under the new entry name).
- **Task 2 (AC 8)**: one-line swap-step-5 edit in shared-data-contract.md (line 148) → `current/colors.sequences`. **Decision E deviation from the gt-2-1/gt-2-2 docs-deferred precedent applied as pinned**: this one line IS this story's behavior contract; everything else in the doc stays gt-4.2.
- **Task 3 (AC 7)**: `cli/main.py` `_build_reloaders` docstring only ("`current/colors.sequences`"); construction at line 228 untouched.
- **Task 4 (AC 5)**: unit tests rebuilt on byte fixtures — `_canonical_sequences()` (19 OSC + ST + trailing LF, file ends LF), `_make_sequences` symlink seeding, `_make_dangling` → colors.sequences. Byte-read tests assert sink == artifact VERBATIM (LFs included); hex pass-through rebuilt on mixed-case bytes. 8-case malformed-YAML parametrize RETIRED → 3-case byte-corruption parametrize (empty / `b"junk\n"` / non-UTF8 garbage), each False + no sink write + caplog WARNING; CRLF + BOM tests retired (no text decoding remains); dangling/unreadable/regular-file/TTY open-write/vacuous family kept fixture-switched (corruption/dangling/unreadable additionally caplog-asserted). Old `_canonical()`/`_expected_payload()` kept solely for the NEW parity test (Decision C): sink == artifact AND `artifact.replace(b"\x1b\\\n", b"\x1b\\") == _expected_payload()`, with the WHY-not-raw-equality comment pinned in the test docstring and a same-constants cross-check between the two fixture derivations. Reconcile/fake scaffolding untouched.
- **Task 5 (AC 6)**: integration `_FakeCsg` now writes the REALISTIC full 19-sequence LF-terminated `colors.sequences`; `_expected_payload_from_colors_yaml` replaced by `_pinned_sequences_bytes()` computed INDEPENDENTLY from the palette constants (template semantics restated, no adapter call, no artifact re-read); seeded-apply asserts `sink.read_bytes() == expected` (LF-inclusive); unwritable-sink and vacuous tests kept (vacuous docstring → colors.sequences). **NEW dangling test — one interpretation note**: reconcile unconditionally repairs `current/` symlinks (`_repoint_symlink` → `os.replace`) BEFORE reloaders run, so a pre-broken dangling link can never reach the applier through `run()`; the test instead injects a first `_LinkBreaker` reloader that breaks the freshly repointed entry at reload time, then asserts `"TerminalColorApplier" in reload_failures` — the same dangling-failure class surfaced through the same use-case boundary, without weakening the AD-6 repair contract.
- **Task 6 (AC 9)**: gates recorded above — zero new lint/type/format violations (never `# type: ignore` on touched lines), layering green with zero edits, AR-3 untouched (reloader list order, history schema, `inspect cache list`, swap order unchanged — only the applier's READ source moved). **Test-count delta documented**: 601 → 595 collected (597 → 591 passed, 4 skipped constant) = NET −6: retired 8-case malformed-YAML parametrize + non-UTF8 + BOM + CRLF (−11), added 3-case corruption parametrize + parity test + integration dangling test (+5).
- **Decision pins A–E confirmed in code**: A — no deprecated fallback remains, no second derivation path (grep-verified blast radius); B — two-clause shape guard only, no grammar re-implementation; C — verbatim bytes + LF-augmented parity relation pinned by test; D — every `colors.yaml` guard/log name switched, precedence order verbatim; E — one-line contract edit landed here, rest deferred to gt-4.2.
- **Scope boundaries respected**: csg tree untouched (template/renderer read as spec only); ConsumerPointer spec/seeder, provisioning, domain/ports/application, `hashing.py`, seeder all untouched; no new files, no new dependencies; the applier still writes ONLY the TTY (never creates/repoints/deletes anything under `current/`).

### File List

- src/runtime/src/runtime/adapters/terminal_color_applier.py (rewritten)
- src/runtime/src/runtime/cli/main.py (docstring-only)
- _bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md (one line)
- src/runtime/tests/unit/test_terminal_color_applier.py (rewritten)
- src/runtime/tests/integration/test_terminal_color_applier_integration.py (rewritten)
- _bmad-output/implementation-artifacts/gt-2-3-terminalcolorapplier-reads-artifact.md (status/record)
- _bmad-output/implementation-artifacts/sprint-status.yaml (gt-2-3 → review)

### Change Log

- 2026-09-07 — gt-2-3 implemented: TerminalColorApplier switched from parsing `current/colors.yaml` to reading `current/colors.sequences` bytes verbatim; parser + `_build_payload` retired (Decision A), minimal corrupt-artifact guard added (Decision B), LF-augmented parity test pins Decision C, guard-order/entry-name swap (Decision D), one-line shared-data-contract swap-step-5 edit (Decision E). All gates green at exact baseline; suite 591 passed + 4 skipped (NET −6 vs 597 baseline, documented above).

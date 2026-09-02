---
baseline_commit: e07bb7c
---

# Story 2.6: Terminal palette applier

Status: done

## Story

As a user,
I want the terminal to apply the new palette after a swap,
so that shell/terminal colors match the wallpaper.

## Acceptance Criteria

1. **Palette applied from `current/colors.yaml`.** **Given** a swap repointed `current/colors.yaml` → `cache/palettes/<ph>/colors.yaml` (through the runtime seeder, AD-17/AR-8), **When** the terminal palette applier runs, **Then** it resolves the `current/colors.yaml` symlink, parses the pinned CSG colors.yaml schema (scalars `background`, `foreground`, `cursor` + a 16-item `colors` list, all `#rrggbb` hex — the exact shape `colors.yaml.j2` renders), and builds the OSC terminal-palette byte sequence in the exact shape of the project's pinned `colors.sequences` channel: `ESC]4;0;<hex>ESC\` … `ESC]4;15;<hex>ESC\` then `ESC]10;<fg>ESC\`, `ESC]11;<bg>ESC\`, `ESC]12;<cursor>ESC\` — per consumer-wiring.md line 34 ("Terminal colors: applied from `current/colors.yaml` by the terminal adapter, not by a symlink") and shared-data-contract swap step 5 ("Terminal palette applied **once** from `current/colors.yaml`"), FR-6.

2. **Apply-once to the live terminal via `/dev/tty`.** **Given** the parsed palette, **When** the applier applies, **Then** it writes the OSC sequence bytes to the controlling terminal `/dev/tty` exactly once per `reload()` invocation — recoloring the terminal's ANSI palette through which the terminal consumers (starship prompt styles, zsh UI) resolve their colors. No per-consumer config file is written, no consumer symlink is created, and NO import of `color_scheme_generator` occurs (AD-15 forbidden set — the runtime MIRRORS `csg`'s `terminal_applier.py` mechanics, never imports them).

3. **R5 reload-failure reporting.** **Given** the terminal cannot be re-themed — missing `current/colors.yaml` consumer entry, dangling symlink, unparseable/malformed colors.yaml, `/dev/tty` cannot be opened (no controlling terminal / headless), or the write fails (`OSError` family) — **When** the applier reports, **Then** it returns `False` with a warning log naming the cause, the reconcile use case populates `ReconcileResult.reload_failures` with `"TerminalColorApplier"`, and the CLI exits non-zero (existing `cli/main.py:366-375` path). Headless / no-TTY is a SURFACED failure, not a skip (carried decision from rt-2-3/2-4/2-5 — spec-literal R5).

4. **Vacuous-True precedence.** **Given** `state_root/current/` contains NO `colors.yaml` entry (palette layer null / nothing to apply), **When** the applier reloads, **Then** it logs at debug level and returns `True` (vacuously — there is no palette to apply), EVEN when no controlling terminal exists — using the family's exact guard order (`hyprpaper_reloader.py:176-183`): `current/` dir absent → `True`; `colors.yaml` entry absent → `True`; the missing-TTY/parse failure checks run only AFTER a consumer entry exists. The nothing-to-apply state WINS over the missing-TTY failure — the precedence resolved in rt-2-5 review (AC 4 vacuous-True beats R5 missing-binary; enumerate first, fail on the channel only when there is something to apply). A colors.yaml entry that EXISTS but is dangling/corrupt is a failure (AC 3), not vacuous.

5. **Wired into the composition root.** **Given** the adapter is wired into `ReconcileDesktopStateUseCase`, **When** the swap sequence reaches step 5 (reload), **Then** `TerminalColorApplier` is invoked once via the existing `reloaders` list (the loop at `reconcile.py:257-266` needs NO changes), joining `[HyprlandReloader(), AgsReloader(), HyprpaperReloader(state_root=state_root)]` in the CLI composition root (`cli/main.py:329`) as the FOURTH entry, constructed with the explicit reconcile `state_root`. The composition-root wiring test (`TestReconcileCompositionRootWiring`, `test_cli_reconcile.py:141-169`) is UPDATED to expect all four reloaders with `state_root` plumbed. Stale scope comments (`cli/main.py:344-346`, `reconcile.py:12-14`) refreshed to "terminal is Story 2.6 — shipped".

## Tasks / Subtasks

- [x] Task 1 — Create `adapters/terminal_color_applier.py` (AC: 1, 2, 3, 4)
  - [x] Implement `TerminalColorApplier(IDesktopReloader)` (module `src/runtime/src/runtime/adapters/terminal_color_applier.py` — the spine manifest's `terminal_color_applier` name, ARCHITECTURE-SPINE.md adapters list). Constructor: `__init__(self, state_root: Path | None = None, tty_path: Path | None = None)`; when `state_root` is `None`, resolve the runtime default exactly as `cli/main.py:56-64` does (`$XDG_STATE_HOME` or `~/.local/state`, + `/dotfiles`, absolute) via a thin `_resolve_state_root` mirroring `hyprpaper_reloader.py`'s — explicit `state_root` for tests. `tty_path` is the apply TARGET (default `None` → `/dev/tty`): the sanctioned test seam for BOTH test layers (unit + integration) — NO `builtins.open` patching except the single write-failure unit test (Task 5).
  - [x] Consumer enumeration (FS authority, NFR-3) in the family's exact guard order (`hyprpaper_reloader.py:176-183`): first `current_dir = state_root/current`; if not a dir → debug log + `True`. Then `link = current_dir/colors.yaml`; if the entry does not exist AT ALL (`not link.exists() and not link.is_symlink()`) → debug log + `True` (AC 4 vacuous — must run BEFORE any TTY check; precedence lesson). If dangling (`link.is_symlink() and not link.exists()`) → warning + `False` (mirror hyprpaper_reloader.py:190-193's dangling check; do NOT rely on `resolve()` raising).
  - [x] Strict colors.yaml parse keyed to the PINNED template shape (`colors.yaml.j2`): line-oriented parse extracting `background: "<hex>"`, `foreground: "<hex>"`, `cursor: "<hex>"`, and the 16 `  - "<hex>"` items under `colors:`. Validate each against `^#[0-9a-fA-F]{6}$` (CSG's `_HEX_PATTERN`, models.py:15). Exactly 16 colors required, in order (index = ANSI slot). Any deviation (missing key, wrong count, bad hex) → warning + `False` (fail-loud; the file is machine-generated by the runtime's own pinned CSG template — never "best effort" parse). NO PyYAML dependency (see Dev Notes "Parsing decision").
  - [x] Sequence construction — byte-exact with the pinned `colors.sequences.j2` + its renderer post-processing (`]` → `\x1b]`, `\` → `\x1b\\`): for i, hex in enumerate(colors): `\x1b]4;{i};{hex}\x1b\\`; then `\x1b]10;{foreground}\x1b\\`, `\x1b]11;{background}\x1b\\`, `\x1b]12;{cursor}\x1b\\`. Emit as one `bytes` payload (ASCII encode).
  - [x] TTY apply: open the resolved `tty_path` (default `/dev/tty`) in `"wb"` mode and write the payload + flush, inside the mandated exception tuple `(FileNotFoundError, PermissionError, OSError, ValueError)` wrapping open+write (no subprocess in this adapter — there is no binary to resolve; the tty open replaces the hyprctl-spawn step). Any failure → warning with the exception detail + `False`. Success → `True`. Do NOT check `sys.stdout.isatty()` as a precondition (csg does, because csg's stdout may be captured mid-pipeline; the runtime adapter's contract is R5-surfaced-failure — attempting the write unconditionally is what makes headless a SURFACED failure per AC 3). Document the divergence from csg's guards in the module docstring.
  - [x] Module docstring MUST record (dense, evidence-citing, no inline "why" comments): the channel decision (OSC 4/10/11/12 derived from `current/colors.yaml`, apply-once per swap step 5), the consumer chain (terminal ANSI palette → starship/zsh styles), the colors.sequences byte shape source (`colors.sequences.j2` + JinjaTemplateRenderer binary post-processing), the AD-15 no-import note (mirrored, not imported, from `csg`'s `terminal_applier.py`), the strict-parser coupling to `colors.yaml.j2`, the AC-4-before-AC-3 precedence statement, the R5 headless-surfaced decision, and the known Phase-2 limitations (invoking terminal only; no daemon; new shells still read provisioning's `generated/palettes/colors.sequences`). Cite [consumer-wiring.md:34], [shared-data-contract.md swap step 5], [AD-15], [R5].
- [x] Task 2 — Wire into CLI composition root (AC: 5)
  - [x] In `cli/main.py` `_run_reconcile()`, add a lazy import next to the existing adapter imports (`cli/main.py:309-317`): `from runtime.adapters.terminal_color_applier import TerminalColorApplier`.
  - [x] Change `reloaders=[HyprlandReloader(), AgsReloader(), HyprpaperReloader(state_root=state_root)]` (`cli/main.py:329`) to `reloaders=[HyprlandReloader(), AgsReloader(), HyprpaperReloader(state_root=state_root), TerminalColorApplier(state_root=state_root)]` — Hyprland, AGS, Hyprpaper, terminal; deterministic order matching the swap-sequence reload listing. **Construct with the explicit `state_root` already computed at `cli/main.py:306`** (do NOT rely on the constructor's env-default — same rationale as rt-2-5 Task 3: the applier must read `current/` from the SAME state_root the reconcile use case writes).
  - [x] Update the now-stale comment at `cli/main.py:344-346` ("restarts Hyprland, restarts AGS, and applies the Hyprpaper wallpaper IPC per monitor") to include the terminal palette application. The generic reload-failure comment (`cli/main.py:365-367`) is fine as-is.
  - [x] **UPDATE `TestReconcileCompositionRootWiring`** (`tests/unit/test_cli_reconcile.py:141-169`): the four-reloader list is now the contract — assert `[HyprlandReloader, AgsReloader, HyprpaperReloader, TerminalColorApplier]` with `reloaders[2]._state_root` AND `reloaders[3]._state_root` == the captured reconcile `state_root`. This test WILL fail if you wire the adapter but forget the test update — fix both in the same commit.
  - [x] NO changes to `reconcile.py`'s reload loop or `ReconcileDesktopStateUseCase` constructor — `TestReconcileStructuralScopeLock` (`test_reconcile.py:689-708`) already pins the `reloaders` param; composition-root-only change.
- [x] Task 3 — CLI crash-recovery test isolation (mirror rt-2-5's forced deviation, PROACTIVELY this time)
  - [x] `tests/unit/test_cli_crash_recovery.py` runs the real CLI composition root (no `_run_reconcile` monkeypatch) — the newly wired `TerminalColorApplier` would reach the dev host's real `/dev/tty` (recoloring the developer's actual terminal or failing surfaced and flipping `reload_failures`). Add a `_PassingTerminalColorApplier` stub + `monkeypatch.setattr("runtime.adapters.terminal_color_applier.TerminalColorApplier", _PassingTerminalColorApplier)` in the same two tests that already isolate `HyprpaperReloader` (test_cli_crash_recovery.py:153-206 pattern — extend, don't duplicate), documented in the existing test-isolation docstring. rt-2-5 needed an unplanned deviation commit for exactly this; do it as part of the story.
- [x] Task 4 — Stale scope comments (mirror rt-2-4 Task 3 / rt-2-5 Task 4)
  - [x] `reconcile.py:12-14` currently reads "…Hyprpaper is Story 2.5; terminal follows in 2.6". After this story, the terminal ships — update to "…Hyprpaper is Story 2.5; terminal is Story 2.6". Docstring-only; no behavior change. (Also update the module-list docstring line in `cli/main.py` if it names the reloaders.)
- [x] Task 5 — Unit tests `tests/unit/test_terminal_color_applier.py` (AC: 1, 2, 3, 4)
  - [x] Follow `test_hyprpaper_reloader.py`'s style: construct with EXPLICIT `state_root` (a tmp dir you build `current/colors.yaml` in — real symlink to a real file written with the pinned schema; do NOT poke private state). For the TTY path, use the constructor's `tty_path` seam (Task 1): point it at a tmp file and assert the written BYTES — never open the real `/dev/tty` in tests.
  - [x] **Parse/sequence:** `test_builds_osc_sequences_from_pinned_schema` (write a canonical colors.yaml fixture → assert captured bytes == the exact expected payload: 16 × `\x1b]4;{i};{hex}\x1b\\` + `\x1b]10;…` `\x1b]11;…` `\x1b]12;…`, pin the byte shape); `test_hex_values_pass_through_verbatim` (uppercase/mixed-case hex accepted — CSG emits lowercase but the validator allows `[0-9a-fA-F]`).
  - [x] **Vacuous (AC 4):** `test_missing_colors_yaml_returns_true` (no `current/` dir → `True`, TTY hook NOT invoked); `test_current_dir_exists_no_colors_yaml_returns_true` (existing-but-empty `current/` → `True` — the literal-branch test rt-2-5 review demanded); `test_vacuous_true_wins_without_tty` (no colors.yaml AND `/dev/tty` unopenable → still `True` — precedence pinned); `test_missing_consumer_no_write_attempted` (zero open calls).
  - [x] **Failure (AC 3):** `test_dangling_symlink_is_failure`; `test_malformed_yaml_is_failure` parametrized (missing `cursor` key / 15 colors / 17 colors / non-hex color / truncated file → `False`, sink never written); `test_tty_open_failure_returns_false` parametrized via REAL `tty_path` variants (a directory as target → `IsADirectoryError`; a path under a missing dir → `FileNotFoundError`; a file with `chmod 000` → `PermissionError`) — all deterministic, no patching; `test_tty_write_failure_returns_false` (the ONE sanctioned patch in the file: `monkeypatch.setattr("builtins.open", ...)` raising `OSError`, narrowly scoped to this single test with a comment — the adapter has no subprocess seam like its siblings, so the open call IS the I/O boundary); `test_port_conformance` (`isinstance(applier, IDesktopReloader)`).
  - [x] **State-root plumbing:** `test_env_default_state_root_resolution` (mirror the hyprpaper tests: patch env/`Path.home` to force the `$XDG_STATE_HOME` default and the `~/.local/state` fallback — explicit-path tests stay deterministic).
  - [x] **Reconcile integration (mirror `_make_reconcile_with_reloaders` in `test_ags_reloader.py:368-386`):** `test_terminal_failure_populates_reload_failures` (failing fake reloader beside passing ones → `"TerminalColorApplier"` present/absent correctly); `test_all_reloaders_invoked_once` (four fakes each called exactly once — AC 5).
- [x] Task 6 — Integration test `tests/integration/test_terminal_color_applier_integration.py` (AC: 1, 2, 3, 5)
  - [x] Honest contract: the integration test does NOT have a real terminal to recolor, and it does NOT go through the CLI composition root — the family pattern composes the use case DIRECTLY (`_make_reconcile`-style helper, `test_hyprpaper_reloader_integration.py:145-155`: real `JsonStateRepository` + fake csg/weg/itr + fake mutex). E2E: seed → apply → reconcile with `reloaders=[TerminalColorApplier(state_root=tmp_state_root, tty_path=sink)]` (a tmp file as the apply target). Assert the sink file contains the byte-exact OSC payload derived from the seeded palette's colors.yaml (read the palette artifacts from the seeded cache entry to compute the expected payload independently). The production default (`tty_path=None` → `/dev/tty`) is what keeps the adapter honest — the test injects the sink.
  - [x] Failure paths: reconcile with `TerminalColorApplier` pointing at an unwritable sink (dir as target) → `"TerminalColorApplier"` in `result.reload_failures` and CLI exit non-zero (mirrors `test_hyprpaper_reloader_integration.py`'s surfaced-failure assertions); vacuous path (state_root without `current/colors.yaml`) → no failure, sink untouched.
- [x] Task 7 — Full green gate (AC: all)
  - [x] `uv run --directory src/runtime pytest -q` (**377 passed, 2 skipped** — baseline 353 → +24 from this story)
  - [x] `uv run --directory src/runtime ruff check src/runtime` (zero NEW violations; 3 pre-existing)
  - [x] `uv run --directory src/runtime ruff format --check src/runtime` (new/edited files format-clean)
  - [x] `uv run --directory src/runtime mypy --strict src/runtime` (zero NEW errors; 4 pre-existing)
  - [x] `tests/architecture/test_layering.py` green (adapter lives in adapters/; no new import categories)

## Dev Notes

### Scope boundary — terminal palette application ONLY

This story delivers the `TerminalColorApplier` reload adapter. It does NOT:
- add `colors.sequences` to the cache or the palette `meta.json` `artifact_hashes` — the shared-data-contract pins EXACTLY `colors.yaml`/`colors.conf`/`colors.gtk.css` (AR-9: on-disk schemas "must be written exactly"; changing the artifact set is a spine change). The applier derives the sequences from `colors.yaml` instead.
- rewrite provisioning's rendered `.zshrc` or flip `COLOR_SCHEME_OUTPUT_DIR` (the rendered `~/.config/zsh/.zshrc` line 30 still cats `<install>/generated/palettes/colors.sequences` — provisioning-owned, `zsh_config` role `tasks/main.yml:51`; runtime NEVER edits provisioning-rendered configs or writes under the install spine, AD-5). Consequence (recorded as known limitation): a NEW shell picks up provisioning's default sequences, not the runtime's current palette. Closing that gap is a future cross-domain provisioning delta.
- implement a terminal-multiplexer or per-terminal-emulator config writer (no kitty/alacritty/foot configs exist in the spine — `dotfiles/config/` holds only ags/hypr/hyprpaper/icon-template-color-scheme-mappings/nvim/starship/wlogout/zsh). The ANSI-palette channel is the only channel that exists.
- implement per-monitor variants — swap step 5 says "terminal palette applied ONCE" (single `current/colors.yaml`, no monitor dimension).
- change the swap sequence, `ReconcileResult`, or the CLI reload-failure error path (all exist from rt-2-2/2-3/2-4/2-5).
- rewire `wallpaper set` (Story 2.7 capstone).

### The channel design (this IS the deliverable decision)

**Channel: OSC 4/10/11/12 escape sequences written to `/dev/tty`, derived from `current/colors.yaml`.** Grounds:

1. **consumer-wiring.md:34** — "Terminal colors: applied from `current/colors.yaml` by the terminal adapter (CAP-6), **not by a symlink** (terminals read a config file, not a shared path)." The applier is a reader of `current/colors.yaml`, not another symlink repoint.
2. **shared-data-contract swap step 5** — "Terminal palette applied once from `current/colors.yaml`" — pins the input file and the once-per-swap arity, listed alongside the per-monitor backend reloads.
3. **The consumers are ANSI-resolved.** `starship.toml` styles ("bold red", "purple", `dotfiles/config/starship/starship.toml:19,34`) and zsh's theme colors resolve against the TERMINAL EMULATOR's 256/16-color ANSI palette — recoloring the live terminal's palette slots 0–15 (OSC 4) + fg/bg/cursor (OSC 10/11/12) recolors starship and zsh with zero per-consumer work. There is no starship palette-import mechanism and no terminal-emulator config in the spine to rewrite.
4. **Precedent inside the project:** CSG ships exactly this mechanism — `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/terminal_applier.py` writes a generated `colors.sequences` file's bytes to `/dev/tty`; the zshrc chain consumes the same artifact at shell startup (`.zshrc.j2:30`). The runtime replicates the mechanism from `current/colors.yaml` because the runtime cache does not contain `colors.sequences` (see parsing decision).
5. **AD-15:** `color_scheme_generator` is in the forbidden import set — the adapter must NOT import csg's `terminal_applier` or its templates; it mirrors the mechanics (and cites them).

**Parsing decision (strict line parser, no new dependency):** `colors.yaml` is machine-generated by the runtime's own pinned CSG template (`colors.yaml.j2`: three scalar keys + 16-item list, `#rrggbb` hex — CSG's `Color.hex` is validated `^#[0-9a-fA-F]{6}$`, models.py:15). The runtime `pyproject.toml` deps are exactly `typer` + `cli-output` — adding PyYAML for a 20-line pinned schema is unjustified. Parse strictly against the pinned shape and fail-loud (`False`) on ANY deviation: the file is a cache artifact addressed by a hash of the templates that produced it, so "unexpected shape" means a broken cache entry, and per R5 that is a surfaced failure, not a fallback. Hand-rolled YAML parsing is normally an anti-pattern — it is correct HERE only because the producer template is pinned and hash-addressed; document that coupling in the docstring.

**Sequence byte shape (pinned):** CSG renders `colors.sequences.j2` as literal `]4;N;<hex>\` lines and post-processes `]` → `\x1b]`, `\` → `\x1b\\` (`JinjaTemplateRenderer`, csg docs table line 114). The runtime payload must be byte-equivalent: `\x1b]4;0;#rrggbb\x1b\\` × 16, then `\x1b]10;<fg>\x1b\\`, `\x1b]11;<bg>\x1b\\`, `\x1b]12;<cursor>\x1b\\`. OSC 4 sets ANSI palette slot N; OSC 10/11/12 set default foreground/background/cursor. This is the decades-stable XTerm OSC contract; all mainstream terminals (kitty, alacritty, foot, st, VTE-based) honor it. No web research dependency — the project's own `colors.sequences.j2` is the spec of record; do not invent additional OSC codes.

### The `IDesktopReloader` port + reload loop (existing — do not modify)

`ports/desktop_reloader.py`: `reload() -> bool`. `ReconcileDesktopStateUseCase` already has `reloaders: list[IDesktopReloader]` and the Step-5 loop outside the lock (`reconcile.py:257-266`): each reloader is called once, per-reloader exceptions are caught, `False` → class name into `reload_failures`. The applier reads `state_root/current/colors.yaml` itself (FS authority, NFR-3) — the loop passes no state. No per-monitor parameter on the port.

### Reuse — leverage existing infrastructure (do not duplicate)

- `IDesktopReloader` port — use as-is.
- `HyprpaperReloader`'s constructor + `_resolve_state_root` pattern (`hyprpaper_reloader.py`) — copy the state-root resolution semantics (mirror `cli/main.py:56-64`), NOT a shared helper (rt-2-5 defer: a shared helper is not layering-clean across application/adapters). The terminal applier resolves NO binary (no subprocess at all) — simpler than its siblings.
- csg's `terminal_applier.py` guards/`/dev/tty` write pattern — mirror the write mechanics (`open("/dev/tty", "wb")` + flush); do NOT mirror its `isatty` no-op guard (divergence documented above). Mirror, never import (AD-15).
- The composition root pattern: lazy import + explicit `state_root` plumbing + reloader-list append (`cli/main.py:309-329`) — the third time this exact change is made (rt-2-4 added AGS, rt-2-5 added Hyprpaper).
- Test scaffolding: `_FakeMutex`/`_FakeCsg`/`_FakeWeg`/`_FakeItr`/`_setup_spine`/`_make_reconcile_with_reloaders` patterns already copied across the hyprland/ags/hyprpaper test files (shared-conftest refactor remains a pre-existing deferred item — follow the current copy-paste convention).
- CLI crash-recovery isolation pattern: `_PassingHyprpaperReloader` + `monkeypatch.setattr` (test_cli_crash_recovery.py:153-206) — extend with the terminal stub.

### Behavioral decisions carried from rt-2-3/2-4/2-5 (do not soften)

Missing/non-live consumer = **surfaced failure**. On a headless/dev machine with no controlling terminal, `TerminalColorApplier` returns `False` and `reconcile` exits non-zero with `TerminalColorApplier` in the failure list — exactly like `HyprlandReloader` fails with no Hyprland session. This is spec-literal R5 ("reports failure if the terminal cannot be re-themed"). Do NOT convert it into a skip, and do NOT import csg's isatty-no-op semantics. The ONLY vacuous success is "no colors.yaml consumer entry at all" (AC 4), which wins over the TTY check by ordering (rt-2-5 review D2 resolution).

### Code style gates (enforced)

Python 3.14, `mypy --strict` (no untyped defs, `from __future__ import annotations` at top), ruff line-length 100, ruff select E/F/I/N/W/UP/B. Parenthesize multi-except tuples (PEP 758). Timestamps `datetime.now(UTC).isoformat().replace("+00:00", "Z")` (only if the adapter ever timestamps — it likely doesn't). House style: dense module docstrings citing AD-numbers and evidence, no inline "why" comments. No new runtime dependencies (`pyproject.toml` untouched: typer + cli-output only).

### Invariants (non-negotiable)

- **Enumerate before TTY:** the AC-4 vacuous check (`current/colors.yaml` absent) happens FIRST; a missing consumer returns `True` without touching `/dev/tty` (rt-2-5 review precedence lesson, now a cross-adapter invariant).
- **Byte-exact sequence shape:** `ESC]4;<slot>;<#rrggbb>ESC\` × 16 in ANSI-slot order, then `ESC]10;`/`ESC]11;`/`ESC]12;` — matching `colors.sequences.j2` + post-processing. No extra OSC codes, no terminfo negotiation.
- **Strict schema validation:** exactly 16 colors, `^#[0-9a-fA-F]{6}$` each, all three scalar keys present — any deviation → `False` (fail-loud).
- **One write per `reload()`**, to `/dev/tty` (or the injected `tty_path` in tests), `wb` mode, flushed.
- **Exception tuple** around open+write: `(FileNotFoundError, PermissionError, OSError, ValueError)` → warning log, return `False`. (No subprocess exceptions — there is no subprocess.)
- **Missing consumer entry = vacuous `True`; dangling/corrupt entry = surfaced `False`; no TTY with a valid entry = surfaced `False`.**
- **No imports from `color_scheme_generator`** (AD-15 forbidden set) — the sequence shape is re-derived from the pinned template, cited in the docstring.
- **Test safety verified this session:** `TestReconcileStructuralScopeLock` (test_reconcile.py:689-708) pins `reloaders` as a param (no structural edits needed); `TestReconcileCompositionRootWiring` (test_cli_reconcile.py:141-169) pins the EXACT three-reloader list and WILL FAIL until updated to four (update it in the same commit as the wiring); `test_cli_crash_recovery.py` invokes the real composition root and needs the terminal stub isolation (Task 3) — skipping it recreates rt-2-5's unplanned-deviation commit.

### Previous story intelligence (rt-2-5 — the direct predecessor)

- **rt-2-3/2-4/2-5 review lessons to apply proactively:**
  1. Vacuous-True vs surfaced-failure precedence must be explicit in code order AND tested (rt-2-5 D2: `test_missing_hyprctl_zero_symlinks_returns_true` + literal empty-dir branch test).
  2. Composition-root wiring needs a positive test or a mis-wire passes green (rt-2-5 D2 patch → `TestReconcileCompositionRootWiring` — this story UPDATES it, does not bypass it).
  3. Real-CLI tests reach live host consumers through newly wired adapters — isolate proactively (rt-2-5 needed a deviation commit for the live hyprpaper wire error; the terminal adapter reaches the live `/dev/tty`).
  4. Docstrings must not overclaim — cite only verified facts and their sources (rt-2-5 P1: the spaces-vs-comma claim correction).
  5. Report accurate test counts in the Dev Agent Record (rt-2-5 D3: arithmetic note rewritten by review).
- **rt-2-5 shipped** `HyprpaperReloader` with: state_root constructor + `_resolve_state_root` mirror, enumerate-first reload structure (sorted per-monitor scan), dangling-check-before-resolve, mandated exception tuple, composition-root wiring with explicit state_root, `reconcile.py` scope-comment update. The terminal applier is structurally the SIMPLEST member of the family: no binary resolution, no subprocess, no monitor loop — one consumer file, parse, write.
- **Baseline suite (verified this session): 353 passed, 2 skipped.** Pre-existing lint debt: 3 ruff errors, 4 mypy errors — zero NEW is the bar.

### Git intelligence

HEAD = `e07bb7c` ("fix: auto-commit code review findings" — the rt-2-5 review patch application; the story implementation auto-commit before it was `0fc602f feat(rt-2-5): hyprpaper channel verification + per-monitor reload adapter`). The reloaders list exists and contains exactly three entries; this story appends the fourth. Repo commit style: `feat(rt-2-x): <story description>` for implementation, `fix: auto-commit code review findings` for review patches.

### Latest technical information

No new external dependencies — the adapter uses stdlib only (`pathlib`, `os` via `Path.open`, `re` for validation; NO subprocess). OSC 4/10/11/12 is the stable XTerm/OpenBSD terminal-palette contract; the project's own pinned `colors.sequences.j2` template + its documented binary post-processing (`]` → `\x1b]`, `\` → `\x1b\\`) is the authoritative byte-shape spec — no upstream research needed and none should override it. CSG `Color.hex` is `^#[0-9a-fA-F]{6}$` (models.py:15). Python 3.14, Typer, pytest, ruff, mypy pinned in `src/runtime/pyproject.toml`/`uv.lock`; do NOT bump them.

### Testing standards summary

- Runner: `uv run --directory src/runtime pytest -q`. Unit tests are pure fakes with explicit paths and the `tty_path` sink; integration tests compose the use case DIRECTLY (`_make_reconcile`-style helper, fake csg/weg/itr) and assert byte-level sink outcomes end-to-end. The headless/no-TTY case is a surfaced-failure assertion, not a skip.
- Lint/type gates in Task 7, all with `--directory src/runtime`; zero NEW violations is the bar.
- Layering: domain purity untouched (adapter holds all I/O), ports are ABCs, cross-package forbidden set unchanged.
- Assertion style: unit tests assert behavior + contracts (byte-exact payload, precedence order, return values, state-root plumbing); integration tests assert filesystem/sink outcomes and `reload_failures` end-to-end.

### Project Structure Notes

New files:
- `src/runtime/src/runtime/adapters/terminal_color_applier.py` (NEW — terminal palette applier)
- `src/runtime/tests/unit/test_terminal_color_applier.py` (NEW — unit tests)
- `src/runtime/tests/integration/test_terminal_color_applier_integration.py` (NEW — integration test with injected TTY sink)

Modified:
- `src/runtime/src/runtime/cli/main.py` (lazy `TerminalColorApplier` import + fourth reloader entry with explicit `state_root`; stale comment refresh)
- `src/runtime/src/runtime/application/reconcile.py` (docstring-only: scope comment 2.6 shipped)
- `src/runtime/tests/unit/test_cli_reconcile.py` (`TestReconcileCompositionRootWiring` → four reloaders + state_root plumbing)
- `src/runtime/tests/unit/test_cli_crash_recovery.py` (test-isolation only: `_PassingTerminalColorApplier` monkeypatch extension)

No changes: `domain/`, `ports/` (IDesktopReloader already exists), `pyproject.toml`, `seeder.py`, `json_state_repository.py`, `csg_adapter.py` (the 3-format pin stands), provisioning, `dotfiles/config/**`.

### References

- Epics: `_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase2.md` — Story 2.6 ACs, FR-6, R5, AD-17/AR-8 consumer wiring
- Architecture spine: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/ARCHITECTURE-SPINE.md` — AD-6 (swap step 5), AD-15 (forbidden imports), AD-17 (consumer wiring), adapters manifest (`terminal_color_applier`)
- Shared data contract: `_bmad-output/planning-artifacts/architecture/architecture-dotfiles-repo-v3-2026-08-18/shared-data-contract.md` — swap step 5 ("Terminal palette applied once from current/colors.yaml"), palette meta.json artifact pin (3 artifacts)
- Spec companions: `_bmad-output/specs/spec-dotfiles-runtime-phase2/consumer-wiring.md:34` (terminal channel), `SPEC.md` CAP-6
- Byte-shape spec of record: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.sequences.j2` (+ `colors.yaml.j2` for the parse schema); CSG `domain/models.py:15` (`_HEX_PATTERN`); CSG `adapters/terminal_applier.py` (mirrored `/dev/tty` mechanics — NOT imported)
- Existing code: `src/runtime/src/runtime/ports/desktop_reloader.py`, `src/runtime/src/runtime/adapters/hyprpaper_reloader.py` (state-root + enumerate-first pattern to mirror), `src/runtime/src/runtime/application/reconcile.py` (reload loop + stale scope comment), `src/runtime/src/runtime/cli/main.py` (composition root `cli/main.py:329`, lazy imports, reload-failure exit)
- Previous stories: `_bmad-output/implementation-artifacts/rt-2-5-hyprpaper-channel-verification.md` (direct predecessor — review lessons, composition-root wiring test, crash-recovery isolation), `rt-2-4-ags-restart-reload-adapter.md`, `rt-1-11-first-run-self-seeding.md` (seed-time terminal-applier note, line 84)
- Consumer wiring as-built: `dotfiles/config/zsh/.zshrc.j2:30` (`cat colors.sequences &`), `src/provisioning/ansible/roles/zsh_config/tasks/main.yml:51` (`COLOR_SCHEME_OUTPUT_DIR`), `dotfiles/config/starship/starship.toml` (ANSI-style consumers)

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

- Baseline verified before implementation: `uv run --directory src/runtime pytest -q` → 353 passed, 2 skipped.
- Post-implementation full gate: 377 passed, 2 skipped (+24 from this story: 20 unit + 3 integration + the auto-parametrized `test_layering.py` case collected for the new adapter file; the composition-wiring test was modified, not added).
- `ruff check src/runtime` → 3 errors (all pre-existing; zero NEW).
- `ruff format --check src/runtime` → clean (terminal_color_applier.py reformatted once for W292 trailing-newline + E501 line-length).
- `mypy --strict src/runtime` → 4 errors (all pre-existing; zero NEW; checked 34 source files).
- `tests/architecture/test_layering.py` → 54 passed.

### Completion Notes List

- ✅ Shipped Task 1: `TerminalColorApplier(IDesktopReloader)` in `adapters/terminal_color_applier.py`. Family guard order (`hyprpaper_reloader.py:176-183`): absent `current/` → vacuous `True`; absent `current/colors.yaml` entry → vacuous `True` (before any TTY check — AC 4 precedence); dangling symlink → `False`. Strict line-oriented parse of the pinned `colors.yaml.j2` schema (3 scalars + exactly 16 `#rrggbb` colors, `_HEX_PATTERN` semantics), NO PyYAML. Byte-exact OSC 4/10/11/12 payload (`colors.sequences.j2` shape), ASCII-encoded, written once per `reload()` to `/dev/tty` (or injected `tty_path` seam) with the mandated `(FileNotFoundError, PermissionError, OSError, ValueError)` tuple; no `sys.stdout.isatty()` precondition (R5 headless = surfaced failure). AD-15: mirrored csg's `terminal_applier.py` mechanics, never imported. Dense evidence-citing module docstring covers channel decision, consumer chain, byte-shape source, strict-parser coupling, AC-4-before-AC-3 precedence, headless decision, Phase-2 limitations.
- ✅ Shipped Task 2: wired as the FOURTH reloader in `_run_reconcile` (lazy import + explicit `state_root`), updated `TestReconcileCompositionRootWiring` to the four-reloader contract with `_state_root` asserted for reloaders[2] and [3]. No `reconcile.py` loop change.
- ✅ Shipped Task 3: `_PassingTerminalColorApplier` stub + monkeypatch added to both CLI crash-recovery tests that isolate reloaders (proactive isolation of the live `/dev/tty`).
- ✅ Shipped Task 4: `reconcile.py:12-14` scope comment updated to "terminal is Story 2.6"; `cli/main.py` reconcile docstring now lists the terminal palette application.
- ✅ Shipped Task 5: 20 unit tests — parse/sequence byte-shape pinning, verbatim hex pass-through, 4 vacuous-True tests (incl. literal empty-dir branch and vacuous-wins-without-TTY), 5-param malformed-yaml failure, 3-param real `tty_path` open-failure (IsADirectoryError/FileNotFoundError/PermissionError), single sanctioned `builtins.open` write-failure patch, port conformance, env-default state-root resolution, and 2 reconcile-loop tests (`TerminalColorApplier` name in/out of `reload_failures`, four fakes called once).
- ✅ Shipped Task 6: 3 integration tests composing the use case directly (`_make_reconcile` helper): E2E seed→apply→reconcile with the injected sink computing the expected payload INDEPENDENTLY from the seeded cache `colors.yaml`; unwritable-sink surfaced failure (`"TerminalColorApplier"` in `reload_failures` — CLI exit non-zero already covered by `cli/main.py` reload-failure path); vacuous real-state reload (True, sink untouched).
- ✅ Shipped Task 7: full green gate green — 377 passed / 2 skipped; ruff check + format clean (0 new); mypy 0 new; layering green.

### File List

- `src/runtime/src/runtime/adapters/terminal_color_applier.py` (NEW — terminal palette applier)
- `src/runtime/src/runtime/cli/main.py` (MOD — lazy `TerminalColorApplier` import, fourth reloader with explicit `state_root`, reconcile docstring updated to include terminal palette application)
- `src/runtime/src/runtime/application/reconcile.py` (MOD — docstring-only scope comment: terminal is Story 2.6)
- `src/runtime/tests/unit/test_terminal_color_applier.py` (NEW — 20 unit tests)
- `src/runtime/tests/integration/test_terminal_color_applier_integration.py` (NEW — 3 integration tests with injected TTY sink)
- `src/runtime/tests/unit/test_cli_reconcile.py` (MOD — `TestReconcileCompositionRootWiring` → four reloaders + `_state_root` plumbing)
- `src/runtime/tests/unit/test_cli_crash_recovery.py` (MOD — `_PassingTerminalColorApplier` isolation stub added to the two isolated crash-recovery tests + docstring update)

## Change Log

- 2026-09-02 — Story created (ready-for-dev) with terminal-channel design pinned: OSC 4/10/11/12 derived from `current/colors.yaml`, strict template-keyed parse (no new deps), `/dev/tty` apply-once, vacuous-True precedence, composition-root four-reloader wiring + mandatory test updates. Baseline: 353 passed, 2 skipped.
- 2026-09-02 — Quality validation pass applied (5 fixes): integration tests compose the use case directly via `_make_reconcile` helper (not the CLI composition root — matches `test_hyprpaper_reloader_integration.py:145-155`); `tty_path: Path | None = None` mandated as the single TTY seam in Task 1's constructor (removed the ambiguous pick-one between open-patching and injection; one narrowly-scoped `builtins.open` patch sanctioned for the write-failure unit test only); dangling-check citation corrected to `hyprpaper_reloader.py:190-193`; AC 4 pinned to the family's exact guard order (`hyprpaper_reloader.py:176-183`).
- 2026-09-02 — Story implemented and marked for review: `TerminalColorApplier` shipped (family guard order, strict pinned-schema parse, byte-exact OSC payload, surfaced-failure TTY contract, no csg import), wired as the fourth CLI reloader with explicit `state_root`, crash-recovery isolation added proactively, scope comments refreshed. 23 new tests (20 unit + 3 integration); full gate: 377 passed / 2 skipped, ruff & format 0 NEW, mypy 0 NEW, layering green.

### Review Findings (2026-09-02 code review: blind hunter + edge case hunter + acceptance auditor)

- [x] [Review][Patch] Parser leniency violates fail-loud-on-ANY-deviation invariant — duplicate `background:`/`foreground:`/`cursor:` lines silently overwrite (last-wins); a second `colors:` header re-enters list mode so a SPLIT list totaling 16 passes; a scalar line inside the colors block both ends the list AND overwrites the scalar (8 items + repeated `cursor:` + 8 more items = 16, corrupted palette applied); any unrecognized line is silently skipped despite the docstring claiming "everything else must match the exact quoted line shapes" [adapters/terminal_color_applier.py:124-125,130-143]
- [x] [Review][Patch] `test_terminal_failure_populates_reload_failures` passes for the wrong reason and `_canonicalize_palette_yaml` is dead code — the fake csg seeds `"colors: []"` so the applier fails at the PARSE stage, never reaching the write; the sink (`tmp_path/"sink"`) is a nonexistent-but-creatable path, so naively calling the dead helper would flip the test to failure-free. Fix: canonicalize the seeded palette via the helper AND point `tty_path` at a directory so the failure is genuinely at the write stage [tests/unit/test_terminal_color_applier.py:363-366,400-409]
- [x] [Review][Patch] "Byte-exact" docstring overclaim — the real pinned artifact contains an LF after every `\x1b\\` (verified: `colors.sequences.j2` lines end with `` \` `` and `JinjaTemplateRenderer` uses `trim_blocks=True`, so the newline survives the `\` → `\x1b\\` post-processing; csg's `terminal_applier.py` writes those raw bytes), while `_build_payload` concatenates without newlines. Functionally benign; fix the wording to per-sequence byte-equivalence + LF-free concatenation (and the test docstrings/claims that repeat it) — rt-2-5 lesson: docstrings must not overclaim [adapters/terminal_color_applier.py:24-31,154-155]
- [x] [Review][Patch] Docstring byte-shape typo "ESCy]" (three occurrences — should be "ESC]") [adapters/terminal_color_applier.py:27-29]
- [x] [Review][Patch] Uncited absolute claims in module docstring — "decades-stable XTerm/OpenBSD OSC contract; all mainstream terminals (kitty, alacritty, foot, st, VTE-based) honor it" cites no source, violating the house rule the story itself mandates; reword to what is verifiable (the project's pinned template is the spec of record) [adapters/terminal_color_applier.py:18-20]
- [x] [Review][Patch] `reconcile.py` scope-comment indentation mangled — continuation lines went flush-left / 3-space instead of preserving docstring indent [application/reconcile.py:12-13]
- [x] [Review][Patch] `test_vacuous_true_wins_without_tty` does not exercise an unopenable TTY — the stand-in path is nonexistent-but-writable, so precedence is pinned only via the sink-creation side effect, not the spec's literal premise ("/dev/tty unopenable → still True"); use a directory as `tty_path` for a discriminating pin [tests/unit/test_terminal_color_applier.py:162-168]
- [x] [Review][Patch] Test gaps: `except (OSError, UnicodeDecodeError)` read-failure branch dead in the suite (no unreadable/non-UTF-8 colors.yaml test); existing-but-not-symlink regular-file entry traversal unpinned; CRLF/BOM parser variants unpinned (regressions would pass the suite) [tests/unit/test_terminal_color_applier.py:187-221]
- [x] [Review][Patch] Both new test files end without a trailing newline, contradicting the Dev Record's "format-clean (new/edited files)" claim [tests/unit/test_terminal_color_applier.py EOF, tests/integration/test_terminal_color_applier_integration.py EOF]
- [x] [Review][Patch] Dev Record arithmetic note imprecise — "+24 (20 unit + 3 integration + 1 composition-wiring assertion upgrade)": the 24th collected item is the auto-parametrized layering case for the new adapter; the composition-wiring test was modified, not added (rt-2-5 lesson: accurate test counts) [story Dev Agent Record]
- [x] [Review][Defer] No test renders the real pinned `colors.yaml.j2` — the parser/template coupling is guarded only by hand-written fixtures; a csg Jinja-env change (e.g. `trim_blocks`) would make every real artifact unparseable (fail-loud everywhere, but unguarded) [tests/unit/test_terminal_color_applier.py:26-38] — deferred, family-wide fixture pattern (cross-package render test is a structural/layering question)
- 2026-09-02 — Code review applied (10/10 patch findings fixed; 1 defer logged to deferred-work.md; 8 dismissed). Parser tightened to the pinned shape (duplicate scalars, second `colors:` header, unknown/junk/stray lines, scalar-whitelist extras all fail-loud); wrong-reason reconcile test fixed (`_FakeCsg` now writes the canonical schema, sink is a real unwritable dir, dead `_canonicalize_palette_yaml` removed); docstrings corrected (per-sequence byte-equivalence + LF-free concat instead of the false "byte-exact" claim, "ESCy]" typos, uncited vendor sentence dropped); `reconcile.py` docstring indent fixed; tests added for regular-file entry, unreadable/non-UTF-8/BOM colors.yaml, CRLF acceptance, junk-line/duplicate-scalar/split-list malformed params, literal unopenable-TTY vacuous pin; both test files reformatted + trailing newline; Dev Record arithmetic corrected. Gates: 385 passed / 2 skipped (baseline 377), ruff 3 pre-existing (0 new), mypy 4 pre-existing (0 new), layering OK. Status → done.

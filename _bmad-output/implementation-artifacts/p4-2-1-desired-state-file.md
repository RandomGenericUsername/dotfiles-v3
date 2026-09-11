# Story 4.2: Desired-State File + Schema + Loader

Status: ready-for-dev

baseline_commit: 816ac84

Epic: Phase 4 Epic 2 — Declarative State (`_bmad-output/planning-artifacts/epics-dotfiles-runtime-phase4.md`)

## Story

As a user,
I want a `desired.json` file with a validated schema and a loader,
so that the future diff engine has a declared intent document to converge toward.

## Acceptance Criteria

1. `state_root/desired.json` carries `{version, wallpaper, keep, pinned}` with strict validation: `version` must be `1`; `wallpaper` a non-empty string; `keep` an integer `>= 0`; `pinned` a list of 64-char lowercase-hex strings; unknown keys rejected (fail loud on typos, matching repo philosophy) (AC 1)
2. Absent `desired.json` is NOT an error — the loader returns `None` ("no declared intent"; plain `reconcile` keeps today's imperative behavior). Malformed `desired.json` raises `ValueError` with the file path and reason (AC 2)
3. `DesiredState` is a frozen domain dataclass; all filesystem I/O lives in the adapter; `test_layering.py` passes unchanged (AC 3)

## Tasks / Subtasks

- [ ] Add `DesiredState` frozen dataclass to `src/runtime/src/runtime/domain/models.py` (AC: 1, 3)
  - [ ] Fields: `wallpaper: str` (source image path as written by the user), `keep: int`, `pinned: tuple[str, ...]` (entry hashes). No `version` field on the model (version is a file-format concern, validated at load, not carried).
  - [ ] stdlib allowlist only; no I/O imports.
- [ ] Create `src/runtime/src/runtime/adapters/desired_state_reader.py` (AC: 1, 2)
  - [ ] `read_desired_state(state_root: Path) -> DesiredState | None`: absent file → `None` (never creates the file — readers don't provision); unparseable/non-object/wrong `version`/bad `wallpaper`/`keep`/non-list `pinned`/non-hex pin/unknown key → `ValueError` naming the file and the offending field.
  - [ ] Symlinked `desired.json` → `ValueError` (refuse to follow, mirroring the history/meta symlink policy — a redirectable intent file is a spoofing vector).
  - [ ] Docstring records the v1 schema contract: `{version: 1, wallpaper: str, keep: int >= 0, pinned: [64-hex]}`.
- [ ] Create `src/runtime/tests/unit/test_desired_state.py` (AC: 1, 2, 3)
  - [ ] Valid file → exact `DesiredState` (incl. defaults? No — all four keys required; missing key → `ValueError`. Explicit over implicit for intent files.)
  - [ ] Absent file → `None`, nothing created.
  - [ ] Each malformation → `ValueError`: unparseable, non-object, wrong version, empty wallpaper, negative/non-int keep, non-list pinned, non-hex pin, unknown key, symlinked file.
  - [ ] Model purity: frozen/immutable (mutating raises), zero I/O imports in the touched domain region (covered by layering test).
- [ ] Run `uv run --directory src/runtime pytest tests/unit/test_desired_state.py tests/architecture/test_layering.py` and confirm green

## Dev Notes

### Scope boundary — schema + loader ONLY

Story 4.2 defines and reads intent. It does **NOT** implement:
- Writing `desired.json` from any command (planner/`wallpaper set` scope — p4-3-x)
- `actual-state` projection (p4-2-2)
- Diff engine or planner behavior (Epic 3)
- Any change to `reconcile`, `prune`, `doctor`, or existing commands (nothing consumes the loader yet — dead code by design, wired in p4-3-x)

### Layering (AD-25, locked)

- `DesiredState` in `domain/` (pure); loader in `adapters/` (all FS I/O); no `application/` unit (nothing orchestrates yet — the diff engine will)
- `test_layering.py` is the mechanical gate — run it, do not modify it

### Conventions consumed (do not redefine)

1. `state_root/desired.json` sits beside `current.json`/`history.jsonl` (runtime-owned state dir, AD-5).
2. Fail-loud validation with file+field in the message (repo-wide declarative-config philosophy).
3. Symlink refusal mirrors history/meta policy.
4. Integer bounds via validation, not Typer (loader-level, CLI-agnostic for future daemon use).

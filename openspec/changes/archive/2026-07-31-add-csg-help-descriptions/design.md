## Context

`csg --help` lists all 9 commands with no descriptions, so users cannot tell what each command does without reading source. The command functions live in separate files (`info_cmd.py`, `dump_config_cmd.py`, etc.), registered in `cli/main.py`.

## Goals / Non-Goals

**Goals:**
- Give every `csg` command a short one-line description visible in `csg --help` and `csg <command> --help`.

**Non-Goals:**
- No changes to command behavior, flag layout, or command output beyond help text.
- No docstring-driven help refactor.

## Decisions

### D1: Use `help=` at each command registration site in `cli/main.py`

**Choice**: Add `help=` to each `@app.command()`/registration in `main.py` for `generate`, `info`, `dump-config`, `dump-templates`, `install`, `list-backends`, `show`, `uninstall`, `version`.

**Rationale**: The command functions live in separate files; docstrings would require importing or re-wrapping. `help=` is a one-line change at the registration point, visible and hard to lose, and the functions stay focused on implementation rather than CLI presentation.

**Alternatives considered**:
- Docstrings on the command functions: requires re-wrapping/importing; couples presentation to implementation. Rejected.

## Risks / Trade-offs

- None material. Help text is presentation-only; the 9 descriptions are pinned by the verification tasks (run `csg --help` and each `csg <command> --help`).

## Open Questions

None.

# Help Text Display

## Decision

Every `csg` command must have a short, one-line description visible in `csg --help` and `csg <command> --help`.

## Acceptance

- **GIVEN** the user runs `csg --help`
- **THEN** the Commands table lists each command with a non-empty description

- **GIVEN** the user runs `csg <command> --help` for any of: `generate`, `info`, `dump-config`, `dump-templates`, `install`, `list-backends`, `show`, `uninstall`, `version`
- **THEN** the output shows a one-line description below the `Usage:` line

## Chosen approach

Add a `help=` parameter at each command registration site in `main.py`. This is preferred over docstrings because:
- The command functions live in separate files (`info_cmd.py`, etc.) — docstrings would require importing or re-wrapping
- `help=` is a one-line change at the registration point, more visible and harder to lose
- The functions themselves remain focused on implementation, not CLI presentation

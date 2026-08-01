# Help Text Display — Delta

## Why

The hand-written `csg --help` settings-discovery list advertised 4 config strategies while the resolver chain actually has 5 — the `--config` flag (`CliPathStrategy`) was first in priority but absent from the help text. This delta pins the corrected contract.

## MODIFIED Requirements

### Requirement: Every csg command has a one-line description in help output
Each of the 9 `csg` commands — `generate`, `info`, `dump-config`, `dump-templates`, `install`, `list-backends`, `show`, `uninstall`, `version` — SHALL carry a short, one-line description that SHALL appear in the Commands table of `csg --help` and below the Usage line of `csg <command> --help`.

#### Scenario: Root help lists all commands with descriptions
- **WHEN** the user runs `csg --help`
- **THEN** the Commands table lists each of the 9 commands with a non-empty description

#### Scenario: Per-command help shows the description
- **WHEN** the user runs `csg <command> --help` for any of `generate`, `info`, `dump-config`, `dump-templates`, `install`, `list-backends`, `show`, `uninstall`, `version`
- **THEN** the output shows a one-line description below the `Usage:` line

### Requirement: Root help lists all 5 config-discovery strategies
`csg --help` SHALL list the config-discovery strategies in the same order and count as the real resolver chain: `--config` flag, `COLORSCHEME_CONFIG_FILE_PATH` env var, `settings.toml` in CWD or up to 3 parent levels, XDG default, package-bundled defaults (5 steps, highest priority first).

#### Scenario: Root help lists all five strategies
- **WHEN** the user runs `csg --help`
- **THEN** the Settings discovery list contains `1. --config flag` as its first numbered step
- **AND** the list contains exactly 5 numbered steps ending with `5. Package-bundled defaults`
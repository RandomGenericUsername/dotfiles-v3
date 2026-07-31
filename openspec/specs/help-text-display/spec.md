# help-text-display Specification

## Purpose
TBD - created by archiving change add-csg-help-descriptions. Update Purpose after archive.
## Requirements
### Requirement: Every csg command has a one-line description in help output
Each of the 9 `csg` commands — `generate`, `info`, `dump-config`, `dump-templates`, `install`, `list-backends`, `show`, `uninstall`, `version` — SHALL carry a short, one-line description that SHALL appear in the Commands table of `csg --help` and below the Usage line of `csg <command> --help`.

#### Scenario: Root help lists all commands with descriptions
- **WHEN** the user runs `csg --help`
- **THEN** the Commands table lists each of the 9 commands with a non-empty description

#### Scenario: Per-command help shows the description
- **WHEN** the user runs `csg <command> --help` for any of `generate`, `info`, `dump-config`, `dump-templates`, `install`, `list-backends`, `show`, `uninstall`, `version`
- **THEN** the output shows a one-line description below the `Usage:` line


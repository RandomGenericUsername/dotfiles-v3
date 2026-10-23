## ADDED Requirements

### Requirement: The `itr` binary exposes exactly three commands
The module SHALL install a single CLI binary named `itr` whose entry point is `icon_templates_renderer.cli.main:app`. The binary SHALL expose exactly three subcommands — `render`, `list`, and `validate` — and no others. No `version`, `info`, `dump-config`, `dump-templates`, `install`, or `uninstall` command SHALL exist. The app help text SHALL be `Render SVG icon templates with color scheme values`.

#### Scenario: only three commands are available
- **WHEN** `itr --help` is invoked
- **THEN** the listed commands are exactly `render`, `list`, and `validate`
- **AND** the help contains `Render SVG icon templates with color scheme values`

#### Scenario: no sibling-only commands exist
- **WHEN** `itr version`, `itr info`, `itr dump-config`, `itr install`, or `itr uninstall` is invoked
- **THEN** the exit code is non-zero (unknown command)

### Requirement: `render` command surface and flag set
`itr render <yaml_file>` SHALL accept a positional `yaml_file: Path` argument and the options `--icon`, `--unsafe`, `--template-dir`, `--color-scheme`, and `--output-dir`. The command SHALL render SVG icons from templates using a color scheme and SHALL print `Rendered: <path>` for each rendered file followed by a blank line and `<N> icon(s) rendered.`. On any `IconRendererError` it SHALL print `Error: <exc>` to stderr and exit with code 1.

#### Scenario: render prints per-variant lines and a summary
- **WHEN** `itr render icons.yaml` renders two variants
- **THEN** stdout contains `Rendered: <path1>` and `Rendered: <path2>`
- **AND** stdout ends with a blank line followed by `2 icon(s) rendered.`

#### Scenario: render errors surface to stderr with exit 1
- **WHEN** `itr render missing.yaml` is invoked
- **THEN** stderr contains `Error: YAML file not found: <path>`
- **AND** the exit code is 1

### Requirement: `--icon` filters to a single named group
For `render` and `list` and `validate`, supplying `--icon <name>` SHALL restrict the operation to the icon group named `<name>`. If no group with that name exists, the command SHALL exit non-zero with `Icon '<name>' not found in <yaml>` (rendered as `Error: ...` for render/validate, or non-zero exit for list).

#### Scenario: render single icon group
- **WHEN** `itr render icons.yaml --icon battery` is invoked
- **THEN** only the battery group's variants are rendered

#### Scenario: render unknown icon group exits non-zero
- **WHEN** `itr render icons.yaml --icon nonexistent` is invoked
- **THEN** the exit code is non-zero
- **AND** stderr contains `Icon 'nonexistent' not found`

#### Scenario: list unknown icon group exits non-zero
- **WHEN** `itr list icons.yaml --icon nonexistent` is invoked
- **THEN** the exit code is non-zero

### Requirement: `--unsafe` permits unresolved placeholders
`itr render --unsafe` SHALL allow unresolved `{{placeholder}}` tokens to pass through into the output unchanged instead of raising. The `--unsafe` flag SHALL take precedence over the group's `unsafe` setting when truthy; when `--unsafe` is falsy (the default) the group's `unsafe` value SHALL apply.

#### Scenario: unsafe flag overrides group
- **WHEN** `itr render icons.yaml --unsafe` is invoked on a template containing `{{unknown_color}}`
- **THEN** the exit code is zero
- **AND** the output file retains `{{unknown_color}}` verbatim

### Requirement: `list` command surface and output
`itr list <yaml_file>` SHALL accept a positional `yaml_file: Path` plus `--icon` and `--template-dir`. Without `--icon`, it SHALL print each group as `<group>:` followed by `  - <variant>` lines. With `--icon <name>`, it SHALL print `Variants:` followed by `  - <variant>` lines for that group's variants.

#### Scenario: list shows all groups and variants
- **WHEN** `itr list icons.yaml` is invoked on a config with groups `battery` and `network`
- **THEN** stdout contains `battery:` and `network:` and `  - ` lines under each

#### Scenario: list --icon shows only that group's variants
- **WHEN** `itr list icons.yaml --icon battery` is invoked
- **THEN** stdout contains `Variants:` and the battery variant names appear under `  - `
- **AND** stdout does NOT contain `network:`

### Requirement: `validate` command surface and exit semantics
`itr validate <yaml_file>` SHALL accept a positional `yaml_file: Path` plus `--icon`, `--template-dir`, and `--color-scheme`. It SHALL check that the YAML is valid, that each group's color-scheme file exists, and that each variant's template file exists; on the first missing file it SHALL print `Error: <exc>` to stderr and exit non-zero. On success it SHALL print `Validation passed.` and exit zero.

#### Scenario: validate passes on a valid config
- **WHEN** `itr validate icons.yaml` is invoked on a valid config referencing existing files
- **THEN** stdout contains `Validation passed.`

#### Scenario: validate fails on a missing template
- **WHEN** `itr validate broken.yaml` is invoked where a variant's template does not exist
- **THEN** the exit code is non-zero
- **AND** stderr contains `Error: Template not found:`

### Requirement: Plain output is the default and matches v2 verbatim
The default output format SHALL be plain text reproducing the v2 output strings exactly: `Rendered: <path>` per variant, a blank line, then `<N> icon(s) rendered.` for render; `<group>:` and `  - <variant>` lines for list-all; `Variants:` and `  - <name>` lines for list-`--icon`; `Validation passed.` for validate; `Error: <exc>` to stderr on failure. The plain format SHALL be the default even when the sibling `OutputPort`/`cli-output` architecture is adopted.

#### Scenario: render plain output is verbatim
- **WHEN** `itr render icons.yaml` renders two variants to `out/a.svg` and `out/b.svg`
- **THEN** stdout is exactly `Rendered: out/a.svg\nRendered: out/b.svg\n\n2 icon(s) rendered.\n`

#### Scenario: validate plain output is verbatim
- **WHEN** `itr validate icons.yaml` succeeds
- **THEN** stdout is exactly `Validation passed.\n`

### Requirement: Optional output-format, quiet, and verbose global flags
The CLI MAY expose additive global flags `--output-format {plain,json,rich}` (default `plain`), `-q/--quiet`, and `-v/--verbose` (count). These flags SHALL NOT alter default user-facing behavior (plain default matches v2). They are additive and SHALL NOT remove any v2 surface. If this open decision is vetoed, these flags SHALL be omitted and the plain `typer.echo`-style output SHALL be kept.

#### Scenario: default output-format is plain
- **WHEN** `itr render icons.yaml` is invoked without `--output-format`
- **THEN** the output is the plain v2 text

#### Scenario: explicit plain equals default
- **WHEN** `itr render icons.yaml --output-format plain` is invoked
- **THEN** the output equals the default plain output exactly

### Requirement: Composition-root error handling exits non-zero on IconRendererError
Every command SHALL wrap its use-case call in a `try/except IconRendererError` that calls `OutputPort.error(exc)` (producing `Error: <exc>` to stderr) and raises `typer.Exit(code=1)`. No stack trace SHALL be printed for `IconRendererError` subclasses.

#### Scenario: domain error produces a clean stderr line
- **WHEN** any command raises an `IconRendererError` subclass
- **THEN** stderr contains a single `Error: <message>` line
- **AND** no traceback is printed
- **AND** the exit code is 1
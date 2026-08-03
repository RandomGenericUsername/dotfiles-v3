## MODIFIED Requirements

### Requirement: Path precedence is unified (settings-first)
For each of `templates_dir`, `color_scheme`, `output_dir`, the effective root SHALL be resolved with precedence: CLI flag > env (`ICON_RENDERER__…`) > settings.toml field > discovery (templates/color_scheme) / bundled default (output_dir) > error. env SHALL be the single env mechanism (no separate path env var).

#### Scenario: env overrides settings
- **WHEN** `ICON_RENDERER__TEMPLATES__DIR=/env/tpls` is set
- **AND** settings.toml `[templates] dir = "/settings/tpls"`
- **THEN** templates are read from `/env/tpls`

#### Scenario: discovery fallback when settings absent
- **WHEN** settings.toml has no `[templates] dir`
- **AND** no env/flag is set
- **AND** a `templates/` directory exists in a traversed parent
- **THEN** that directory is used as the templates root

#### Scenario: output_dir bundled default
- **WHEN** no flag/env/settings provides `output_dir`
- **THEN** the bundled default `/tmp/icon-templates-renderer` is used

### Requirement: Icons YAML is simplified
The icons YAML SHALL NOT declare top-level `templates_root`/`color_scheme`/`outputs_root`. Per-group `template_dir` and `output_dir` SHALL be relative subpaths under the global root, default `"."`. Per-group `color_scheme` SHALL NOT be declared (one global scheme per render).

#### Scenario: default relative dirs
- **WHEN** a group omits `template_dir` and `output_dir`
- **THEN** templates are read from the global templates root and outputs written to the global output root

#### Scenario: relative subdir
- **WHEN** a group declares `template_dir: sub/`
- **THEN** templates are read from `<templates_root>/sub/`

## REMOVED Requirements

### Requirement: Per-group `color_scheme`
Per-group `color_scheme` is removed; one global scheme per render.

### Requirement: Top-level `templates_root`/`color_scheme`/`outputs_root`
Top-level roots are removed; global roots come from settings/discovery.

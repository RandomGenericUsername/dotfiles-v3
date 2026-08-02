## ADDED Requirements

### Requirement: SVG placeholder token shape
Substitution SHALL recognise placeholders matching the regular expression `\{\{(\w+)\}\}` — i.e. a key of one or more word characters between double curly braces. Every match SHALL be processed as a color-mapping lookup; non-matching text SHALL be left untouched.

#### Scenario: word-character placeholders are matched
- **WHEN** an SVG body `<path fill="{{background}}"/>` is substituted with mappings `{"background": "#1a1a2e"}` and a scheme containing `background`
- **THEN** the result is `<path fill="#1a1a2e"/>`

#### Scenario: non-placeholder text is preserved
- **WHEN** an SVG body `<svg>{{a}} text {{b}}</svg>` is substituted with `{"a": "#111111", "b": "#222222"}`
- **THEN** the result is `<svg>#111111 text #222222</svg>`

### Requirement: Missing mapping raises unless unsafe
When a `{{placeholder}}` key has no entry in the merged color mappings, the substitution SHALL raise `MissingMappingError` with a message of the form `Placeholder '{{{<key>}}}' has no entry in color_mappings`, unless the run is in `unsafe` mode, in which case the placeholder token SHALL be left verbatim in the output.

#### Scenario: missing mapping raises by default
- **WHEN** `<svg>{{unknown_color}}</svg>` is substituted with mappings `{}` and `unsafe=False`
- **THEN** `MissingMappingError` is raised with `Placeholder '{{unknown_color}}' has no entry in color_mappings`

#### Scenario: unsafe leaves an unmapped placeholder verbatim
- **WHEN** `<svg>{{unknown_color}}</svg>` is substituted with mappings `{}` and `unsafe=True`
- **THEN** the result is `<svg>{{unknown_color}}</svg>`

### Requirement: Literal hex values are returned as-is
When a color-mapping value begins with `#`, the substitution SHALL return that value verbatim without consulting the color scheme.

#### Scenario: hex literal bypasses the scheme
- **WHEN** `{{k}}` is substituted with mappings `{"k": "#abcdef"}`
- **THEN** the result is `#abcdef` regardless of the scheme's contents

### Requirement: Scheme-key lookup raises on missing key unless unsafe
When a color-mapping value does not begin with `#`, the substitution SHALL resolve it through the color scheme by key. If the scheme has no such key, the substitution SHALL raise `ColorSchemeKeyNotFoundError` with a message of the form `color_mappings entry for '<key>' references color scheme key '<value>' which does not exist`, unless the run is `unsafe`, in which case the placeholder token SHALL be left verbatim.

#### Scenario: scheme key resolves
- **WHEN** `{{k}}` is substituted with mappings `{"k": "background"}` and a scheme containing `background="#1a1a2e"`
- **THEN** the result is `#1a1a2e`

#### Scenario: unknown scheme key raises by default
- **WHEN** `{{k}}` is substituted with mappings `{"k": "missing_key"}` and a scheme without `missing_key`, `unsafe=False`
- **THEN** `ColorSchemeKeyNotFoundError` is raised naming `missing_key`

#### Scenario: unsafe leaves a missing-scheme-key placeholder verbatim
- **WHEN** `{{k}}` is substituted with mappings `{"k": "missing_key"}` and a scheme without `missing_key`, `unsafe=True`
- **THEN** the result is `{{k}}`

### Requirement: Effective unsafe falls back to the group when the CLI flag is unset
The `unsafe` mode effective for a group SHALL be `request.unsafe` when it is not `None`, otherwise the group's `unsafe` attribute. A falsy CLI `--unsafe` SHALL NOT force non-unsafe when the group declares `unsafe: true`.

#### Scenario: group unsafe true applies when flag is absent
- **WHEN** a group declares `unsafe: true` and `render` is called with `unsafe=None`
- **THEN** unresolved placeholders in that group are left verbatim

#### Scenario: group unsafe true applies when flag is false-y
- **WHEN** a group declares `unsafe: true` and `render` is called with `unsafe` derived from `--unsafe` passed as `False` (i.e. `unsafe or None` yields `None`)
- **THEN** the group's `unsafe: true` still applies

#### Scenario: CLI unsafe true overrides a group unsafe false
- **WHEN** a group declares `unsafe: false` and `--unsafe` is passed
- **THEN** unresolved placeholders are left verbatim for that render run

### Requirement: Template-not-found raises before rendering
The renderer SHALL verify each variant's template file exists before reading it; a missing template SHALL raise `TemplateNotFoundError` with message `Template not found: <path>`.

#### Scenario: missing template raises
- **WHEN** a variant's `template` path does not exist
- **THEN** `TemplateNotFoundError` is raised with `Template not found: <path>`

### Requirement: Output directory and files are created
The renderer SHALL create the variant's output parent directory (and any missing parents) before writing the rendered SVG, and SHALL write the rendered text to the variant's output path using UTF-8.

#### Scenario: output directory is created and file written
- **WHEN** a variant renders to `out/deep/battery-0.svg` and `out/deep/` does not exist
- **THEN** the directory `out/deep/` is created
- **AND** the file `out/deep/battery-0.svg` exists with the substituted SVG content

### Requirement: Render semantics reproduce v2 sequencing
`render` SHALL, for each group: resolve the vocabulary defaults from `yaml_path.parent / "defaults.yaml"` (or an explicit path), load the group's color scheme, create the group's `output_dir` (parents=True, exist_ok=True), then for each variant resolve mappings (variant > group > vocab) and render the variant to its output path. It SHALL return the list of output paths in variant order. When `--icon` is supplied, only that group is processed.

#### Scenario: render produces output paths in order
- **WHEN** `render` runs over a config with two groups each with two variants
- **THEN** the returned paths are in group-then-variant order

#### Scenario: render --icon processes only the named group
- **WHEN** `render(icon="battery")` runs over a config with groups `battery` and `network`
- **THEN** only `battery`'s variants are rendered and returned
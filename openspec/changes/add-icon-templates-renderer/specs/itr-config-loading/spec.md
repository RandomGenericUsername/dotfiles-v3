## ADDED Requirements

### Requirement: Icons YAML config structure
The icons YAML SHALL be a mapping of icon-group keys. It MAY declare top-level optional keys `templates_root`, `color_scheme`, and `outputs_root`. Each icon group SHALL require `color_scheme`, `template_dir`, `output_dir`, and `variants`, and MAY declare `color_mappings` and `unsafe: bool`. Each entry in a group's `variants` SHALL require `name`, `template`, and `output`, and MAY declare `color_mappings`.

#### Scenario: valid icons YAML parses
- **WHEN** a YAML with a group containing all required fields and two variants is loaded
- **THEN** an `IconConfig` with one group and two variants is produced

#### Scenario: missing required group field is rejected
- **WHEN** a group lacks `color_scheme` (or `template_dir` / `output_dir` / `variants`)
- **THEN** `InvalidYamlError` is raised with a message naming the group and the missing field, e.g. `Icon '<name>' is missing required field: 'color_scheme'`

#### Scenario: missing required variant field is rejected
- **WHEN** a variant lacks `name` (or `template` / `output`)
- **THEN** `InvalidYamlError` is raised with a message naming the group, e.g. `A variant in icon '<group>' is missing required field: 'name'`

### Requirement: YAML loader error messages
The loader SHALL raise `InvalidYamlError("YAML file not found: <path>")` when the file is missing, `InvalidYamlError("Failed to parse YAML: <e>")` on a YAML parse error, and `InvalidYamlError("YAML root must be a mapping of icon group keys")` when the root is not a dict. Message strings SHALL match v2 verbatim.

#### Scenario: missing YAML file
- **WHEN** a nonexistent YAML path is loaded
- **THEN** `InvalidYamlError` is raised whose message is `YAML file not found: <path>`

#### Scenario: malformed YAML
- **WHEN** a YAML that fails to parse is loaded
- **THEN** `InvalidYamlError` is raised whose message begins with `Failed to parse YAML:`

#### Scenario: non-mapping YAML root
- **WHEN** a YAML whose root is a list is loaded
- **THEN** `InvalidYamlError` is raised with message `YAML root must be a mapping of icon group keys`

### Requirement: Three-tier path override precedence
For `template_dir`, `output_dir`, and `color_scheme`, paths SHALL be resolved with precedence: CLI override → YAML top-level root → relative to the YAML file's directory. Absolute path strings SHALL be passed through as-is. For `template_dir` and `output_dir`, a CLI override or a top-level root SHALL be joined with the YAML-declared string (e.g. `override / template_dir_str`). For `color_scheme`, a CLI override or a top-level `color_scheme` SHALL replace the whole path (no joining).

#### Scenario: template_dir CLI override joins the declared subdir
- **WHEN** `--template-dir /new/templates` is given and the group declares `template_dir: battery/`
- **THEN** templates are read from `/new/templates/battery/`

#### Scenario: top-level templates_root is used when no override
- **WHEN** the YAML declares `templates_root: /root/tpls` and a group declares `template_dir: battery/`
- **AND** no `--template-dir` is given
- **THEN** templates are read from `/root/tpls/battery/`

#### Scenario: relative template_dir resolves from the YAML location
- **WHEN** a group declares `template_dir: templates/battery/` and no override or root exists
- **THEN** templates are read from `<yaml_dir>/templates/battery/`

#### Scenario: color_scheme override replaces the whole path
- **WHEN** `--color-scheme /new/colors.yaml` is given
- **THEN** the group's declared `color_scheme` is ignored and `/new/colors.yaml` is used regardless of the group's value

#### Scenario: top-level color_scheme is used for all groups
- **WHEN** the YAML declares a top-level `color_scheme: /global/colors.yaml`
- **AND** a group declares `color_scheme: /ignored/ignored.yaml`
- **THEN** `/global/colors.yaml` is used for that group

#### Scenario: output_dir override joins the declared subdir
- **WHEN** `--output-dir /new/out` is given and the group declares `output_dir: battery/`
- **THEN** outputs are written under `/new/out/battery/`

#### Scenario: absolute paths pass through
- **WHEN** a group declares an absolute `template_dir: /abs/battery/`
- **THEN** templates are read from `/abs/battery/` regardless of the YAML directory

### Requirement: Color scheme loader dispatches by suffix and indexes colors
The color-scheme loader SHALL load `.yaml`/`.yml` files by reading `special.background`, `special.foreground`, `special.cursor`, and a `colors` list, indexing list entries as `color0`, `color1`, … `colorN`. It SHALL load `.json` files by reading `special` and a `colors` object, preserving the object's keys as-is (no re-indexing). Any other suffix SHALL raise `ColorSchemeNotFoundError` with message `Unsupported color scheme format: <suffix>. Use .yaml or .json`. A missing file SHALL raise `ColorSchemeNotFoundError` with message `Color scheme file not found: <path>`.

#### Scenario: yaml color scheme list becomes colorN
- **WHEN** `colors.yaml` with `special: {background: "#1a1a2e", foreground: "#e0e0e0"}` and `colors: ["#1a1a2e", "#e94560"]` is loaded
- **THEN** the scheme exposes `background="#1a1a2e"`, `foreground="#e0e0e0"`, `color0="#1a1a2e"`, `color1="#e94560"`

#### Scenario: json color scheme dict preserves keys
- **WHEN** `colors.json` with `special: {background: "#aabbcc"}` and `colors: {color5: "#112233", color0: "#aabbcc"}` is loaded
- **THEN** the scheme exposes `background="#aabbcc"`, `color5="#112233"`, `color0="#aabbcc"` (keys preserved, not re-indexed)

#### Scenario: unsupported suffix is rejected
- **WHEN** a file `colors.txt` is loaded
- **THEN** `ColorSchemeNotFoundError` is raised with `Unsupported color scheme format: .txt. Use .yaml or .json`

#### Scenario: missing color scheme file is rejected
- **WHEN** a nonexistent color-scheme path is loaded
- **THEN** `ColorSchemeNotFoundError` is raised with `Color scheme file not found: <path>`

### Requirement: Vocabulary defaults loader
The vocabulary loader SHALL load `defaults.yaml` from the icons YAML's directory (or an explicit path). When the path is absent or `None`, it SHALL return an empty mapping. The file MUST contain a `defaults` mapping; otherwise `InvalidYamlError("Vocabulary file must contain a 'defaults' mapping: <path>")` is raised. A falsy `defaults` SHALL yield an empty mapping. A `defaults` that is not a dict SHALL raise `InvalidYamlError("'defaults' must be a mapping of placeholder names to tokens")`. Keys and values SHALL be coerced to `str`.

#### Scenario: absent defaults yaml yields empty
- **WHEN** no `defaults.yaml` exists next to the icons YAML
- **THEN** the vocabulary defaults are an empty mapping

#### Scenario: defaults mapping is loaded
- **WHEN** `defaults.yaml` containing `defaults: {background: background, foreground: foreground}` is loaded
- **THEN** the vocabulary exposes `{"background": "background", "foreground": "foreground"}`

#### Scenario: missing defaults key is rejected
- **WHEN** `defaults.yaml` is `other: {}` (no `defaults` key)
- **THEN** `InvalidYamlError` is raised with `Vocabulary file must contain a 'defaults' mapping:`

#### Scenario: non-dict defaults is rejected
- **WHEN** `defaults.yaml` is `defaults: ["a", "b"]`
- **THEN** `InvalidYamlError` is raised with `'defaults' must be a mapping of placeholder names to tokens`

### Requirement: Mapping merge priority variant > group > vocab_defaults
When rendering a variant, the effective color mappings SHALL be the merge of vocabulary defaults, the group's `color_mappings`, and the variant's `color_mappings`, in that ascending priority: variant overrides group overrides vocab.

#### Scenario: variant overrides group
- **WHEN** vocab is `{"k": "v0"}`, group mappings is `{"k": "v1", "g": "gv"}`, variant mappings is `{"k": "v2"}`
- **THEN** the merged mappings are `{"k": "v2", "g": "gv"}`

#### Scenario: group overrides vocab
- **WHEN** vocab is `{"k": "v0"}`, group mappings is `{"k": "v1"}`, variant mappings is `{}`
- **THEN** the merged mappings are `{"k": "v1"}`

#### Scenario: vocab fills when neither overrides
- **WHEN** vocab is `{"k": "v0", "x": "x0"}`, group mappings is `{"k": "v1"}`, variant mappings is `{}`
- **THEN** the merged mappings are `{"k": "v1", "x": "x0"}`

### Requirement: load_one by icon name raises IconNotFoundError
The config loader SHALL provide `load_one(yaml_path, icon, overrides)` returning the single `IconGroup` named `icon`; if no group with that name exists, it SHALL raise `IconNotFoundError` with a message of the form `Icon '<name>' not found in <yaml>`.

#### Scenario: unknown icon name raises
- **WHEN** `load_one(yaml, "nonexistent", overrides)` is called
- **THEN** `IconNotFoundError` is raised with `Icon 'nonexistent' not found in <yaml>`
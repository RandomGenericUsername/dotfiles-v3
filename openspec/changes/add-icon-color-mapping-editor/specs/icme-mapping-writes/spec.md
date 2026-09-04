## ADDED Requirements

### Requirement: `itr mapping show` exposes everything the editor needs as JSON
`itr mapping show <yaml_file> [--icon <group>] --json` SHALL emit, for each selected group: its variants, each variant's resolved template path and template SVG body, the merged mapping table per variant with the origin of each entry (`vocabulary`, `group`, or `variant`), the color-scheme token table with hex values, and the list of tokens referenced by mappings but absent from the color scheme. The command SHALL NOT write any file.

#### Scenario: merged mappings carry their origin
- **WHEN** `itr mapping show icons.yaml --icon battery --json` is invoked
- **THEN** each mapping entry reports whether it came from the vocabulary, the group, or the variant

#### Scenario: missing tokens are reported explicitly
- **GIVEN** a mapping references a token absent from the color scheme
- **WHEN** `itr mapping show --json` is invoked
- **THEN** that token appears in the missing-token list rather than causing a non-zero exit

### Requirement: `itr mapping set` performs a single scoped, comment-preserving edit
`itr mapping set <yaml_file> --icon <group> --placeholder <NAME> --token <TOKEN> [--variant <name>]` SHALL set exactly one mapping entry: on the group's `color_mappings` when `--variant` is omitted, or on that variant's `color_mappings` when supplied, creating the `color_mappings` key if absent. All other content of the file — comments, key order, quoting, and indentation — SHALL be preserved byte-for-byte outside the edited entry.

#### Scenario: group-scoped set
- **WHEN** `itr mapping set icons.yaml --icon battery --placeholder COLOR_ACCENT --token color10` is invoked
- **THEN** `battery.color_mappings.COLOR_ACCENT` becomes `color10`
- **AND** every comment and every other key in the file is unchanged

#### Scenario: variant-scoped set creates an override
- **GIVEN** the variant `battery-50-charging` has no `color_mappings`
- **WHEN** `itr mapping set … --variant battery-50-charging --placeholder COLOR_ACCENT --token color10` is invoked
- **THEN** a `color_mappings` block containing only that entry is added to that variant
- **AND** the group mapping is unchanged

#### Scenario: unknown group, variant, or placeholder is rejected
- **WHEN** `itr mapping set` names a group or variant that does not exist
- **THEN** the command exits non-zero with an `IconRendererError` message and writes nothing

### Requirement: `itr mapping set-default` retargets a vocabulary default
`itr mapping set-default <defaults_file> --placeholder <NAME> --token <TOKEN>` SHALL set `defaults.<NAME>` in the vocabulary file, preserving all other content, comments, and ordering. It SHALL support `--dry-run --diff` with the same semantics as `itr mapping set`. It SHALL reject a placeholder name that does not already exist in the vocabulary, and SHALL NOT add or remove placeholder names.

#### Scenario: vocabulary default retargeted
- **WHEN** `itr mapping set-default defaults.yaml --placeholder COLOR_FOREGROUND --token color15` is invoked
- **THEN** `defaults.COLOR_FOREGROUND` becomes `color15`
- **AND** every comment and other entry is unchanged

#### Scenario: unknown placeholder rejected
- **WHEN** the named placeholder is absent from the vocabulary
- **THEN** the command exits non-zero and writes nothing

### Requirement: Vocabulary changes report the groups that shadow them
`itr mapping set-default` SHALL report, on stdout and in its JSON output, every icon group whose `color_mappings` (or whose variants' `color_mappings`) overrides the named placeholder and therefore ignores the new default. Those overrides SHALL NOT be modified. When `--icons <icons.yaml>` is not supplied, the command SHALL resolve the manifest alongside the vocabulary file.

#### Scenario: shadowing groups listed
- **GIVEN** `battery` maps `COLOR_ACCENT` in `icons.yaml`
- **WHEN** `itr mapping set-default … --placeholder COLOR_ACCENT --token color3` is invoked
- **THEN** the output lists `battery` as shadowing the new default
- **AND** `battery.color_mappings.COLOR_ACCENT` is unchanged

### Requirement: `itr mapping set --dry-run` reports the diff without writing
`itr mapping set --dry-run --diff` SHALL print the unified diff the edit would produce and SHALL leave the file untouched.

#### Scenario: dry run leaves the file byte-identical
- **WHEN** `itr mapping set --dry-run --diff …` is invoked
- **THEN** a unified diff of the pending change is printed
- **AND** the file's contents are unchanged

### Requirement: Tokens are validated against the color scheme before writing
`itr mapping set` SHALL reject a `--token` that is neither a literal `#rrggbb` value nor a key of the resolved color scheme, unless `--unsafe` is supplied.

#### Scenario: unknown token rejected
- **WHEN** `--token surface` is supplied and the color scheme has no `surface` key
- **THEN** the command exits non-zero and writes nothing

#### Scenario: literal hex accepted
- **WHEN** `--token "#ff0066"` is supplied
- **THEN** the mapping is written with the literal value

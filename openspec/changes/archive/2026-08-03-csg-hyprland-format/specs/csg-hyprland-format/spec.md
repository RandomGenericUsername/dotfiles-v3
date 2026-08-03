## ADDED Requirements

### Requirement: Hyprland colors.conf output format

`ColorFormat` SHALL include a member `HYPRLAND` with value `"conf"`, so that the template-naming convention produces `defaults/templates/colors.conf.j2` and an output file `colors.conf`. `csg generate` SHALL accept `-f conf` (and `default_formats` containing `"conf"`) and write a Hyprland-compatible `colors.conf`.

The rendered file SHALL contain one variable per line in this order: `$background`, `$foreground`, `$cursor`, `$accent`, then `$color0` through `$color15`. Each value SHALL be `rgb(<hex>)` where `<hex>` is the palette color's hex without a leading `#`. No value SHALL be quoted. No line SHALL end with a semicolon. `$accent` SHALL equal `colors[1]`.

#### Scenario: generate with -f conf writes valid colors.conf

- **WHEN** `csg generate <image> -f conf` is invoked
- **THEN** a file `colors.conf` is written
- **AND** the file contains `$background = rgb(<bg>)` where `<bg>` is the background color hex without `#`
- **AND** the file contains `$color0 = rgb(<c0>)` through `$color15 = rgb(<c15>)` using the 16 palette colors
- **AND** the file contains `$accent = rgb(<c1>)` where `<c1>` is `colors[1]`
- **AND** no value is quoted and no line ends with a semicolon

#### Scenario: default_formats includes conf

- **WHEN** settings `output.default_formats = ["conf"]` and `csg generate <image>` is invoked without `-f`
- **THEN** `colors.conf` is generated
- **AND** no other format files are generated

### Requirement: Hyprland format participates in the templates catalog

The bundled templates directory SHALL include `colors.conf.j2`, making the total bundled format count 9. `csg info` SHALL report `"conf"` in `templates.formats` and `templates.templates_count` SHALL equal 9 for the bundled templates. `csg dump-templates` SHALL copy `colors.conf.j2` alongside the existing bundled templates.

#### Scenario: info reports the ninth format

- **WHEN** `csg info` is run against the bundled templates
- **THEN** `templates.templates_count` equals 9
- **AND** `templates.formats` includes `"conf"`

#### Scenario: dump-templates copies the new template

- **WHEN** `csg dump-templates --output <dir>` is run
- **THEN** `<dir>/colors.conf.j2` exists alongside the other bundled template files

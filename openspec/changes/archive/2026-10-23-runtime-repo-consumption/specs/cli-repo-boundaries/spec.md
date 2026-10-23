# cli-repo-boundaries (delta)

## MODIFIED Requirements

### Requirement: dotfiles-v3 is a consumer, never an importer or vendor

`dotfiles-v3` SHALL consume the six packages and `dotfiles-runtime` as pinned tools and git dependencies. No runtime module SHALL import a CLI package, and after the last slice no in-tree copy of any of the six or the runtime SHALL remain under `src/`.

#### Scenario: the runtime boundary is subprocess-only

- **WHEN** the `dotfiles-runtime` repo is searched for `import` or `from` of `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine` or `oci_runtime`
- **THEN** no match exists

#### Scenario: no in-tree copy remains

- **WHEN** `git ls-files 'src/cli-tools/*' 'src/shared/*' 'src/runtime/*'` is run after the final slice
- **THEN** the output is empty

#### Scenario: the dotfiles tree is not a build context

- **WHEN** a csg or weg image is built after the final slice
- **THEN** the build context is the CLI repo checkout, and no Dockerfile in it contains `src/cli-tools` or `src/shared`

# Icon Color Mapping Editor

Authoring-time GUI for recoloring icon templates by editing `color_mappings`.
Click a shape → pick a palette swatch → save. See
`openspec/changes/add-icon-color-mapping-editor/` for the full specification
and `tests/fixtures/substitution.json` for the preview-fidelity contract.

## Prerequisites

- AGS v3 (`ags` on PATH) with GTK4.
- `itr` on PATH (build `src/cli-tools/icon-templates-renderer`).
- A provisioned checkout: icon templates under
  `dotfiles/assets/icon-templates/`, mappings in
  `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`, and a
  generated palette (default
  `~/.local/share/dotfiles/generated/palettes/colors.yaml`).

## Launch

```sh
make run
```

This tool edits **repo sources** (`icons.yaml`, `defaults.yaml`). It is not
provisioned to machines and never touches `generated/` or runs `itr render`;
rendered icons refresh on the next wallpaper/theme run as usual.

## Editing flow

Picks never write to disk. They accumulate in a pending set (keyed by group,
variant-or-null, placeholder) with a live YAML diff sourced from
`itr mapping set --dry-run --diff`. **Save mappings** applies each edit
through `itr mapping set` / `set-default` and reloads; a failed save keeps
the pending edits. **Revert** discards them. Saving is blocked when
`icons.yaml` or `defaults.yaml` changed on disk since load — reload first.

Scopes: *Whole group* writes `<group>.color_mappings` (default),
*This variant only* adds a `variants[].color_mappings` override, *All icons*
retargets `defaults.yaml` and names the groups shadowing the placeholder.

## Testing

- `make lint` — bundles the app (fails on syntax errors).
- `make test` — runs the substitution contract: every fixture in
  `tests/fixtures/substitution.json` must render identically in
  `lib/substitute.ts` and in ITR's `PlaceholderSubstitutionService`
  (the Python half lives in
  `src/cli-tools/icon-templates-renderer/tests/unit/domain/test_substitution_agreement.py`).

Known divergence: Python `\w` matches Unicode word characters while the
TypeScript `/\w/` is ASCII-only. Placeholder names are `COLOR_*` ASCII by
vocabulary convention, so the contract holds for all real inputs.

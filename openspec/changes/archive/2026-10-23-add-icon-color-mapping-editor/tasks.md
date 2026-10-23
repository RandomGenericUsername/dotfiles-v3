## 1. ITR: mapping read surface

- [x] 1.1 `domain/models.py` — frozen `MappingEntry(placeholder, token, origin)` with `MappingOrigin` enum (`VOCABULARY`/`GROUP`/`VARIANT`), `VariantMappingView(variant, template_path, svg_body, entries)`, `MappingShowRequest`/`MappingShowResult` (groups, palette table, missing tokens)
- [x] 1.2 `domain/services.py` — extend `MappingResolutionService` with `merge_with_origin(vocab, group, variant) -> tuple[MappingEntry, ...]`; unit-test precedence and origin attribution
- [x] 1.3 `ports/icon_renderer.py` — add `mapping_show(request) -> MappingShowResult`; update port-contract tests
- [x] 1.4 `adapters/icon_renderer.py` — implement `mapping_show`: load config + vocabulary + scheme, read template bodies, collect tokens referenced but absent from the scheme (never raise for missing tokens), and per placeholder the list of groups that override it (shadow set)
- [x] 1.5 `adapters/output/projectors.py` + `{plain,json}_output.py` — project `MappingShowResult`; JSON is the GUI contract
- [x] 1.6 `cli/mapping.py` — `itr mapping show <yaml_file> [--icon] [--template-dir] [--color-scheme]`; register the `mapping` Typer sub-app in `cli/main.py`
- [x] 1.7 Integration tests: origin attribution, missing-token list, template bodies present, exit 0 with unresolvable tokens

## 2. ITR: mapping write surface

- [x] 2.1 Add `ruamel.yaml` to `pyproject.toml`; `uv sync`
- [x] 2.2 `ports/mapping_writer.py` — `MappingWriterPort`: `set_mapping(yaml_path, group, variant|None, placeholder, token) -> str` (returns new document text), `diff(yaml_path, new_text) -> str`
- [x] 2.3 `adapters/ruamel_mapping_writer.py` — round-trip loader with `preserve_quotes`, indent inferred from the file; create `color_mappings` when absent; raise `IconNotFoundError`/`VariantNotFoundError` for unknown targets
- [x] 2.4 `domain/exceptions.py` — add `VariantNotFoundError`, `UnknownTokenError` (message style matching existing errors)
- [x] 2.5 Token validation: literal `^#[0-9a-fA-F]{6}$` passthrough, else must be a key of the resolved scheme unless `--unsafe`
- [x] 2.6 `cli/mapping.py` — `itr mapping set … [--variant] [--dry-run] [--diff] [--unsafe]`; atomic write (temp file + replace)
- [x] 2.7 `itr mapping set-default <defaults.yaml> --placeholder --token [--icons] [--dry-run] [--diff]` — same writer against the vocabulary file; reject unknown placeholder names; never add or remove names; report shadowing groups (plain + JSON)
- [x] 2.8 Round-trip tests: comments, key order, quoting, indentation preserved; group set; variant override creation; vocabulary set; shadow report correctness; dry-run byte-identical; unknown group/variant/placeholder/token rejected with no write
- [x] 2.9 `make check` green in `src/cli-tools/icon-templates-renderer`

## 3. GUI scaffold

- [x] 3.1 Create `src/gui-tools/icon-color-mapping-editor/` (`app.tsx`, `style.css`, `ui/`, `lib/`, `README.md`) and a `Makefile` with `run`/`lint`
- [x] 3.2 `lib/itr.ts` — spawn `itr mapping show --json` / `itr mapping set` via Gio subprocess, typed results, error surfacing
- [x] 3.3 `lib/model.ts` — session state: loaded groups, selection, scope, pending-edit set keyed by (group, variant|null, placeholder)
- [x] 3.4 `lib/substitute.ts` — display-only `{{NAME}}` substitution mirroring `PlaceholderSubstitutionService` (literal `#` passthrough, unresolved marker)
- [x] 3.5 Shared fixture set + test asserting `substitute.ts` and the Python service agree on every fixture

## 4. GUI: preview and hit-testing

- [x] 4.1 `ui/Preview.tsx` — render every variant of the group, selected variant enlarged, siblings as thumbnails
- [x] 4.1a Whole-group toggle in the canvas bar (default on) switching to a single-variant view without touching selection, scope, or pending edits
- [x] 4.1b Override marker on thumbnails whose variant has an on-disk or pending variant-scoped `color_mappings` entry
- [x] 4.1c Canvas bar shows the active variant's template path
- [x] 4.2 Assign each shape a unique ID color; render an offscreen ID pass; map click coordinates → shape via pixel readback
- [x] 4.3 Hover highlight and selection outline on the visible pass
- [x] 4.4 Unresolved fill (hatch) for placeholders with no mapping or a missing token
- [x] 4.5 Backdrop toggle (neutral default / bar background), backdrop never alters rendered colors
- [x] 4.6 Re-render all variants on every pending-edit change

## 5. GUI: selection, picker, scope

- [x] 5.1 `ui/InputsPanel.tsx` — three inputs with resolved paths and read-only/writable labels
- [x] 5.1a Picker per input row that reloads the session from the new path, clears selection and pending edits; pickers disabled while pending edits exist
- [x] 5.1b Launch defaults: `dotfiles/assets/icon-templates/`, `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (+ `defaults.yaml` alongside), `~/.local/share/dotfiles/generated/palettes/colors.yaml`
- [x] 5.2 `ui/GroupTree.tsx` — groups and variants; selecting a variant enlarges it in the preview
- [x] 5.2a Selecting a group loads it into the preview pane; selecting a variant (tree or thumbnail) clears the shape selection
- [x] 5.3 `ui/SelectionPanel.tsx` — shape, `{{PLACEHOLDER}}`, current token + hex, "N shapes across M variants", keyboard-accessible shape list
- [x] 5.3a No hardcoded constants: all counts/lists (affected variants/groups, shadowers, usage, tokens) derive from `mapping show` output + pending edits
- [x] 5.4 `ui/TokenPicker.tsx` — all scheme tokens as swatches; absent tokens disabled with `not in colors.yaml`; dynamic heading; disabled state when nothing is selected
- [x] 5.4a Indexed grid (`color0`–`color15`) above named-token rows, stable order; palette tokens only, no free-form literal entry
- [x] 5.5 `ui/ScopeSwitch.tsx` — `This variant only` / `Whole group` (default) / `All icons`, each with its blast-radius sentence and target file+key
- [x] 5.5b Scope hints use the pinned copy templates from `icme-ui`; usage count shows variants actually using the placeholder
- [x] 5.5a `All icons` scope: list the shadowing groups from `mapping show`, and warn when the previewed group is among them (the edit will not change what is on screen)
- [x] 5.6 Apply a pick to the pending-edit set (never to disk)

## 6. GUI: pending edits, diff, save

- [x] 6.1 `ui/DiffPane.tsx` — YAML diff of pending edits, sourced from `itr mapping set --dry-run --diff`
- [x] 6.2 `Save` — apply each pending edit through `itr mapping set` / `itr mapping set-default`, then reload from `itr mapping show`; surface any failure without losing pending state; never trigger a render
- [x] 6.3 `Revert` — clear pending edits and restore previews
- [x] 6.4 Guard against saving when `icons.yaml` or `defaults.yaml` changed on disk since load (mtime check, warn and offer reload)
- [x] 6.5 Surface `itr`/filesystem failures in the GUI without losing state: unreadable picker choice keeps the session, failed save retains pending edits

## 7. Verification and docs

- [ ] 7.1 Manual pass against the real battery group: click each shape, retarget `COLOR_ACCENT` group-wide, verify all four variants change, save, `itr render`, confirm generated SVGs match the preview
- [ ] 7.2 Variant-override pass: same placeholder, variant scope, confirm only that variant changes after render
- [ ] 7.3 Vocabulary pass: `All icons` scope on a placeholder no group overrides, confirm every group changes after render; repeat on a shadowed placeholder and confirm the warning was accurate
- [x] 7.4 `docs/Adding an Icon — ITR and Provisioning Pipeline.md` — document the editor as the recommended recoloring path and the `itr mapping` commands
- [x] 7.5 `README.md` in the tool folder: prerequisites, launch command, explicit note that it edits the spine's seeded `icon-mappings/` (machine-owned), is provisioned as `ags-icme` + launcher bin, and that rendered icons refresh on the next wallpaper/theme run
- [x] 7.6 Layout pass against `mock.html`: three regions, uniform grid with bordered active card, state affordances, heading copy, pinned footer — modulo the divergences listed in `design.md` (hatch, no preselection, mock-only copy)

## 8. Deployment: provision the editor, seed-once mappings, tool upgrade

- [x] 8.1 `lib/inputs.ts` defaults retargeted to the spine (`~/.local/share/dotfiles/icon-mappings/icons.yaml`, spine `icon-templates/`), `ICME_*` env overrides kept
- [x] 8.2 gui_tools role: deploy the app files into `config/ags-icme/` (raw per-file copy — Jinja2 would eat `{{PLACEHOLDER}}` literals), config-links entry for `ags-icme`
- [x] 8.3 cli_tools role: `icon-color-mapping-editor` launcher bin (`ags run -d ~/.config/ags-icme`), plus `uv tool install --force` upgrade task so already-provisioned machines re-pin csg/weg/itr on every bootstrap
- [x] 8.4 assets role: `icon-mappings` **converge** (reverted same-day from a seed-once experiment that broke "edit repo, bootstrap, deployed") — bootstrap propagates repo mapping edits on every run
- [x] 8.5 `SUPER+I` keybind → `icon-color-mapping-editor`
- [x] 8.6 Structural tests updated: assets parity (converge restored), gui_tools icme file list, cli_tools upgrade locks
- [x] 8.7 Spec/docs updated: D1 + context (repo-authoritative authoring), proposal non-goals, icme-ui defaults scenario, README, pipeline doc §4.2
- [x] 8.8 Launcher is a provisioned template (`cli_tools/templates/icon-color-mapping-editor.j2`): checkout path baked in at deploy time, `cd`s into the checkout when present (repo-authoritative authoring), spine fallback otherwise

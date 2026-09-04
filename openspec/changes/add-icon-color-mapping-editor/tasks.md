## 1. ITR: mapping read surface

- [ ] 1.1 `domain/models.py` — frozen `MappingEntry(placeholder, token, origin)` with `MappingOrigin` enum (`VOCABULARY`/`GROUP`/`VARIANT`), `VariantMappingView(variant, template_path, svg_body, entries)`, `MappingShowRequest`/`MappingShowResult` (groups, palette table, missing tokens)
- [ ] 1.2 `domain/services.py` — extend `MappingResolutionService` with `merge_with_origin(vocab, group, variant) -> tuple[MappingEntry, ...]`; unit-test precedence and origin attribution
- [ ] 1.3 `ports/icon_renderer.py` — add `mapping_show(request) -> MappingShowResult`; update port-contract tests
- [ ] 1.4 `adapters/icon_renderer.py` — implement `mapping_show`: load config + vocabulary + scheme, read template bodies, collect tokens referenced but absent from the scheme (never raise for missing tokens)
- [ ] 1.5 `adapters/output/projectors.py` + `{plain,json}_output.py` — project `MappingShowResult`; JSON is the GUI contract
- [ ] 1.6 `cli/mapping.py` — `itr mapping show <yaml_file> [--icon] [--template-dir] [--color-scheme]`; register the `mapping` Typer sub-app in `cli/main.py`
- [ ] 1.7 Integration tests: origin attribution, missing-token list, template bodies present, exit 0 with unresolvable tokens

## 2. ITR: mapping write surface

- [ ] 2.1 Add `ruamel.yaml` to `pyproject.toml`; `uv sync`
- [ ] 2.2 `ports/mapping_writer.py` — `MappingWriterPort`: `set_mapping(yaml_path, group, variant|None, placeholder, token) -> str` (returns new document text), `diff(yaml_path, new_text) -> str`
- [ ] 2.3 `adapters/ruamel_mapping_writer.py` — round-trip loader with `preserve_quotes`, indent inferred from the file; create `color_mappings` when absent; raise `IconNotFoundError`/`VariantNotFoundError` for unknown targets
- [ ] 2.4 `domain/exceptions.py` — add `VariantNotFoundError`, `UnknownTokenError` (message style matching existing errors)
- [ ] 2.5 Token validation: literal `^#[0-9a-fA-F]{6}$` passthrough, else must be a key of the resolved scheme unless `--unsafe`
- [ ] 2.6 `cli/mapping.py` — `itr mapping set … [--variant] [--dry-run] [--diff] [--unsafe]`; atomic write (temp file + replace)
- [ ] 2.7 Round-trip tests: comments, key order, quoting, indentation preserved; group set; variant override creation; dry-run byte-identical; unknown group/variant/token rejected with no write
- [ ] 2.8 `make check` green in `src/cli-tools/icon-templates-renderer`

## 3. GUI scaffold

- [ ] 3.1 Create `src/gui-tools/icon-color-mapping-editor/` (`app.tsx`, `style.css`, `ui/`, `lib/`, `README.md`) and a `Makefile` with `run`/`lint`
- [ ] 3.2 `lib/itr.ts` — spawn `itr mapping show --json` / `itr mapping set` via Gio subprocess, typed results, error surfacing
- [ ] 3.3 `lib/model.ts` — session state: loaded groups, selection, scope, pending-edit set keyed by (group, variant|null, placeholder)
- [ ] 3.4 `lib/substitute.ts` — display-only `{{NAME}}` substitution mirroring `PlaceholderSubstitutionService` (literal `#` passthrough, unresolved marker)
- [ ] 3.5 Shared fixture set + test asserting `substitute.ts` and the Python service agree on every fixture

## 4. GUI: preview and hit-testing

- [ ] 4.1 `ui/Preview.tsx` — render every variant of the group, selected variant enlarged, siblings as thumbnails
- [ ] 4.2 Assign each shape a unique ID color; render an offscreen ID pass; map click coordinates → shape via pixel readback
- [ ] 4.3 Hover highlight and selection outline on the visible pass
- [ ] 4.4 Unresolved fill (hatch) for placeholders with no mapping or a missing token
- [ ] 4.5 Backdrop toggle (neutral / bar background)
- [ ] 4.6 Re-render all variants on every pending-edit change

## 5. GUI: selection, picker, scope

- [ ] 5.1 `ui/InputsPanel.tsx` — three inputs with resolved paths and read-only/writable labels
- [ ] 5.2 `ui/GroupTree.tsx` — groups and variants; selecting a variant enlarges it in the preview
- [ ] 5.3 `ui/SelectionPanel.tsx` — shape, `{{PLACEHOLDER}}`, current token + hex, "N shapes across M variants", keyboard-accessible shape list
- [ ] 5.4 `ui/TokenPicker.tsx` — all scheme tokens as swatches; absent tokens disabled with `not in colors.yaml`; dynamic heading; disabled state when nothing is selected
- [ ] 5.5 `ui/ScopeSwitch.tsx` — `Whole group` (default) / `This variant only` with the blast-radius sentence
- [ ] 5.6 Apply a pick to the pending-edit set (never to disk)

## 6. GUI: pending edits, diff, save

- [ ] 6.1 `ui/DiffPane.tsx` — YAML diff of pending edits, sourced from `itr mapping set --dry-run --diff`
- [ ] 6.2 `Save` — apply each pending edit through `itr mapping set`, then reload from `itr mapping show`; surface any failure without losing pending state
- [ ] 6.3 `Revert` — clear pending edits and restore previews
- [ ] 6.4 Guard against saving when the manifest changed on disk since load (mtime check, warn and offer reload)

## 7. Verification and docs

- [ ] 7.1 Manual pass against the real battery group: click each shape, retarget `COLOR_ACCENT` group-wide, verify all four variants change, save, `itr render`, confirm generated SVGs match the preview
- [ ] 7.2 Variant-override pass: same placeholder, variant scope, confirm only that variant changes after render
- [ ] 7.3 `docs/Adding an Icon — ITR and Provisioning Pipeline.md` — document the editor as the recommended recoloring path and the `itr mapping` commands
- [ ] 7.4 `README.md` in the tool folder: prerequisites, launch command, explicit note that it edits repo sources and is not provisioned

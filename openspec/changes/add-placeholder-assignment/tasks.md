# Tasks: add-placeholder-assignment

## 1. ITR: template analysis surface

- [x] 1.1 Domain: `TemplateShape` (id, tag, paint_attr, paint_value: placeholder name or literal), `TemplateAnalysis` (mode: templated/bare, shapes); extraction reuses the root-inheritance rules from the GUI extractor (root `fill`/`stroke` fall back before the "missing fill paints black" default)
- [x] 1.2 Port `TemplateReaderPort` + adapter reading raw file bytes (no XML round-trip); `analyze` projection for plain output
- [x] 1.3 CLI `itr template analyze <file> [--json]` with structured output parity tests (real templates: battery fill-based, power-menu stroke-based, a synthetic bare file)
- [x] 1.4 Integration test: bare classification on a hex-only file; templated classification on a mixed file

## 2. ITR: template write surface

- [x] 2.1 Port `TemplateWriterPort`; adapter performing single-shape paint-attribute rewrites via exact substring replacement, byte-preserving outside the edit, atomic write (temp file + rename)
- [x] 2.2 Name validation `[A-Z][A-Z0-9_]*` in the domain (shared constant with the GUI); unknown shape id / missing paint attribute / invalid name → typed errors, no write
- [x] 2.3 CLI `itr template set-placeholder <file> --shape <id> --name <NAME>`
- [x] 2.4 Unit tests: re-place placeholder among siblings (shapes 1–3 same placeholder, only one changes); bare hex → placeholder; stroke-painted shapes; comments/attrs preserved byte-for-byte; failure cases leave file untouched
- [x] 2.5 Round-trip test over all real templates in `dotfiles/assets/icon-templates/`: analyze → write → analyze reports the new placeholder and unchanged everything else

## 3. GUI: Templates tab

- [x] 3.1 `lib/templates.ts`: analyze/assignment wrappers over the ITR verbs + shape extraction reuse (`extractShapes`, `rewriteWithIdColors` for hit-testing)
- [x] 3.2 Tab bar (Mappings | Templates) with state preserved across switches; Mappings tab embedded unchanged
- [x] 3.3 Template tree (grouped, badged templated/bare) + file input row; center preview of the selected file with ID-color click selection
- [x] 3.4 Selection panel: shape/paint/resolves-to/used-by rows; assignment list (existing placeholders with chip, token, usage, current/new markers); new-placeholder field with inline validation + vocabulary-default mini palette
- [x] 3.5 Pending model: template edits keyed (template_path, shape_id) with old→new; new-placeholder vocabulary pendings; bare-mode progress tracker (assigned N/M)
- [x] 3.6 Diff pane: per-template-file sections with abbreviated per-shape lines + `defaults.yaml` entries; Revert discards both; Save pipeline = template writes → vocabulary defaults → manifest registration (brand-new files only) → mapping writes → reload; stale guard extended to template files (mtime), Reload retains pendings

## 4. Manifest registration for brand-new files

- [x] 4.1 Detect "template file not referenced by any manifest entry"; registration via existing manifest-write verbs (group/variant inference per design D5)
- [x] 4.2 Unit test: new file gains a group+variant entry; referenced files never restructured

## 5. Verification and docs

- [ ] 5.1 Headless parity test: CLI-staged edit vs GUI save pipeline produce identical file bytes
- [ ] 5.2 Manual pass against real templates: re-place one battery-25 shape onto a new `COLOR_COUNTOUR`; onboard a downloaded bare SVG; verify `itr render` output after save; verify bootstrap propagation
- [ ] 5.3 README + pipeline doc: Templates tab section (assignment, new placeholders, bare onboarding, manifest registration)
- [ ] 5.4 Layout pass against `mock.html` (this change folder): tabs, badges, assign panel, progress, diff sections

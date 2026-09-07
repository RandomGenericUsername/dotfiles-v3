## Context

The mapping editor renders shapes and hit-tests them by rewriting each shape's paint attribute to a unique ID color (`lib/svg.ts`: `extractShapes`, `rewriteWithIdColors`). A shape carries either `fill` or `stroke` as its paint attribute — including stroke-painted icons where `fill="none"` is declared on the `<svg>` root and inherited (fixed 2026-09-07). The vocabulary lives in `defaults.yaml` (`defaults:` mapping `COLOR_*` → palette token), group/variant overrides in `icons.yaml`; both are written through `itr mapping set` / `set-default` (comment-preserving ruamel writer).

Template files under `dotfiles/assets/icon-templates/<group>/<variant>/icon.svg` are hand-authored SVGs. A *templated* file contains `{{NAME}}` placeholders in paint attributes; a *bare* file paints with literal hex colors. The mapping editor's spec explicitly forbade template writes — this change adds them as a separate capability with its own CLI surface, keeping the mapping-write invariants intact.

The approved interaction model lives in `mock.html` in this change folder (two tabs; tab 1 embeds the existing editor unchanged).

## Goals / Non-Goals

**Goals**
- Assign an existing placeholder — or create a new one — to exactly one shape of a template file, from the GUI.
- Onboard bare SVGs shape-by-shape, partial onboarding allowed (unassigned shapes keep literal colors).
- New placeholders resolve immediately: assignment picks their vocabulary default in the same interaction.
- Same deferred-write discipline as mappings: pending buffer, live preview, diff pane, save/revert.
- Template file edits touch exactly one attribute of one shape; everything else preserved byte-for-byte.

**Non-Goals**
- No palette writes, no `generated/` writes, no `itr render` from the GUI.
- No free-form SVG editing (path data, geometry, grouping) — paint attributes only.
- No bulk reassignment across files in one action (per-file, per-shape).
- No automatic manifest restructuring for existing groups; registration applies only to a brand-new template file that no manifest entry references.
- No migration of existing templates; nothing changes for files the user doesn't touch.

## Decisions

### D1. One tool, two tabs; the Templates tab edits one file at a time

The editor window gains a tab bar: *Mappings* (existing UI, unchanged) and *Templates*. The Templates tab selects a single template file (tree grouped by the first path segment under the template root, badged `templated`/`bare`), previews it large, and edits its shapes. Group/variant scope does not exist here — blast radius is the file; the mapping *consequences* of a new placeholder are visible in the same pending diff.

Rationale: the mock's model. Placeholder assignment is a file-local operation; a group/variant scope switch would conflate file identity with mapping precedence (which the Mappings tab already owns).
Alternatives: a separate second window (rejected — duplicates input handling and the pending/diff model); weaving template edits into the Mappings tab (rejected — the mock review showed the two intents want different right panels).

### D2. ITR gains a template-write surface: `itr template analyze` and `itr template set-placeholder`

New port `TemplateWriterPort` with a hexagonal adapter (raw string surgery like `RuamelMappingWriter` — no XML parse/serialize round-trip):

- `itr template analyze <file> [--json]` — emits mode (`templated` | `bare`), and per shape: id (document order, same numbering as the GUI extractor), tag, paint attribute (`fill`/`stroke`), and current value (`{{NAME}}` or literal hex). Inherited paint attributes from the `<svg>` root are resolved the same way the GUI extractor does it.
- `itr template set-placeholder <file> --shape <id> --name <NAME>` — rewrites that one shape's paint attribute to `{{NAME}}`. Fails on unknown shape id or invalid name. Preserves every other byte of the file. Works identically on templated files (replaces the old placeholder value) and bare files (replaces the literal hex).

Rationale: the GUI already shells out to `itr mapping` for writes; template writes follow the same pattern so the Python side owns file safety and the GUI stays thin. The name validation lives in ITR (`[A-Z][A-Z0-9_]*`) and is mirrored in the GUI for immediate feedback.
Alternatives: GUI-side file writes (rejected — file safety must live where the mapping writer lives); full XML DOM rewriting (rejected — round-tripping would reformat the file).

### D3. Bare-SVG detection is value-shape, not a marker file

`analyze` classifies a template as `bare` when **no** shape's paint attribute carries a placeholder value. A file is `templated` if at least one shape uses `{{…}}`. Mixed files (some placeholders, some hex) are `templated`; their hex shapes can be assigned like bare ones — the mode only changes the badge and the progress tracker (which counts shapes with placeholders).

Rationale: matches the mock; no side-car state to drift. The badge reflects intent ("bare — assign placeholders") but the operation is identical.

### D4. New placeholders are assigned with their vocabulary default in one interaction

Assigning a brand-new name requires choosing a palette token for it in the same panel interaction. Save emits `itr mapping set-default defaults.yaml --placeholder <NAME> --token <TOKEN> --icons icons.yaml` (the existing verb — shadow reporting included). Until saved, the GUI resolves the pending name through its in-memory vocabulary so the preview shows the chosen color immediately.

Rationale: a placeholder without a mapping renders magenta in `itr render`; forcing the default at creation time makes that state unreachable through the tool. Group/variant-specific mappings for a new placeholder remain available afterwards in the Mappings tab.
Alternatives: create the placeholder unmapped and warn (rejected — the mock's flow picks the token inline and users approved it).

### D5. Manifest registration only for brand-new files

On save, a template file that no `icons.yaml` entry references gets a manifest entry (group inferred from the first path segment; variant from the second, `default` unless the filename differs) — via the existing manifest-write verbs. Files already referenced are never restructured. The GUI surfaces this as a diff section like any other.

Rationale: onboarding a downloaded icon must end with a renderable manifest entry, but the tool must not rewrite manifests for established groups (blast radius).

### D6. Pending model: template edits join the existing pending buffer

Pending keys extend to `(template_path, shape_id)` carrying old value → new name, plus new-placeholder vocabulary pendings (already covered by vocabulary pending keys). The diff pane gains a section per template file with abbreviated per-shape lines. Save runs the pipeline: template writes → vocabulary defaults → manifest registration (when needed) → mapping writes (if any from the other tab) → reload. A failed template write keeps all pendings, exactly like mapping writes.

## Risks / Trade-offs

- **String surgery on SVGs** — same risk class as the YAML writer; mitigated by single-attribute rewrites on the exact element substring, byte-preservation everywhere else, and round-trip tests on real templates.
- **Shape id ↔ document order coupling** — ids shift if the file changes between analyze and write; the save pipeline re-reads and validates before writing (stale-guard applies to template files too, keyed on mtime).
- **Bare onboarding leaves mixed files** — accepted and surfaced (progress N/M); `itr render` treats literal colors as literals, so a partially assigned file renders correctly at every step.

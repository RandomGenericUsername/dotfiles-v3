## Why

The mapping editor (see `add-icon-color-mapping-editor`) can only recolor placeholders that already exist in a template. Two real workflows are still impossible without hand-editing SVG files:

1. **Re-placing a placeholder.** A shape paints with `{{COLOR_FOREGROUND}}` and the user wants it on its own token — e.g. introduce `COLOR_COUNTOUR` for exactly one shape of the unplugged battery icon while the other shapes keep `COLOR_FOREGROUND`. Today that means opening the SVG and editing the attribute by hand.
2. **Onboarding a bare SVG.** The user downloads an icon (real hex colors, no placeholders), drops it into `dotfiles/assets/icon-templates/…`, and then must hand-discover its colors, invent placeholder names, and rewrite attributes — with no preview of what each placeholder will look like.

Both are the same operation: **assign a placeholder to a shape** — picking an existing vocabulary name or creating a new one — and let the tool rewrite the template file.

## What Changes

The `icon-color-mapping-editor` becomes a **two-tab tool**. Tab *Mappings* is the existing editor, unchanged. A new tab *Templates* provides placeholder assignment over one template file at a time:

- **Template tree:** template files under the template root (read from the manifest / template root), each badged **templated** (has `{{…}}` placeholders) or **bare** (no placeholders — real hex colors).
- **Shape assignment:** click a shape in the preview → the panel lists every existing placeholder (with its resolved color, mapping token, and usage count) plus a **new placeholder** field. *Assign* rewrites that shape's paint attribute (`fill` or `stroke`) to `{{NAME}}` — one shape, nothing else in the file touched.
- **New placeholders:** name validated against `[A-Z][A-Z0-9_]*`; assigning a new name also picks its **vocabulary default** (palette token) at the same time, producing a pending `defaults.yaml` entry so the placeholder resolves immediately.
- **Bare-SVG onboarding:** bare templates render with their literal colors and show an `assigned N/M` progress tracker; each shape can be assigned independently, and shapes left untouched keep their literal color — partial onboarding is explicitly allowed.
- **Live preview:** the preview resolves placeholders through the same merged mapping as before (vocabulary — including pending new placeholders — → group → variant), so a newly created placeholder shows its chosen color immediately.
- **Deferred writes:** template edits and new vocabulary entries accumulate in the same pending buffer as mapping edits; the diff pane shows per-shape template lines (`- fill="{{COLOR_FOREGROUND}}"` / `+ fill="{{COLOR_COUNTOUR}}"`) plus `defaults.yaml` entries. Nothing touches disk until *Save*; *Revert* discards.

Save writes, in order: each edited template file (single-attribute rewrites), `defaults.yaml` vocabulary entries for newly created placeholders (via the existing `itr mapping set-default`), and — only for a template file not yet referenced by the manifest — an `icons.yaml` manifest entry.

The interaction model is validated in `mock.html` in this change folder, which this proposal codifies.

## Capabilities

### New Capabilities

- `icme-templates`: template-file writes performed by ITR on the GUI's behalf — shape analysis, single-shape placeholder assignment, bare-SVG detection.

### Modified Capabilities

- `icme-ui`: the editor gains the tabbed layout with the *Templates* tab (selection panel, assignment picker, bare-mode progress, integrated pending diff).

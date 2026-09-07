## Context

The icon pipeline is: `dotfiles/assets/icon-templates/**/icon.svg` (placeholders `{{COLOR_*}}`) + `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml` (per-group and per-variant `color_mappings`) + `defaults.yaml` (vocabulary defaults) + `generated/palettes/colors.yaml` (token → hex) → `itr render` → `generated/icons/*.svg` → AGS reads `icons.json` through `dotfiles/config/ags/lib/icon-registry.ts`.

Substitution is implemented by `PlaceholderSubstitutionService.substitute` (`src/cli-tools/icon-templates-renderer/src/icon_templates_renderer/domain/services.py`): each `{{NAME}}` is looked up in the merged mapping table; a value starting with `#` is a literal, otherwise it is a palette key resolved through `ColorScheme.get`. Mapping precedence is vocabulary defaults → group `color_mappings` → variant `color_mappings`. `FileColorSchemeLoader` turns the `colors:` list into `color0..color15` and keeps top-level scalars (`background`, `foreground`, `cursor`).

Today `defaults.yaml` maps `COLOR_BACKGROUND: surface` and `COLOR_SECONDARY: accent`, but CSG's `colors.yaml.j2` emits only `background`, `foreground`, `cursor`, `colors[0..15]` — those tokens do not exist, so any icon using them fails to render. This change surfaces that gap in the UI but does not fix it.

Provisioning/runtime split matters here: provisioning copies repo assets into `~/.local/share/dotfiles/` and runs the CLI tools to produce `generated/`; runtime reconciles state and never references the checkout. This tool is the *authoring* surface for mappings, and the authoring model is **repo-authoritative** (decision 2026-09-07, reverted from the same-day seed-once experiment): the editor targets the repo manifest whenever a checkout is detectable from the working directory — the provisioned launcher `cd`s into the checkout when it exists — and edits the seeded spine copy on machines without one. Bootstrap converges the manifest on every run, so "edit repo, bootstrap, deployed" simply works; a brief seed-once/machine-owned-manifest model was tried and reverted the same day because it broke that workflow (repo edits silently not propagating). The app itself is fully provisioned (gui_tools role, raw per-file copy into `config/ags-icme/`, own instance, launcher bin, `SUPER+I` keybind); runtime stays repo-free.

## Goals / Non-Goals

**Goals**
- Make "which shape uses which placeholder, mapped to which token, showing which color" visible at a glance.
- One-click recolor by editing `color_mappings`, with the group-wide blast radius visible before saving.
- Preview fidelity: what the GUI shows equals what `itr render` would produce.
- Comment- and formatting-preserving writes to `icons.yaml`.

**Non-Goals**
- No SVG template writes, no palette writes, no `generated/` writes, no runtime/bar integration.
- No new placeholder *names* in the vocabulary (values may be retargeted), no fix for the missing `surface`/`accent`/`accent-muted` tokens.
- No re-render or re-provision after saving; the generated icons refresh on the next wallpaper/theme run.

## Decisions

### D1. Identity and location: `src/gui-tools/icon-color-mapping-editor/`, provisioned as its own AGS instance

Development lives in `src/gui-tools/icon-color-mapping-editor/` (AGS GTK4/astal, TypeScript: `app.tsx`, `style.css`, `ui/`, `lib/`). Provisioning deploys it like any standalone GUI app: the gui_tools role copies the app files into `<install>/config/ags-icme/` (RAW per-file `ansible.builtin.copy`, never `template` — the sources contain literal `{{PLACEHOLDER}}` sequences that Jinja2 would evaluate), config-links symlinks `~/.config/ags-icme`, and the cli_tools role installs a launcher bin `icon-color-mapping-editor` (`ags run -d ~/.config/ags-icme`) plus a `SUPER+I` keybind. It is not registered in the bar's `app.tsx` and not autostarted — launch-on-demand.

Rationale (updated 2026-09-07): the app is provisioned like any standalone GUI app (repo-authoritative code with `force: true`, capture-tool deploy shape); the DATA it edits is repo-authoritative when a checkout exists on the machine — the launcher bakes the checkout path at provision time and `cd`s into it — falling back to the spine's seeded copy otherwise. Runtime never needs the repo either way.
Alternatives: repo-only launcher pointing at the checkout (rejected — contradicts the deployability requirement); a window inside the runtime AGS instance (rejected — couples authoring to the bar process); a separate GTK4 Python app (rejected — user asked for AGS, and AGS is already a project dependency).

### D2. Semantics: the tool edits mappings, never templates (option B)

Selecting a shape selects the *placeholder* that shape uses; picking a swatch changes what that placeholder resolves to. The SVG template is never modified.

Rationale: it is the only semantics that reaches every palette color with today's four-name vocabulary. Editing the template instead (option A) can only cycle between placeholders that already exist, and would require adding a `COLOR_0..COLOR_15` vocabulary to `defaults.yaml` to reach arbitrary colors. Chosen by the user after both were mocked.
Consequence: a change is never "this one shape" — it is at least "every shape in this variant that uses this placeholder", hence D3 and D4.

### D3. Three edit scopes, ordered by blast radius

- *This variant only* writes `<group>.variants[name=<variant>].color_mappings.<PLACEHOLDER>` in `icons.yaml` — highest precedence, narrowest effect.
- *Whole group* (default) writes `<group>.color_mappings.<PLACEHOLDER>` in `icons.yaml`.
- *All icons* writes `defaults.<PLACEHOLDER>` in `defaults.yaml` — the vocabulary default, lowest precedence, affecting every group that does not override the placeholder.

The panel always states the blast radius in words before the pick ("affects all 4 variants", "affects 9 groups"). Group is the default because a group mapping is the normal authoring intent.

The vocabulary scope has a trap worth designing against: because it is the *lowest* precedence, an edit to `defaults.COLOR_ACCENT` has no visible effect on `battery`, which overrides it. The panel therefore names the shadowing groups before the pick, and if the currently previewed group is among them, the picker warns that the change will not affect what is on screen. Alternative considered: silently deleting the shadowing group overrides so the vocabulary edit "wins" — rejected as destructive and surprising.

### D3a. `defaults.yaml` is the second writable file

`defaults.yaml` joins `icons.yaml` as writable, reached only through the *All icons* scope, through the same comment-preserving writer (D5). Everything else about it is unchanged: it is loaded by the existing `VocabularyLoaderPort`, and the tool never adds or removes placeholder names — it only retargets the token an existing name maps to.

### D4. Preview shows every variant of the group, live

The center pane renders the whole group (the selected variant enlarged, siblings as thumbnails), re-rendered on every pending edit. Rationale: D2 makes group-wide recoloring the common case; showing one variant would hide the effect. A "bar background" toggle switches the preview backdrop so contrast against the actual bar can be judged.

### D5. Python owns YAML in both directions; the GUI is a pure view

GJS has no YAML support, and hand-rolling one in TypeScript would risk destroying comments and key order in a hand-maintained config. Instead `itr` gains a read-only-plus-surgical-write command group and the GUI shells out to it:

- `itr mapping show <icons.yaml> --icon <group> --json` → groups, variants, template paths, per-variant merged mappings (with the origin of each: `vocabulary` | `group` | `variant`), the palette token table with hexes, and the raw template SVG bodies.
- `itr mapping set <icons.yaml> --icon <group> [--variant <name>] --placeholder <NAME> --token <TOKEN>` → a single comment-preserving edit (`ruamel.yaml` round-trip, `preserve_quotes`, indent matched to the file).
- `itr mapping set-default <defaults.yaml> --placeholder <NAME> --token <TOKEN>` → the same single-entry, comment-preserving edit against the vocabulary file, plus a report of the groups that shadow the placeholder.
- `itr mapping set --dry-run --diff` → the unified diff the GUI shows in its pending-changes pane.

Rationale: reuses the existing hexagonal domain (`MappingResolutionService`, loaders) so preview and render can never drift; makes the write path testable without a GUI; keeps the GUI dependency-free. `ruamel.yaml` is added as an ITR dependency for the write path only — `PyYAML` continues to serve the read path.
Alternatives: a JS YAML library in the GUI bundle (rejected — duplicate resolution logic, comment loss); rewriting the whole file with PyYAML (rejected — destroys comments and ordering).

### D6. Preview substitution runs in the GUI, using the same rules

The GUI applies `{{NAME}}` → token → hex to the SVG string it received from `itr mapping show`, mirroring `PlaceholderSubstitutionService`: literal `#…` values pass through, unknown placeholders render as a hatched "unresolved" fill rather than failing. This is display-only; the authoritative substitution stays in ITR, and a contract test asserts the GUI's rule table matches the domain service's behavior on a shared fixture set.

### D7. Click-to-select via an offscreen ID buffer

GTK image widgets offer no hit-testing. Each shape is assigned a unique flat RGB "ID color"; the group is rendered a second time into an offscreen surface with those ID colors, and a click reads the pixel under the cursor to recover the shape. Rationale: exact, handles overlapping and non-rectangular paths, and cheap at these sizes (templates are 1–4 paths). Fallback (also always available): a shape list in the panel with hover highlight, which is the keyboard-accessible path.

### D8. Deferred writes with an explicit diff

Picks mutate an in-memory pending-edit set keyed by (group, variant|null, placeholder). The footer renders the resulting YAML diff; *Save* applies each edit through `itr mapping set` and reloads; *Revert* clears the set. Nothing is written on pick. Rationale: mapping edits are group-wide and easy to regret; the diff is also the artifact the user reviews before committing.

### D9. Unavailable tokens are shown disabled, never hidden

A token referenced by a mapping but absent from `colors.yaml` (today `surface`, `accent`, `accent-muted`) renders greyed with "not in colors.yaml", and a shape whose placeholder resolves to one renders with the unresolved hatch. Rationale: the gap is real and currently silent; hiding it would make the tool lie about what `itr render` will do.

## Risks / Trade-offs

- **AGS/GJS SVG rendering** — preview quality depends on librsvg's handling of the templates; mitigated by rendering the same SVG string ITR would write, and by keeping the ID-buffer pass structurally identical to the visible pass.
- **Shelling out per interaction** — `itr mapping show` runs once per group load, not per click; picks are in-memory. If startup latency is noticeable, the JSON payload can be cached per (icons.yaml mtime, colors.yaml mtime).
- **`ruamel.yaml` as a new dependency** — confined to the new write adapter; the read path is untouched, so existing behavior cannot regress.
- **Two substitution implementations** (D6) — mitigated by the shared-fixture contract test; the GUI copy is display-only and never decides what is written.

## Resolved Questions

- *Should Save run `itr render`?* No. Save is strictly a source edit; the user's flow is edit → set wallpaper, which re-renders through the normal runtime path. A future change may add an opt-in sync.
- *Should the tool edit `defaults.yaml`?* Yes, as the *All icons* scope (D3, D3a), with shadowing groups reported before the pick.

## Visual Reference

`mock.html` in this change folder is authoritative for layout structure and copy (codified in `specs/icme-layout`): three-region arrangement, enlarged main preview with sibling thumbnails, heading strings, and footer order. It is NOT authoritative for behavior details — the specs govern. Deliberate divergences from the mock:

- Unresolvable shapes use the hatched unresolved fill (spec), not the mock's magenta `#ff00ff` shortcut.
- Nothing is preselected on load (the mock preselects `path#3` as a demo convenience); the picker starts inert per `icme-ui`.
- Only the battery group carries real data in the mock (`screen-recorder/play` is inert there); the tool loads every group from `icons.yaml`.
- The top note banner and the explainer hint paragraph are mock-only copy, not required UI text.

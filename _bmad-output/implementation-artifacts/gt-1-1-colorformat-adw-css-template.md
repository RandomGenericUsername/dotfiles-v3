---
baseline_commit: 516f113
---

# Story 1.1: `ColorFormat.ADW_CSS` + `colors.adw.css.j2`

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As a developer,
I want a new csg format `adw.css` mapping the palette to libadwaita named colors,
So that GTK4/libadwaita apps (AGS bar chrome, icme, dialogs) can be recolored from the wallpaper palette.

## Acceptance Criteria

1. **Given** the existing `ColorFormat` enum (`src/color_scheme_generator/domain/enums.py`), **When** `ADW_CSS = "adw.css"` is added as a member (following the dotted-value precedent of `GTK_CSS = "gtk.css"`), **Then** `ColorFormat.ADW_CSS.value == "adw.css"` and `tests/unit/domain/test_enums.py::TestColorFormat::test_members` asserts it; insert after `GTK_CSS` to group the CSS-family formats.

2. **Given** the template catalog derivation (`TemplateCatalogService.derive`, `domain/services.py`) matches `colors.*.j2` stems against `ColorFormat` values, **When** `defaults/templates/colors.adw.css.j2` is created alongside the enum member, **Then** the bundled catalog derives 10 templates (was 9) with no `TemplatesValidationError`, and the rendered output defines the libadwaita named colors per the pinned §5 mapping table (restated in Dev Notes):
   - `window_bg_color`, `view_bg_color`, `headerbar_bg_color`, `card_bg_color`, `dialog_bg_color`, `popover_bg_color`, `sidebar_bg_color` = `background`
   - `window_fg_color`, `view_fg_color`, `headerbar_fg_color`, `card_fg_color`, `sidebar_fg_color` = `foreground`
   - `accent_color`, `accent_bg_color` = `colors[4]` (color_04); `accent_fg_color` = `background`
   - `destructive_color`, `destructive_bg_color` = `colors[8]` (color_08); `destructive_fg_color` = `background`
   - `success_color`/`success_bg_color` = `colors[6]` (color_06); `warning_color`/`warning_bg_color` = `colors[12]` (color_12); `error_color`/`error_bg_color` = `colors[9]` (color_09); all `*_fg_color` variants = `background` — **this concrete slot pin is the proposed resolution of §5's loose "color_06/color_10 + color_12/color_14" wording; confirm hues against a real palette render before review and record the final pin in csg docs (AR-2)**
   - `@define-color color_00` ... `@define-color color_15` passthrough lines (GTK3-compatible custom names, identical to `colors.gtk.css.j2` output) are included

3. **Given** `LocalProcessor._render_formats` derives template name `colors.{fmt.value}.j2` and output path `colors.{fmt.value}` from each requested `ColorFormat`, **When** `csg generate <img> -f adw.css` runs in LOCAL mode, **Then** `colors.adw.css` is written to `request.config.output_dir`.

4. **Given** container mode (`ContainerProcessor` mounts the host-resolved templates dir into the container at `/templates` and forwards each requested format as a repeated `--format <value>` inner-CLI flag), **When** `csg generate <img> -f adw.css` runs with `runtime.mode == container`, **Then** `colors.adw.css` is written to the container output mount with identical bytes to the local render for the same palette — no image rebuild required (templates are bind-mounted, not baked).

5. **Given** the render-contract test precedent `tests/unit/adapters/test_hyprland_format.py`, **When** a mirrored `tests/unit/adapters/test_adw_css_format.py` is written against the bundled templates dir, **Then** it asserts named-color completeness: every name from the AC-2 list appears exactly once as `@define-color <name> <hex>`, the 16 `color_NN` passthrough lines are present, all hex values come from the expected palette slots, and no extra `@define-color` lines exist. Plus a CLI-level assertion that `-f adw.css` produces the file (mirror the smoke-test style of `tests/unit/cli/test_generate.py`).

6. **Given** `csg dump-templates` copies every `*.j2` in the bundled templates dir with zero per-template code, **When** dump-templates runs, **Then** `colors.adw.css.j2` is among the copied templates (extend `tests/unit/cli/test_dump_templates_command.py` coverage).

7. **Given** the mapping table is contract data (AR-2: pinned in csg docs), **When** the story completes, **Then** `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md` is updated: the `ColorFormat` enum inventory row (~line 32) lists `ADW_CSS`, the templates inventory (~line 674, "9 Jinja2 templates...") reflects 10 templates, and the palette-slot-to-named-color mapping table from AC 2 is pinned verbatim there.

## Tasks / Subtasks

- [x] Task 1 — Add the enum member (AC: 1, 2)
  - [x] Edit `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py`: add `ADW_CSS = "adw.css"` to `ColorFormat` after `GTK_CSS = "gtk.css"` (line 35). No other enum touches.
  - [x] Update `tests/unit/domain/test_enums.py::TestColorFormat::test_members` with `assert ColorFormat.ADW_CSS.value == "adw.css"`.
  - [x] WARNING — ordering: the enum member MUST land in the same change as (or before) the template file. `TemplateCatalogService.derive` raises `TemplatesValidationError` on any `colors.*.j2` whose stem is not a `ColorFormat` value (`domain/services.py:94-103`) — adding the template alone breaks every test that loads the bundled catalog.

- [x] Task 2 — Create `colors.adw.css.j2` (AC: 2, 3)
  - [x] Create `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.adw.css.j2`.
  - [x] Render context available in templates (`adapters/jinja_template_renderer.py:54-62`): `background`, `foreground`, `cursor` (each a `Color` with `.hex` including leading `#`, and `.rgb` tuple), `colors` (list of 16 `Color`), `source_image`, `backend`, `generated_at`. Use `{{ background.hex }}` / `{{ colors[4].hex }}` style, mirroring `colors.gtk.css.j2`'s `{% for i in range(16) %}` loop with `{{ '%02d' % i }}`.
  - [x] Template body: the named-color block from the AC-2 pin, then the 16 `@define-color color_NN` passthrough lines (copy that loop verbatim from `colors.gtk.css.j2`).
  - [x] Do NOT add any `sequences`-style binary post-processing — `JinjaTemplateRenderer` special-cases only `*.sequences.j2` (`jinja_template_renderer.py:75`); adw.css renders as plain text with zero renderer changes.
  - [x] Jinja env uses `StrictUndefined` + `trim_blocks=True` + `lstrip_blocks=True` — every referenced variable must exist in the context above; match the gtk.css template's whitespace style.

- [x] Task 3 — Render-contract + CLI tests (AC: 3, 5, 6)
  - [x] Create `tests/unit/adapters/test_adw_css_format.py` mirroring `test_hyprland_format.py`: `_BundledDirResolver` stub + `_bundled_templates_dir` fixture (path `<pkg>/src/color_scheme_generator/defaults/templates`) + deterministic 16-color `_scheme` fixture; render to `tmp_path / "colors.adw.css"` and assert the AC-5 completeness contract (build the expected name-to-slot mapping as a literal dict in the test so template drift fails loudly).
  - [x] Extend CLI coverage in `tests/unit/cli/test_generate.py` (or sibling): invoke generate with `--format adw.css` and assert `colors.adw.css` exists in the output dir.
  - [x] Extend `tests/unit/cli/test_dump_templates_command.py`: assert `colors.adw.css.j2` is among the copied files (command enumerates `bundled.iterdir()` filtered on `.endswith(".j2")` — no code change needed, only test visibility).

- [x] Task 4 — Container + dry-run verification (AC: 4)
  - [x] Confirm `ContainerProcessor` forwards `-f adw.css` unmodified: inner command gets `["--format", fmt.value]` per requested format (`container_processor.py:216-217`) and the resolved templates dir is mounted at `/templates` (`container_processor.py:158-170`, mount at `:201-202`). Assert the planned inner command contains `--format adw.css` if an existing container test exercises format forwarding; otherwise record a manual verification note in completion notes.
  - [x] Confirm dry-run plans the new format: `DryRunProcessor._build_command_plan` echoes `--format <value>` per requested format (`dry_run_processor.py:155-158`) — extend one assertion in `tests/unit/adapters/test_dry_run_processor.py` if a formats-loop assertion exists; no processor code change expected.

- [x] Task 5 — Docs pin (AR-2) + green suite (AC: 7)
  - [x] Update `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md`: ColorFormat enum row (~line 32) gains `ADW_CSS`; templates inventory (~line 674) counts 10 templates and lists `colors.adw.css.j2`; add the pinned mapping table as a short subsection near the templates inventory — this table is the AR-2 contract data (future template edits auto-invalidate runtime cache keys via `canonical_hash_dir`; no action here, just don't reformat the table later).
  - [x] Run the full csg suite green:
    ```bash
    uv run --directory src/cli-tools/color-scheme-generator pytest -q
    uv run --directory src/cli-tools/color-scheme-generator pytest tests/unit/adapters/test_adw_css_format.py -v
    uv run --directory src/cli-tools/color-scheme-generator ruff check .
    uv run --directory src/cli-tools/color-scheme-generator ruff format --check .
    ```
  - [x] Do NOT modify any file outside `src/cli-tools/color-scheme-generator/` — runtime artifact-set growth is gt-2-1; the runtime `CsgAdapter` flag list (`--format yaml --format conf --format gtk.css`) stays 3-artifact until then.

## Dev Notes

### Scope boundary — this story is CSG FORMAT ONLY

Story gt-1-1 adds the `adw.css` format inside csg and nothing else. It does **NOT** implement:

- Runtime `PaletteArtifacts` growth (`colors_adw_css`/`colors_sequences` fields, `meta.json` hashing) — gt-2-1
- `CsgAdapter` requesting `-f adw.css` (still requests yaml/conf/gtk.css only) — gt-2-1
- `IConsumerPathSpec` declarative pointers / `config/gtk-4.0/colors.css` symlink — gt-2-2
- `TerminalColorApplier` reading `colors.sequences` — gt-2-3
- GTK config-in-spine (`config/gtk-{3,4}.0`, `@import "colors.css";` skeletons) — gt-3-1
- AGS/icme style polish — gt-4-1

Resist touching `src/runtime/` entirely. csg is a standalone package with its own suite; runtime consumes it as a black-box binary via `shutil.which("csg")` + subprocess (never `import color_scheme_generator`).

### Verified facts about csg internals (READ BEFORE CODING)

- **Filename derivation is automatic.** `LocalProcessor._render_formats` (`adapters/local_processor.py:82-89`): for each requested `ColorFormat`, template name = `colors.{fmt.value}.j2`, output file = `request.config.output_dir / f"colors.{fmt.value}"`. Adding the enum member + template file is sufficient — no filename mapping exists anywhere else. Precedent: `GTK_CSS = "gtk.css"` already proves dotted values work.
- **Catalog is enum-keyed, not extension-keyed.** `TemplateCatalogService.derive` (`domain/services.py:74-104`) strips the `colors.` prefix and `.j2` suffix, then does `ColorFormat(fmt_key)`; unknown stems raise `TemplatesValidationError`. Consequence: enum member and template file must land together (Task 1 warning).
- **CLI format option.** `cli/main.py:161-162` defines `-f/--format` as a repeatable `list[ColorFormat] | None`. When omitted: `settings.output.default_formats` from `defaults/settings.toml` (= `["json", "sh"]`); only when that setting is empty does the CLI fall back to ALL catalog templates (`main.py:208-220`). **This story therefore does NOT change default `csg generate` output** — the new format is strictly opt-in via `-f adw.css` until a consumer (gt-2-1) requests it. Keep `defaults/settings.toml` untouched.
- **`csg dump-templates` needs zero code change.** `cli/dump_templates_cmd.py:52-54` iterates the bundled dir and copies every `*.j2` via `shutil.copy2`. The new file is picked up automatically.
- **Container mode: templates are bind-mounted, not baked.** `ContainerProcessor` resolves the templates dir host-side (`template_dir_resolver`, falling back to `defaults/templates` next to `settings.toml`, else `/usr/share/color-scheme-generator/templates`) and mounts it at `/templates` (`container_processor.py:158-170`, volume mount `:201-202`). Requested formats become repeated `--format <value>` inner-CLI flags (`:216-217`). AC 4 therefore holds without rebuilding `csg-pywal-*` / `csg-custom-*` images.
- **Dry-run processor is format-agnostic.** `DryRunProcessor._build_command_plan` (`adapters/dry_run_processor.py:155-158`) loops `request.config.formats` and echoes `--format <value>` into the plan string; catalog pre-flight resolves the templates dir (`:74-80`). With template + enum present, dry-run plans the format with no changes.
- **Render env flags that bite:** `StrictUndefined` (any typo'd variable is a hard render error), `trim_blocks`/`lstrip_blocks` (block tags leave no blank lines — write the template like `colors.gtk.css.j2` does), and the `sequences.j2`-only binary post-processing branch (`jinja_template_renderer.py:75-77`) that must NOT trigger for adw.css.

### The §5 mapping table (pinned contract — from `gtk-theming-investigation.md` §5)

| libadwaita named color | palette source |
|---|---|
| `window_bg_color`, `view_bg_color`, `headerbar_bg_color`, `card_bg_color`, `dialog_bg_color`, `popover_bg_color`, `sidebar_bg_color` | `background` |
| `window_fg_color`, `view_fg_color`, `headerbar_fg_color`, `card_fg_color`, `sidebar_fg_color` | `foreground` |
| `accent_color`, `accent_bg_color`, `accent_fg_color` | `color_04` (+ `color_05` alt) |
| `destructive_*` | `color_08`/`color_09` pair |
| `success_*` / `warning_*` / `error_*` | `color_06`/`color_10` + `color_12`/`color_14` mapping, pinned once in the template |
| `@define-color color_00..15` | passthrough (GTK3-compatible custom names stay available) |

The libadwaita override channel is `@define-color` lines consumed from `~/.config/gtk-4.0/gtk.css` (via gt-3-1's `@import "colors.css";` pointing at the runtime's `current/colors.adw.css` symlink, gt-2-2). This story only produces the artifact.

### libadwaita named-color verification (web-checked 2026-09-07)

- Source: libadwaita docs "Named Colors / CSS Variables" — https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/css-variables.html (checked 2026-09-07). All names required by the §5 table exist in current libadwaita: window/view/headerbar/card/dialog/popover/sidebar bg+fg, `accent_color`/`accent_bg_color`/`accent_fg_color`, and the `destructive_*`/`success_*`/`warning_*`/`error_*` triplets (`_color`, `_bg_color`, `_fg_color`).
- **Deliberately out of scope** (gaps are future template edits; cache keys auto-invalidate — investigation §6): backdrop variants (`headerbar_backdrop_color`, `sidebar_backdrop_color` — docs state backdrop colors default to aliases of `window_bg_color`/`sidebar_bg_color` when not overridden, so leaving them unset is safe once the bg colors are defined), `secondary_sidebar_*` (1.4+), `thumbnail_*` (1.3+), `overview_*` (1.7+), per-tone accents (`accent_<tone>_color`), shade/border colors (`*_shade_color`, `*_border_color`, `shade_color`, `scrollbar_outline_color`). If a rendered surface still shows a stock color during gt-4-1 verification, add the missing name to THIS template (an AR-2 documented edit), not to runtime.

### Source tree components to touch

| Path | Action | Notes |
|------|--------|-------|
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py` | **EDIT** | Add `ADW_CSS = "adw.css"` to `ColorFormat` (after `GTK_CSS`, ~line 35). Only change in this file. |
| `src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.adw.css.j2` | **CREATE** | Named-color overrides per §5 pin + 16 `color_NN` passthrough lines (loop copied from `colors.gtk.css.j2`). |
| `src/cli-tools/color-scheme-generator/tests/unit/domain/test_enums.py` | **EDIT** | Assert `ColorFormat.ADW_CSS.value == "adw.css"`. |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_adw_css_format.py` | **CREATE** | Render-contract test (named-color completeness), mirroring `test_hyprland_format.py` fixtures/pattern. |
| `src/cli-tools/color-scheme-generator/tests/unit/cli/test_generate.py` | **EDIT** | Add `-f adw.css` produces `colors.adw.css` assertion. |
| `src/cli-tools/color-scheme-generator/tests/unit/cli/test_dump_templates_command.py` | **EDIT** | Assert the new template is copied. |
| `src/cli-tools/color-scheme-generator/tests/unit/adapters/test_dry_run_processor.py` | **EDIT** (conditional) | Extend a formats-plan assertion if one exists; otherwise skip (no processor change expected). |
| `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md` | **EDIT** | Enum row (~line 32), templates inventory (~line 674), pin the mapping table (AR-2). |
| `src/cli-tools/color-scheme-generator/defaults/templates/colors.gtk.css.j2` | **REFERENCE ONLY** | Copy its `color_NN` loop verbatim; do not edit. |
| `src/cli-tools/color-scheme-generator/defaults/settings.toml` | **LEAVE ALONE** | `default_formats = ["json", "sh"]` stays — new format is opt-in. |
| `src/runtime/**` | **LEAVE ALONE** | Artifact-set growth is gt-2-1. |

### Testing standards summary

- **Runner:** `uv run --directory src/cli-tools/color-scheme-generator pytest -q` — csg has its own suite (`pyproject.toml`: `testpaths=["tests"]`, `pythonpath=["src", "."]`, `addopts=["--strict-markers", "-rxX"]`, dev group `pytest>=9.1.1`). Tests live under `tests/unit/...`; there is no `tests/integration/` in this package — the "integration render test" named in the epic is implemented as the repo's established render-contract test style in `tests/unit/adapters/` (exactly where `test_hyprland_format.py` lives despite its contract nature).
- **Lint:** `ruff check` + `ruff format --check` — `target-version = "py314"`, `line-length = 100`, lint select `E,F,I,N,W,UP,B`, quote-style double. Note: csg's `pyproject.toml` has **no mypy config** (unlike `src/runtime/`) — do not add one in this story.
- **Fixture pattern:** deterministic `ColorScheme` built from literal hex values (see `test_hyprland_format.py::_scheme` — `background=Color("#1a1b26", ...)`, 16-color `colors` tuple); bundled-templates dir resolved by path so the test exercises the REAL shipped template, not a fixture copy.
- **Completeness assertion style:** assert the exact set of `@define-color` names (set equality), each mapped to the expected slot's hex — set-completeness catches both missing names and accidental extras. This is the "named-color completeness" the epic requires.

### Previous story / repo intelligence relevant here

- **rt-1-4 / rt-1-7 (runtime, context only):** runtime invokes csg with `--format yaml --format conf --format gtk.css` and env overrides; cache keys are `sha256(ph‖templates)` where templates hash = `canonical_hash_dir(defaults/templates/)`. Adding a template file **changes every palette cache key** on the runtime side — expected and desired (AR-2 auto-invalidation); gt-2-1 documents existing cache entries becoming misses.
- **csg conventions (git log):** stories commit `feat(...)`/`fix(...)` scoped to the package; keep changes inside `src/cli-tools/color-scheme-generator/` only. Baseline commit for this story: `516f113` ("docs(bmad): GTK theming consumer plan").
- **Template inventory precedent:** the last format addition (`colors.conf.j2` → `ColorFormat.HYPRLAND = "conf"`) followed this exact two-file pattern (enum + template) and got a dedicated render-contract test (`test_hyprland_format.py`) — this story replicates it for adw.css.

### Project Structure Notes

- All work stays under `src/cli-tools/color-scheme-generator/` (own `pyproject.toml`, own tests, own docs). No new directories.
- **Story location override:** `sprint-status.yaml`'s `story_location` field (line 41) points at the MAIN repo path `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3/_bmad-output/implementation-artifacts` — this is stale for the worktree. This story file (and all gt-* stories) live in the WORKTREE copy: `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3-gtk-theming/_bmad-output/implementation-artifacts/`. Correct the `story_location` field in a later housekeeping change.
- Worktree: `feat/gtk-theming-consumer`; the main worktree `dotfiles-repo-v3` must not be touched by this story.

### References

- Epics: `_bmad-output/planning-artifacts/epics-gtk-theming.md` — Epic 1 Story 1.1 ACs (FR-1, AR-2), Epic overview
- Investigation: `_bmad-output/planning-artifacts/gtk-theming-investigation.md` — §1 P1 root cause, §2 csg actor duty ("owns the adw mapping semantics"), §5 mapping table (pinned contract), §6 risks (coverage gaps = future template edits)
- Sprint status: `_bmad-output/implementation-artifacts/sprint-status.yaml` — `gt-1-1-colorformat-adw-css-template` (first backlog story of gt-epic-1)
- csg enum: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py` — `ColorFormat` (9 members)
- csg catalog: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/services.py` — `TemplateCatalogService.derive` (enum-keyed, `TemplatesValidationError` on unknown)
- csg render: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/local_processor.py` (`_render_formats`), `adapters/jinja_template_renderer.py` (context, StrictUndefined, sequences branch)
- csg CLI: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/cli/main.py` (generate `-f` resolution), `cli/dump_templates_cmd.py` (bundled copy loop)
- csg container: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/container_processor.py` (templates mount + format forwarding)
- csg dry-run: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/dry_run_processor.py` (`_build_command_plan` formats loop)
- csg tests: `tests/unit/adapters/test_hyprland_format.py` (render-contract pattern), `tests/unit/domain/test_enums.py`, `tests/unit/cli/test_generate.py`, `tests/unit/cli/test_dump_templates_command.py`, `tests/unit/adapters/test_dry_run_processor.py`
- csg docs: `src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md` (enum row ~line 32, templates inventory ~line 674 — AR-2 pin target)
- libadwaita named colors (web-verified 2026-09-07): https://gnome.pages.gitlab.gnome.org/libadwaita/doc/1-latest/css-variables.html

## Dev Agent Record

### Agent Model Used

opencode-go/glm-5.3-flash (BMad dev-story, DS workflow, worktree `feat/gtk-theming-consumer`)

### Debug Log References

- RED→GREEN confirmed: enum test failed (`AttributeError: no attribute 'ADW_CSS'`) before member added; passed after.
- Full suite: `pytest -q` → **569 passed, 1 failed** — the 1 failure is `tests/unit/adapters/test_template_dir_resolver.py::test_resolve_falls_back_to_package_defaults`, verified PRE-EXISTING at baseline (git stash → identical failure): this machine has `~/.config/color-scheme-generator/templates/` (9 deployed templates from provisioning) which wins the resolver chain before package defaults. Environment-dependent, not caused by this story; unmodified.
- `ruff check .` → 28 errors, ALL pre-existing baseline (verified identical via git stash; none in story-touched files). All 9 story-touched `.py` files pass `ruff check` + `ruff format --check` individually. Package-wide `ruff format --check` shows 49 files with pre-existing drift (baseline condition).
- mypy: not configured in csg `pyproject.toml` (0 matches) — skipped per dev notes.
- Real e2e render: `csg generate <synthetic 64×64 PNG> --backend custom --runtime local --templates-dir <bundled> -f adw.css -o <dir>` → success, `colors.adw.css` written with all 43 `@define-color` lines (27 named + 16 passthrough). Note: user-level deployed templates dir shadows bundled defaults, so `--templates-dir` was needed locally; container/spine deployments need a re-dumped templates set to serve adw.css (gt-2-1 provisioning concern).

### Completion Notes List

- **Final mapping pin (AR-2), confirmed and recorded in template header + `docs/ARCHITECTURE_PLAN.md`:** accent←color_04 (fg←background); destructive←color_08 (fg←background); success←color_06 (fg←background); warning←color_12 (fg←background); error←color_09 (fg←background); 7 bg surfaces←background; 5 fg surfaces←foreground; color_00..15 passthrough identical to `colors.gtk.css.j2`. Real-render evidence (synthetic purple-gradient wallpaper, custom backend): all five pinned slots rendered **distinct valid hex values** (`#4f2571`/`#5f2579`/`#3f4679`/`#405581`/`#305579`), fg/bg pairs resolve to `background`/`foreground` exactly. Caveat recorded in docs: slot hue semantics are positional k-means extraction (wallpaper-dependent), not ANSI-fixed — if a real wallpaper renders a pinned slot visually wrong, edit template + docs table together (cache auto-invalidates).
- **Container mode (AC 4):** format-forwarding contract asserted by new unit test `test_inner_command_forwards_adw_css_format` (fake runtime; inner argv contains `--format adw.css`). Real container exec NOT run here (no spare image rebuild + runtime unavailable in this environment at story time — the default container-mode invocation errored against the stale `csg-custom-latest` image, which is expected: images bake old code, templates are bind-mounted). **Manual verification step for gt-4-1/G1.1:** run `csg generate <img> -f adw.css` with `runtime.mode=container` after images are rebuilt; templates bind-mount at `/templates`, so no image change is required for the template itself.
- **Dry-run (AC 4):** new test asserts the command plan echoes `--format adw.css`; zero processor changes (as predicted by dev notes).
- **Catalog:** bundled catalog now derives 10 templates with `ColorFormat.ADW_CSS` present (`test_derive_from_real_bundled_templates` tightened from `>= 8` to `== 10`).
- **dump-templates:** zero code change (as predicted); first test extended to include the dotted-filename template in the copy assertions.
- **Baseline conditions observed (out of scope, not touched):** 28 pre-existing ruff lint errors; 49 files with pre-existing format drift; 1 env-dependent resolver test failure (above). Suggest a housekeeping story.
- Runtime (`src/runtime/**`) and `defaults/settings.toml` untouched — scope boundary honored.

### File List

- src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py (modified — added `ADW_CSS = "adw.css"`)
- src/cli-tools/color-scheme-generator/src/color_scheme_generator/defaults/templates/colors.adw.css.j2 (new — 27 named-color overrides + 16 passthrough + AR-2 header comment)
- src/cli-tools/color-scheme-generator/tests/unit/domain/test_enums.py (modified — ADW_CSS assertion)
- src/cli-tools/color-scheme-generator/tests/unit/domain/test_services.py (modified — bundled catalog == 10 + ADW_CSS)
- src/cli-tools/color-scheme-generator/tests/unit/adapters/test_adw_css_format.py (new — render-contract: named-color completeness, no-extras, passthrough≡gtk.css, hex validity)
- src/cli-tools/color-scheme-generator/tests/unit/cli/test_generate.py (modified — `-f adw.css` CLI test)
- src/cli-tools/color-scheme-generator/tests/unit/cli/test_dump_templates_command.py (modified — adw template copied)
- src/cli-tools/color-scheme-generator/tests/unit/adapters/test_dry_run_processor.py (modified — plan echoes `--format adw.css`)
- src/cli-tools/color-scheme-generator/tests/unit/adapters/test_container_processor.py (modified — inner command forwards `--format adw.css`)
- src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md (modified — enum row, 10-template inventory, AR-2 pinned mapping table + out-of-scope list)
- _bmad-output/implementation-artifacts/sprint-status.yaml (modified — story status)
- _bmad-output/implementation-artifacts/gt-1-1-colorformat-adw-css-template.md (modified — this file)

## Change Log

- 2026-09-07 — Story gt-1-1 implemented: `ColorFormat.ADW_CSS` enum member + `colors.adw.css.j2` template (§5 mapping pinned per AC-2, confirmed via real render), render-contract/CLI/dry-run/container-forwarding tests, AR-2 docs pin in `ARCHITECTURE_PLAN.md`. Suite: 569 passed, 1 pre-existing env-dependent failure. Status → review.

### Review Findings

Code review (2026-09-07, commit 58d9646): 0 CRITICAL, 0 HIGH, 0 MEDIUM, 1 patch applied, 1 defer, 4 dismissed as noise. Baseline claims re-verified: 28 ruff errors + 49 format-drift files identical on story-touched-vs-untouched file split (all 9 story-touched `.py` files pass `ruff check` + `ruff format --check`); `test_resolve_falls_back_to_package_defaults` fails identically pre/post (env-dependent, `~/.config` shadows package defaults).

- [x] [Review][Patch] Docs inventory wording implied all 10 templates were ported verbatim from v2 [src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md:674] — fixed in review commit: reworded to "9 ported verbatim + 2 additions".
- [x] [Review][Defer] AC-4 container-mode real exec not run in this story [src/cli-tools/color-scheme-generator/src/color_scheme_generator/adapters/container_processor.py:216] — deferred, already documented as manual verification step for gt-4-1/G1.1 (stale `csg-custom-latest` image errored at story time; templates bind-mount makes it image-independent).
- Dismissed (noise, contract-consistent): CLI test asserts file written by `FakeProcessor` not a real render (real rendering covered by `test_adw_css_format.py` render-contract tests + recorded manual e2e; the CLI test's job is format-string plumbing); container test asserts first `--format` occurrence (single-format request, unambiguous); `== 10` catalog tightening is intentionally fail-loud inventory; adw.css omits `color_background`/`color_foreground`/`color_cursor` passthrough names present in gtk.css (§5 pin covers `color_00..15` only — deliberate, documented).

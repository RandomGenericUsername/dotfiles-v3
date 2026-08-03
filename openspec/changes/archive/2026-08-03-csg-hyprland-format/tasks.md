## 1. Enum member

- [x] 1.1 Add `ColorFormat.HYPRLAND = "conf"` to `domain/enums.py` (after `SCSS`, L39). Preserve existing member order.
- [x] 1.2 Verify `domain/__init__.py` re-export picks up the new member automatically (it re-exports the symbol — confirm no explicit member list needs updating).

## 2. Template

- [x] 2.1 Author `defaults/templates/colors.conf.j2` emitting, in order: `$background`, `$foreground`, `$cursor`, `$accent` (= `colors[1].hex`), then `$color0`..`$color15`, each `rgb(<hex-without-#>)`, one per line, no quotes, no trailing semicolons. Strip `#` via `[1:]` slicing on `.hex`.

## 3. Tests

- [x] 3.1 Add assertion in `tests/unit/domain/test_enums.py::TestColorFormat::test_members` for `ColorFormat.HYPRLAND == "conf"` (mirror L24–L31 one-assert-per-member pattern).
- [x] 3.2 Add a format-rendering test (e.g. in `tests/unit/adapters/` or a new `test_hyprland_format.py`) that:
  - renders the new template with a fixed palette
  - asserts output matches the Hyprland syntax contract (`^$color0 = rgb([0-9a-f]{6})$` etc., no `#`, no `;`, no quotes)
  - asserts `$accent` equals `colors[1]` hex without `#`
- [x] 3.3 Confirm `tests/unit/domain/test_services.py::TestTemplateCatalogService::test_derive_from_real_bundled_templates` still passes (`>= 8` lower bound tolerates 9).

## 4. Docs & specs

- [x] 4.1 `docs/ARCHITECTURE_PLAN.md` — update `ColorFormat` enum row (L32) to include `HYPRLAND = "conf"`; add `colors.conf.j2` to the bundled-templates file tree (L493–500); update the "8 Jinja2 templates" count and `{css,gtk.css,...}` brace-list (L673) to 9 including `conf`.
- [x] 4.2 `openspec/specs/csg-templates-info-catalog/spec.md` — update L16 ("8 for bundled templates") and L92 ("all 8 standard format entries") to 9; L17 example may add `"conf"`.

## 5. Verification

- [x] 5.1 Run `uv run pytest tests/unit -q` from `src/cli-tools/color-scheme-generator` — all green.
- [x] 5.2 Run `uv run ruff check src tests` — no new violations.
- [x] 5.3 Run `uv run ruff format --check` on changed files.
- [x] 5.4 Manual smoke: `csg generate <image> -f conf` writes `colors.conf` with valid Hyprland syntax; `csg info` shows 9 formats including `conf`; `csg dump-templates` copies `colors.conf.j2`.
- [x] 5.5 If any Dockerfile in `defaults/docker/` enumerates templates by explicit filename (rather than COPYing the dir wholesale), add `colors.conf.j2` to its COPY list.

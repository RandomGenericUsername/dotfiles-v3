---
baseline_commit: c9581e7
---

# Story 2.1: Declarative Manifests

Status: review

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Change Log

- 2026-08-08: Story created — ultimate context engine analysis completed; comprehensive developer guide created.
- 2026-08-08: Story implemented and marked ready for review. Added `ManifestKind` + `AssetKind.spine_segment()`, typed `ProvisionManifest.kind` as `ManifestKind`, extended `YamlManifestReader` with per-kind schemas, authored the five `dotfiles/provisioning/*.yaml` manifests, extended reader tests, and marked the Story 1.2 deferred-work items resolved (186 passed / 0 skipped; ruff + mypy + layering guard clean).

## Story

As an operator,
I want `dotfiles/provisioning/*.yaml` manifests describing desired machine state,
So that provisioning is data-driven and the orchestrator can read desired state from the repo.

## Acceptance Criteria

1. `dotfiles/provisioning/` contains `packages.yaml`, `assets.yaml`, `filesystem.yaml`, `symlinks.yaml`, and `cli-tools.yaml` describing desired machine state (AC 1, FR-12)
2. `packages.yaml` lists the verified logical package set (`hyprland`, `hyprpaper`, `waybar`, `fonts`); per-manager package names resolve in Ansible `group_vars` (Story 2.2/2.3), per NFR-3 (AC 2, FR-12)
3. `assets.yaml` lists wallpapers + icon templates + icon mappings to deploy, each tagged with an `AssetKind` (AC 3, FR-12)
4. `filesystem.yaml` describes the XDG + install-dir subtree layout (AC 4, FR-12)
5. `symlinks.yaml` maps repo `dotfiles/config/*` to `~/.config/*` for every EXISTING config dir (AC 5, FR-12)
6. `cli-tools.yaml` specifies csg/weg/itr install specs (`uv tool install` targets with repo source paths) (AC 6, FR-12)
7. Every manifest parses with `YamlManifestReader` (Story 1.5) into a domain `ProvisionManifest` object (AC 7, FR-12)
8. Manifest content matches the verified package set and existing assets from the plan (§2/§4/§6) — no empty or typo'd package/asset lists (AC 8, FR-12)

## Tasks / Subtasks

- [x] Reconcile deferred domain shapes (retro AI-1) — `domain/enums.py` + `domain/models.py` (AC: 7)
  - [x] Add `ManifestKind` StrEnum to `domain/enums.py`: `PACKAGES`, `ASSETS`, `FILESYSTEM`, `SYMLINKS`, `CLI_TOOLS` (values: `packages`, `assets`, `filesystem`, `symlinks`, `cli-tools`)
  - [x] Add `AssetKind.spine_segment()` mapping — single source of truth for the install-spine deploy target (resolves the 1.2 deferred "icon-mapping vs icon-mappings" item)
  - [x] Type `ProvisionManifest.kind` as `ManifestKind` (was free-form `str` — resolves the 1.2 deferred "kind is free-form str" item)
  - [x] Verify domain stays zero-I/O (allowlist `dataclasses`, `enum` + `domain.enums` import only) — layering guard must stay green
- [x] Extend `YamlManifestReader` with per-kind entry schemas (AC: 7)
  - [x] Replace global `_ALLOWED_SPEC_KEYS = {name, version}` with a per-`ManifestKind` allowed-key map (see Dev Notes schema table)
  - [x] Validate `kind` against `ManifestKind` (fail-closed on unknown kinds)
  - [x] Validate per-kind required keys + `AssetKind` values for assets.yaml entries; keep `name`/`version` capture into `Spec`; validate-but-do-not-capture rich keys (`target`, `source`, `kind`) — Ansible is the consumer
  - [x] Preserve ALL existing strict behavior: duplicate-key rejection, unknown-key rejection, non-UTF-8 rejection, whitespace-only rejection, `version: "" → None`, ≤200-char error payloads
- [x] Author `dotfiles/provisioning/packages.yaml` (AC: 1, 2, 8)
  - [x] Entries: the verified logical package set — `hyprland`, `hyprpaper`, `waybar`, `fonts` (versions optional/null). Do NOT split per package manager — distro isolation lives in Ansible `group_vars` (NFR-3)
- [x] Author `dotfiles/provisioning/assets.yaml` (AC: 1, 3, 8)
  - [x] Entries tagged with `AssetKind`: wallpapers (source `dotfiles/assets/wallpapers/wallpapers.tar.gz`, incl. verified `default.png`), icon-templates (source `dotfiles/assets/icon-templates/` — status-bar, wlogout, screenshot-tool), icon-mappings (source `dotfiles/config/icon-template-color-scheme-mappings/` — 9 YAMLs), csg-templates, weg-effects
  - [x] Must be non-empty and match the actual repo tree (see Dev Notes verified inventory)
- [x] Author `dotfiles/provisioning/filesystem.yaml` (AC: 1, 4, 8)
  - [x] Entries for XDG config/state/cache + the full install-spine subtree (wallpapers/, icon-templates/, icon-mappings/, csg-templates/, weg-effects.yaml, generated/{palettes,effects,icons,.weg-tmp}/)
- [x] Author `dotfiles/provisioning/symlinks.yaml` (AC: 1, 5, 8)
  - [x] Entries for the EXISTING config dirs only: `nvim`, `starship`, `wlogout`, `zsh` → `~/.config/<dir>`. Do NOT list `hypr`/`hyprpaper`/`waybar` (those dirs land in Story 2.8; verify's symlink check needs every entry to resolve to a real file)
- [x] Author `dotfiles/provisioning/cli-tools.yaml` (AC: 1, 6, 8)
  - [x] Entries: `csg` (source `src/cli-tools/color-scheme-generator`), `weg` (source `src/cli-tools/wallpaper-effects-generator`), `itr` (source `src/cli-tools/icon-templates-renderer`) — the `uv tool install` targets
- [x] Extend manifest-reader tests (AC: 7, 8)
  - [x] Extend `tests/unit/adapters/test_yaml_manifest_reader.py`: parse each authored manifest against the real repo file (happy path)
  - [x] Add per-kind schema tests: unknown kind rejected, per-kind required-key violations rejected, unknown per-kind entry keys rejected, `AssetKind` validation in assets.yaml
  - [x] Update any existing test constructing `ProvisionManifest(kind=...)` or asserting on `kind` to use `ManifestKind` — three files: `tests/unit/test_domain.py`, `tests/unit/ports/test_manifest_reader.py` (FakeManifestReader `kind="packages"`), and `tests/unit/adapters/test_yaml_manifest_reader.py`
- [x] Verify layering guard + full suite (AC: 7)
  - [x] `uv run pytest tests/architecture/test_layering.py` — green (domain + adapters modified)
  - [x] `uv run pytest` — full suite green (was 156 passed / 0 skipped)
  - [x] `uv run ruff check .` + `uv run ruff format --check .` + `uv run mypy src tests` clean
  - [x] Standalone nicety: `python tests/architecture/test_layering.py` exits 0

## Dev Notes

### Scope — what Story 2.1 is and is not

**IS:** the five `dotfiles/provisioning/*.yaml` manifests (data files), plus the minimal domain/reader reconciliation needed so they parse strictly into `ProvisionManifest` objects. This story RESOLVES the retro AI-1 deferred domain shapes.

**IS NOT:** Ansible scaffold (`ansible/`, inventory, `requirements.yml`, `group_vars` — Story 2.2), roles (Stories 2.3–2.12), compositor skeleton configs `dotfiles/config/{hypr,hyprpaper,waybar}/` (Story 2.8), any runtime consumption of manifests (the orchestrator does NOT glob manifests — Story 1.6/1.7 scope guard), Python-side package inspection.

### Who consumes the manifests (critical context)

- **Primary consumer = Ansible content (Epic 2).** Stories 2.3–2.12 read these YAMLs directly (roles/playbooks). The manifests must carry the rich data Ansible needs (`target`, `source`, `AssetKind`, subtree layout, install specs).
- **Secondary consumer = `YamlManifestReader` (Story 1.5).** AC 7 requires every manifest to parse into a domain `ProvisionManifest`. The reader is **strict/fail-closed** (unknown keys rejected, duplicate keys rejected, `{kind, entries}` top-level only). Rich per-kind fields must be explicitly allowed by extending the reader — this is the reconciliation work, not optional.

### The deferred-shape reconciliation (from retro AI-1 + deferred-work.md)

Deferred from Story 1.2 review, explicitly assigned to "Story 2.1":
- *"`ProvisionManifest.kind` is a free-form `str` overlapping `AssetKind` semantics — concrete kinds arrive with manifests (Story 2.1)"* → add `ManifestKind` enum and type `kind` as it.
- *"`AssetKind` values may not match future install-spine path segments (`icon-mapping` vs `icon-mappings`)"* → resolve by adding `AssetKind.spine_segment()` (single source of truth); do NOT necessarily change the enum VALUES (a mapping method avoids a breaking value change) unless tests prove it cleaner.
- *"`ProvisionResult.tasks` is an anonymous tuple with no status enum"* → OUT OF SCOPE here (task status is an executor concern; revisit only if a manifest needs it).

### Domain changes — `src/provisioning/src/provisioning/domain/`

**`enums.py`** — add:
```python
class ManifestKind(StrEnum):
    PACKAGES = "packages"
    ASSETS = "assets"
    FILESYSTEM = "filesystem"
    SYMLINKS = "symlinks"
    CLI_TOOLS = "cli-tools"
```
Add `AssetKind.spine_segment()` mapping to the deploy target under the install dir:
```python
class AssetKind(StrEnum):
    ...
    def spine_segment(self) -> str:
        return _SPINE_SEGMENT[self]
# _SPINE_SEGMENT = {
#   AssetKind.WALLPAPER: "wallpapers",
#   AssetKind.ICON_TEMPLATE: "icon-templates",
#   AssetKind.ICON_MAPPING: "icon-mappings",   # note plural — the spine dir
#   AssetKind.CSG_TEMPLATE: "csg-templates",
#   AssetKind.WEG_EFFECTS: "weg-effects.yaml", # a FILE, not a dir
# }
```
Zero-I/O constraint: only `enum` imports; add the new enum to `__all__`.

**`models.py`** — type `ProvisionManifest.kind` as `ManifestKind` (import from `provisioning.domain.enums`). `Spec` stays `(name, version)` — do NOT add fields (rich per-kind data stays in YAML for Ansible; the domain view is deliberately minimal — Story 1.2 "avoid over-modeling"). Frozen/hashable invariants and `__all__` stay intact.

### Reader extension — `src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py`

Keep the top-level contract `{kind, entries}`. Replace the global `_ALLOWED_SPEC_KEYS` with a per-`ManifestKind` entry schema:

| kind | Allowed entry keys | Required | Notes |
|---|---|---|---|
| `packages` | `name`, `version` | `name` | unchanged from today |
| `assets` | `name`, `version`, `kind`, `source` | `name`, `kind` | `kind` must be a valid `AssetKind` value |
| `filesystem` | `name` | `name` | subtree node names (see layout below) |
| `symlinks` | `name`, `target`, `version` | `name`, `target` | `name` = repo source dir, `target` = `~/.config/<dir>` |
| `cli-tools` | `name`, `source`, `version` | `name`, `source` | `source` = repo package path for `uv tool install` |

Behavior to PRESERVE exactly (Story 1.5 review hardening — do not regress):
- `_StrictSafeLoader` duplicate-key rejection; unknown top-level keys rejected; entry must be a mapping; `name` non-empty after `.strip()`; `version` string-or-null, `"" → None`; UTF-8 enforced; error payloads ≤200 chars; `ManifestReadError` (ValueError) for all.
- Unknown `kind` value → `ManifestReadError` naming the value and the supported `ManifestKind` set.
- Rich keys (`target`, `source`, `kind`) are **validated but not captured** into the returned `Spec` — the reader returns `ProvisionManifest(kind=ManifestKind, entries=(Spec(name, version), ...))`. Ansible reads the full YAML directly.

Worked example — the `{kind, entries}` envelope, one manifest per kind:
```yaml
# packages.yaml
kind: packages
entries:
  - name: hyprland
  - name: hyprpaper
  - name: waybar
  - name: fonts

# assets.yaml — rich per-kind keys are validated, not captured
kind: assets
entries:
  - name: wallpapers
    kind: wallpaper
    source: dotfiles/assets/wallpapers/wallpapers.tar.gz
  - name: battery
    kind: icon-mapping
    source: dotfiles/config/icon-template-color-scheme-mappings/battery.yaml

# symlinks.yaml
kind: symlinks
entries:
  - name: nvim
    target: nvim
  - name: zsh
    target: zsh
```

### Manifest authoring — verified repo inventory (AC 8 grounding)

Source of truth: [plan §2 current repo state], [plan §4 tool settings facts], [plan §5 chaining spine], [plan §6 layout], [SPEC assumptions]. Verified against the actual working tree:

**Packages** (verified set — SPEC assumption "Hyprland, Hyprpaper, Waybar, fonts, and the csg/weg/itr CLIs are installable via Ansible on Arch and Debian-family targets"):
- `hyprland`, `hyprpaper`, `waybar`, `fonts`. Per-manager names (`pacman`/`apt`) belong to Ansible `group_vars` (Story 2.2/2.3) — NOT the manifest (NFR-3 distro isolation). The three CLIs go in `cli-tools.yaml`, not `packages.yaml`.
- **Interpretation ratified 2026-08-08:** the PRD/epics phrase "packages per package manager" is knowingly refined to "logical package set, per-manager names in `group_vars`" — per NFR-3 (distro isolation in `group_vars`, no distro branching in Python or `bootstrap.sh`) and plan §11 step 7. Story 2.3 applies the mapping.

**Assets** (verified present):
- `dotfiles/assets/wallpapers/wallpapers.tar.gz` — 55 files, **contains `default.png`** (SPEC assumption, verified via `tar -tzf`)
- `dotfiles/assets/icon-templates/` — subdirs `status-bar/`, `wlogout/`, `screenshot-tool/` (SVG icon templates)
- `dotfiles/config/icon-template-color-scheme-mappings/` — **9 YAMLs**: battery, email-client, icons, network, power-menu, screenshot-tool, wallpaper-selector, wlogout, defaults
- CSG bundled Jinja templates → deployed to `<install>/csg-templates/`; WEG effects catalog → emitted to `<install>/weg-effects.yaml` (both locked in plan §9 / SPEC)

**Symlinks** (EXISTING config dirs only): `nvim`, `starship`, `wlogout`, `zsh` (`.zshrc.j2` inside `zsh/`). The `icon-template-color-scheme-mappings/` dir is an ASSET (deployed to `<install>/icon-mappings/`), NOT a symlink. `hypr`/`hyprpaper`/`waybar` do NOT exist yet (Story 2.8) — do NOT list them.

**CLI tools** (verified paths): `src/cli-tools/color-scheme-generator`, `src/cli-tools/wallpaper-effects-generator`, `src/cli-tools/icon-templates-renderer` — the `uv tool install` targets (plan §3 locked decision). Note: `src/cli-tools/openspec/` also exists in the tree but is NOT an install target — do not include it.

**Filesystem** — XDG + install spine (plan §5): `wallpapers/`, `icon-templates/`, `icon-mappings/`, `csg-templates/`, `weg-effects.yaml`, `generated/{palettes,effects,icons,.weg-tmp}/` + XDG config/state/cache.

### Layout reminder — where files live

```
dotfiles/provisioning/            ← NEW dir (plan §6) — create it
├── packages.yaml
├── assets.yaml
├── filesystem.yaml
├── symlinks.yaml
└── cli-tools.yaml
```
The manifests are repo data files under `dotfiles/` — NOT under `src/provisioning/`. The `src/provisioning` package (Python) is only touched by the domain/reader reconciliation above.

### Layering guard & regression care (Story 1.3)

- `domain/enums.py` and `domain/models.py` are scanned by `tests/architecture/test_layering.py`. New imports must stay in the domain allowlist (`dataclasses`, `enum`, `provisioning.domain.*`). `AssetKind`/`ManifestKind` both live in `enums.py`; `models.py` already imports `provisioning.domain.enums`.
- `adapters/` may import `domain` + `ports` only (no `application`/`cli`). `yaml` is already a declared dep (`PyYAML>=6.0`, Story 1.5) so `import yaml` stays allowed.
- Search for every existing `ProvisionManifest(kind=...)` construction and `kind` assertion (domain tests, reader tests) — update to `ManifestKind`. Run the FULL suite; nothing may regress from the 156-pass baseline.

## Project Structure Notes

- `dotfiles/provisioning/` — new top-level manifests dir (matches plan §6; currently does not exist — plan §2 "Missing/not started").
- `src/provisioning/src/provisioning/domain/{enums,models}.py` — reconciled (ManifestKind, AssetKind.spine_segment, ProvisionManifest.kind type).
- `src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py` — per-kind schemas.
- `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` — extended.
- No new dependencies. No `dotfiles/config/{hypr,hyprpaper,waybar}/` (Story 2.8). No Ansible content (Story 2.2+).

## Testing Requirements

- **Parse-the-real-manifests tests** — for each of the five authored manifests: `YamlManifestReader().read(Path("dotfiles/provisioning/<name>.yaml"))` returns `ProvisionManifest` with the correct `ManifestKind` and non-empty `Spec` entries (AC 7, 8).
- **Per-kind schema negative tests** — unknown `kind`, unknown per-kind entry key, missing required key (`target`/`source`/`kind` where mandated), invalid `AssetKind` value in assets.yaml — each raises `ManifestReadError`.
- **Preserve existing strictness** — duplicate key, non-UTF-8, whitespace-only name, `version: "" → None` — keep existing cases green.
- `uv run pytest tests/unit/adapters/`, `uv run pytest tests/architecture/test_layering.py`, `uv run pytest` (full), ruff check/format, `mypy src tests` (strict — annotate helpers/fixtures), standalone layering runner.

## Previous Story Intelligence

### Story 1.5 — Adapters (the reader being extended)
- `YamlManifestReader` (strict): top-level `{kind, entries}`, entries `{name, version?}`, duplicate/unknown-key rejection, `version: null|"" → None`, UTF-8 enforced, `ManifestReadError` (ValueError). [Source: src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py]
- Deferred: "YAML alias-expansion (billion-laughs) exhaustion via `safe_load` — manifests are the user's own dotfiles; hardening item, not in story scope" → do NOT reopen.

### Story 1.2 — Domain (being reconciled)
- `ProvisionManifest(kind: str, entries: tuple[Spec, ...])`; `Spec(name, version)`; frozen/hashable via tuple fields. [Source: src/provisioning/src/provisioning/domain/models.py]
- `AssetKind` values: wallpaper, icon-template, icon-mapping, csg-template, weg-effects. [Source: src/provisioning/src/provisioning/domain/enums.py]
- Deferred items (this story resolves the two kind/AssetKind ones): "kind is free-form str overlapping AssetKind semantics"; "AssetKind values may not match install-spine path segments (icon-mapping vs icon-mappings)".

### Retro AI-1 (Epic 1 retrospective)
"Reconcile deferred domain shapes in Story 2.1: concrete ProvisionManifest kinds, AssetKind values aligned with install-spine path segments." Owner: Amelia (Developer). Success = manifests land without the deferred-shape workarounds; deferred-work 1-2 entries marked done.

## References

- [Source: _bmad-output/planning-artifacts/epics-dotfiles-provisioning-phase1.md#286-302] — Story 2.1 ACs
- [Source: _bmad-output/planning-artifacts/prds/prd-dotfiles-repo-v3-2026-08-03/prd.md#190-195] — FR-12 Declarative Manifests
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#190-195] — plan §6 manifests layout
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#17-44] — plan §2 current repo state / missing dirs
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#106-132] — plan §5 chaining spine (filesystem + assets structure)
- [Source: docs/01-dotfiles-provisioning-phase1-plan.md#282] — plan §11 step 6 (manifests populated from actual package set + existing assets)
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#70] — verified package set assumption
- [Source: _bmad-output/specs/spec-dotfiles-provisioning-phase1/SPEC.md#75] — default.png in wallpapers.tar.gz assumption
- [Source: src/provisioning/src/provisioning/domain/{enums.py,models.py}] — current domain shapes
- [Source: src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py] — strict reader to extend
- [Source: _bmad-output/implementation-artifacts/deferred-work.md#123-128] — Story 1.2 deferred items
- [Source: _bmad-output/implementation-artifacts/epic-1-retro-2026-08-08.md] — AI-1 reconciliation action item

## Dev Agent Record

### Agent Model Used

opencode-go/deepseek-v4-flash

### Debug Log References

### Completion Notes List

- Implemented retro AI-1 deferred domain reconciliation: `ManifestKind` StrEnum (5 members), `AssetKind.spine_segment()` mapping to install-spine targets (resolves `icon-mapping` vs `icon-mappings`), `ProvisionManifest.kind` typed as `ManifestKind` (domain stays zero-I/O — only `enum`/`dataclasses`/`domain.enums` imports).
- Extended `YamlManifestReader` with a per-kind entry schema map (`_ENTRY_SCHEMAS`): allowed + required keys per kind, fail-closed on unknown `kind` values and unknown `AssetKind` values, rich keys (`target`, `source`, `kind`) validated-but-not-captured. All prior strict behaviors preserved (duplicate/unknown-key rejection, UTF-8, whitespace-only, `version: "" → None`, ≤200-char errors).
- Authored five manifests grounded in the verified repo inventory: `packages.yaml` (4 logical packages), `assets.yaml` (5 asset entries, all sources verified to exist), `filesystem.yaml` (XDG + install-spine subtree incl. `weg-effects.yaml`), `symlinks.yaml` (4 existing config dirs only — no hypr/hyprpaper/waybar), `cli-tools.yaml` (csg/weg/itr).
- Tests: added `TestYamlManifestReaderPerKindSchemas` (13 cases), `TestReadRealManifests` (parse the actual repo manifests, AC 7/8), `TestManifestKind`, `AssetKind.spine_segment` tests; updated `ProvisionManifest`/reader/port-fake tests to `ManifestKind`. Full suite: 186 passed / 0 skipped. Ruff + mypy + layering guard (incl. standalone runner) all clean.

### File List

- `src/provisioning/src/provisioning/domain/enums.py` — added `ManifestKind`, `AssetKind.spine_segment()` + `_SPINE_SEGMENT`, updated `__all__`
- `src/provisioning/src/provisioning/domain/models.py` — `ProvisionManifest.kind: ManifestKind`
- `src/provisioning/src/provisioning/adapters/yaml_manifest_reader.py` — per-kind entry schemas, fail-closed kind/AssetKind validation
- `dotfiles/provisioning/packages.yaml` — new manifest
- `dotfiles/provisioning/assets.yaml` — new manifest
- `dotfiles/provisioning/filesystem.yaml` — new manifest
- `dotfiles/provisioning/symlinks.yaml` — new manifest
- `dotfiles/provisioning/cli-tools.yaml` — new manifest
- `src/provisioning/tests/unit/test_domain.py` — `ManifestKind` + `spine_segment` tests, `ManifestKind`-typed fixtures
- `src/provisioning/tests/unit/ports/test_manifest_reader.py` — FakeManifestReader uses `ManifestKind`
- `src/provisioning/tests/unit/adapters/test_yaml_manifest_reader.py` — per-kind schema tests + real-manifest parse tests
- `_bmad-output/implementation-artifacts/deferred-work.md` — marked Story 1.2 kind/AssetKind items resolved

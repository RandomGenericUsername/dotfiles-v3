# btop theme integration — findings, decisions, and open items

STATUS: investigation + throwaway prototyping only.
NO repo files touched. All scratch lives in /tmp/opencode/.
Repo `git status` at time of writing: 14 entries, ALL pre-existing
audio-panel work (dotfiles/config/ags/audio/*, _bmad-output/.../ux-*,
openspec/changes/redesign-ags-audio-panel/). Nothing from this effort.

This document is INPUT to the OpenSpec/BMAD spec phase, not a deliverable.


## Phase discipline

1. INVESTIGATE / PROTOTYPE   <- current phase (this doc + /tmp scratch)
2. LOCK DECISIONS            <- user sign-off
3. WRITE SPEC                <- openspec/changes/... (or bmad, per scope)
4. IMPLEMENT via TDD         <- delegated to implementing agent, with harness,
                                 working ONLY from the spec, so no drift and
                                 the architecture/contracts stay intact.

Nothing from phase 1 may leak into the repo. Prototypes exist to de-risk the
spec, not to be promoted.


## Locked decisions

- Three themes as a difficulty dial, not a feature list:
  - `csg-minimal`  - all gradients are wallpaper luminance slices
  - `csg-balanced` - + temp and cached(POWER) forced cool->warm
  - `csg-full`     - + cpu forced cool->warm (6 call sites)
- File names carry the `csg-` prefix (provenance in a 44-theme menu).
- Meters grouped by TRUE MEANING, not by key name:
  - room-left   : free, available
  - consumption : used, cached
- Box outlines + div_line: neutral, one dim ramp stop shared by
  cpu_box / mem_box / net_box / proc_box / div_line.
- Each theme is a separate CSG format (one template -> one file; a template
  cannot emit three files).
- "Only the selected theme reacts" needs NO work: each file rewrites only on
  its own format's regeneration, and btop has no hot-reload. Free.
- btop.conf ships with `save_config_on_exit = false` (default true would let
  btop truncate/rewrite the spine-owned config through the symlink).


## Verified facts (evidence)

### btop theme format (btop 1.4.7, commit d3389d7)
- Parser: src/btop_theme.cpp. 48 keys in `Default_theme` (:52-101).
- NOTHING is required. Missing -> `Default_theme` value (:280-284), plus a
  second pass for meter_bg->inactive_fg, graph_text->inactive_fg,
  process_*->cpu_* (:287-302).
- Scan (:430-442): custom_theme_dir -> user_theme_dir -> theme_dir.
  Predicates are `file.path().extension() == ".theme"` and
  `access(path, R_OK) != -1`. BOTH are lexical / link-following.
  => symlinks work; verified against a real 3-hop chain.
- Selection: `color_theme` in btop.conf (:451-471) matched against the
  DISCOVERED list by full path / filename / stem. An absolute path outside
  the scanned dirs silently falls back to Default (no error).
- Empty values (:255-264): `main_bg=""` -> transparent; `<x>_mid=""` or
  `<x>_end=""` -> clean 2-stop gradient (documented idiom, used by the
  built-in TTY theme).
- Values: `#RRGGBB`, `#GG` greyscale, or "12 34 56" decimals. NO 8-digit/alpha.
- `#` is a comment ONLY at column 0; leading whitespace before `[` mangles
  the line. Every emitted line must start at column 0.
- `Config::write()` truncates and rewrites btop.conf on exit when
  `save_config_on_exit` (default true, :379; write at :836-845).
- Log goes to `$XDG_STATE_HOME/btop.log` (:873) - outside the spine, no action.

### Key names lie - traced every Theme::g() call site (btop_draw.cpp)
| gradient | ACTUALLY renders | scaled by |
|---|---|---|
| temp      | CPU temp, per-core temps, GPU temp | temp*100/temp_max (RELATIVE) |
| cpu       | CPU meter, GPU util graphs+meter, core graphs, enc/dec meters, battery | load % |
| cached    | **CPU watts, GPU power draw, P-state** | watts / max_observed_watts |
| available | **disk I/O activity (%busy)**, not memory | 50-100 clamp |
| used      | disk used meter, GPU VRAM | % |
| free      | disk free meter, GPU mem util | % (0-5% offset) |
| download/upload | net graphs | auto-rescaled |
| process   | process-list thread/mem/cpu | per-thread usage |

=> `cached` is POWER not cache. `available` is DISK I/O not free RAM.
=> `cpu` is the workhorse: 6 call sites.
=> the user's GPU screenshot row uses cpu + temp + cached(13.0W) + used(VRAM).
=> `temp` is relative-scaled, so semantic cool->warm survives wallpaper change.
=> Meter direction: `invert ? 100-y : y` (btop_draw.cpp:411).
=> `cpu_invert_lower` defaults TRUE (lower CPU graph fills downward).

### CSG mechanics
- One template -> one file: local_processor.py:83-86
  `colors.{fmt.value}.j2` -> `colors.{fmt.value}`.
- `TemplateCatalogService.derive` (services.py:82-101) raises
  TemplatesValidationError for any `colors.*.j2` not in ColorFormat.
  => TEMPLATE AND ENUM MEMBER MUST LAND TOGETHER, or csg breaks entirely.
  => NO shared .j2 partial is possible (an extra .j2 parses as a format).
- Multi-dot enum values are fine (precedent: GTK_CSS = "gtk.css").
- All backends sort colors by sum(rgb) ASCENDING
  (pywal_generator.py:74, custom_generator.py:78, wallust_generator.py:108)
  => colors[] is a LUMINANCE RAMP, not an ANSI palette. Role-based mapping
  is mandatory.
- Live palette has only 8-9 DISTINCT colors across 16 slots (pywal returns
  duplicate pairs) => templates dedupe adjacent ramp stops.

### Runtime distribution (3 layers, all verified on-disk)
1. current/ (runtime-owned, $XDG_STATE_HOME/dotfiles/)
   repoint_current_symlinks, seeder.py:595-693; artifact tuple :657-665
2. consumer pointers into the install spine
   repoint_consumer_symlinks, seeder.py:694-787
   table: consumer_path_spec.py:26-33
   verified: ags/colors.css -> ~/.local/state/dotfiles/current/colors.gtk.css
3. config_links (provisioning-owned)
   ~/.config/<name> -> <install>/config/<name>
   verified: ~/.config/kitty -> ~/.local/share/dotfiles/config/kitty
   managed dirs list: config_links/vars/main.yml:70-89

- `skip_on_missing_parent` (seeder.py:759): pointer skipped+warned, NEVER
  mkdir. So provisioning must create <install>/config/btop/themes/.
- bootstrap order: ... config_copies -> settings -> zsh_config ->
  wlogout_config -> kitty_config -> config_links -> runtime-seed -> verify
  (playbooks/bootstrap.yaml:47-77)
- runtime-seed DOES generate the palette at provision time
  (runtime-seed.yaml:42-52, `wallpaper set <install>/wallpapers/default.png`),
  and runs AFTER config_links. So targets exist at install; only the
  DESTINATION PARENT dir needs provisioning (a `state: directory` task in a
  new btop_config role, mirroring kitty_config).
- HYPRLAND IS THE CLOSEST PRECEDENT for the themes-subdir shape:
  dotfiles/config/hypr/colors.lua:14-27 parses `^%$([%w]+) = rgb%(([%x]+)%)`
  from current/colors.conf at dofile time. Same "consumers read current/
  directly, no spine pointer" shape.
- Kitty full end-to-end precedent:
  docs/handoffs/HANDOFF-kitty-terminal-colors.md:70-108
  (3 changes: CSG -> runtime -> provisioning, in that order).
- Also precedent for a config-carrying color format: ITR reads
  current/colors.yaml (roles/settings/templates/itr-settings.toml.j2:17).

### btop already wired in this repo
- installed via package vars (group_vars/arch.yml:100,
  group_vars/debian-family.yml:87)
- launched from the ags bar widget: dotfiles/config/ags/bar/widgets/btop.tsx
  `execAsync(["kitty", "--", "btop"])`  <- no flags; relies on XDG discovery
- ~/.config/btop/themes exists but is EMPTY; no btop.conf yet.

### Docs drift (fold into the change)
- docs/99-dotfiles-hexagonal-architecture.md:340 says 3 formats; it's 7.
- src/cli-tools/color-scheme-generator/docs/ARCHITECTURE_PLAN.md:32 omits KITTY.


## Wiring surface (for the spec - NOT to be executed in phase 1)

CSG side:
- domain/enums.py:31-42  add BTOP_MINIMAL/ BTOP_BALANCED / BTOP_FULL
- defaults/templates/colors.btop-{minimal,balanced,full}.theme.j2  (new, 3)
- templates_count assertions in tests/ + `csg info`  (currently 11 -> 14)
- openspec/specs/csg-*-format/spec.md (precedent:
  openspec/specs/csg-hyprland-format/spec.md)

Runtime side:
- adapters/csg_adapter.py:280-298   add 3 --format flags
- adapters/csg_adapter.py:351-359  existence assert
- adapters/csg_adapter.py:368-376  PaletteArtifacts construction
- adapters/seeder.py:485-493       load_palette_entry
- adapters/seeder.py:657-665       current/ artifact loop
- domain/models.py:58              PaletteArtifacts dataclass
- application/derive.py:291-299    PALETTE_ARTIFACT_NAMES (completeness oracle)
- application/derive.py:728-736    artifact_hashes map
- application/reconcile.py:497,540,601  three hardcoded lists

Contracts (HARD GATE - additionalProperties:false, required is closed):
- contracts/schemas/meta.schema.json:47-67  add all 3 keys to required+properties
- enforced by `make contracts-check`

Provisioning side:
- NEW role btop_config (mirror kitty_config): render btop.conf with
  color_theme = "csg-minimal", save_config_on_exit = false;
  create <install>/config/btop/themes/
- roles/verify/vars/main.yml:140-147  verify_csg_template_files (+3)
- roles/verify/vars/main.yml:366-372  verify_palette_files (+3)
- config_links/vars/main.yml:70-89    add `btop`
- verify/vars/main.yml:571            verify_managed_link_dirs (+btop)
  (these two lists are compared EXACTLY by test_verify_managed_link_dirs)

Gates: pytest x3 (runtime, csg, provisioning), test_layering.py, make contracts-check


## Open items for the user

1. TEMPLATE CONTENT - three variants drafted in /tmp/opencode/btop-preview/
   (make_templates.py) but NOT rendered/approved yet. Needs eyeballing.
   Proposed stops use uniq[] dedupe indices; may need tuning.
2. btop.conf defaults beyond color_theme + save_config_on_exit:
   ship stock values, or tune any? (graph_symbol, presets, update_ms, ...)
3. Default theme on first install: csg-minimal, or leave btop's "Default"
   and let the user pick?
4. Confirm no reloader is wanted (theme applies on next btop launch).

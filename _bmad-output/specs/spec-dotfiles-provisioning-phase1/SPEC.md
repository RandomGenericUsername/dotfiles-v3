---
id: SPEC-dotfiles-provisioning-phase1
companions:
  - chaining-spine.md
  - ../../../docs/01-dotfiles-provisioning-phase1-plan.md
sources: []
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate. Source documents listed in frontmatter are for traceability only — consult them only if you need narrative rationale or prose color this contract intentionally omits.

# Dotfiles System — Phase 1 Provisioning

## Why

The dotfiles project is a **Desktop State Reconciliation Engine**, not a wallpaper manager or CLI wrapper collection. Phase 1 is the bottom of that stack (architecture doc §27): Domain 1, **Machine State Reconciliation**. It establishes the operational environment — packages, the `csg`/`weg`/icon-renderer CLIs, wallpapers, icon templates, icon color mappings, filesystem layout, symlinks, and per-tool settings files — that the Phase 2 runtime reconciliation layer is allowed to assume exists (§12). The three compute providers and shared config libraries already exist; nothing yet orchestrates the machine state they run on. This phase closes that gap by making the machine *capable*, not by reconciling the desktop.

## Capabilities

- **CAP-1**
  - **intent:** An operator can diff desired machine state against actual state before any mutation.
  - **success:** `dotfiles-provision plan` prints a desired-vs-actual execution plan and makes no system changes. The diff is Ansible's native `--check` mode; the Python side reads only `ansible_os_family` (`IFactReader`) to select `group_vars/{arch,debian-family}.yml` and never inspects packages itself.
- **CAP-2**
  - **intent:** An operator can apply provisioning idempotently and re-runnably.
  - **success:** `dotfiles-provision apply` runs the Ansible playbooks; a re-run produces no drift (Ansible is the state authority — no `provisioning-state.json` is persisted in Phase 1).
- **CAP-3**
  - **intent:** An operator can verify the machine satisfies the §12 runtime preconditions.
  - **success:** `dotfiles-provision verify` is green when all ten done-criteria hold (install dir, system binaries, CLI tools, assets, settings parse, default palette, compositor configs, filesystem structure, symlinks, preconditions).
- **CAP-4**
  - **intent:** A fresh machine can be fully provisioned in one command.
  - **success:** `git clone && ./scripts/bootstrap.sh` bootstraps Python+uv and completes `dotfiles-provision bootstrap` with verify green.
- **CAP-5**
  - **intent:** The three compute providers read and write through a shared install spine.
  - **success:** after provisioning, `csg`/`weg`/`itr` invoked with `--config <provisioned-settings>` read from and write to `$XDG_DATA_HOME/dotfiles/` (palettes, effects, icons) with no per-invocation path flags; ITR's `color_scheme.path` chains to CSG's palette output.

## Constraints

- **§11 boundary:** `src/provisioning` is its own uv package importing `cli-output` only — never `core`, `infrastructure`, or the CLI-tool packages. It knows machine state only; it has no wallpaper-invalidation, palette, or cache logic.
- Provisioning establishes operational capability only; it does not reconcile the desktop (§25).
- The four §12 runtime preconditions (binaries installed, assets placed, filesystem structure exists, settings files parseable) must be assertable via `VerifyCapabilityUseCase` without reaching into provisioning internals.
- Per-tool settings files must render and parse exactly: CSG `output.directory`; WEG `output.directory` + `processing.temp_dir`; ITR `output.output_dir` + `templates.dir` + `color_scheme.path` — absolute paths into the install dir (see `chaining-spine.md`).
- ITR's settings resolver is active (all commands call `config_resolver.resolve()`); ITR has no dump command, so provisioning writes its settings.toml directly (4 keys).
- CSG templates dir is **not** a settings field; provisioning deploys the bundled templates to `<install>/csg-templates/` and the Phase 2 runtime invokes CSG with `--templates-dir <install>/csg-templates/`.
- WEG effects catalog is a deployed file: provisioning emits it via `weg dump-effects --output` into the install dir and points WEG's effects chain at it.
- Distro differences are isolated to `group_vars/{arch,debian-family}.yml`; the Python orchestrator never branches on distro.
- **Default palette generated at apply time:** provisioning's `default_palette` role invokes `csg generate <install>/wallpapers/default.png -f conf` (wallpaper unpacked from `dotfiles/assets/wallpapers/wallpapers.tar.gz`) writing `<install>/generated/palettes/`. Replacing the tarball → next `apply` regenerates. `overwrite=true` is scoped per-task via `environment: COLORSCHEME__OUTPUT__OVERWRITE: "true"` and never written into the rendered settings file (which keeps `overwrite = false`).
- **Compositor color fragments:** Hyprland skeleton uses `source = ~/.config/hypr/colors.conf` (emitted by CSG's `conf` format, copied from the palette dir); Waybar `style.css` uses `@import "colors.css";` (from CSG's `css` format); Hyprpaper is flat static pointing at `<install>/wallpapers/default.png`. Phase 2 overwrites only the fragment files.
- **Bootstrap chain:** `scripts/bootstrap.sh` pre-seeds Python+uv then runs `uv run --directory ./src/provisioning dotfiles-provision bootstrap`. `ansible-core` is a runtime dep of `src/provisioning`; external collections (`community.general`, `ansible.posix`, `kewlfft.aur`) are declared in `ansible/requirements.yml`.
- **AUR strategy (Arch):** the `packages` role self-bootstraps `yay` (`base-devel`+`git` → guarded `makepkg -si yay-bin`) then uses `kewlfft.aur.aur` for AUR installs; distro logic stays in `vars/arch.yml`.
- **No persisted provisioning state:** Ansible is the state authority (idempotent playbooks); `verify` re-derives state on demand. No `provisioning-state.json` in Phase 1.
- **§11 enforced mechanically:** `tests/architecture/test_layering.py` enforces the in-package hexagon (mirroring `oci-runtime`) plus Rule 5 — cross-package forbidden roots `core`, `infrastructure`, `color_scheme_generator`, `wallpaper_effects_generator`, `icon_templates_renderer`, `config_assembler_engine`, `oci_runtime`; only `provisioning` and `cli_output` are allowed.
- **Verify gate pins `icons.yaml`:** the ITR settings-parse gate invokes `itr list <install>/icon-mappings/icons.yaml --config ~/.config/itr/settings.toml` (not `defaults.yaml`, which lacks a `variants` field and is not listable).

## Non-goals

- The runtime reconciliation core (`src/core/`) and its infrastructure adapters (`src/infrastructure/`).
- The root `dotfiles` CLI (architecture doc §28 Task Group F).
- Persistence of *desktop* state (separate from provisioning's state store).
- A persisted `provisioning-state.json` receipt (deferred to Phase 2+ only if a drift-history need surfaces).
- Content hashing, invalidation, and derived-artifact tracking.
- Writing derived colors into the Hyprland/Hyprpaper/Waybar templates that provisioning only places.
- An `itr dump-config` command for parity with csg/weg.
- Desktop convergence / reactive runtime.

## Success signal

`dotfiles-provision verify` is green and `dotfiles-provision bootstrap --check` is clean against the ten done-criteria; and on a fresh Arch or Debian-family machine, `git clone && ./scripts/bootstrap.sh` completes with verify green, after which `csg`/`weg`/`itr` read and write through the install spine with no per-invocation path flags.

## Assumptions

- Hyprland, Hyprpaper, Waybar, fonts, and the `csg`/`weg`/`itr` CLIs are installable via Ansible on Arch and Debian-family targets.
- `uv` can be pre-seeded by `bootstrap.sh` if absent.
- `$XDG_DATA_HOME` defaults to `~/.local/share` when unset.
- Settings-schema facts (per-tool settings.toml fields, env prefixes, dump commands) are verified against the current codebase and treated as the contract.
- Wallpaper input to CSG and WEG is a positional CLI argument, never a settings field.
- `dotfiles/assets/wallpapers/wallpapers.tar.gz` contains a `default.png` (verified present); it is the source of the default palette and Hyprland/Waybar first-boot colors.
- CSG ships the `conf` (Hyprland) output format (verified working); provisioning emits `colors.conf` directly and does not author a compositor-format template.

## Open Questions

None.

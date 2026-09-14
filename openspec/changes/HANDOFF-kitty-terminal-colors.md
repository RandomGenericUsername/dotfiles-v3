# HANDOFF — Kitty terminal colors follow the wallpaper palette

**Audience:** an orchestrating agent that will implement/verify this work.
**Repo:** `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3`
**Branch:** `master` (no `main`; `origin/HEAD -> origin/master`). Do not create `main`.
**State at handoff:** clean tree (only untracked `src/gui-tools/hypr_pano/` from another
workstream — ignore). `master` is ahead of `origin/master` by 1 (`fd8df77`, the OpenSpec plans).

---

## 1. Ultimate goal

**Every open terminal (kitty) should adopt the runtime wallpaper color scheme when the
wallpaper changes — event-driven, no shell polling, no pty hacks.** Today only *new*
shells pick up the palette, and the daemon cannot recolor any terminal.

The runtime is the single palette producer and already pushes colors to consumers
(Hyprland, AGS, hyprpaper, GTK, rofi). kitty is the missing consumer.

The agreed mechanism (Option 1): **kitty-native config `include` + reload signal**.

```
wallpaper change
  → csg derives palette (colors.kitty artifact)   [Change 1]
  → runtime caches it + exposes current/colors.kitty + signals kitty SIGUSR1  [Change 2]
  → kitty.conf includes current/colors.kitty; kitty reloads → ALL windows re-theme  [Change 3]
```

---

## 2. Why terminals don't re-theme today (evidence, all verified on host)

| Fact | Evidence |
|---|---|
| Host runs **kitty 0.48.2**; `~/.config/kitty/` is **empty** (no `kitty.conf`) | `kitty --version`; `ls ~/.config/kitty` |
| CSG has **no kitty format** | `ColorFormat` enum = `json, sh, css, gtk.css, adw.css, yaml, sequences, rasi, scss, conf`; `conf` is **Hyprland** (`$var = rgb()`) |
| A custom template cannot fill the gap | `TemplateCatalogService.derive` rejects any `colors.*.j2` not in `ColorFormat` (`TemplatesValidationError`) |
| Generated `colors.conf` is **not** kitty syntax | kitty rejects it: `Ignoring invalid config line: '$color0 = rgb(...)'` |
| `.zshrc` only themes **at shell startup** | `dotfiles/config/zsh/.zshrc.j2:33` `(cat "{{COLOR_SCHEME_CURRENT_DIR}}/colors.sequences" &)` is top-level, not a `precmd` hook |
| The live-terminal applier reaches only its **own** tty | `TerminalColorApplier` writes OSC to `/dev/tty`; from the daemon there is no tty → logged failure every converge |
| kitty supports what we need | man `kitty.conf`: `include`, reload via `kill -SIGUSR1 $KITTY_PID`, `auto_reload_config` |

`colors.sequences` is OSC `4;n;#rrggbb` ×16 + `10`/`11`/`12` (fg/bg/cursor) — good for OSC-capable
terminals but never delivered to open kitty windows.

---

## 3. Architecture you must respect

- **Hexagonal runtime** (`src/runtime`): domain (pure) ← ports ← adapters; application use
  cases; composition root in `cli/main.py`. Import boundaries enforced by
  `tests/architecture/test_layering.py`.
- **CSG is the palette producer** (`src/cli-tools/color-scheme-generator`). The runtime
  **must not import** csg (AD-15); it invokes the CLI and consumes artifacts.
- **Palette cache/consumer chain (AD-17)**: `csg_adapter` requests formats and hashes outputs;
  `derive.PALETTE_ARTIFACT_NAMES` is the completeness oracle; `ensure_palette_entry_complete`
  evicts incomplete entries (self-heal); `reconcile` repoints `current/<artifact>` symlinks;
  reloaders run the desktop consumers after a swap.
- **Provisioning = config-in-spine**: `config_copies` (static dirs) + `config_links`
  (`~/.config/<x> -> <install>/config/<x>`); **rendered** (machine-specific) configs live in a
  dedicated role (`zsh_config` is the template to copy). `install_dir` is never defaulted;
  env facts use `ansible_facts.env` (F4 lock).
- **R5 reload semantics**: a reloader returns `True` (applied or vacuous) / `False` (surfaced,
  appears in `ReconcileResult.reload_failures`).
- **No polling anywhere.** Reactive daemon watches the spine (AD-36/39/40) and auto-converges.
- **AD-44**: cross-boundary contracts have one machine-checkable definition; `make contracts-check`.

---

## 4. The three OpenSpec changes (dependency order)

Location: `openspec/changes/`. Each has `proposal.md`, `design.md`, `tasks.md`,
`specs/<capability>/spec.md`, `.openspec.yaml`.

### Change 1 — `add-csg-kitty-color-format` (capability `csg-kitty-format`)
- Add `ColorFormat.KITTY = "kitty"` (`domain/enums.py`).
- Add `defaults/templates/colors.kitty.j2` — **plain kitty syntax**: `background`,
  `foreground`, `cursor`, `color0..15`, `selection_background`, `selection_foreground`, all
  `key #rrggbb`, no metadata, no `$`/`rgb()`.
- Renders to `colors.kitty` via the existing path (`local_processor.py` `colors.<value>.j2`).
- Tests: enum, catalog discovery, exact rendered fragment; parse with
  `kitty +runpy 'from kitty.config import load_config; load_config(["/tmp/colors.kitty"])'` (no
  "Ignoring invalid config line").
- **Cannot be done by a custom template dir alone** — the enum is the authority.

### Change 2 — `add-runtime-kitty-terminal-reload` (capabilities `runtime-palette-artifacts`, `runtime-reloaders`)
- `adapters/csg_adapter.py` (~L284-295): add `--format kitty`; hash `colors.kitty` (~L351-355).
- `application/derive.py` `PALETTE_ARTIFACT_NAMES` (L241-248): add `"colors.kitty"`; include it
  in the written `artifact_hashes`.
- `application/reconcile.py` expected artifacts + `current/` symlink set (L449-454, L491+): add
  `colors.kitty`.
- New `adapters/kitty_reloader.py` (`IDesktopReloader`): enumerate kitty PIDs, send `SIGUSR1`;
  **no kitty ⇒ `True` (vacuous)**; signal failure ⇒ `False` (R5). Injectable pid-source/signaller.
- `cli/main.py` `_build_reloaders` (L364-369): add `KittyReloader`; add
  `include_terminal: bool = True` so the **daemon excludes** `TerminalColorApplier`
  (no controlling tty → kills the per-converge `/dev/tty` failure noise). CLI keeps it.
- Migration: old palette entries lack `colors.kitty` → auto-evicted/re-derived. No manual step.

### Change 3 — `provision-kitty-color-config` (capability `provisioning-terminal-config`)
- New rendered role `kitty_config` (copy `zsh_config`): `kitty.conf.j2` with
  `include <state>/dotfiles/current/colors.kitty`, `include local.conf`, `auto_reload_config no`.
  State path derived as `zsh_config_state_current_dir` (`<XDG_STATE_HOME|~/.local/state>/dotfiles/current`).
- `local.conf` created only if absent (never clobbered).
- Wire: `filesystem` (config home), `config_links` (`~/.config/kitty -> <install>/config/kitty`),
  `packages` (ensure kitty), `verify` (link + `kitty.conf` + include line; add `colors.kitty` to
  expected palette artifacts), a `playbooks/kitty-config.yaml` imported in `bootstrap.yaml`.
- Deterministic reload comes from Change 2 (`SIGUSR1`), so auto-reload is off.

---

## 5. Agreed decisions (locked)

1. **Reload mechanism:** runtime `KittyReloader` sends `SIGUSR1` (deterministic), not relying on
   kitty `auto_reload_config` (a symlink repoint is not a watched-content change).
2. **kitty.conf ownership:** provisioning owns `~/.config/kitty/kitty.conf`; user customizations
   go in the included `local.conf`.
3. **kitty absent:** vacuous success (a terminal may legitimately not be open); surfaced failure
   only when a kitty process exists but signalling fails.
4. **Artifact name:** `kitty` format → `colors.kitty`; `current/colors.kitty`.

---

## 6. Host / environment (for live verification)

- Repo path above; active branch `master`.
- Runtime tool installed at `~/.local/share/uv/tools/dotfiles-runtime`; reinstall with
  `uv tool install --force --no-cache "$PWD/src/runtime"` (same as the `cli_tools` role).
- Daemon: `systemctl --user status dotfiles-runtime-daemon`; unit
  `~/.config/systemd/user/dotfiles-runtime-daemon.service`, `ExecStart … daemon run --activate`
  (activated on purpose — spine edits auto-converge). Owns `org.dotfiles.Events`.
- State current dir: `/home/inumaki/.local/state/dotfiles/current` (symlinks to
  `cache/palettes/<hash>/…`).
- kitty instances: several running; `pgrep -x kitty`.
- `~/.config/kitty/` currently empty (Change 3 creates it).
- Workspace root for commands: run tests with `uv run --directory src/runtime pytest` and
  `uv run --directory src/cli-tools/color-scheme-generator pytest`; provisioning tests
  `uv run --directory src/provisioning pytest -m "not integration and not container_target"`.

---

## 7. Verification (end-to-end acceptance)

After all three land:
1. Change wallpaper (`dotfiles-runtime wallpaper set <img>`) → `current/colors.kitty` repoints to
   the new palette entry.
2. All **open** kitty windows re-theme (KittyReloader `SIGUSR1`); a **new** kitty window starts
   themed.
3. `csg` unit tests green; runtime suite green + layering + `make contracts-check`; provisioning
   unit green; `verify` green.
4. Daemon journal shows no `/dev/tty` failure on converge.

Per-change checks are in each `tasks.md`.

---

## 8. Pitfalls / risks

- **Cache migration:** adding `colors.kitty` to `PALETTE_ARTIFACT_NAMES` invalidates existing
  palette entries; rely on the existing self-heal, do not hand-migrate.
- **Symlink vs watched file:** do not rely on `auto_reload_config`; signal explicitly.
- **kitty does not parse the Hyprland `conf` format** — the kitty template must be plain
  `key #rrggbb`.
- **Config ownership:** do not overwrite a user's hand-written `kitty.conf`; that is why the
  provisioned file includes `local.conf` (created only if absent).
- **kitty package:** confirm it is in the package manifest; add it if missing.
- **Reloader ordering:** append `KittyReloader`; do not disturb the pinned Hyprland→AGS→Hyprpaper
  →Terminal order.
- **`install_dir` / env facts:** mirror `zsh_config`'s fail-loud assert + `ansible_facts.env`
  (F4 lock); never `default()` `install_dir`.
- **Do not** broadcast OSC to `/dev/pts/*` (rejected).

---

## 9. Orchestration guidance

- Work the changes **in order** (CSG → runtime → provisioning); runtime depends on the artifact
  existing, provisioning on the runtime exposing it.
- OpenSpec CLI is **not installed** here; treat the change folders as the spec of record and
  implement/verify directly. Match existing conventions in `openspec/changes/*`.
- Repo conventions: conventional commits; each change is independently landable; keep
  `uv run --directory src/runtime pytest`, layering, and `make contracts-check` green; add tests
  mirroring existing patterns (`tests/unit/...`).
- Do **not** commit or push unless the human asks. The human asked for this handoff to be handed
  to another orchestrating agent — surface a plan, then execute.

---

## 10. Key reference files

- CSG: `src/cli-tools/color-scheme-generator/src/color_scheme_generator/domain/enums.py`,
  `domain/services.py` (catalog), `adapters/local_processor.py`,
  `defaults/templates/colors.rasi.j2` (style reference).
- Runtime: `src/runtime/src/runtime/adapters/csg_adapter.py`,
  `application/derive.py`, `application/reconcile.py`, `adapters/hyprland_reloader.py`
  (reloader pattern), `adapters/terminal_color_applier.py`, `ports/desktop_reloader.py`,
  `cli/main.py` (`_build_reloaders` ~L352-370).
- Provisioning: `src/provisioning/ansible/roles/zsh_config/` (rendered config-in-spine template),
  `roles/config_links/`, `roles/filesystem/`, `roles/verify/`, `roles/packages/`,
  `playbooks/bootstrap.yaml`.
- Plans: `openspec/changes/add-csg-kitty-color-format/`,
  `openspec/changes/add-runtime-kitty-terminal-reload/`,
  `openspec/changes/provision-kitty-color-config/` (each with proposal/design/tasks/specs).

---

## 11. Related landed work (context, already on `master`)

- Phase 5 reactive runtime is complete: daemon (`--activate`), event bus
  (`org.dotfiles.Events1` + `org.dotfiles.Job1`), capture host, watch/reactive converge.
- Recent fixes relevant here: daemon unit `ExecStart` fix + start-on-bootstrap (`21332c2`);
  bar GJS `recursiveUnpack` (`06d90a7`); daemon restart-on-unit-change (`6dd697f`); inotify
  rebuild self-loop/flood fix (`d7954b1`); daemon activated (`94fb9d3`); double-reconcile fix
  (`0f03568`).
- The reactive converge is what makes a spine edit (or palette change) auto-apply — the terminal
  work rides on it.

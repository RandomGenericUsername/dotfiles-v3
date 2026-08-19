# Reality-Check Review — Architecture Spine (Runtime Core, Phase 2)

**Reviewer:** Reality-check reviewer (bmad-architecture reviewer gate)
**Date:** 2026-08-18
**Scope:** ARCHITECTURE-SPINE.md (211 lines) — verify every committed decision was web-researched or reality-checked against the actual project rather than asserted from training data.
**Method:** Read the full spine; read docs/99-dotfiles-hexagonal-architecture.md (§Per-Tool Settings Contract 305-327, §8.0/§9/§11/§15/§16/§19-26), docs/01-dotfiles-provisioning-phase1-plan.md, docs/02-config-in-spine-pattern.md; inspected source at src/cli-tools/{color-scheme-generator,wallpaper-effects-generator,icon-templates-renderer}, src/shared/config-assembler-engine, src/provisioning/ansible/roles/compositor_configs; web-checked Hyprland wiki + hyprpaper repo for reload mechanisms; cross-checked pinned versions in uv.lock.

---

## Verdict

The spine's committed decisions are overwhelmingly grounded in the actual project: every named technology exists, every env-var override chain was verified in code (not just docs), and the provisioning/runtime boundary claims match the as-built roles. No critical or blocking errors. Three medium-strength findings on XDG placement semantics, an ITR env-key precision footgun, and an unvalidated hyprpaper swap mechanism; plus minor drift in the AD-17 verify-criterion phrasing.

---

## 1. Checked items — confirmed real and consistent

### 1.1 Python, Typer, stdlib JSON store, SHA-256
- **Real, current, fits.** Python 3.12/3.14 in use across the repo (`requires-python = ">=3.14"` for csg & itr, `">=3.12"` for weg & provisioning; `cpython-314` artifacts present). Typer 0.27.0 pinned in `uv.lock` (2026-07-15) for the tool packages and listed as a provisioning dep. The spine does not pin versions — appropriate at this altitude.
- stdlib `json` store (AD-3) and `hashlib`/SHA-256 (AD-8) are stdlib-only; no third-party persistence dependency is introduced. AD-8's "versioned hashing" (`hash_algorithm` in meta.json) is a sound guard against silent cache invalidation.

### 1.2 AD-7 env-var override chains — verified in CODE, not just docs
All three tools resolve settings through `config-assembler-engine` (`src/shared/config-assembler-engine`), and the `PREFIX__SECTION__KEY` chain is real:
- `OsEnvironmentReader` (`config_assembler_engine/adapters/env_reader.py`) matches `PREFIX__` + lowercases the remainder — confirms the `__` separator format the spine uses.
- **CSG:** `ResolutionPolicy(env_prefix="COLORSCHEME")` + `OverrideRule("output.directory", …)` → **`COLORSCHEME__OUTPUT__DIRECTORY`** is a real, working override. ✓
- **WEG:** `ResolutionPolicy(env_prefix="WALLPAPER")` + `OverrideRule("output.directory", …)` → **`WALLPAPER__OUTPUT__DIRECTORY`** is real. ✓ (Note: WEG also uses a second prefix `WALLPAPER_EFFECTS` for the effects-config-file path — not used by the spine, but consistent.)
- **ITR:** `ResolutionPolicy(env_prefix="ICON_RENDERER")` → **`ICON_RENDERER__*`** real. ⚠️ See Finding 2 — the concrete output key is `ICON_RENDERER__OUTPUT__OUTPUT_DIR`, not `__OUTPUT__DIRECTORY`.
- This matches docs/99 "Per-Tool Settings Contract" (305-327) exactly (prefixes, XDG subdirs, ITR `[output] output_dir`, WEG `[processing] temp_dir`).

### 1.3 Tools exist and are the ones the runtime drives
- `src/cli-tools/color-scheme-generator`, `wallpaper-effects-generator`, `icon-templates-renderer` all exist with `src/<pkg>/{domain,ports,adapters,cli,application}` layout. The forbidden-import set in AD-15 matches the actual module names. `config-assembler-engine` and `oci-runtime` exist under `src/shared/`. ✓

### 1.4 Desktop reload tools
- **Hyprland `hyprctl reload`** — real (re-reads `hyprland.conf`, including its `source = ~/.config/hypr/colors.conf` line; that source line is confirmed present in the compositor_configs skeleton vars).
- **Waybar restart** — real; Waybar has no in-process reload, process restart is the standard approach.
- **Hyprpaper reload** — `hyprctl hyprpaper reload` re-reads `hyprpaper.conf`; confirmed the tool is IPC-controlled (hyprpaper repo README) and installed as a system binary (plan done-criterion 2). ⚠️ See Finding 3 for the swap-path caveat.

### 1.5 XDG_STATE_HOME / XDG_DATA_HOME
- `$XDG_DATA_HOME/dotfiles/` (~/.local/share) as the install spine: correct standard usage and matches docs/99 §9 / docs/01 line 58 and the provisioning roles.
- `$XDG_STATE_HOME/dotfiles/` (~/.local/state) as runtime-owned root: the default is correct and the variable is real (freedesktop.org Base Directory spec). ⚠️ But see Finding 1 — the cache placement under it deviates from the standard's semantics.

### 1.6 AD-17 provisioning delta — grounded in as-built roles
- `compositor_configs` role currently **copies** `generated/palettes/colors.conf → <install>/config/hypr/colors.conf` and `colors.gtk.css → <install>/config/waybar/colors.css` (vars/main.yml fragment_copies, `force: true`), with `~/.config/{hypr,waybar,hyprpaper}` as dir-level symlinks into the spine. The spine's delta (flip the two fragment files to symlinks into `current/`, flip hyprpaper.conf wallpaper path, settings ITR color_scheme path) is exactly the right change to make — grounded, not invented.
- `hyprpaper.conf` is confirmed flat-static (`preload = ~/.local/share/dotfiles/wallpapers/default.png`) with an in-file comment saying Phase 2 re-bakes it — consistent with AD-17.
- ITR `[color_scheme] path` env override `ICON_RENDERER__COLOR_SCHEME__PATH` exists (itr `_helpers.py` / `icon_renderer.py`). ✓

### 1.7 AD-12 (sync/imperative), AD-2/AD-8 (content-addressed SHA-256), AD-10 (derivation graph), AD-15 (bounded context)
- All trace to concrete docs/99 sections: §22 (sync, no daemon/async/event bus), §26 (don't-build table), §15 (hash contents not filenames), §16 (derived artifacts), §19/§20 (port/adapter table incl. `IDesktopReloader`), §11 (provisioning/runtime boundary). ✓

---

## 2. Findings (tiered)

### F1 — HIGH: `cache/` under `$XDG_STATE_HOME` misuses XDG semantics (AD-5/AD-3)
The spine bundles `cache/` + `current/` + `current.json` + `history.jsonl` all under `$XDG_STATE_HOME/dotfiles/`. The XDG Base Directory spec reserves:
- `$XDG_STATE_HOME` for **non-essential state** (history, logs, recent documents) that must survive reboots,
- `$XDG_CACHE_HOME` for **non-essential re-derivable data** — i.e., caches.

A content-addressed cache of derived artifacts, which AD-3 itself calls "re-derivable except history," is precisely the "cache" category. As written, AD-5 commingles delete-safe data (cache) with must-not-lose data (history.jsonl per AD-4) in one tree, so a user/tool doing spec-correct cleanup (e.g. clearing `~/.cache` or `~/.local/state`) hits the wrong or the wrong-sized boundary either way. **Recommend:** split `cache/` + `current/` symlinks → `$XDG_CACHE_HOME/dotfiles/` (default `~/.cache/dotfiles/`) and keep `current.json` + `history.jsonl` under `$XDG_STATE_HOME/dotfiles/` (AD-4's must-not-lose piece stays in state). If the single-tree design is deliberate, add an explicit justification and keep the two homes cleanly documented. (Either way the default paths stated in AD-5 are correct per the spec.)

### F2 — MEDIUM: ITR output env key diverges from the sibling pattern — pin the concrete key (AD-7/AD-17)
AD-7 gives literal keys for CSG and WEG (`…__OUTPUT__DIRECTORY`) but only `ICON_RENDERER__*` for ITR. The real ITR output override is **`ICON_RENDERER__OUTPUT__OUTPUT_DIR`** (field `output.output_dir`, per itr `_helpers.py`, `icon_renderer.py`, and docs/99 line 315). The wildcard is technically safe, but an implementer reading AD-7's sibling literals will very plausibly write `ICON_RENDERER__OUTPUT__DIRECTORY` — a silent no-op that keeps writing to the provisioning-owned dir. **Recommend:** state the exact key `ICON_RENDERER__OUTPUT__OUTPUT_DIR` (and the `ICON_RENDERER__COLOR_SCHEME__PATH` used in AD-17) in AD-7.

### F3 — MEDIUM: hyprpaper wallpaper-swap mechanism not validated on the target version (AD-17)
The design swaps the wallpaper by repointing `current/wallpaper.png` + hyprpaper.conf path + reload. `hyprctl hyprpaper reload` does re-read `hyprpaper.conf`, but preload/apply-on-reload behavior has differed across hyprpaper versions; the tool's documented channel for a wallpaper change is its IPC (`hyprctl hyprpaper wallpaper <output>,<path>`). Repointing a symlink under the `preload`/`wallpaper` line and relying on config reload should be validated against the installed hyprpaper (Arch package) in the Phase 2 spike before AD-17 is treated as committed. Add an explicit reality-check task. (Related: the current hyprpaper.conf bakes `~/.local/share/dotfiles/wallpapers/default.png` and its comment flags Phase 2 as the re-bake owner — consistent with AD-17's delta.)

### F4 — LOW: AD-17's "verify criterion 6" phrasing drifts from the actual criterion
docs/01 line 251 defines criterion 6 as: `<install>/generated/palettes/colors.conf` AND `colors.yaml` both exist and parse (plus an `$accent == $color1` check). AD-17 compresses this to "generated/palettes OR current/colors.yaml" — an OR where the source is an AND, and drops the `.conf` existence/parse check. Align the wording so the provisioning-delta spec and the done-criterion stay referentially identical.

### F5 — LOW: two preconditions worth making explicit in the spine
- **WEG `[processing] temp_dir` is NOT env-overridable** — it is absent from WEG's `_ALL_SETTINGS_FIELDS`/`_OVERRIDE_RULES` (`assembled_config_resolver.py`). AD-7 only claims the output dir, so nothing is wrong today, but a note that temp-dir isolation requires a CLI flag or settings edit prevents a future surprise.
- **Runtime Python floor unspecified.** The spine's new `src/runtime` package doesn't state a `requires-python`. csg/itr demand ≥3.14 while weg/provisioning demand ≥3.12; since the tools are subprocesses this is harmless, but pin the runtime floor (≥3.12) at spec/epics so the layering-test stdlib-allowlist story (AD-14) has a concrete interpreter target.

### F6 — INFO: reload commands asserted without citation
`hyprctl reload`, Waybar restart, and hyprpaper reload are all real (web-verified against the Hyprland wiki / hyprpaper repo), but the spine cites no sources for them. Recommend one source line in AD-17's Cons* column so the next reviewer doesn't redo this check. The CSG/ITR determinism caveat already in Deferred is the right call — keep it, it is a genuine reality-gap the spine correctly refuses to paper over.

---

## 3. Summary table

| # | Sev | Item | Reality-check outcome |
|---|---|---|---|
| F1 | HIGH | cache under XDG_STATE_HOME | Standard deviation; split cache→XDG_CACHE_HOME or justify |
| F2 | MED | ITR env key is `__OUTPUT__OUTPUT_DIR` not `__OUTPUT__DIRECTORY` | Wildcard OK but footgun; pin the literal |
| F3 | MED | hyprpaper symlink+reload swap unvalidated | Verify against installed version / use IPC |
| F4 | LOW | verify criterion 6 OR-vs-AND drift | Align wording with docs/01 |
| F5 | LOW | WEG temp_dir not env-overridable; runtime py floor unstated | Document both |
| F6 | INFO | reload tools real but uncited; determinism caveat already deferred | Add source refs |

**Overall:** no critical defects; the spine is a faithful, code-grounded projection of the actual project. Address F1–F3 before locking spec/epics.

# Rubric-Walker Review — ARCHITECTURE-SPINE.md

**Spine:** dotfiles-repo-v3 Runtime Core (Phase 2), 2026-08-18
**Reviewer role:** rubric-walker (good-spine checklist)
**Method:** read the full spine (211 lines), then verified every checklist item against the brownfield (`src/provisioning/`, `src/provisioning/ansible/roles/*`, `src/shared/oci-runtime/`, `dotfiles/provisioning/*`, `docs/99`, provisioning's `tests/architecture/test_layering.py`).

---

## Checklist results

### 1. Fixes the real divergence points for the level below — mostly, with one critical miss and one silent dimension

The spine fixes the genuine feature-altitude divergence points and does it well:

- **Hexagon layout / layering** — AD-1, AD-13, AD-14, AD-15. Verified exact against `src/provisioning/tests/architecture/test_layering.py`: the domain stdlib allowlist (`dataclasses, enum, typing, collections, collections.abc, functools, re, __future__`), banned stdlib, Path-FS-method ban, ports-ABC rule, and the Rule-5 cross-package forbidden set (`core, infrastructure, color_scheme_generator, wallpaper_effects_generator, icon_templates_renderer, config_assembler_engine, oci_runtime`) match the provisioning test verbatim. AD-13 correctly resolves the docs/99 §9 drift (`src/core/` + `src/infrastructure/` → nested hexagon).
- **Cache correctness** — AD-2/AD-8/AD-10 keying matches the stated derivation graph (palette = hash(wallpaper, csg templates); effects = hash(wallpaper, effects catalog); icons = hash(palette, icon templates, icon mappings)).
- **Boundary** — AD-5 holds against the brownfield: provisioning creates only `$XDG_STATE_HOME` (base), not `$XDG_STATE_HOME/dotfiles/`, so "provisioning never writes under state_root" is technically true.
- **Execution model** — AD-12 ratifies docs/99 §22 exactly (synchronous, no daemon/async/event-bus/distributed).

**Missed divergence points:**

- **CRITICAL — tool-integration contract (AD-7), see Finding C1.** The one brownfield decision that MUST be ratified and is not.
- **HIGH — the operational/environmental envelope is entirely silent** (checklist item 6): deployment & environments, infra/provider (container engine), operations. See Finding H1.
- Medium — CSG/ITR determinism is deferred but underpins the cache-key trust model (Finding M1).
- Medium — AD-17 introduces provisioning deltas to a *completed* phase without scoping them (Finding M3).

### 2. Every AD's Rule is enforceable and prevents its stated divergence — **one AD fails**

All ADs except AD-7 are enforceable: their Rules name testable mechanisms, most already proven by provisioning's mechanical test. **AD-7 fails both enforceability and prevention** — its uniform env-override mechanism is only verified for one of three tools, and it omits the container-mode contract. See C1.

### 3. Deferred items — one interacts with a live invariant

CLI packaging (spec-time, acceptable), done-criteria (process item, acceptable), cache eviction (Phase 3, acceptable), IStateRepository API (Phase 3, acceptable) are legitimate deferrals. **CSG/ITR determinism verification is the boundary case** (M1): it is deferred to "before the cache key is trusted," but the fallback ("add a fixed seed to the cache key") changes the AD-8 hash schema, so it is a design fork being postponed rather than decided.

### 4. Named tech is verified-current — **pass**

- Python ≥3.12 — `src/provisioning/pyproject.toml` (`requires-python = ">=3.12"`, `.venv` runs 3.12).
- Typer — provisioning cli uses `typer` (`cli/main.py:20,50`), dep `typer>=0.12`.
- Hyprland / Waybar / Hyprpaper — `dotfiles/provisioning/packages.yaml` installs `hyprland`, `hyprpaper`, `waybar`; skeleton configs exist under `dotfiles/config/{hypr,hyprpaper,waybar}/`.
- csg / weg / itr — `dotfiles/provisioning/cli-tools.yaml` (installed via `uv tool install`, `~/.local/bin`); roles `default_palette` (csg), `assets` (weg dump-effects), `icons` (itr render) drive them; they live in `src/cli-tools/` per docs/99 §9.
- JSON store — new for runtime; no brownfield contradicts it except docs/99 §23's "Initially: SQLite" (see M2).

No stale or wrong tech names found.

### 5. Ratifies rather than contradicts the brownfield — **one exception**

Ratified correctly: nested hexagon + mechanical layering test, provisioning-drives-Ansible, install spine at `$XDG_DATA_HOME/dotfiles/` (verified in `filesystem.yaml` and the hyprpaper skeleton `preload = ~/.local/share/dotfiles/wallpapers/default.png`), settings.toml rendered into the spine (`install/config/{color-scheme-generator,weg,itr}/settings.toml` per `settings/templates/*.j2`), palette outputs `colors.conf`/`colors.gtk.css`/`colors.yaml` (default_palette + compositor_configs copy of fragments into `~/.config/hypr/colors.conf` and `~/.config/waybar/colors.css`).

**Not ratified:** the container-mode product decision (2026-08-12) for csg/weg — AD-7 is silent on it (C1).

### 6. Dimensions owned by feature altitude — **the operational/environmental envelope is left silent**

Deployment & environments, infra/provider strategy (container engine for csg/weg; runtime install/update path), and operations (logging, error surface, notifications, whole-reconcile concurrency, lockfile recovery) are all undecided. The spine never even states the single-machine/single-user assumption it implicitly makes. This is the rubric's item-6 finding (H1).

---

## Findings

### C1 (CRITICAL) — AD-7's Rule is neither enforceable as written nor does it prevent its stated divergence

The spine's AD-7 Rule is: "runtime directs tool output per cache entry via env-prefix overrides (`COLORSCHEME__OUTPUT__DIRECTORY`, `WALLPAPER__OUTPUT__DIRECTORY`, `ICON_RENDERER__*`)." Verified against the brownfield:

1. **Container mode is a product decision AD-7 drops.** csg and weg run in container mode (`csg-settings.toml.j2` `[runtime] mode = "container"`; `weg-settings.toml.j2` `[runtime] mode = "container"`). The host never installs pywal/imagemagick. Provisioning's `default_palette` role forces `COLORSCHEME__RUNTIME__MODE=container` and detects the engine (podman → docker → fail-loud, `COLORSCHEME__CONTAINER__ENGINE`). A runtime implementing only output-dir overrides would run csg/weg in local mode and fail, or use the settings' hardcoded `engine = "podman"` on a docker-only machine and fail. The engine-detection strategy is owned by no AD.
2. **The env-override mechanism is verified for exactly ONE tool.** `COLORSCHEME__OUTPUT__DIRECTORY` is used by provisioning (default_palette). `WALLPAPER__OUTPUT__DIRECTORY` (weg) and `ICON_RENDERER__*` (itr) are never used anywhere in the brownfield — provisioning invokes weg as `weg dump-effects --output <path>` and itr as `itr render <mappings> --config <settings.toml>`. Whether these env prefixes exist at all is unverified; `ICON_RENDERER__*` is a wildcard, not a rule.
3. **Per-call input redirection is missing.** itr consumes `[color_scheme].path = install/generated/palettes/colors.yaml` from its untouched settings.toml; a per-cache-entry itr call must redirect that input to the palette entry, not just the output dir.
4. **itr is local-mode; csg/weg are container-mode** — the same runtime code path handles three tools with different env contracts. The spine gives the lower level no decision on how this asymmetry is handled (per-tool env contract table, adapter owning it).

This is precisely an unratified brownfield decision. Fix: AD-7 must carry the container-mode + engine-discovery contract (or explicitly delegate engine discovery to a runtime adapter with the podman→docker→fail-loud rule), name concrete per-tool env keys (verified against each tool), and specify the itr `color_scheme.path` input redirection.

### H1 (HIGH) — The operational/environmental envelope is an entirely silent dimension

Checklist item 6. The spine decides nothing about:

- **Deployment & environments:** single-machine/single-user is implicitly assumed but never decided; there is no decision on how the runtime package is installed/updated (docs/99 §26 lists "runtime package installation → belongs to provisioning" as a thing to avoid building now, so the runtime install path is currently *unowned* — nobody's job).
- **Infra/provider strategy:** container engine for csg/weg (see C1); reliance on `~/.local/bin` uv-tool-installed binaries (csg/weg/itr on PATH) is assumed but never owned by an AD.
- **Operations:** no logging/error-surface decision, no user-feedback path (Hyprland notifications), no whole-reconcile concurrency decision (AD-9 covers cache-population races only; two concurrent reconciles can still race on `current.json` last-writer-wins and on history ordering — the spine never says whether that is acceptable), no stale-lockfile/partial-reconcile recovery story beyond AD-6's "store lags, recoverable on next run."

Two stories building "reconcile" and "wallpaper set" could diverge on each of these with no spine hook. Fix: add an AD (or explicit decisions under Deferred/Open Questions) for environments, runtime install/update ownership, container-engine strategy, and the ops surface.

### M1 (MEDIUM) — CSG/ITR determinism is deferred but it underpins the cache-key trust model

AD-2/AD-8/AD-10 make cache correctness depend on hash-of-inputs keying. If csg is non-deterministic, a regenerate produces different output under the same key and the cache silently serves drift — the exact failure AD-2 claims to prevent. The Deferred note ("must be verified before the cache key is trusted; if non-deterministic, add a fixed seed to the cache key") is a design fork (it changes the AD-8 hash schema) being postponed, not decided. The spine's own mitigation (AD-10 nodes record `artifact_hashes`) should be elevated to a Rule: a reconcile that finds a recorded `artifact_hashes` mismatch under the same input hash must regenerate and log. Either gate the determinism check into Phase 2 or make the artifact-hash drift check a binding rule now.

### M2 (MEDIUM) — AD-3 silently overrides docs/99 §23 ("Initially: SQLite")

docs/99 §23 recommends SQLite for Phase 2 persistence and §26 lists "multi-backend persistence" as avoid-now. AD-3 flips to a JSON store without flagging the deviation from a cited source. The choice is defensible, but the AD should record the deviation (Prevents/Binds) so the lower level doesn't re-litigate or silently reintroduce SQLite.

### M3 (MEDIUM) — AD-17 binds deltas to a *completed* provisioning phase that the spine never scopes

AD-17's runtime side is enforceable, but its implementation requires provisioning changes to a DONE phase: compositor_configs fragment copies → symlinks, hyprpaper conf wallpaper path → `current/wallpaper.png`, itr settings `color_scheme.path` → `current/colors.yaml`, and a relaxation of verify done-criterion 6 (`generated/palettes OR current/colors.yaml`). The spine never declares these as Phase 2 provisioning-delta scope — it ties directly into the deferred "Phase 2 done-criteria," so epics could assume provisioning stays frozen while AD-17 requires it to move. Related: AD-11 defines only two bootstrap states; the third (neither provisioning output nor `current.json` present — a fresh machine before any provision) is undefined.

### L1 (LOW) — CLI-packaging deferral is a real epics fork

Provisioning already ships `dotfiles-provision` (`[project.scripts]` in `pyproject.toml`). The deferred umbrella-`dotfiles` vs `dotfiles-runtime` fork is a legitimate spec-time decision, but the spine should note the name-collision risk so a story doesn't squat on a bare `dotfiles` binary.

---

## Verdict

The spine is unusually strong on structure and brownfield-ratification — hexagon/layering/ports/boundary rules are verified verbatim against provisioning's mechanical test, the derivation graph matches the stated context facts, and all named tech is current — but it is not gate-ready: AD-7 drops the csg/weg container-mode and engine-discovery contract and assumes a uniform env-override mechanism that is verified for only one of three tools (critical), and the operational/environmental envelope (deployment, infra/provider, operations) is a wholly silent dimension (high). Fix C1 and decide H1 before epics; absorb M1–M3 into the spine or explicit Phase 2 scope.

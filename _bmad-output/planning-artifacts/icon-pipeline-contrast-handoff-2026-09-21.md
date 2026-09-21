# Icon Pipeline + Contrast Guard — Context Handoff

**Date:** 2026-09-21
**Status:** Investigation complete, no implementation performed
**Trigger:** Owner manually ran ITR against the installed spine's `icons.yaml` (wifi group) and observed that high contrast "is not being applied properly — the whole icon has the same value for all the placeholders." Screenshot showed a uniformly dark wifi glyph on the light bar.
**Question to resolve:** Was the contrast guard implemented as a quick workaround that fails to account for its dependents, and how *should* high-contrast variants be generated?
**Branch context:** `feat/pipewire-audio-ags` worktree (rebased onto main `3d42dfd0`); the icon work in flight adds `microphone` group + `volume`/`microphone` BAR_GROUPS membership + a proposed (not yet built) panel-pinned variant scheme.

---

## 1. System map (verified paths)

```
REPO (authoritative, version-controlled)
  dotfiles/assets/icon-templates/<group>/<variant>/icon.svg   # SVG with {{PLACEHOLDER}}s
  dotfiles/config/icon-template-color-scheme-mappings/
    icons.yaml      # groups → color_mappings + variants (template/output)
    defaults.yaml   # vocabulary: PLACEHOLDER → palette-key defaults
  dotfiles/config/ags/icons.json   # GENERATED from icons.yaml (nice_json, sorted keys)
                                   # — regenerated, never hand-edited. Verified
                                   # byte-identical to yaml→json conversion.

        │  assets role (ansible.posix.synchronize, DELETE — converges spine to repo)
        ▼
SPINE (generated deployment target, NOT a place to edit)
  ~/.local/share/dotfiles/icon-templates/...
  ~/.local/share/dotfiles/icon-mappings/icons.yaml (+ defaults.yaml)

        │  runtime seed: `dotfiles-runtime wallpaper set <png>`
        ▼
CONTRAST GUARD (staging-only, temp dir — never written back to spine)
  reads:  spine icons.yaml + current/colors.yaml + sampled wallpaper top-band
  writes: overlay icons.yaml (group-level COLOR_FOREGROUND/JOIN retargets only)
          + meta.json decisions[] (group/placeholder/from/to/ratio_before/after)

        │  itr render (overlay as input when guard fires, else spine directly)
        ▼
CACHE (content-addressed — key hashes the EFFECTIVE mappings bytes)
  ~/.local/state/dotfiles/cache/icons/<hash>/  (*.svg + meta.json)

        │  current/icons → symlink to one cache entry
        ▼
CONSUMERS (all read the same files)
  AGS bar (transparent, over wallpaper) via IconRegistry → current/icons/*.svg
  AGS panels/popups (dark glass) via IconRegistry → SAME files
  Capture tool, notifications overlay, wallpaper selector → SAME files
```

**Critical invariant:** one rendered file per icon output serves ALL consumers. There is no per-consumer render. Whatever the guard does to a group affects every surface using that group.

---

## 2. Placeholder resolution mechanics (how ITR turns templates into SVGs)

Merge precedence (highest → lowest), verified in
`src/cli-tools/icon-templates-renderer/.../domain/services.py`
(`MappingResolutionService`, "Priority (highest to lowest): variant > group > vocabulary"):

1. `variants[].color_mappings` (per-variant override)
2. group-level `color_mappings`
3. `defaults.yaml` vocabulary

Substitution is plain regex `_PLACEHOLDER_RE = \{\{(\w+)\}\}` over the whole SVG text — works in `fill=""`, `stroke=""`, or anywhere. Unresolved placeholders are an error unless `--unsafe`.

`itr render` requires, per group: `--template-dir`, `--color-scheme`, `--output-dir` (or a `settings.toml` via `--config` supplying all three). **A manual `itr render` without `--color-scheme` does NOT use the live palette** — it falls back to settings discovery/bundled defaults. A manual render also **never applies contrast** (the overlay exists only as a temp dir during `wallpaper set`).

`itr mapping set/show` performs comment-preserving single-entry edits on the YAML. It edits whichever file you point it at — including the spine copy.

---

## 3. Contrast guard mechanics (what it does and does NOT do)

- **Trigger:** only inside `wallpaper set` / runtime seed. Never on login, never on `itr` manual runs, never watches files.
- **Inputs:** spine `icons.yaml` text, `current/colors.yaml`, sampled top-strip luminance (~bar height, Pillow) or palette `background` fallback.
- **Scope (structural, verified in `derive.py` `_scan_group_color_mappings` / `_patch_overlay_text`):** lines at exactly indent-4 under a group-level `color_mappings:` section, placeholder in `(COLOR_FOREGROUND, COLOR_JOIN)`, group in `BAR_GROUPS`. Variant blocks live at indent 6+ → **structurally unreachable**. Literals (`#rrggbb`) pass through. `bar_mappings` untouched.
- **Current BAR_GROUPS** (`src/runtime/.../domain/icon_contrast.py`): battery, network, btop, thunderbird, tray, ui, power-menu, email-client, wallpaper-selector, settings, **volume, microphone** (last two added by the audio work).
- **Outputs:** staged overlay + `meta.json` `contrast` record. Guard failure degrades to spine mappings with a warning (never hard-fails `wallpaper set`).
- **Cache key** hashes the overlay bytes → a contrast flip is a new cache entry; identical inputs hit cache.

---

## 4. The wifi incident — observed facts (not hypotheses)

1. **Spine file was hand-modified.** `diff repo vs ~/.local/share/dotfiles/icon-mappings/icons.yaml` shows exactly one delta:
   `network.COLOR_CROSS: color13` (repo) → `color15` (spine).
   The guard CANNOT have done this — `COLOR_CROSS` is not in the retarget tuple. This is a manual edit (owner's ITR run or the mapping editor).
2. **Guard DID fire for network.** Active cache entry meta: `network COLOR_FOREGROUND color15 -> background`, ratio 1.0 → 10.44, `backdrop_source: sampled`.
3. **Rendered `wifi-full-default.svg` contains a single fill: `#201f0e`** (dark). Its template has exactly ONE placeholder (`COLOR_FOREGROUND` ×4 paths), no opacity tiers. **wifi-full is monochrome by template design** — four arcs, one token.
4. **The screenshot (uniform dark wifi glyph on light bar) is therefore the CORRECT output** of: guard retarget (FOREGROUND→background) applied to a single-token template. It is not, by itself, evidence of malfunction.
5. **The spine edit only affects `wifi-no-internet`-family variants** (the sole `COLOR_CROSS` consumers) — collapsing their accent/detail distinction to the foreground token. If the owner observed *those* icons going monochrome, the cause is the manual edit, not the guard.
6. **The manual edit will be destroyed** on next bootstrap: the assets role rsyncs with delete (`synchronize`, converged-host rationale 2026-09-07). Spine is not a durable place for experiments. The documented loop is repo → bootstrap → spine.

---

## 5. "High contrast not applied properly" — ranked hypotheses

- **H1 (most likely): manual `itr render` without `--color-scheme`/overlay.** A hand-run render uses bundled/discovered settings, not the live palette, and never the contrast overlay — so its output matches neither the bar nor the panels. *Check:* re-run with explicit `--color-scheme $HOME/.local/state/dotfiles/current/colors.yaml --template-dir <spine-or-repo-templates> --output-dir <tmp>` and diff against `current/icons/`.
- **H2: editing the spine instead of the repo.** Any spine edit is invisible to `git`, invisible to review, and clobbered by the next bootstrap. The one-line CROSS diff above is exhibit A.
- **H3: expecting per-placeholder contrast.** The guard retargets at group/placeholder granularity (FOREGROUND→one token). It does not — and was never designed to — assign *distinct* contrast tokens per shape within one icon. Multi-tone icons must encode tone in the template (opacity groups, second placeholder + mapping) at authoring time.
- **H4: expecting the guard to run outside `wallpaper set`.** It doesn't. Changing wallpaper-adjacent state without re-seeding leaves stale renders by design.
- **H5 (ruled out for wifi-full): template defect.** Verified the template is single-token by construction; no defect.

---

## 6. Workaround-vs-architecture assessment

**Principled (keep):**
- Structural scope guard (indent-based, not name-based) with unit tests pinning exemptions (`camera-accent`, `warning-caution`, `ui/search` precedent documented in-manifest).
- Content-hash cache keyed on effective mappings; staging-only overlay (spine stays read-only); graceful degradation with warning.
- `meta.json` decisions audit trail per cache entry.
- Single-source templates; `icons.json` as pure generated projection (byte-verified).

**Fragile / workaround-smelling (the real debt):**
1. **One render serves bar + panels.** The guard optimizes icons for the wallpaper backdrop, but panels sit on dark glass. Any group consumed in both places (`volume`, `microphone`, and now-observed `network` if the net popup uses it) is wrong in exactly one of them on every light wallpaper. This is THE architectural gap — not the guard's scope logic, but its single-consumer assumption. The screenshots in the audio/panel work (washed speaker glyphs on dark cards) are this, not a guard bug.
2. **Manual ITR runs are unsupported but unguarded.** Nothing stops (or warns) a hand-run against the spine with wrong settings; the failure mode is silent wrong-color output. `itr` cannot know the "live" inputs (current palette path, overlay) without flags the user must remember.
3. **Spine editability.** The spine is writable and tools (`itr mapping set`, the color-mapping editor without a checkout) will write it, yet bootstrap rsync-deletes divergences. Divergent spine state is undetectable until render output looks wrong.
4. **No per-variant contrast.** `decide_overrides` works at (group, placeholder) granularity. An icon needing *two* contrast-aware tones (e.g. base + detail) cannot express that; authors must use opacity or a non-retargeted second token.

---

## 7. How high-contrast variants SHOULD be generated (recommended design)

**Option A — panel-pinned variant overrides (recommended; zero runtime changes):**
- For each dual-use variant, add a `panel-*` sibling reusing the SAME template, with explicit variant-level `COLOR_FOREGROUND: <bright-token>` (e.g. `foreground`), outputs `*-panel-*.svg`. Concrete set: `volume`: panel-muted/lowest/low/medium/max (5); `microphone`: panel-mic-on/off (2).
- Panels resolve `panel-*`; bar keeps bare variants. The existing exemption rule does the work — no guard, cache, or registry changes.
- Regenerate `icons.json` via the established `yaml → nice_json(sorted)` transform (byte-diff must show only additions).
- Extend `verify_icons_samples` (+ pinning test) and add one overlay test asserting panel variants survive retarget (mirror the `camera-accent` test).
- Cost: ~7 outputs per wallpaper set; one naming convention to maintain (`panel-` prefix). Document it next to the `ui/search` precedent.

**Rejected:** per-consumer renders (breaks content-hash cache + single registry path); CSS tinting in panels (loses palette fidelity); exempting the groups (sacrifices the verified-correct bar); teaching the guard about panels (machinery duplicating what the exemption rule already provides).

**Prerequisite renames/notes:** `settings/*` is bar-only (verified — sole consumer `bar/widgets/settings.tsx`), so no panel variants needed there. `battery`/`network`/etc. are bar-only; untouched.

---

## 8. Verification playbook (proves each link)

```bash
# 1. Spine == repo? (must be empty; a diff means hand-edits that bootstrap will clobber)
diff dotfiles/config/icon-template-color-scheme-mappings/icons.yaml \
     ~/.local/share/dotfiles/icon-mappings/icons.yaml
# 2. What the guard actually decided (live entry):
python3 -c "import json,glob; [print(x) for m in glob.glob('$HOME/.local/state/dotfiles/cache/icons/*/meta.json') for x in json.load(open(m)).get('contrast',{}).get('decisions',[])]" | sort -u
# 3. What a variant really rendered to:
grep -oh 'fill="#[0-9a-fA-F]*"\|stroke="#[0-9a-fA-F]*"' ~/.local/state/dotfiles/current/icons/<name>.svg | sort -u
# 4. Manual render that MATCHES production (explicit everything, temp dir):
tmpdir=$(mktemp -d); itr render <icons.yaml> --icon <group> --template-dir <templates> --color-scheme "$HOME/.local/state/dotfiles/current/colors.yaml" --output-dir "$tmpdir"; grep -h -o 'fill="#[0-9a-fA-F]*"' "$tmpdir"/*.svg | sort -u; rm -rf "$tmpdir"
# 5. Template placeholder inventory for any icon:
grep -oh "{{[A-Z_]*}}" <template.svg> | sort | uniq -c
```

---

## 9. Open decisions for the owner

1. Approve Option A (panel-pinned variants) and the `panel-*` naming, or choose an alternative from §7.
2. Confirm the wifi spine edit (`COLOR_CROSS color13→color15`) should be **reverted** (repo reconverges on next bootstrap anyway) — and whether the no-internet accent distinction should be preserved as authored.
3. Decide whether manual spine edits get a guardrail (e.g. `itr` warning when target is under the install spine, or a verify check diffing spine vs repo mappings) — currently silent divergence is possible.
4. Decide whether the `BAR_GROUPS` dual-use rule gets documented as an invariant ("any group consumed on dark glass MUST expose panel-pinned variants") so future groups (tray overrides, power-menu, email-client) don't repeat this.

---

## Appendix — file inventory (all paths repo-relative unless ~)

- Templates: `dotfiles/assets/icon-templates/<group>/<variant>/icon.svg`
- Manifest: `dotfiles/config/icon-template-color-scheme-mappings/{icons.yaml,defaults.yaml}`
- Generated manifest: `dotfiles/config/ags/icons.json` (= `to_nice_json(yaml)`, sorted keys)
- Guard domain: `src/runtime/src/runtime/domain/icon_contrast.py` (`BAR_GROUPS`, `PLACEHOLDERS`, `decide_overrides`)
- Guard pipeline: `src/runtime/src/runtime/application/derive.py` (`_scan_group_color_mappings`, `_patch_overlay_text`, `_effective_icon_mappings`, `_stage_icon_overlay`)
- Hash: `src/runtime/src/runtime/adapters/hashing.py` (`icons_entry_hash`)
- Tests: `src/runtime/tests/unit/test_icon_contrast.py`, `test_derive_icon_contrast_overlay.py`
- Provisioning: assets role (`synchronize`, converged), `verify` role (`itr list` gate, `verify_icons_samples`), compositor role (`icons.yaml → icons.json` generation)
- Consumers: AGS `IconRegistry` (`dotfiles/config/ags/lib/icon-registry.ts`) → `~/.local/state/dotfiles/current/icons/`
- ITR: `src/cli-tools/icon-templates-renderer/` (services.py merge precedence; `_PLACEHOLDER_RE`)

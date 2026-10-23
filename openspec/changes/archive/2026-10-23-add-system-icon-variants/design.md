## Context

Chain today (`src/runtime` + provisioning + AGS):

```
Repo: dotfiles/assets/icon-templates/<group>/<variant>/icon.svg
    + dotfiles/config/icon-template-color-scheme-mappings/{icons.yaml,defaults.yaml}
  → assets role: synchronize whole dirs icon-templates + icon-mappings
    (assets/vars/main.yml:70-71, converge-with-delete; spine read-only)
  → runtime seed: dotfiles-runtime wallpaper set → DerivationPipeline.ensure_icons
    (application/derive.py:39-72) → staging overlay (D2 of add-icon-contrast-guard)
    → itr render → cache/icons/<ih>/ (ih hashes EFFECTIVE overlay bytes)
  → compositor_configs: icons.yaml → icons.json (tasks/main.yml:27-28,
    json.dumps(sort_keys)), deploys AGS sources
  → verify: verify_icons_samples (verify/vars/main.yml:367) + icons.json presence
  → AGS IconRegistry (dotfiles/config/ags/lib/icon-registry.ts) → current/icons/*.svg
```

Guard scope (structural, verified in `derive.py::_scan_group_color_mappings` /
`_patch_overlay_text`): lines at exactly indent-4 under group-level
`color_mappings:`, placeholder in `(COLOR_FOREGROUND, COLOR_JOIN)`, group in
`BAR_GROUPS` (`domain/icon_contrast.py:22`). Variant blocks (indent 6+) are
structurally unreachable. Literals `#rrggbb` pass through. `bar_mappings`
untouched. Merge precedence `variant > group > vocabulary` (ITR
`domain/services.py::MappingResolutionService`).

Dual-use evidence: bar `bar/widgets/audio.tsx:82` resolves bare
`volume`/`microphone`; settings panel `components/sliders/VolumeSlider.tsx:66`
resolves `volume`; audio popup `audio/AudioPopup.tsx:97 systemIcon()` resolves
both at `:479,480,483,484,600,665,705,806,861,887,892`. `levelVariant()`
(`audio/state.ts:656`, `VolumeSlider.tsx:32`) returns bare names — prefixing
happens at resolve time so both surfaces share one vocabulary.

Templates already exist on disk (`dotfiles/assets/icon-templates/volume/{muted,
lowest,low,medium,max}`, `microphone/default/mic-{on,off}.svg`), so this change
adds manifest rows only — no artwork, no asset-category work.

## Goals / Non-Goals

**Goals**

- Bar icons keep full guard behavior (`auto/on/off` via `icon-contrast-opt-out`
  store + flag); system icons always render from authored mappings.
- Same art, two outputs, one cache entry; identical inputs still hit cache.
- Author rule documentable in one sentence (see D4).
- `make bootstrap` green end-to-end as the accept gate.

**Non-Goals**

- See proposal. Additionally: no `settings/*` split (bar-only, verified sole
  consumer `bar/widgets/settings.tsx`); no `media-transport` / `app-icons` /
  `capture-tool` / `settings-panel` / `brightness` changes (already correctly
  unguarded or out of scope).

## Decisions

### D1. `system-` prefix (locked, replaces `panel-*`)

Variant names: `system-muted`, `system-lowest`, `system-low`, `system-medium`,
`system-max`, `system-mic-on`, `system-mic-off`. Outputs:
`volume-system-*.svg` (5), `microphone-system-*.svg` (2). Rationale: owner
rejected `panel` (the popup is not a panel); `system` covers settings-panel +
audio popup + any future dark-glass consumer. Alternatives (`-system` suffix,
`system_*`, separate groups) rejected — prefix keeps `grep system-` trivial and
matches the prior `panel-*` investigation shape 1:1.

### D2. Variant-level `COLOR_FOREGROUND: foreground` pin (zero runtime change)

Each `system-*` variant pins `COLOR_FOREGROUND: foreground` (bright token for
dark glass). The guard cannot rewrite it by construction (D-scope above);
precedent: `ui/search` (`icons.yaml:309-319`, documents exactly this exemption)
and `camera-accent` / `warning-caution` (pinned to `color6`/`color3`, overlay
tests pin the exemption). Rejected: guard v2 / per-consumer decisions (worst of
both — duplicates the exemption with machinery), dual renders (breaks single
content-hash cache), CSS tinting (loses palette fidelity), exempting the groups
(sacrifices the verified-correct bar).

### D3. Resolve rule: bar bare, system `system-`

`levelVariant()` untouched (returns bare). Call sites prefix:
`VolumeSlider.tsx:66` → `"system-" + variant()`; `AudioPopup.tsx` sites →
`"system-" + X`. Bar `audio.tsx` untouched. `media-transport` rows
(`AudioPopup.tsx:362,379,397,445`) untouched (group not in `BAR_GROUPS`).

### D4. Standing author rule (docs)

"Bar resolves bare, system resolves `system-*`. Any group consumed on dark
glass MUST expose `system-*` copies from day one. Bar-only = single entry in
guard list; system-only = single entry outside guard list; both = two entries."
Goes into `docs/Adding an Icon §14`, replacing `panel` wording.

### D5. Provisioning carries it; `make bootstrap` is the gate

1. `assets` syncs updated `icons.yaml` (no new asset entries — whole-dir sync).
2. `compositor_configs` regenerates `icons.json` + deploys edited AGS sources.
3. `runtime-seed` renders 7 new outputs into the icons cache entry.
4. `verify` checks new samples + manifests.
Pre-gates (`pytest -q`, `contracts-check`, `itr list`, `ags bundle`) are
necessary but NOT sufficient — the agent is done only when `make bootstrap`
is green and the owner accepts (light + dark wallpaper proof).

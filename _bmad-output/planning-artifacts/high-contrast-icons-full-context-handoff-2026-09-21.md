# High-Contrast Icons — Full Context Handoff for a New Chat

**Date:** 2026-09-21
**Purpose:** Self-contained brief so a fresh agent/chat can take over the
high-contrast icon architecture topic with zero prior conversation.
Everything below is verified against the repo and the live machine unless
marked `[ASSUMPTION]` or `[OWNER INPUT NEEDED]`.
**Companions (same folder, deeper detail):**
- `icon-pipeline-contrast-handoff-2026-09-21.md` — forensic handoff (mechanics,
  wifi incident evidence, verification playbook, file inventory).
- `high-contrast-icon-architecture-investigation-2026-09-21.md` — scoped
  investigation plan (candidates, invariants, method, acceptance criteria).

---

## 1. Where things live

- **Main repo:** `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3`
  (`master`, tip `3d42dfd0` at time of writing).
- **This work:** git worktree
  `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3-audio`,
  branch `feat/pipewire-audio-ags`, based on main `3d42dfd0`. All paths below
  are relative to the worktree root unless marked `~`.
- **Commits on the branch** (oldest → newest):
  1. `2add9a49` — audio bar indicators + popup, provisioning, icons
  2. `44eb5743` — fix: restore dropped `clampVolume` import (had killed the bar)
  3. `f10caadf` — memlog note for the above
  4. `edc7f2be` — live volume tracking, icon-only bar, gated mic, follower
     anchor, global Esc
  5. `3e145839` — memlog note
  6. `3ab758d7` — forensic handoff doc
  7. `d8f79a74` — investigation brief
- **Owner:** juan david. Speaks English. Decisive, wants evidence over assertion.
  Active agents used so far: Sally (UX designer, finalized DESIGN.md +
  EXPERIENCE.md in `_bmad-output/planning-artifacts/ux-designs/
  ux-dotfiles-repo-v3-audio-2026-09-18/`) and Winston (architect, reviewed the
  contrast investigation and signed it off with trade-offs).

---

## 2. Problem statement (owner's words, condensed)

1. The owner manually ran ITR against the installed spine's `icons.yaml`
   (wifi group). High contrast "is not being applied properly — the whole
   icon has the same value for all the placeholders" (screenshot: uniformly
   dark wifi glyph on the light bar).
2. Suspicion: the contrast guard was "implemented as a quick workaround" that
   doesn't account for its dependents; there is no engine for generating
   high-contrast vs normal variants.
3. Scope confirmed by owner: fix the bar/popup audio issues first (DONE —
   §7), then address the architecture. Contrast work is INVESTIGATION ONLY
   until the owner approves an implementation plan. The owner explicitly said
   to leave the contrast implementation for last.

---

## 3. How the icon pipeline works (verified)

```
REPO (authoritative)
  dotfiles/assets/icon-templates/<group>/<variant>/icon.svg   # {{PLACEHOLDER}}s
  dotfiles/config/icon-template-color-scheme-mappings/{icons.yaml,defaults.yaml}
  dotfiles/config/ags/icons.json  (= yaml→nice_json(sorted), GENERATED, byte-verified)
        │  assets role: ansible.posix.synchronize WITH DELETE (converges spine)
        ▼
SPINE  ~/.local/share/dotfiles/{icon-templates/,icon-mappings/icons.yaml}
        │  runtime seed: dotfiles-runtime wallpaper set <png>
        ▼
CONTRAST GUARD (staging-only temp overlay; spine stays read-only)
  inputs: spine icons.yaml + current/colors.yaml + sampled wallpaper top-band
  scope: group-level COLOR_FOREGROUND/COLOR_JOIN, BAR_GROUPS members only
         (structural: indent-4 lines; variant blocks at indent 6+ unreachable)
  output: overlay icons.yaml + meta.json decisions[] (group/placeholder/from/to/ratios)
        │  itr render (overlay when guard fires, else spine)
        ▼
CACHE ~/.local/state/dotfiles/cache/icons/<hash>/  (key hashes overlay bytes)
        │  current/icons → symlink to one entry
        ▼
CONSUMERS — bar (transparent, over wallpaper) + dark-glass panels/popups +
capture tool + others — ALL read the same files via IconRegistry.
```

Placeholder merge precedence: **variant > group > vocabulary(defaults.yaml)**,
verified in `src/cli-tools/icon-templates-renderer/.../domain/services.py`.
Substitution is whole-text regex (works in `fill=""` and `stroke=""`).
Manual `itr render` without explicit `--color-scheme`/`--template-dir`/
`--output-dir` does NOT use the live palette and NEVER applies contrast.

Current `BAR_GROUPS`: battery, network, btop, thunderbird, tray, ui,
power-menu, email-client, wallpaper-selector, settings, volume, microphone
(last two added by the audio work).

---

## 4. Forensic findings (the wifi incident, all verified live)

1. **Spine was hand-edited** (still present at time of writing):
   `network.COLOR_CROSS: color13` (repo) → `color15` (spine). The guard cannot
   do this (`COLOR_CROSS` not in its retarget tuple) — this is a manual edit
   via `itr mapping set`/editor. Next bootstrap **will clobber it** (rsync
   delete). Owner decision pending: revert or keep.
2. **Guard fired correctly**: active cache meta shows
   `network COLOR_FOREGROUND color15 -> background`, ratio 1.0 → 10.44,
   `backdrop_source: sampled`.
3. **Rendered `wifi-full-default.svg` = single `fill="#201f0e"`** — correct,
   because its template contains exactly ONE placeholder type
   (`COLOR_FOREGROUND` ×4 paths, no opacity tiers). **wifi-full is monochrome
   by template design.** A uniform dark glyph on the light bar is the right
   output, not a malfunction.
4. The hand edit only affects `wifi-no-internet`-family variants (sole
   `COLOR_CROSS` consumers), collapsing their accent distinction.
5. **Root architectural gap (confirmed, not hypothesized): one render serves
   bar + panels.** On light wallpapers the guard optimizes for the wallpaper
   backdrop; the same files render on dark glass where dark ink washes out
   (observed: audio popup + settings-panel speaker glyphs). The guard's scope
   logic is sound; its single-consumer assumption is the debt.

---

## 5. Verified consumer matrix (repo grep, 2026-09-21)

**Bar-only** (safe as-is): battery, network, btop, thunderbird, tray,
settings (+ `ui`, `email-client`, `wallpaper-selector` — allowlisted but no
resolve sites found in the AGS tree; consumers unlocated, classify before
touching).

**Panel-only** (correctly unguarded): settings-panel group, brightness,
capture-tool (deliberately excluded — renders on its own dark UI; test pins
this).

**DUAL-USE (the fix set — exactly 2 groups):**
- `volume` → bar `bar/widgets/audio.tsx` + settings-panel Sound
  (`components/sliders/VolumeSlider.tsx` via `settings-panel/controls/volume.tsx`)
  + audio popup rows (`audio/AudioPopup.tsx`).
- `microphone` → bar `audio.tsx` + audio popup Input/Recording rows.

---

## 6. Recommended design (investigated, NOT implemented)

**Panel-pinned variant overrides.** For each dual-use variant add a `panel-*`
sibling reusing the SAME template with explicit variant-level
`COLOR_FOREGROUND: foreground` (outputs `volume-panel-*.svg` ×5,
`microphone-panel-*.svg` ×2). Panels resolve `panel-*`; bar keeps bare
variants. Why this one: zero runtime/guard/cache/registry changes (the
exemption is regex-structural and already unit-tested); cache key already
covers additions; production precedent exists (`ui/search` pins at variant
level for the same reason, documented in-manifest). Rejected: per-consumer
renders (breaks content-hash cache), CSS tinting (loses palette fidelity),
exempting groups (sacrifices the verified-correct bar), guard v2 (machinery
duplicating the existing exemption).

**Implementation shape when approved:** 7 variants in `icons.yaml` →
regenerate `icons.json` (same transform) → 4 call-site switches
(`VolumeSlider.tsx`, `AudioPopup.tsx` volume+mic sites) → 2 new
`verify_icons_samples` + pinning test → 1 overlay preservation test →
`itr list`/`render` checks → fast unit suites → `ags bundle`. No bootstrap
needed for the change itself.

---

## 7. Audio work already shipped on this branch (context, do not redo)

- Bar `OutputIndicator` (level-aware `volume` glyph, icon-only, scroll =
  volume, left = popup, right = pavucontrol) + `MicIndicator` (`microphone`
  group, visible only while recording, green `#2ecc71` live dot).
- Follower-anchored popup (Output + Change-subview, Applications with
  per-stream routing via `target_endpoint`, Input, Recording; empty sections
  collapse), global `popup-close` Esc, `keymode=NONE` house standard.
- Provisioning: `pipewire-pulse` + `pavucontrol` packages, per-manager names,
  global audio user-unit enable, verify gates — `make bootstrap` green.
- Hard-won runtime facts: this AstalWp build (r973) exposes `wp.nodes`
  (media-class 1=mic, 2=sink, 3=recorder, 4=app stream) + `devices` +
  defaults; `speakers/streams` getters are `undefined` despite the GIR;
  `notify::nodes` fires on membership but NOT volume change — volume/mute use
  endpoint-object 3-path bindings. **Do not "simplify" back to nodes-derived
  levels; the bar will freeze.**
- Critical process lesson (twice learned): `ags bundle` exit 0 does NOT catch
  runtime-only `ReferenceError`s — a widget throw kills the whole Bar window
  (no layer surface). The live gate is "layer mapped + log clean."

---

## 8. Owner decisions on record

1. Popup click: left = popup, right = pavucontrol. Full scope, nothing deferred.
2. Mic on bar; mic icon ONLY when in use, with green dot. No percentage label (icon-only bar).
3. Popup sections: output-device SUBVIEW (1B), separate Recording card (2A), empty sections collapse (3A).
4. Popup anchors under the invoking icon (follower), never screen edge.
5. Global Esc dismisses whichever popup is open (`popup-close`).
6. `astal-bluetooth` deletion stands; rebase onto main tip (done, `2add9a49`→HEAD).
7. Contrast: investigate first, implement only on approved plan. Panel-variant
   naming (`panel-*`) NOT yet approved — open question §9.3.

---

## 9. Open questions (need owner or follow-up)

1. Approve `panel-*` naming + Option A implementation?
2. Revert the spine `COLOR_CROSS` hand-edit (moot after next bootstrap either way)?
3. Guardrail against silent spine divergence (warn in `itr`? verify diff? or accept)?
4. Locate `ui`/`email-client`/`wallpaper-selector` icon consumers and classify.
5. Document the standing rule ("dark-glass consumers MUST use panel-pinned
   variants") in the icon-adding doc?

---

## 10. Suggested first steps in the new chat

1. `git -C <worktree> log --oneline -8` + `git status` to confirm clean tree.
2. Re-run §4-verification playbook from the companion forensic doc
   (spine-vs-repo diff, live meta decisions, rendered fills) to confirm the
   machine state hasn't drifted.
3. Pick up at §9 above or the investigation brief's acceptance checklist
   (`high-contrast-icon-architecture-investigation-2026-09-21.md` §7).
4. House rules this repo enforces (learned the hard way): never hand-edit
   `icons.json` (regenerate); never edit the spine (repo-converged);
   `ags bundle` green ≠ working (check layer + log); one provisioning run
   from one place at a time (two writers corrupt the spine).

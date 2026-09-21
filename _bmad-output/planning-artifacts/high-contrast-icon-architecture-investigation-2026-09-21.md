# High-Contrast Icons: Architecture Investigation Brief

**Date:** 2026-09-21
**Status:** Investigation scoped, not started. No implementation.
**Companion doc:** `_bmad-output/planning-artifacts/icon-pipeline-contrast-handoff-2026-09-21.md`
(the forensic handoff — system map, placeholder mechanics, the wifi incident,
verification playbook). Read that first; this brief does not repeat it.
**Branch context:** `feat/pipewire-audio-ags` (rebased onto main `3d42dfd0`).

---

## 1. The two issues under investigation

**Issue 1 — The current guard is workaround-shaped.**
The contrast guard retargets group-level placeholders for `BAR_GROUPS` at
`wallpaper set` time via a staging-only overlay. It works for its original
single-consumer assumption (transparent bar over wallpaper), but it was built
without accounting for everything that consumes the rendered files. The
concrete breakage: the same rendered SVG serves dark-glass panels, where the
retargeted (dark) ink washes out. There is no model of *who consumes what* —
the guard knows groups, not surfaces.

**Issue 2 — There is no engine for two variants.**
Nothing in the pipeline can produce and serve a high-contrast (bar) and a
normal (panel) rendering of the same icon as first-class outputs. Today's
option set is binary per group: in `BAR_GROUPS` (retargeted everywhere the
group renders, including panels) or out (unprotected on the bar). There is no
per-consumer resolution, no dual-output convention, and no naming/ownership
rule for variant pairs.

---

## 2. Verified consumer matrix (2026-09-21, repo grep)

| Group | In BAR_GROUPS | Bar consumers | Panel/dark-glass consumers | Verdict |
|---|---|---|---|---|
| battery | yes | bar `battery.tsx` | none found | safe as-is |
| network | yes | bar `network.tsx` | none found | safe as-is |
| btop | yes | bar `btop.tsx` | none found | safe as-is |
| thunderbird | yes | bar `thunderbird.tsx` | none found | safe as-is |
| tray | yes | tray widget | none found | safe as-is |
| settings | yes | bar `settings.tsx` | none found | safe as-is |
| power-menu | yes | bar `power-menu.tsx` | none found | safe as-is |
| ui | yes | none found in ags tree | none found | unchecked — locate consumers before touching |
| email-client | yes | none found in ags tree | none found | unchecked — same |
| wallpaper-selector | yes | none found in ags tree | none found | unchecked — same |
| **volume** | yes | bar `audio.tsx` | settings-panel Sound (`VolumeSlider`), audio popup rows | **DUAL-USE — needs the engine** |
| **microphone** | yes | bar `audio.tsx` | audio popup Input/Recording rows | **DUAL-USE — needs the engine** |
| capture-tool | no | bar `recording.tsx` (pause/play/stop) | capture window (own dark UI) | deliberately unguarded; out of scope |
| settings-panel | no | none | settings panel tiles | correctly unguarded; out of scope |
| brightness | no | none (settings panel Display) | settings panel only | correctly unguarded; out of scope |

**Scope of the fix is bounded: exactly the `volume` and `microphone` groups.**
`ui` / `email-client` / `wallpaper-selector` are allowlisted but consumer-unknown —
the investigation must locate their consumers (likely gui-tools or rofi surfaces)
and classify them before any group is moved or split.

---

## 3. Investigation goals

1. Decide the canonical mechanism by which ONE icon source yields TWO
   contrast-correct renderings (bar + panel), owned by the pipeline rather
   than by per-call-site hacks.
2. Decide where the bar-vs-panel distinction lives: manifest naming
   (`panel-*` variants), group split, registry logic, render outputs, or guard
   logic — exactly one owner, no split brain.
3. Preserve every invariant in §5. Prove preservation with the verification
   steps in §7, not by assertion.
4. Produce a file-by-file implementation plan (a follow-up task), NOT the
   implementation itself.

---

## 4. Candidates to evaluate (with honest trade-offs)

### A. Panel-pinned variant overrides (current recommendation)
Add `panel-*` variants reusing the same templates, with explicit variant-level
`COLOR_FOREGROUND` pins; panels resolve `panel-*`, bar keeps bare variants.
- For: zero runtime/guard/cache/registry changes; exemption rule already
  tested and shipped (`ui/search` precedent); same-template reuse = no art
  duplication; cache key already covers variant additions.
- Against: ~7 new outputs per wallpaper set; a second naming vocabulary to
  maintain; relies on authors remembering the `panel-` convention (needs the
  documented invariant from §6).
- Measure: render-count delta, cache-entry growth, `itr list` output sanity.

### B. Dual-render engine (one group, two outputs, consumer-aware resolve)
Render each dual-use group twice (bar overlay + panel base) and teach
`IconRegistry.resolve` (or call sites) which to pick per surface.
- For: single variant list in the manifest; no naming convention to remember.
- Against: breaks the single content-hash cache model (two keys per group);
  requires registry API change + every call site to declare its surface;
  the "which surface" signal must be threaded through AGS code that today
  knows nothing about it. Highest machinery cost. Only justified if variant
  count explodes (Rule of Three: revisit at ≥3 dual-use groups).
- Measure: prototype the registry change and count touched call sites.

### C. Guard v2 (consumer-aware decisions)
Extend the guard to emit per-consumer decisions (e.g. retarget set X for bar,
set Y for panels) instead of one overlay.
- For: keeps manifest small.
- Against: the overlay is a single file consumed by a single `itr render`;
  per-consumer outputs reintroduce B's two-render problem while ALSO
  complicating the dumb-text-patch component whose safety story is its
  simplicity. Worst of both.
- Verdict in advance: evaluate only to document rejection.

### D. Do nothing (accept washed panel icons)
- Rejected already by owner direction (images 2–3 in the audio work show the
  failure on real surfaces). Recorded for completeness.

---

## 5. Invariants that must hold (non-negotiable)

1. **Spine stays read-only.** Repo → bootstrap → spine, one direction. No tool
   writes the spine except provisioning roles.
2. **Single content-hash cache model.** Any new outputs must fall out of the
   existing `icons_entry_hash(overlay bytes)` path — no second key scheme.
3. **`icons.json` stays generated.** `yaml → nice_json(sorted)` byte-verified;
   hand edits forbidden.
4. **Guard scope rule preserved.** Group-level `FOREGROUND`/`JOIN` in
   `BAR_GROUPS` only; variant-level/liter als/`bar_mappings` byte-preserved.
   Existing overlay tests must keep passing unmodified (additive tests only).
5. **No render-time polling or watchers.** Generation happens at `wallpaper
   set` / bootstrap only.
6. **Verify gates stay green and meaningful.** `verify_icons_samples` extended
   for new outputs; no vacuous asserts (each sample must fail loudly if its
   render is missing).

---

## 6. Method

1. Re-verify §2 matrix after any new icon consumption lands (grep is cheap;
   staleness here is how the next dual-use group sneaks in).
2. Spike Option A end-to-end on `microphone` only (2 variants): render,
   resolve from the popup, screenshot bar + panel on a light wallpaper.
   Kill criteria: any guard/cache/registry change required → stop, it isn't
   Option A anymore.
3. Only then generalize to `volume` (5 variants) + call-site switches +
   samples gate + overlay test.
4. Write the file-by-file implementation plan as the investigation output.
   Suggested standing rule to document: *"any group consumed on dark glass
   MUST expose panel-pinned variants; the bar resolves bare variants."*

---

## 7. Acceptance criteria for the investigation (done = ?)

- [ ] Consumer matrix (§2) re-verified, including `ui`/`email-client`/
      `wallpaper-selector` consumers located and classified.
- [ ] Microphone-only spike rendered + screenshotted on light AND dark
      wallpapers (bar correct + panel correct in both).
- [ ] Cache entries inspected: one entry, both outputs present, `meta.json`
      decisions sane.
- [ ] Full existing test suites green (provisioning fast suites, runtime
      contrast suites, `ags bundle` exit 0).
- [ ] Implementation plan written: exact files, variant names/outputs,
      call-site diffs, test additions, verification commands — detailed
      enough that a builder agent executes with zero drift.
- [ ] Open question answered: does `settings/*` (or any other allowlisted
      group) gain a panel consumer in planned work? If yes, it joins the
      dual-use set.

---

## 8. Open questions for the owner

1. `panel-*` naming approved, or prefer a different convention
   (`-panel` suffix, `flat-*`, per-surface groups)?
2. Should the standing rule (§6.4) also cover *future* groups at authoring
   time (checklist in the icon-adding doc), or only fix the two known groups?
3. The spine `COLOR_CROSS color13→color15` hand-edit from the wifi incident:
   revert (repo reconverges on next bootstrap regardless), or keep?
4. Who owns the `ui`/`email-client`/`wallpaper-selector` classification —
   same investigation or separate?

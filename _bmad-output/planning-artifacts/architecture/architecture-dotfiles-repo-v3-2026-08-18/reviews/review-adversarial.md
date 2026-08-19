# Adversarial Review — Architecture Spine, dotfiles-repo-v3 Runtime Core (Phase 2)

- **Reviewer:** adversarial (bmad-architecture reviewer gate)
- **Subject:** `ARCHITECTURE-SPINE.md` (2026-08-18, draft)
- **Method:** two independent construction units (two developer teams) each given only the spine, each required to obey **every** AD to the letter, then checked for interoperability on a shared `state_root`.
- **Verdict:** **REJECT — do not proceed to epics/spec with the spine as written.** The spine pins the *philosophy* (hexagon, content-addressed cache, symlink-led swap, JSON store) but leaves the *shared-data contracts* — every file schema, every ordering, every owner, every env-var name — underspecified. Two units that obey all 17 ADs verbatim build a state root the other unit cannot read, mutate, or recover. The ADs are layer discipline; they are not a build-substrate. Findings F1–F3 are blocking.

---

## 1. Construction of two conformant-but-incompatible units

Unit **A** ("Manifest-first") and Unit **B** ("Pipeline-first") are staffed independently. Each cites the spine as its only contract. Both can point at a line in the spine for every decision below; neither violates an AD as written.

| Dimension | Unit A (Manifest-first) | Unit B (Pipeline-first) | Spine "authority" both cite | Same file, different bytes? |
| --- | --- | --- | --- | --- |
| `current.json` shape | `{"current":{"wallpaper":"<wh>","palette":"<ph>","effects":"<eh>","icons":"<ih>"},"updated_at":"…"}` | `{"wallpaper":"<wh>","palette":"<ph>","effects":"<eh>","icons":"<ih>","version":1}` | AD-3 (manifest), AD-10 (projection) | **YES** — nested vs flat, `updated_at` vs `version` |
| `meta.json` field names | `inputs` / `artifacts` | `input_hashes` / `artifact_hashes` | AD-8 ("records input and artifact hashes") | **YES** |
| `history.jsonl` line shape | `{"ts":"…","trigger":"apply","previous":{…},"current":{…}}` | `{"timestamp":"…","event":"seed","old_state":null,"new_state":{…}}` | AD-4 (one line/reconcile), AD-11 (`trigger: seed`) | **YES** — field names, `ts` vs `timestamp`, `trigger` vs `event` |
| Palette `<ph>` input scope | hash(wallpaper, template **files**, generator version, settings hash) | hash(wallpaper, template **dir path**) | AD-2 ("hash of ALL its derivation inputs" — set never enumerated) | **YES** — different `<ph>` for same wallpaper |
| Post-seed derivation inputs (templates, effects catalog, icon templates/mappings) | mirrored into `state_root/inputs/` at seed, referenced forever after | kept reading install spine on regenerate | AD-11 (never read spine after seed) + AD-12 (generate missing artifacts) — **contradiction, spine silent on resolution** | **YES** — one is even a spine violation, but each team honestly reads the ADs differently |
| Effects generator env key | `WALLPAPER_EFFECTS__OUTPUT__DIRECTORY` | `EFFECTS__OUTPUT__DIRECTORY` | AD-7 (only `COLORSCHEME__…`, `WALLPAPER__…`, `ICON_RENDERER__*` named; weg key missing) | **YES** |
| Env precedence | env overrides settings.toml; fall back to settings.toml | env authoritative; hard-fail if unset | AD-7 (precedence unpinned) | **YES** — same config, different cache population behavior |
| Mutation order | symlinks → `current.json` → history → reload | symlinks → history → reload → `current.json` | AD-6 (symlinks lead, store lags) + AD-4 (history before reload completes) + AD-12 (…reload…persist) | **YES** — different crash states, different recovery |
| Symlink repoint order | wallpaper → effects → palette → icons (derivation parents first) | directory/alphabetical order | AD-6 ("each atomic tmp+rename"; set-level order unpinned) | **YES** |
| Swap owner | `ReconcileDesktopStateUseCase` | `ApplyWallpaperUseCase` | AD-12 (both in pipeline; owner unpinned) | **YES** — different call graph, different dedupe boundary |
| Effects/icon artifact filenames | `effect_<slug>.png`, `<slug>.svg` | `fx_<name>.png`, `<name>.icon.svg` | AD-10, AD-17 (schemes unpinned) | **YES** |
| `IStateRepository` minimal API | `load_current() -> DesktopState`, `save(DesktopState)`, `history() -> list[str]` | `load_current() -> dict`, `save(dict)`, `append_history(str)` | Deferred section ("minimal load_current/save/history") | **YES** |

### Demonstrated failure on a shared state root
1. Unit A runs `dotfiles wallpaper set X` → populates cache, writes `current.json`(A), `meta.json`(A), appends history(A).
2. Unit B runs `dotfiles status` → reads `current.json`(A) with `load_current() -> dict`, expects top-level `wallpaper`; gets `KeyError: 'wallpaper'`. `InspectStateUseCase` crashes on its own seeded data's `meta.json`(A) (`KeyError: 'input_hashes'`).
3. Unit B runs `dotfiles history` → renders history(A) lines as `{missing fields}` / throws.
4. On a fresh machine, Unit B seeds, then Unit A reconciles: Unit A's `<ph>` (different input scope) is absent from cache → regenerates a *second* palette entry for the same wallpaper → `cache/prune` can't tell the duplicate from the live entry, and the swap repoints to the new `<ph>` whose `meta.json` schema Unit A wrote — which Unit B's `status` then misreads. Cache bloat + reader breakage, all AD-conformant.

The two units also disagree on *recovery after a crash mid-swap* (F3): A recomputes `current.json` from symlinks; B replays history. One of them will destroy the other's invariant on the next run.

---

## Findings

### F1 — CRITICAL — No file schema is pinned: `current.json`, `meta.json`, `history.jsonl` are open contracts with three writers each

- **Evidence:** AD-3 defines the store as "`current.json` (manifest) + `history.jsonl` (append-only) + per-entry `meta.json`"; AD-8 says "every `meta.json` records `hash_algorithm: sha256` plus input and artifact hashes"; AD-10 says `DesktopState` = projection of `current.json`; AD-4 requires "one line" per reconcile with `trigger: seed` in AD-11. **Nothing names a field, a type, a nesting, or a version field.**
- **Owners (≥3 each):** `current.json` is written by the seeder (AD-11) and the swap path (AD-6/AD-12) and read by `InspectStateUseCase` + `status`/`history` CLIs. `meta.json` is written by the seeder *and* the cache populator (AD-9) and read by every cache consumer. `history.jsonl` is appended by seed, apply, and reconcile — three code paths, one shape.
- **Unit A vs Unit B divergence:** table rows 1–3 above. Both satisfy "manifest", "projection", "records input and artifact hashes", "one line per reconcile".
- **Hole to close:** new AD "**Store & cache entry schemas**" — pin exact JSON field names, required vs optional, and types for `current.json`, `meta.json`, and the history line (including a shared `trigger` enum: `seed|apply|reconcile` and a `trigger: seed` literal per AD-11); add a `schema_version` to each (extend AD-8's "versioned" discipline from the hash function to the schemas); require a golden-file fixture test that both units' output must match byte-for-byte on identical inputs.

### F2 — CRITICAL — Post-seed derivation-input supply is undefined and AD-2's "all derivation inputs" set is never enumerated

- **Evidence:** AD-11: "One-time; after it, runtime never reads the install spine." AD-12: reconcile must "generate missing artifacts." AD-2: entry dir "named by the hash of ALL its derivation inputs." AD-10: `PaletteEntry: hash(wallpaper, templates)`, `EffectsEntry: hash(wallpaper, effects catalog)`, `IconsEntry: hash(palette, icon templates, mappings)`.
- **Contradiction:** after seeding, the templates / effects catalog / icon templates / mappings — the *inputs* of the palette/effects/icons layers — exist only under the provisioning-owned install spine (AD-5, AD-15). The spine never states they are copied into `state_root`. So the AD-12 regenerate path is **impossible** as written, and each unit "resolves" it differently (A mirrors inputs into `state_root/inputs/` at seed; B keeps a read-backdoor to the spine — the latter is a de-facto AD-11 violation that no review catches because the ADs contradict).
- **Second ambiguity:** the *input set* per layer is not enumerated — which template files? which catalog? generator version in or out? settings hash? seed-time `generated/` snapshot? Units A and B produce different `<ph>/<eh>/<ih>` for the identical wallpaper, so cache entries are not interoperable and the AD-17 "verify criterion 6 (`generated/palettes` OR `current/colors.yaml`)" oracle is ambiguous (both OR-branches can hold different values).
- **Hole to close:** new AD "**Derivation input material**" — enumerate, per layer, the exact input tuple that feeds the hash (file set + catalog version + generator version + settings hash); require seeding to mirror a frozen snapshot of that input set into `state_root/inputs/<layer>/` and pin that path as the only runtime source thereafter; strengthen AD-11 with an explicit "no post-seed spine reads, no exceptions" enforcement (or deliberately carve out a pinned read-only path if a carve-out is truly needed — but the carve-out must be the AD, not an accident).

### F3 — CRITICAL — Mutation ordering is free; AD-6's "desktop stays consistent on crash" is not derivable from "symlinks lead"; recovery is undefined

- **Evidence:** AD-6: "desktop swap repoints the `current/` symlinks (one per consumer path, each atomic tmp+rename)... Symlinks lead, `current.json` follows: on crash the desktop stays consistent and the store lags, recoverable on next run." AD-4: history appended "before desktop reload is considered complete." AD-11: seed "writes `current.json`, creates `current/` symlinks, appends history." AD-12: pipeline "…write configs → reload desktop → persist".
- **Three unpinned orderings:**
  1. **Cross-symlink consistency:** the swap touches ≥6 links (`wallpaper.png`, `colors.yaml`, `colors.conf`, `colors.gtk.css`, `effects/`, `icons/`). "Each atomic" protects one link, not the set. A crash after `colors.conf→<ph_new>` but before `wallpaper.png→<wh_new>` leaves a **mismatched palette** live — precisely the inconsistency AD-6 claims to prevent. The derivation graph (AD-10) gives the correct order (parents before children: wallpaper → effects → palette → icons) but the AD does not require it; Unit B repoints alphabetically.
  2. **Store vs history vs reload:** AD-4 pins history *before* reload; AD-6 pins `current.json` *after* symlinks. Unit A does `symlinks → current.json → history → reload`; Unit B does `symlinks → history → reload → current.json`. On a crash between history and `current.json`, A has an unlogged store write and B has a history line the store never reflected — opposite invariants.
  3. **Recovery:** "recoverable on next run" — *how*? Recompute `current.json` from symlink targets (A) or replay `history.jsonl` (B)? These produce different outcomes after the same crash and can overwrite each other's store.
- **Hole to close:** tighten AD-6 — (a) pin the repoint order to derivation-parent-first (wallpaper → palette → icons; effects), (b) add a set-level consistency rule (e.g., repoint wallpaper first so any partially-swapped palette is still derived from the *live* wallpaper, or require a single generation pointer); tighten AD-12 to a **fixed** mutation sequence `repoint symlinks → write current.json → append history → reload`; define recovery precisely ("on next run, recompute `current.json` from `current/` symlink targets"; never replay history into the store). If multi-invocation races are allowed (two `wallpaper set` in two terminals), AD-9's staging only protects cache population — pin a coordination primitive (e.g., flock on `state_root`) or declare single-writer and enforce it.

### F4 — HIGH — AD-7 env-var override protocol is incomplete: names, precedence, and fallback unpinned; the effects generator has no key

- **Evidence:** AD-7 names `COLORSCHEME__OUTPUT__DIRECTORY`, `WALLPAPER__OUTPUT__DIRECTORY`, and a wildcard `ICON_RENDERER__*`. The `weg_runner` adapter (Structural Seed) has **no** output env key. Precedence vs `settings.toml` is unstated, and nothing verifies the tools honor env at all (spine itself flags determinism as unverified — the same diligence is owed the env contract).
- **Divergence:** Units A and B pick different weg keys and different precedence (override-with-fallback vs authoritative-hard-fail); against a tool that only reads `settings.toml`, A silently writes into the provisioning-owned output dir (an AD-5/AD-15 boundary violation in practice) while B errors out.
- **Hole to close:** amend AD-7 — enumerate the **full** env-key list for all four tools (csg, weg, itr, wallpaper), pin precedence (env wins; fall back to settings.toml), and add a per-tool contract gate (a small verification step that fails loudly if the tool writes anywhere but the pinned env target — same posture as the CSG/ITR determinism check the spine already defers).

### F5 — HIGH — Swap sequence has three candidate owners; effects/icons artifact filename schemes and consumer wiring are unpinned

- **Evidence:** the seeder writes `current/` symlinks (AD-11); AD-12 runs both `ApplyWallpaperUseCase` and `ReconcileDesktopStateUseCase`; AD-6 says "the swap" with no owner. AD-17 pins four consumer paths (`colors.conf`, `colors.css`, `wallpaper.png`, `colors.yaml`) but says nothing about the `effects/` and `icons/` symlinks or the `*.png`/`*.svg` filename schemes inside `cache/effects/<eh>/` and `cache/icons/<ih>/`.
- **Divergence:** A/B choose different swap owners → different call graphs, different regenerate/dedupe boundaries, and divergent crash-window behavior (F3). Filename schemes differ (`effect_<slug>.png` vs `fx_<name>.png`), so `current/effects` content is not interoperable between units, and any consumer globbing `current/icons/*.svg` breaks.
- **Hole to close:** amend AD-6/AD-12 to give `ReconcileDesktopStateUseCase` **sole** ownership of the swap sequence (repoint + `current.json` + history + reload); restrict `ApplyWallpaperUseCase` to compute-desired-graph + populate cache; route seeding (AD-11) through the same reconcile path so seed and swap produce byte-identical layouts. Extend AD-17 to pin effects/icons artifact filename schemes and their consumers.

### F6 — MEDIUM — Deferred section: `IStateRepository` "minimal load_current/save/history" unpins the port surface; CLI surface unpinned

- **Evidence:** Deferred: "Phase 2 ships minimal `load_current`/`save`/`history`". AD-13 repo layout **is** resolved (good — no divergence there). But the *signatures* of those three methods are not, and the CLI command/flag surface (`wallpaper`, `status`, `history`, `cache list/prune`) is unpinned.
- **Divergence:** A/B build different port signatures → different adapters and different use-case call patterns, which defeats the port entirely (the port is only stable if the signature is the contract). Binary-name deferral (`dotfiles` vs `dotfiles-runtime`) is lower risk because AD-5 makes `state_root` independent of binary name — but it still splits the command surface.
- **Hole to close:** pin the `IStateRepository` method signatures and the Phase 2 CLI command/flag surface in the spine now; "decide at spec/epics" may remain for the **binary name only**.

### F7 — MEDIUM — AD-16 copy fallback and seed source under-pinned (minor)

- **Evidence:** AD-16: hardlink, "copy fallback only cross-filesystem." The content-hash cache key is stable across hardlink and copy (good — that risk is closed). But the copy primitive (`shutil.copy2` vs `cp -p`) is unpinned, and whether `meta.json` records source metadata (mtime/ownership) that differs between hardlink (inode shared) and copy is unstated — a downstream of F1.
- **Divergence:** A/B produce different `meta.json` source fields; low blast radius on its own.
- **Hole to close:** one line in AD-16 naming the copy primitive and the `st_dev` check (or EXDEV-retry) policy; fold the source-metadata fields into F1's schema.

---

## Deferred-section audit (item 6 of the brief)

- **CLI packaging** — real but low-risk (binary name doesn't affect shared data); fine to defer, but the **command/flag surface** must be pinned (F6).
- **AD-13 repo layout** — **complete**; the `src/core`+`src/infrastructure` vs nested-hexagon drift is resolved. No hole here.
- **Cache eviction** — deferred to Phase 3; safe because Phase 2 `prune` is a stub, but note the stub's output format is shared-data-adjacent (fold into F6 CLI surface).
- **CSG/ITR determinism** — a genuine pre-condition for the cache key; the spine already defers it, but it is a **release blocker** for F2's cache-key trust, not just a Phase 3 nicety — recommend it be an explicit gate in the Phase 2 done-criteria, alongside AD-7's env contract check (F4).
- **`IStateRepository` minimal API** — the real deferral risk; move to a pinned decision (F6).

---

## Summary of holes to close (new/tightened ADs)

| # | Action | Severity |
| --- | --- | --- |
| F1 | NEW AD: pinned schemas + `schema_version` for `current.json`, `meta.json`, history line; golden-fixture byte-compare test | CRITICAL |
| F2 | NEW AD: per-layer derivation input tuples + seed-time mirror of inputs into `state_root/inputs/`; enforce no post-seed spine reads | CRITICAL |
| F3 | TIGHTEN AD-6 (parent-first repoint order, set-level consistency) + AD-12 (fixed mutation sequence) + define recovery; pin single-writer/lock | CRITICAL |
| F4 | TIGHTEN AD-7: full env-key list, precedence, per-tool env contract gate | HIGH |
| F5 | TIGHTEN AD-6/AD-12: `ReconcileDesktopStateUseCase` sole swap owner; AD-17 extended to effects/icons filename schemes + consumers | HIGH |
| F6 | Pin `IStateRepository` signatures + CLI surface (defer binary name only) | MEDIUM |
| F7 | TIGHTEN AD-16: copy primitive + `st_dev`/EXDEV policy | MEDIUM |

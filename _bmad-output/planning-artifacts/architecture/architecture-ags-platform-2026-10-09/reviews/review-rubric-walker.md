# Rubric-Walker Review — AGS Platform Architecture Spine

**Reviewer:** fresh independent architecture reviewer (subagent), rubric-walker lens
**Date:** 2026-10-09
**Subject:** `_bmad-output/planning-artifacts/architecture/architecture-ags-platform-2026-10-09/ARCHITECTURE-SPINE.md` (278 lines, `status: draft`)
**Inputs checked:** `docs/101-ags-platform-architecture.md`, `docs/100-ags-bar-rearchitecture.md`, `docs/HANDOFF-ags-platform.md`, `.memlog.md`, and the actual brownfield codebase in `/home/inumaki/Development/dotfiles-v3`.
**Sibling reviews already present:** `review-adversarial.md`, `review-brownfield-ratification.md`, `review-web-verify.md`. Where my finding overlaps one of those I say so explicitly rather than claim novelty.

---

## Verdict

**CONDITIONAL — do not freeze yet.** The spine is a strong, honest convergence of doc 101 and correctly freezes the target port surface and the real seams (`IconRegistry`, `BarWidgetSpec`, `overlays`, `DomainEventBusCore`/`EventBusTransport`). But it has **one internal rule contradiction that defeats its own load-bearing AD (AD-1)**, **one whole dimension left silent — the operational/environmental envelope**, and **one contract seam (`icons.json` producer + the validator type seam) that is stated against the brownfield**. These are exactly the "divergences the author talked past." None require re-authoring the spine; all are fixable by the tightening lines below.

---

## Evidence base (what I actually ran/read, not prose)

- `Makefile` (full), `.github/workflows/gates.yml`, `scripts/ci-gates-parity.py`, `scripts/ags-typecheck.py`.
- `dotfiles/config/ags/{kit/icon.ts,kit/widget.tsx,kit/overlay.ts,lib/icon-registry.ts,lib/event-bus-core.ts,app.tsx,bar/Bar.tsx}`.
- `contracts/event-contract.{json,xml}`, `contracts/schemas/`.
- `src/provisioning/ansible/roles/{config_links,gui_tools,compositor_configs,verify}/{vars,tasks}/…`.
- `src/runtime/src/runtime/adapters/{consumer_path_spec,seeder,gtk4_app_subscriber}.py` and a repo-wide `icons.json`/`colors.css` grep.
- All five `src/gui-tools/*` app trees; the three scaffold repos at `/home/inumaki/Development/{contracts,ags-platform,ags-apps}`.
- `.memlog.md` (the author's own constraint/decision ledger).

---

## Findings

Severity scale: **critical** = two AD-conformant units can build incompatible results on a load-bearing seam; **high** = a rule is unenforceable or contradicts the brownfield in a way an implementer will hit immediately; **medium** = a real hole that costs a rewrite or a divergence later; **low** = polish.

### F1 — AD-1 and AD-4 give opposite answers for the bar-specific ports (CRITICAL)

**Section:** AD-1 Rule vs AD-4 Rule, the Layer-namespace table, and the Structural Seed.

- AD-1: *"Bar-specific ports (`LayoutProvider`, `SurfaceSpec`, `PopupHost`) stay with the bar, not the platform."*
- AD-4: *"the platform defines exactly these ports … `LayoutProvider`, `SurfaceSpec`/`SurfaceRegistry`/`PopupHost` …"*
- Layer table: ports live in `ags-platform/ports/`, listing those three.
- Structural Seed: `ags-platform/ports/ # … LayoutProvider, SurfaceSpec/SurfaceRegistry/PopupHost …` **and** `ags-apps/bar/ # … LayoutProvider default, SurfaceSpec bodies, PopupHost …`.

**Why it's a hole.** AD-1 is the top structural invariant — the one rule that keeps the split mechanical. Its carve-out says the bar owns the *interfaces*; AD-4/seed say the platform owns them. Two conformant units can satisfy different ADs: U-A puts `LayoutProvider`/`SurfaceSpec`/`PopupHost` types in `ags-apps/bar`, U-B puts them in `ags-platform/ports`. They cannot compile against each other and the "one-way dependency" cannot be checked. This is the same defect `review-brownfield-ratification.md` F2 already flags; I confirm it independently and rate it critical because it is the load-bearing AD.

**Suggested fix (autofix).** Strike the parenthetical from AD-1, or rewrite it to: *"The bar-specific **default implementations** (`LayoutProvider` default, `SurfaceSpec` bodies, `PopupHost` primitive) live in `ags-apps/bar`; their **interfaces** live in `ags-platform/ports` (AD-4)."* Make AD-1 and AD-4 cite each other so they cannot drift.

**Disposition:** autofix.

---

### F2 — The operational/environmental envelope is silent (CRITICAL)

**Section:** whole-spine; the only operational rule is AD-17 (Distribution) and the AD-19 gate rule. Nothing on CI, environments, or how the framework reaches a machine.

**Why it's a hole.** The checklist explicitly owns this dimension and the spine leaves it undecided:

1. **CI per new repo is undefined.** `contracts/`, `ags-platform/`, `ags-apps/` exist as empty scaffolds with `TODO` Makefiles and **no `.github/` directory at all** (verified: `ls -R /home/inumaki/Development/{contracts,ags-platform,ags-apps}/.github` → nothing). `HANDOFF-ags-platform.md` §7 says so outright: *"Still to define: CI per repo (none yet)."* AD-6 promises *"a regenerate-and-diff gate fails CI on drift"* and AD-19 promises *"the per-app drift/symbol suites run in the root gate"* — but there is no CI in the repos those gates must run in. A rule that names CI it never defines is unenforceable.
2. **How the framework gets onto a host is undefined.** AD-17 says the framework is *"installed as one versioned unit at a shared ancestor … Provisioning installs it once."* It never says **from where**: `git clone` of `ags-platform`? a release tarball? `gh release download`? a vendored copy inside `dotfiles-v3`? The scaffold README says *"extract the ports + adapters from dotfiles-v3 in-place … then publish here,"* so the unit must travel from the repo back into provisioning — the mechanism is unstated.
3. **The credential story for a fresh host is unstated.** The Stack table names *"GitHub (private repos) via `gh`, HTTPS credential helper"* — an **agent-shell** fact (`HANDOFF` §1), not a target-machine fact. A freshly provisioned host running `bootstrap.sh` has no `gh` credential; if provisioning fetches a private repo, install fails. This is the operational half of the distribution decision and it is missing.
4. **Environments are unstated.** The repo already has a VM harness (`make vm-*`) and a **`[self-hosted, linux]`** CI runner for `ags-typecheck` (`.github/workflows/gates.yml:339-348`). The spine never says which environment the platform/apps repos' gates run in, though `ags-platform`'s whole reason for existing is to be typechecked/bundled — and those gates need the desktop stack.

**Why two units diverge.** `contracts` publishes bindings with no CI to check them; `ags-platform` and `ags-apps` have no CI at all; provisioning has no defined fetch step. Any two of these can be built and shipped without a shared, executed definition of "installed."

**Suggested fix (discuss).** Add a short **"Operational envelope"** section (or an AD-21) that decides, at minimum: (a) per-repo CI — runner class (`ubuntu-latest` vs `[self-hosted, linux]`) and the gate list; (b) the framework fetch/install mechanism and its version-pin source; (c) the fresh-host credential path for a private-repo fetch (or a decision to vendor the unit in `dotfiles-v3`); (d) the environment matrix (dev host / VM / self-hosted runner). Anything not decidable now becomes an explicit Open Question, not silence.

**Disposition:** discuss.

---

### F3 — AD-16 names the wrong producer for `icons.json`, and the artifact location is undefined (HIGH)

**Section:** AD-16 Rule; contrast with `compositor_configs` role and the `icons-json-drift` gate.

AD-16 says: *"the runtime produces `icons.json`, optional `bar.json` (`BarLayout`), and `colors.gtk.css`."*

**Brownfield reality (verified):**

- `icons.json` is produced by **provisioning**, not the runtime: `compositor_configs` writes it with `(from_yaml) | to_nice_json(indent=2)` from the committed `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`, into `config/ags/icons.json` **and** `config/ags-capture/icons.json` (`roles/compositor_configs/vars/main.yml:321-326`, `tasks/main.yml:88-96`). The Makefile's `icons-json-drift` gate exists precisely because *"icons.json is GENERATED OUTPUT — the compositor_configs role writes it."*
- The **runtime** produces the rendered SVG art under `…/state/dotfiles/current/icons/` and the palette pointer target `current/colors.gtk.css` (the config-dir `config/ags/colors.css` is a symlink to it — `runtime/adapters/consumer_path_spec.py:49`).
- A repo-wide grep for `icons.json` under `src/runtime/src` returns **zero** hits.
- The bar reads `icons.json` by **build-time import** (`lib/icon-registry.ts` imports `../icons.json`); the other apps read it at **runtime** from `~/.config/ags/icons.json` (e.g. `notifications/lib/icon-registry.ts`).

**Why it's a hole.** The provisioning contract's producer and path are wrong, so the platform's `IconProvider` adapter can point at the wrong place; and AD-16 lists `bar.json` as produced while the Deferred section says *"no such artifact exists today."* This overlaps `review-adversarial.md` F5 (both sides produce) — I confirm it and add the exact producer/path evidence.

**Suggested fix (autofix).** Restate AD-16 as two producers with named destinations: *"Provisioning produces `icons.json` (from `icons.yaml`) into each app's config dir; the runtime produces `colors.gtk.css` (and the rendered art) into the state `current/` dir. Each carries its own `schemaVersion`."* Move `bar.json` to Deferred in AD-16 itself (or delete it from the list until the override exists).

**Disposition:** autofix.

---

### F4 — The validator seam is not implementable as written, and it breaks AD-1 (HIGH)

**Section:** AD-14 + AD-15, against doc 101 §6.1/§6.2/§10.

- AD-14: *"a **pure** `bar-manifest.ts` (no GJS) declares capabilities, params, and icon groups, and is imported by **both** the app and the validator."*
- AD-15: *"`validateLayout` and `validateIcons` are the shared functions."*
- doc 101 §6.2: `validateLayout(layout: BarLayout, capabilities: readonly Capability[])` where `Capability` (doc 101 §6.1) has `create(params, ctx): WidgetSpec` — i.e. runtime objects.
- doc 101 §10 manifest: `export const MANIFEST: CapabilityDecl[]` — a pure declaration with no `create`.

**Two holes.**

1. **Type seam:** the validator wants `Capability[]` (with `create`, referencing `BarContext`/GJS), but the pure manifest supplies `CapabilityDecl[]`. A GJS-free validator cannot consume a type that pulls in `WidgetSpec`/`BarContext`. There is no `CapabilityDecl` type in the frozen port surface.
2. **Dependency inversion:** the platform CLI `ags-bar-validate` importing the bar's `bar-manifest.ts` is a **platform → app** dependency, which AD-1 forbids (*"the platform depends on contracts only"*). The doc 101 CLI takes a `bar-manifest.json` file, which would avoid this — but AD-14 says the validator *imports the `.ts`*.

This is adjacent to `review-adversarial.md` F7 (port-shaped vs artifact-shaped `validateIcons`), but the `Capability`/`CapabilityDecl` mismatch and the AD-1 inversion are not covered.

**Suggested fix (discuss).** Freeze a pure `CapabilityDecl` type **in the platform** (`{id, params?, icons?, multi?}` with no `create`), have `bar-manifest.ts` build `CapabilityDecl[]`, and make the CLI consume a serialized `bar-manifest.json` (data, not an import). `Capability` (with `create`) stays app-side and *composes* a `CapabilityDecl`. State that the validator depends on contracts + the decl type only.

**Disposition:** discuss.

---

### F5 — AD-17 assumes a package boundary that does not exist and omits the migration cleanup (HIGH)

**Section:** AD-17; Structural Seed; Open Questions.

AD-17: *"the framework is installed as one versioned unit … found by a bare specifier via a `node_modules` shortcut."*

**Holes.**

1. A bare specifier (`import … from "ags-platform"`) requires a **package boundary**: a `package.json` with `name`/`main` (or `exports`) and an entry module. The `.memlog.md:22` records the truth: *"No package boundary exists: no package.json, no export map, no tsconfig paths, no node_modules resolution in the AGS tree. Every seam is copied source. Extraction is a rewrite of call sites, not a move."* AD-17 never defines the package manifest, entry point, or `exports` map — so the shortcut it mandates cannot resolve. This overlaps `review-adversarial.md` F10 ("entry point unspecified"); I confirm and add the memlog citation.
2. The `.memlog.md:29` constraint — *"no enumeration or cleanup of the ~200 previously placed per-file copies when switching to a one-unit install"* — is not in the spine at all. AD-17's whole premise is dropping per-file enumeration, but the ~200 stale files placed by `gui_tools_app_files`/`compositor_configs` remain on disk and no rule removes them. Two units can disagree on whether old copies are authoritative.

**Suggested fix (discuss).** Add to AD-17: the framework ships a `package.json` (`name`, `exports`/`main`, `version`); and add a provisioning cleanup step (`state: absent` over the retired framework files, mirroring `gui_tools_capture_obsolete`) as part of the consumption branch.

**Disposition:** discuss.

---

### F6 — AD-19's "run in `gates-ci`" is unenforceable and contradicts the repo's own documented CI split (HIGH)

**Section:** AD-19, against `Makefile` `gates-ci` and `.github/workflows/gates.yml`.

AD-19: *"before extraction begins, `bar-typecheck` and `ags-typecheck` must cover the extracted surface and run in `gates-ci`."*

**Brownfield reality (verified):**

- `Makefile`: `gates-ci: $(filter-out capture-typecheck bar-typecheck ags-typecheck,$(GATES))` — **both are explicitly excluded** from `gates-ci`.
- `gates.yml` header: they *"CANNOT run on a stock `ubuntu-latest` runner at all"* (no AGS/Astal/GTK4; `ags types` writes machine-specific 49 MB `.d.ts`; error buckets keyed to `/usr/share/ags/js/`).
- `gates.yml` gives `ags-typecheck` a `[self-hosted, linux]` job but **`bar-typecheck` has no CI job anywhere** (`ci-gates-parity.py` `CI_EXCLUDED_GATES` lists `bar-typecheck` with a "cannot run" reason).
- `scripts/ags-typecheck.py` today only fails on `dotfiles/config/ags/audio/` (the Makefile baseline is 32 errors); "cover the extracted surface" means clearing that baseline, which AD-19 does not say.

So AD-19 names a specific target (`gates-ci`) that by construction excludes the two gates, and provides no mechanism for `bar-typecheck`. This overlaps `review-brownfield-ratification.md` F3/F4; I confirm and sharpen: the *mechanism* (self-hosted runner for `bar-typecheck`, and the baseline clearing) is the missing decision.

**Suggested fix (discuss).** Reword AD-19 to *"run in CI (self-hosted runner for the desktop-stack gates)"* and reconcile with `ci-gates-parity.py`'s exclusion lists; add the requirement that the `ags-typecheck` baseline reach zero for the extracted surface before extraction. Decide whether `bar-typecheck` gets a self-hosted job.

**Disposition:** discuss.

---

### F7 — The domain-adapter layer (network / battery / bluetooth / audio / services) is unplaced (HIGH)

**Section:** Design Paradigm layer table + Structural Seed + Capability→Architecture Map.

The layer table names `ports` and `adapters` (icons, events, preferences, notifier, theme, baselines) and `bar-specific`. The Structural Seed's `ags-apps/bar/` is *"Shell + 4 shapes, LayoutProvider default, SurfaceSpec bodies, PopupHost, capabilities, bar-manifest.ts"* — **no `domains/`, no `services/`, no `audio/`**. Yet:

- the brownfield's largest body of code is exactly this layer: `dotfiles/config/ags/audio/` (hexagonal: `application/ports.ts`, `domain/`, `adapters/`, `presentation/`), `domains/network/read-model.ts`, `services/{wifi-service,power-service,bluetooth-service,mpris-core,speedtest-service,nm-client}.ts`, `components/{wifi,bluetooth,battery,sliders,primitives}`;
- doc 100 §5.3 calls the reactive read model *"the deepest lesson"* and doc 101 §13 step 2 is *"Reactive domain read models … as Astal adapters"*;
- the Capability map says *"Reactive domain read models (network, battery, bt, audio) | **app adapters**"* — but no layer row and no seed path says where "app adapters" live.

**Why it's a hole.** A whole architecture layer (and the migration's biggest chunk) is decided nowhere. Two units can place the network read model in `ags-platform/adapters/`, in `ags-apps/bar/domains/`, or in a per-app module, and the "platform carries no app-specific policy" rule is untestable. `review-adversarial.md` F1 addresses icon-manifest ownership but not the domain/service layer.

**Suggested fix (autofix + discuss).** Add a layer-table row and a seed path: `ags-apps/<app>/domains/` (Astal read models + actions) and `ags-apps/bar/audio/` (or wherever the audio hexagon lands), and state explicitly that domain read models are app-level adapters that may import platform ports but never another app.

**Disposition:** autofix (seed/layer table); the audio-app-vs-bar placement is a discuss.

---

### F8 — The icon read strategy is left open while the port surface claims to be frozen (HIGH)

**Section:** AD-4/AD-7 vs `lib/icon-registry.ts` and the four app registries.

`.memlog.md:23` records: *"Bar icon registry is build-time (imports `../icons.json`, resolveJsonModule); the 4 apps runtime-read `~/.config/ags/icons.json` (capture also probes `ags-capture/icons.json`). One platform adapter must pick one read strategy."* AD-4 declares the `IconProvider` surface *frozen* and AD-7 declares the uniform icon contract, but neither picks the strategy. Build-time import means the manifest is baked into the bundle (stale until re-bundle); runtime read means a hot-updated `icons.json` is seen without a restart. Two conformant adapters differ observably.

**Suggested fix (discuss).** Add one line to AD-4/AD-7: the platform `IconProvider` adapter **runtime-reads** the manifest from a single config path (or build-time-imports it) — pick one and say why. Overlaps `review-adversarial.md` F1; the missing *decision* is the point.

**Disposition:** discuss.

---

### F9 — AD-6 reverses an owner-accepted AD-44 without marking it superseded, and doesn't state the fate of the live gate (MEDIUM)

**Section:** AD-6.

AD-6: *"This **reverses AD-44** (the prior no-codegen decision)."* The Phase-5 spine (`architecture-dotfiles-repo-v3-2026-09-11-phase5/ARCHITECTURE-SPINE.md:106`) still stands as *"AD-44 — Shared contracts are machine-enforced … no codegen pipeline"* (`phase5/.memlog.md`). The current, executed brownfield gate is `contracts-check` (embedded constants + per-language drift tests), and the codegen prototype is a spike with known gaps (`.memlog.md:42`: reads a second `contract.json`, does not parse the canonical XML, stale). AD-6 does not say AD-44 is superseded, does not say where the generator lives (the `.memlog.md:45` decision says *"Contracts repo owns the generator"* — the spine omits this), and does not say what happens to `contracts-check`. Overlaps `review-adversarial.md` F4; I add the governance/supersession gap.

**Suggested fix (discuss).** Add to AD-6: *"Supersedes Phase-5 AD-44"*; *"the generator lives in `contracts/`"*; and the migration of `contracts-check`/`test_event_contract_drift.py` (retire vs keep as a second net).

**Disposition:** discuss.

---

### F10 — Theme is a port with no injection path (MEDIUM)

**Section:** AD-13 vs AD-4 `BarContext` and AD-2.

AD-13 declares a `Theme` port and AD-4 lists it, but the frozen `BarContext` (AD-4 / doc 101 §4.7) has `overlays, hub, icons, surfaces, notifier, preferences, exec` — **no `theme`**. AD-2 forbids module globals, so an app cannot reach the `Theme` provider except through injection, and there is none. The same is true for `LayoutProvider` (not in `BarContext`) if it is platform-owned (F1). The brownfield confirms the need: three `theme.ts` copies plus direct `app.apply_css` in `bar`, `capture-tool`, `hypr-pano` (`dotfiles/config/ags/app.tsx:138`, `src/gui-tools/capture-tool/app.tsx:45`, `src/gui-tools/hypr-pano/app.tsx:11`). `review-adversarial.md` F9 notes two files/paths; the injection hole is distinct.

**Suggested fix (autofix).** Add `theme: Theme` (and, per F1, the bar-specific providers) to `BarContext`, or define the "provider injection" mechanism AD-2 alludes to but never specifies.

**Disposition:** autofix.

---

### F11 — AD-8's `popup(...)` capability does not exist on `BarContext` (MEDIUM)

**Section:** AD-8 vs AD-4 `BarContext`.

AD-8: *"`popup(...)` and `hub.control(...)` are `BarContext` capabilities."* `BarContext` has `overlays` (`OverlayCoordinator`) and `surfaces` (`SurfaceRegistry`), not a `popup(...)` method. `hub.control(...)` is fine (on `EventHub`). An implementer cannot call a capability the frozen port doesn't expose.

**Suggested fix (autofix).** Name the real member (`ctx.surfaces`/`ctx.overlays`) or add `popup(...)` to `BarContext`. Overlaps `review-adversarial.md` F8 on the content shape; the naming mismatch is the concrete fix.

**Disposition:** autofix.

---

### F12 — "The platform carries no dotfiles paths" vs the Preferences adapter owning the capture-tool file (MEDIUM)

**Section:** Design Paradigm intro vs AD-12 / doc 101 §4.6.

The Design Paradigm says *"The platform carries **no app-specific policy and no dotfiles paths**."* AD-12 says the `Preferences` adapter *"owns the file and the monitor lifecycle"*; doc 101 §4.6 names *"the capture-tool config file (`bar_compact_controls`)"* as the first adapter. So the platform's preferences adapter hardcodes knowledge of the capture-tool's config file — an app-specific path — unless namespaces are registered by the app. AD-12 does not say which. (Relatedly, the `IconProvider` adapter must know `~/.config/ags/icons.json` — a dotfiles path.)

**Suggested fix (discuss).** State that the adapter is **parameterized by namespace→path registrations supplied by apps** (so the platform holds no literal app path), or soften the "no dotfiles paths" claim to "no dotfiles paths in ports; adapters are configured with them."

**Disposition:** discuss.

---

### F13 — AD-20 does not actually state deletion, and the app extraction source (`src/gui-tools/`) is absent from the seed (MEDIUM)

**Section:** AD-20 vs Capability→Architecture Map and Structural Seed.

The Capability map row *"Deletion of duplicates | dotfiles-v3 | AD-20"* attributes deletion to AD-20, but AD-20's Rule is only *"extract in-place … then publish … integrate contracts → platform → apps"* — no deletion step. And the Structural Seed lists `dotfiles-v3/dotfiles/config/ags/` (the bar in-place) and `src/provisioning/`, but **never `src/gui-tools/`**, which is where five of the six apps currently live (`capture-tool`, `hypr-pano`, `notifications`, `wallpaper-selector`, `icon-color-mapping-editor`). The migration story for those apps (source, in-place bridge, deletion) is invisible.

**Suggested fix (autofix).** Add an explicit deletion step to AD-20 (or its own AD), and name `src/gui-tools/<app>/` in the Structural Seed as the apps' current source / in-place bridge.

**Disposition:** autofix.

---

### F14 — The contract-move ripple is unaddressed (MEDIUM)

**Section:** AD-6 / AD-20.

`.memlog.md:16` and `HANDOFF-ags-platform.md` §4.4 record that moving `contracts/` ripples through: the runtime `conftest` repo-root keyed on `contracts/schemas/history.schema.json` (all runtime tests), `bar_subscriber._find_contract` raising at import, four `event-contract-drift.mjs` files hardcoding repo-relative paths, the Makefile `contracts-check`, the CI `contracts` job, and the provisioning `verify`/`gui_tools` vars that pin the exact file layout plus their structural tests (verified in `roles/verify/vars/main.yml` and `gui_tools`). AD-6/AD-20 don't mention repointing any of it.

**Suggested fix (defer + record).** Add a Deferred bullet or an AD-20 prerequisite: "moving `contracts/` repoints the runtime conftest, `bar_subscriber`, the four drift tests, `contracts-check`, and the provisioning verify/gui-tools path pins."

**Disposition:** defer.

---

### F15 — Stack table: stale/ambiguous named tech (LOW–MEDIUM)

**Section:** Stack.

Covered thoroughly by `review-web-verify.md` (AGS 3.1.0 vs 3.1.2; TypeScript 5.9 vs current; "Astal/GNIM embedded" conflates two; Node version omitted though `HANDOFF` §1 says Node 26; the AGS/esbuild behavior is host-verified only, no committed test). I confirm and add only: the spine should name the **Node** version (the `node --test` and type-stripping behavior depends on it) and record that the bare-specifier resolution is **AGS's embedded esbuild**, not Node (the spine's Open Question #3 says "Node resolves", which the sibling review shows is a misnomer).

**Disposition:** autofix (add Node row / reword #3).

---

### F16 — Minor inconsistencies (LOW)

- **`icme` vs `icon-color-mapping-editor`:** the layer table and seed use `icme`; the repo, the deployed dir (`ags-icme`), and doc 101 use `icon-color-mapping-editor`. The Consistency Conventions demand kebab-case stable ids. **autofix.**
- **`OverlayCoordinator`** is called out in AD-4's correction list and referenced by `BarContext`, but is not in AD-4's *"exactly these ports"* enumeration. **autofix.**
- **`EventSource.subscribe` unsubscribe** is described as a target correction but the moved `DomainEventBusCore` has no unsubscribe (handlers live in a `Set` with no removal) — the spine flags `EventHub.select` as "new machinery" but not this. **autofix** (one clause).
- **"runtime" overload:** AD-3 (*"the runtime emits state, never layout"*) and AD-9/AD-16 (runtime layout override / `bar.json`) use "runtime" for the daemon in one place and for a layout-chain element in another; the Deferred section says `bar.json` doesn't exist while AD-16 lists it. Disambiguate "the runtime daemon" from "the runtime layout provider," and mark `bar.json` deferred in AD-16 too. **autofix.**

**Disposition:** autofix (all four).

---

## Dimension coverage matrix (the checklist's "decided / deferred / open / silent")

| Dimension the altitude owns | Status in spine | Note |
|---|---|---|
| Dependency direction / repo topology | decided (AD-1) | contradicted by AD-4 (F1) |
| Ports & shared adapters | decided (AD-4) | validator type seam open (F4); icon read strategy open (F8) |
| Domain read models / services / audio hexagon | **silent** | F7 |
| Widget shapes / layout / surfaces | decided (AD-8/9/10) | `popup()` member mismatch (F11) |
| Icon contract | decided (AD-7) | producer/read-strategy gaps (F3/F8) |
| Event contract / codegen | decided (AD-5/6) | supersession + ripple gaps (F9/F14) |
| Provisioning artifacts / validators | decided (AD-15/16) | producer + type seam (F3/F4) |
| Preferences / Notifier / Theme | decided (AD-11/12/13) | Theme injection + app-path leak (F10/F12) |
| Packaging / distribution | decided (AD-17) | package boundary + cleanup (F5) |
| Baselines ("works with nothing") | decided (AD-18) | — |
| Migration sequencing / gates | decided (AD-19/20) | CI mechanism + deletion (F6/F13) |
| **Deployment & environments** | **silent** | F2 |
| **Infra/provider strategy (fetch, credentials, version pin)** | **silent** | F2 |
| **Operations (rollback, cleanup, recovery)** | partial (Open Questions) | F2/F5 |
| **CI per repo** | **silent** | F2 |
| **Tech currency** | partial (Stack) | F15 |

The three rows in bold are the checklist's "whole dimension left silent" finding, and they cluster in one place: **the operational/environmental envelope (F2)**.

---

## What the spine gets right

- The target-vs-current framing (Design Paradigm paragraph) is honest and matches `.memlog.md`; the six AD-4 corrections are each verifiable against the code (`IconRef.fallback` absent, `subscribe` returns `void`, `IconSource` union absent, `BarMapping` snake_case, `overlays` singleton, `EventHub.select` unimplemented).
- Duplication counts are exact: 5 `icon-registry.ts`, 4 `event-bus-core.ts` + 2 bespoke notification readers, 3 `theme.ts`, 5 popup chromes (doc 101 said 4, spine correctly adds Bluetooth).
- AD-17's premise (notifications per-file list omits `lib/speedtest-events.ts` while `NotificationsWindow.tsx:8` imports it) is TRUE and verified.
- The deployment-shape correction (shared ancestor so `config/ags` **and** every `config/ags-*` resolve) is the right fix for the `.memlog.md:26` finding and matches the real `config/ags-*` dirs.
- AD-18's "works with nothing" and AD-10's mount-lazily rule are enforceable and prevent named races.

---

## Disposition summary

| # | Finding | Sev | Disposition |
|---|---|---|---|
| F1 | AD-1 vs AD-4 bar-specific ports | critical | autofix |
| F2 | Operational/environmental envelope silent | critical | discuss |
| F3 | AD-16 wrong producer / location for `icons.json` | high | autofix |
| F4 | Validator type seam + AD-1 inversion | high | discuss |
| F5 | Package boundary missing + ~200-file cleanup | high | discuss |
| F6 | AD-19 `gates-ci` unenforceable vs CI reality | high | discuss |
| F7 | Domain-adapter layer unplaced | high | autofix + discuss |
| F8 | Icon read strategy left open | high | discuss |
| F9 | AD-44 supersession + `contracts-check` fate | medium | discuss |
| F10 | Theme port has no injection path | medium | autofix |
| F11 | `popup()` not on `BarContext` | medium | autofix |
| F12 | Preferences app-specific path leak | medium | discuss |
| F13 | AD-20 deletion + `src/gui-tools/` source | medium | autofix |
| F14 | Contract-move ripple | medium | defer |
| F15 | Stack tech currency / Node | low | autofix |
| F16 | Minor inconsistencies (naming, OverlayCoordinator, unsubscribe, "runtime") | low | autofix |

**Recommended gate to unfreeze:** F1, F2, F3, F4, F6, F7, F8 resolved (or explicitly deferred with a named revisit condition). F1/F3/F7/F10/F11/F13/F15/F16 are safe autofixes; F2/F4/F5/F6/F8/F9/F12 need an owner decision.

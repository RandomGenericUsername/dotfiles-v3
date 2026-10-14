# Adversarial Review — AGS Platform Architecture Spine

- **Reviewer lens:** adversary. Construct two units one level down that each obey every AD to the letter, yet still build incompatibly — clashing shared-data shapes, two owners of one entity, conflicting state-mutation paths.
- **Target:** `ARCHITECTURE-SPINE.md` (draft, 2026-10-09), `_bmad-output/planning-artifacts/architecture/architecture-ags-platform-2026-10-09/`
- **Codebase:** `/home/inumaki/Development/dotfiles-v3` (read-only; spine not edited)
- **Date:** 2026-10-09

**Verdict:** The spine freezes a strong *dependency direction* and a strong *ownership rule* (AD-3), but it freezes almost none of the **shared-data identity** those rules depend on. Every seam below is a place where two units can each quote the ADs and still disagree about *which artifact is the truth*, *who owns a topic/entity*, or *what the envelope is called*. Ten holes; five are critical/high and would produce real, silent runtime divergence on the current tree.

The recurring root cause: **the spine names ports and rules but not the artifacts' identity, location, envelope, or single producer.** AD-3 says "the state key is the boundary"; AD-6 says "the contract is the single source"; AD-16 says "each artifact carries its own `schemaVersion`" — but the spine never says *which file the port reads*, *which unit writes it*, or *which field is the version*. Two conforming implementations therefore fork at the first integration.

---

## F1 — The icon manifest has three owners and two shapes; the port reads a different source than the artifact

**Severity: CRITICAL**

**The two units:**

- **Unit A — `ags-apps/bar`'s `IconProvider` adapter.** Built from the *committed, build-time-bundled* manifest. Today: `dotfiles/config/ags/lib/icon-registry.ts:2` does `import iconsData from "../icons.json"` — a static import resolved by esbuild at bundle time. The committed file (`dotfiles/config/ags/icons.json`, 22 groups, git-tracked) has **no `schemaVersion`** and carries `bar_mappings` with snake_case keys (`icon_size`, `states`, `widget`) — verified.
- **Unit B — `ags-apps/notifications`' `IconProvider` adapter.** Built from the *runtime-read file* `~/.config/ags/icons.json` (`src/gui-tools/notifications/lib/icon-registry.ts:15`), lazily cached, with `reloadIconManifest()`. Same for `wallpaper-selector/lib/icon-registry.ts:31` and `hypr-pano/lib/icon-registry.ts:30`. (Capture-tool reads a *fourth* copy: `~/.config/ags-capture/icons.json`, per `src/provisioning/ansible/roles/compositor_configs/vars/main.yml:326`.)

**ADs each obeys:**

- Unit A: AD-7 (code emits a state key; provider maps `key → variant → art` through `bar_mappings.states`), AD-4 (`IconSource` tagged union; `BarMapping` camelCase at the port; adapter translates `icon_size`), AD-1 (bar-specific port stays in the app).
- Unit B: AD-7, AD-4, and **AD-16** (the runtime produces `icons.json` with its own `schemaVersion`; the app reads the artifact).

**The incompatibility (exact):**

The spine says `provider.barMappings(group)?.states[v] → provider.resolve(group, v)` (AD-7) and that the runtime produces `icons.json` with a `schemaVersion` (AD-16). It never says **the provider's source is the runtime artifact**, nor that `bar_mappings` and `variants` come from the *same* file. So:

- Unit A reads a **build-time-bundled** manifest whose `bar_mappings.states` is frozen at `ags bundle` time; its `variants` list names SVG outputs the runtime may have replaced.
- Unit B reads the **runtime** artifact and can hot-reload it.

Both are valid `IconProvider`s. But the runtime's `icons regenerate` rewrites the rendered set under `~/.local/state/dotfiles/current/icons/` (the art dir every registry hardcodes: `icon-registry.ts:30`, `notifications/lib/icon-registry.ts:14`). After a regenerate, Unit B sees the new table; Unit A's table is stale and can name a variant whose `output` no longer exists — silently blanking a glyph. Worse, AD-15's `missing-icon-key` is validated by provisioning against **whichever `icons.json` provisioning happens to hold**, while the bar resolves against its bundled copy. The validator and the bar can validate different manifests and both pass.

This is a **clashing shared-data shape** (schemaVersion-less bundle vs versioned artifact) *and* a **two-owners-of-one-entity** collision (runtime + provisioning + the repo all "own" the manifest). The three existing drift tests do not cover icons at all — they only cover event-contract literals.

**Proposed AD-21 — One icon manifest, one source, read at runtime.**
The `IconProvider`'s source is the runtime artifact at a single fixed path; `bar_mappings` and `variants` MUST come from the same artifact. No consumer may `import` a committed `icons.json`; the build-time bundle is deleted. Provisioning validates the *runtime artifact*, never a repo copy. The `IconProvider` adapter is the only translator from the artifact's snake_case to the port's camelCase.

---

## F2 — `speedtest.state` has two producers; AD-3's "only the runtime changes state" is already violated

**Severity: CRITICAL**

**The two units:**

- **Unit A — the AGS bar's `services/speedtest-service.ts`.** It publishes `starting`/`done`/`error` via `publishSpeedTestState` (`dotfiles/config/ags/lib/event-bus.ts:172`, called at `services/speedtest-service.ts:196`). It is an **app**.
- **Unit B — the runtime's `application/speedtest.py`.** `SpeedTestJob` publishes the terminal `speedtest.state done` through the hub (`speedtest.py:63-72`). It is the **runtime**.

**ADs each obeys:**

- Unit A: AD-6 (payload is contract-shaped; enums/requireds typed so a bad payload is a compile error), AD-5 (goes through the one client's `Emit`/`Control`), AD-11 (it is a *sender*).
- Unit B: AD-6, AD-5, **AD-16** ("runtime owns events — the topic vocabulary and the job lifecycle").

**The incompatibility (exact):**

The contract names **one** producer: `contracts/event-contract.json:69` → `"speedtest.state": { "producer": "speed-test service" }`, and the contract notes promise **"Exactly one done OR error is emitted per run."** With two producers on one topic:

- The bar emits `done` after its own (manual/scheduled/connect) run; the runtime job emits `done` for the scheduled run. If both run, two terminal events land on the same topic; the notifications card (replace-by-key, `NotificationsWindow.tsx:1033`) flips twice and the `producer` field is a lie on half of them.
- The hub's `seq` is per-topic monotonic and dedup is `(epoch,seq)`, so **neither producer can enforce the "one terminal per run" invariant** — it is a cross-unit invariant with no owner.
- This directly contradicts **AD-3**: "only the runtime changes state; apps render." Unit A is an app mutating shared domain state. AD-5's "one event client" does not help: it is one *client*, not one *producer*.

**Proposed AD-22 — One producer per topic; apps never `Emit` domain state.**
For every contract topic, exactly one unit is the producer, and that unit is the runtime (or a runtime-hosted job). Apps post `NotificationIntent`s (AD-11) and call `Control`; they never `Emit`. The `producer` field is a contract-checked invariant, not documentation. If an app must originate a run, it `Control`s a runtime job.

---

## F3 — The event client's restart contract is optional; two consumers diverge on restart and on the hydration edge

**Severity: HIGH**

**The two units:**

- **Unit A — the bar's client.** `DomainEventBusCore` (`dotfiles/config/ags/lib/event-bus-core.ts`) installs `DomainEvent`, `JobsCleared`, **and** `NameOwnerChanged`; on `JobsCleared` it resets via `handleHubRestart()` (clears `hydrated`, fires restart handlers, re-hydrates) and re-delivers hydration when `state.epoch > 0 || payload non-empty` (`event-bus-core.ts:147-161`).
- **Unit B — the notifications app's clients.** `speedtest-events.ts` and `wallpaper-events.ts` install `DomainEvent` + `NameOwnerChanged` only; **no `JobsCleared`**. Their `dispatch` uses a strict `epoch < lastEpoch || (epoch === lastEpoch && seq <= lastSeq)` predicate (`speedtest-events.ts:55`) and hydration goes through that same predicate, so a `(0,0)` payload is **dropped**. Restart "handling" is just a re-`hydrate()` on a new owner; stale state is never explicitly invalidated.

**ADs each obeys:**

- Unit A: AD-5 (subscribe-before-read hydration + `(epoch,seq)` dedup inside the client), AD-4 (`EventSource.onRestart?` optional, so it may implement it).
- Unit B: AD-5 (dedup inside the client), AD-4 (onRestart is **optional** — Unit B legitimately omits it).

**The incompatibility (exact):**

AD-5 mandates "subscribe-before-read hydration + `(epoch, seq)` dedup lives there" but is silent on **what happens on hub restart** and on the **exact hydration predicate**. Two consequences, both reachable:

1. **Restart reset:** hub restarts with a new epoch while a run is mid-flight. Unit A clears the bar's recording indicator to `idle` and re-hydrates (`recording.tsx:112` registers `onRestart(reset)`). Unit B has no restart reset: the notifications card for a run that was `starting` in the old epoch never receives a terminal event (the new epoch's `seq` starts at 1 and the run is gone), so the card is **stuck on "starting" forever**. Same client contract, opposite behavior.
2. **Hydration edge:** a topic whose first state is `(epoch=0, seq=0)` with a non-empty payload is **delivered by Unit A** (`hydrateTopic` bypasses `isNewer` and checks payload non-empty) and **dropped by Unit B** (dispatch requires strictly newer). The two clients disagree on the very first hydration.

**Proposed AD-23 — One restart contract, one hydration predicate.**
The client handles `JobsCleared` *and* `NameOwnerChanged`; on either, it MUST invalidate all consumer state (emit a reset) **before** re-hydrating. `onRestart` is **mandatory**, not optional. The hydration predicate is defined once (deliver iff `epoch > 0 || seq > 0 || payload non-empty`), and both signal and hydration paths use the identical `isNewer`. A consumer that has not registered a reset handler is a startup error.

---

## F4 — Codegen'd bindings vs the runtime's hand-embedded tables: the drift gate is asymmetric, so the tables are already ahead of the contract

**Severity: CRITICAL**

**The two units:**

- **Unit A — `contracts/gen` (the generator, AD-6).** Emits Python + TS bindings and JSON schemas from `event-contract.xml`/`.json`; artifacts are committed into each consumer; a regenerate-and-diff gate fails CI on drift. The generator can only emit what the contract declares.
- **Unit B — the runtime's embedded tables.** `runtime/domain/hub.py:59` embeds `KNOWN_TOPICS`; `runtime/adapters/emit_validation.py:116` embeds `TOPIC_SCHEMAS`. Both are **hand-maintained**, pinned by "conformance tests" (`test_dbus_conformance.py:188`), not generated.

**ADs each obeys:**

- Unit A: AD-6 verbatim ("generated artifacts are committed into each consumer; a regenerate-and-diff gate fails CI on drift").
- Unit B: AD-6 as well — the runtime is a consumer; the module docstring says the table "mirrors `contracts/event-contract.json` … pinned executable by the conformance tests." AD-6's diff gate does not cover a table that is not generated.

**The incompatibility (exact):**

The runtime's embedded schema is **already ahead of the contract**, and the gate cannot see it:

- `emit_validation.py:176-204` declares `wallpaper.state` with `stage` (7-value enum) and `reload_failures` (string array). `contracts/event-contract.json:92-101` declares only `state`, `wallpaper_hash`, optional `trigger`.
- The notifications app **reads both** (`NotificationsWindow.tsx:321,344`). So a binding generated strictly from the contract would omit `stage`/`reload_failures`, while the runtime happily emits them — the exact "second source of truth" AD-6 exists to kill, and the exact gap the spine's **Deferred** section admits ("The `wallpaper.state.stage` contract gap — folded into the contracts codegen work (AD-6), not fixed here").
- `test_embedded_schema_table_matches_contract_topics` only checks **contract ⊆ schema** (`sorted(schema["required"]) == sorted(set(payload) - optional)`, and type checks for fields *present in the contract*). It never checks **schema ⊆ contract**. So extra runtime fields pass forever. The "diff gate" the spine promises would compare a *generated* artifact to the contract; the runtime's table isn't generated, so it isn't in the diff.

**Proposed AD-24 — No hand-embedded contract tables; the runtime imports the generated module; conformance is bidirectional.**
Every consumer's constants/schemas are generated artifacts (no exceptions for "the installed tool can't read `contracts/`" — the generated module ships *with* the runtime). The conformance gate asserts **set equality both ways**: `generated.topics == contract.topics`, `generated.schema == contract` (no extra properties, no extra required, no extra enums). `wallpaper.state.stage`/`reload_failures` are either promoted into the contract or removed from the runtime and the notifications consumer.

---

## F5 — Provisioning and the runtime both *produce* the same artifacts; AD-16 names only the runtime

**Severity: HIGH**

**The two units:**

- **Unit A — provisioning (dotfiles-v3).** `compositor_configs/tasks/main.yml:86-100` generates `icons.json` from `icons.yaml` and writes it to `config/ags/icons.json` **and** `config/ags-capture/icons.json`. It also creates the `config/ags/colors.css` symlink to the runtime's `colors.gtk.css` (`test_compositor_configs_role.py:814-817`).
- **Unit B — the runtime.** AD-16: "the runtime produces `icons.json`, optional `bar.json` (`BarLayout`), and `colors.gtk.css`." Today the runtime produces the *rendered SVGs* under `current/icons/` and `current/colors.gtk.css`; the manifest and the symlink come from provisioning.

**ADs each obeys:**

- Unit A: AD-15 (provisioning runs `validateLayout`/`validateIcons` and fails install on error — it therefore needs the artifacts), AD-14 (the manifest is imported by the app and the validator).
- Unit B: AD-16 (the runtime is the producer of the artifacts).

**The incompatibility (exact):**

AD-16 assigns production to the runtime; AD-15 requires provisioning to validate. The spine never says **provisioning must not generate**. So two units each obey their AD and produce `icons.json`:

- provisioning writes a `schemaVersion`-less manifest into the config dir at install time;
- the runtime writes a `schemaVersion`-bearing manifest into the state dir on `icons regenerate`.

The bar then reads a **third** copy (the committed bundle, F1). The entity "the icon manifest" has three owners and two envelopes. The validator runs against provisioning's copy; the runtime rewrites its own; the bar reads the bundle. The three can be mutually inconsistent with every AD satisfied.

**Proposed AD-25 — Exactly one producer per artifact; provisioning validates, never produces.**
`icons.json`, `bar.json`, and `colors.gtk.css` are produced by the runtime alone, at one path, with one envelope. Provisioning's only artifact verbs are *read* and *validate*; it MUST NOT generate or symlink any of the three. The repo commits none of them. This is the producer-side twin of AD-16's "the validator is the only place the two sides meet."

---

## F6 — The layout artifact has two version fields; the chain can silently drop the runtime override

**Severity: HIGH**

**The two units:**

- **Unit A — the repo-default `LayoutProvider` (bar-specific, AD-9).** Returns a `BarLayout` with `version: 1` (AD-4's port type: `readonly version: 1`).
- **Unit B — the runtime `LayoutProvider` (dotfiles host).** Reads the optional `bar.json` artifact; AD-16 says each artifact carries its own **`schemaVersion`**, and "an unknown version degrades, never crashes."

**ADs each obeys:**

- Unit A: AD-9 (whole-layout replacement; repo default always non-null), AD-4 (`BarLayout.version: 1`).
- Unit B: AD-16 (per-artifact `schemaVersion`; unknown version degrades), AD-9 (returns the whole layout or null).

**The incompatibility (exact):**

The port type versions the layout with `BarLayout.version` (AD-4); the artifact envelope versions it with `schemaVersion` (AD-16). The spine never says whether `bar.json` is `{ schemaVersion: N, ...BarLayout }`, a bare `BarLayout`, or where `version` lives. So:

- Unit A returns `{ version: 1, sections: … }`.
- Unit B reads `bar.json`, looks for `schemaVersion` (per AD-16), finds `version` instead, classifies it as an **unknown version**, and — obeying AD-16's "degrade, never crash" — returns `null`.

The chain is `user › runtime › repo-default` with "first non-null wins" (AD-9). Unit B's null falls through to the repo default, so **the runtime override is silently dropped**, and the user's `bar.json` never applies. Every AD is satisfied; the feature is dead. This is a clashing shared-data shape on the exact artifact AD-16 invents.

**Proposed AD-26 — One version field per artifact, named in the port.**
The artifact envelope is `{ schemaVersion: N, layout: BarLayout }`; `BarLayout.version` is deleted (or defined as *the envelope's* `schemaVersion`). The runtime `LayoutProvider` validates `schemaVersion` and, on mismatch, returns `null` **and emits a warning** — it never silently degrades into a no-op. The chain order and the null-fall-through rule are stated explicitly.

---

## F7 — `validateIcons` is port-shaped at runtime but artifact-shaped at install, and the baseline makes the two disagree

**Severity: HIGH**

**The two units:**

- **Unit A — the bar runtime (AD-15/AD-18).** Runs `validateIcons(icons: IconProvider, capabilities)` at startup and degrades. On a bare desktop the `icons` argument is the **symbolic baseline** `IconProvider` (AD-18), which has **no `bar_mappings`** and returns `{ kind: "name" }`.
- **Unit B — provisioning (AD-15/AD-16).** Runs `ags-bar-validate --manifest bar-manifest.json --icons icons.json --layout bar.json` and fails install on error. Here `icons` is the parsed artifact (snake_case), not an `IconProvider` (camelCase port).

**ADs each obeys:**

- Unit A: AD-15 (same functions, lenient enforcement), AD-18 (works with nothing; symbolic baseline), AD-7 (resolution chain `barMappings?.states[v] → resolve → fallback → blank`).
- Unit B: AD-15 (same functions, strict enforcement), AD-16 (validate the artifact), AD-4 (camelCase at the port).

**The incompatibility (exact):**

`missing-icon-key` is an **error** for groups declaring `states` (AD-15). But the baseline provider has no `states` table at all. So:

- At runtime with the baseline, `validateIcons` either (a) reports every declared state as missing → `ok:false` → the bar would have to ignore its own validator, or (b) special-cases the baseline, in which case it is **not the same function** AD-15 promises.
- At install, the validator is handed a **file** while the function signature takes an **`IconProvider`**. Either provisioning builds an adapter (and must translate snake_case → camelCase per AD-4) or it parses the file directly (and the port's camelCase guarantee is bypassed). The spine says "the adapter translates" but does not say the *validator* uses the adapter.
- `bar-manifest.ts` is a **pure TS module imported by both the app and the validator** (AD-14), yet the CLI takes `--manifest bar-manifest.json` (AD-15). Nothing says how the `.ts` becomes the `.json`, so the JSON can be hand-authored and drift — the exact failure AD-14 prevents.

**Proposed AD-27 — The validator's input is defined; the manifest is generated; baseline validation is explicit.**
`validateIcons` takes the **parsed artifact** (not a port) plus a flag for baseline mode; in baseline mode it validates structure only and never reports `missing-icon-key`. Provisioning builds the port adapter from the artifact (single translation site). `bar-manifest.json` is a generated artifact of the AD-6 codegen, gated regenerate-and-diff; it is never hand-authored.

---

## F8 — The `popup()` capability's content is unshaped, so a second live surface instance defeats AD-10

**Severity: MEDIUM**

**The two units:**

- **Unit A — `PopupHost` (AD-10).** Mounts `SurfaceSpec.body` **as a factory**, only while visible, tearing down when hidden; "at most one overlay is live."
- **Unit B — a widget using the `popup(...)` capability (AD-8).** AD-8 says "`popup(...)` and `hub.control(...)` are `BarContext` capabilities, not shapes." The spine never types `popup`'s content. Today the recording widget builds a `<popover>` with its content **constructed once** at widget-build time (`recording.tsx:191-225`) and holds it live alongside the bar.

**ADs each obeys:**

- Unit A: AD-10 verbatim.
- Unit B: AD-8 verbatim (it calls a capability), AD-10 (it did not construct a `SurfaceSpec`, so the "body is a factory" rule does not apply to it).

**The incompatibility (exact):**

Because `popup()`'s argument is unspecified, Unit B can pass **eagerly constructed JSX** while Unit A passes a **factory**. The `OverlayCoordinator`'s one-open-at-a-time guarantee (AD-9/AD-10) only covers surfaces registered as overlays; a `popup()` content tree built at widget construction time is live for the app's whole lifetime, independent of the coordinator. So the settings panel (which embeds Wifi/Bluetooth content) and the wifi `PopupHost` can both hold `WifiContent` simultaneously — the exact shared-state race AD-10 claims to make "structurally impossible." The two units each obey the letter of AD-8/AD-10.

**Proposed AD-28 — Every popup flows through `PopupHost`; `popup()` takes a factory or a `SurfaceSpec` id.**
The `popup` capability's content is a factory `(host) => JSX.Element` or a registered `SurfaceSpec` id — never constructed JSX. Content built at widget-construction time is forbidden. A `SurfaceSpec` may declare `singleton`; the coordinator enforces it across both overlay and embedded mounts.

---

## F9 — Theme is applied from two different files by two different paths

**Severity: MEDIUM**

**The two units:**

- **Unit A — a `Theme` adapter (AD-13).** "Applies the palette / `colors.gtk.css`." It would apply the runtime artifact path directly.
- **Unit B — every current app.** Applies `~/.config/ags/colors.css` directly via `app.apply_css` (`bar/app.tsx:138`, `capture-tool/app.tsx:45`, `hypr-pano/app.tsx:11`, plus `lib/theme.ts` in notifications/wallpaper-selector/icme).

**ADs each obeys:**

- Unit A: AD-13 (the port applies `colors.gtk.css`), AD-16 (that is the runtime artifact name).
- Unit B: AD-13's intent (routes theming), AD-16 (the artifact is runtime-owned), and it reads the **stable symlink** `colors.css → current/colors.gtk.css` (provisioning-owned today).

**The incompatibility (exact):**

AD-16 names the artifact `colors.gtk.css`; the deployed, generation-stable path is `colors.css` (a symlink the runtime repoints). An adapter implementing AD-13 by applying `colors.gtk.css` directly **caches a generation path**: after `wallpaper.state` repoints the symlink, the adapter is stale. An adapter applying `colors.css` is correct but does not "apply `colors.gtk.css`" per the AD's wording. Two conforming adapters diverge on whether a palette swap is visible without restart. Today the divergence is worse: each app calls `app.apply_css` itself, which AD-13 explicitly forbids ("direct `app.apply_css` calls"), yet nothing in the spine says which path the port applies.

**Proposed AD-29 — The Theme port applies the stable artifact path and re-applies on state transitions.**
The port applies the runtime artifact through its stable pointer (`colors.css`), never a generation path, and re-applies on `wallpaper.state` transitions. Direct `app.apply_css` outside the adapter is a build error.

---

## F10 — The distribution shortcut names a package whose entry point is unspecified

**Severity: MEDIUM**

**The two units:**

- **Unit A — the framework unit (`ags-platform/<version>/`).** AD-17: "installed as one versioned unit at a shared ancestor." The structural seed shows `<install>/ags-platform/<version>/`.
- **Unit B — provisioning's shortcut.** AD-17/structural seed: `config/node_modules/ags-platform -> ../../ags-platform/<version>`.

**ADs each obeys:**

- Unit A: AD-17 (one unit, versioned, found by a bare specifier).
- Unit B: AD-17 (the `node_modules` shortcut), and the spine's own Open Question ("verify before relying on it").

**The incompatibility (exact):**

A bare specifier `import { x } from "ags-platform"` requires the target to resolve as a **package** — a `package.json` with `name: "ags-platform"` and a `main`/`exports` entry. The seed shows the shortcut pointing at the *version directory*, but nothing in the spine requires that directory to contain a resolvable `package.json`, nor says whether the shortcut is a symlink to the version dir or a dir containing it. Two units each obey AD-17 and produce a tree where `ags-platform` either resolves (if the unit ships a `package.json`) or fails with a module-not-found that looks like a missing dependency. The spine explicitly defers this to an Open Question, which means the distribution contract is not frozen while AD-17 claims it is.

**Proposed AD-30 — The framework unit ships a resolvable package; the shortcut's shape is fixed.**
`ags-platform/<version>/` contains `package.json` (`name: "ags-platform"`, `exports` for ports/adapters). The shortcut is `config/node_modules/ags-platform -> ../../ags-platform/<version>`. A post-install smoke test resolves `ags-platform` from `config/ags` *and* every `config/ags-*` before provisioning succeeds. `ags`/`gnim` remain distinct built-in aliases.

---

## Summary

| # | Seam | Two units | Severity | Proposed AD |
|---|---|---|---|---|
| F1 | Icon provider — build-time vs runtime manifest | bar bundled `icons.json` vs notifications runtime `icons.json` | **critical** | AD-21 one manifest, one source |
| F2 | Event topic ownership | bar `speedtest-service.ts` vs runtime `speedtest.py` (both emit `speedtest.state`) | **critical** | AD-22 one producer per topic |
| F3 | Event client restart/hydration | bar client (JobsCleared+reset) vs notifications clients (no reset) | **high** | AD-23 one restart contract |
| F4 | Codegen vs embedded tables | `contracts/gen` vs runtime `TOPIC_SCHEMAS`/`KNOWN_TOPICS` | **critical** | AD-24 generated-only, bidirectional |
| F5 | Artifact producers | provisioning vs runtime both produce `icons.json`/symlink | **high** | AD-25 provisioning validates only |
| F6 | Layout artifact version | `BarLayout.version` vs per-artifact `schemaVersion` | **high** | AD-26 one version field |
| F7 | Validator input / manifest materialization | runtime `IconProvider` + baseline vs provisioning `icons.json` CLI | **high** | AD-27 defined validator input |
| F8 | Surface mount policy | `PopupHost` factory vs `popup()` constructed JSX | **medium** | AD-28 popup takes a factory |
| F9 | Theme artifact path | `Theme` adapter (`colors.gtk.css`) vs apps (`colors.css`) | **medium** | AD-29 stable path |
| F10 | Distribution package | framework unit vs `node_modules` shortcut | **medium** | AD-30 resolvable package |

### The single tightest fix

If only one thing changes: **add an AD that names, for every shared artifact and topic, its single producer, its single path, its envelope/version field, and its single consumer entry point** — and make the conformance gates bidirectional. F1, F4, F5, F6 all reduce to "the spine froze the ports but not the artifacts' identity." AD-6's codegen can enforce it *if* the runtime's tables stop being hand-embedded (F4) and the manifest is generated rather than bundled or provisioned (F1/F5).

### Note on method

Every pair above was constructed from the current tree, not hypothesized: the file/line evidence is inline. No pair requires a unit to *violate* an AD; each fails only because the spine leaves an artifact's identity or an invariant's owner unstated. That is the hole class to close.

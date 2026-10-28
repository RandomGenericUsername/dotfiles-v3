# 101 — AGS Platform Architecture

> **Status:** design-of-record. This is the *decoupling* design that grew out of
> the bar re-architecture exploration (`docs/100-ags-bar-rearchitecture.md`).
> Doc 100 is the findings + prototype log for the bar itself; **this** doc is the
> architecture the bar (and the other AGS apps) are meant to settle into.
>
> It is written so a fresh agent can implement from it without this
> conversation. It is deliberately honest about what is verified, what is
> decided, and what is still open.

> **Note (bar source moved):** the AGS bar source lives in the external
> `ags-bar` repo and deploys as the standalone `v0.1.1` tag; the `ags_apps_units`
> provisioning role installs it at `<install>/apps/bar/<tag>` and links the
> app-list `spineLink` as `<install>/config/ags`. The in-repo
> `dotfiles/config/ags/` tree and the old `ags-apps` monorepo role are retired;
> the paths below are historical. The deployed consumer path `~/.config/ags/...`
> is unchanged.

---

## 0. TL;DR

1. A bar widget mixes six jobs in one file (system binding, domain rules, icon
   lookup, GTK drawing, input wiring, overlay policy). Doc 100 split those apart
   with a **widget-descriptor kit**.
2. Walking the rest of the bar and the other AGS apps surfaced a **bigger**
   problem: the same handful of things are re-implemented in every app —
   **five copies of the icon registry** and **five divergent readers of the
   `org.dotfiles.Events` contract**.
3. So the target is not "extract the bar." It is: extract a small **platform**
   (ports + shared adapters) that every AGS app depends on, and make each app
   thin.
4. The organising rule that keeps it decoupled: **code owns meaning, behaviour,
   and intent; data/providers own looks, presence, and delivery.** The **state
   key** is the boundary object between the two. The runtime changes **state**,
   never **layout**.

Final layout: **`ags-platform`** (the reusable seams) plus seven standalone
app repos (`ags-bar`, `ags-notifications`, `ags-capture-tool`, `ags-clipboard`,
`ags-wallpaper-selector`, `ags-icme`, `ags-btop-theme-studio`). `contracts` is
the shared event/app-schema repo; the Python runtime consumes it independently.

---

## 1. The problem

### 1.1 The bar (doc 100)

A bar widget (`dotfiles/config/ags/bar/widgets/*.tsx`) does six unrelated jobs:
bind the system, encode domain rules, navigate the icon manifest, draw GTK, wire
input, and coordinate overlays. Across eleven widgets that duplicates a pointer/
anchor/icon block five times, hides domain rules in views, and scatters the
"one popup at a time" policy over five files.

### 1.2 The deeper finding: cross-app duplication

Exploring the rest of the AGS apps (not just the bar) showed the same seam
re-implemented everywhere:

| Duplicated thing | Copies |
|---|---|
| Icon registry (`icon-registry.ts`) | **5** — bar, capture-tool, notifications, hypr-pano, wallpaper-selector |
| `org.dotfiles.Events` client | **5** — hypr-pano, icon-color-mapping-editor, wallpaper-selector (full clients) + notifications (`speedtest-events.ts`, `wallpaper-events.ts`, bespoke) |

The event contract is **versioned** (`Events1`/`Events2`, see
`contracts/event-contract.*`). Five hand-rolled readers will not agree on version
handling — this is exactly the drift the contract exists to prevent.

### 1.3 The goal

- Give each job exactly one owner (the descriptor kit for the bar; ports +
  shared adapters for everything).
- Make the look of every icon come from **data**, not code.
- Make the bar (and each app) a **thin consumer** of a shared platform, so the
  eventual repo split is mechanical rather than a rewrite.

---

## 2. The one rule (load-bearing)

> **Code owns meaning, behaviour, and intent.**
> **Data / providers own looks, presence, and delivery.**

Three consequences that everything below assumes:

- **The state key is the boundary object.** Code produces *meaning* (e.g.
  `"wifi-full"`); data decides *which art* that meaning draws. Neither side needs
  the other's vocabulary except through that string.
- **The runtime changes state, never layout.** *Composition* (is a widget in the
  bar at all?) is static config — the repo default, optionally overridden by the
  runtime. *Visibility* (is it shown now?) is reactive state (`visible?(state)`).
  A widget appearing when a recording starts is a **state** change, not a layout
  edit. (This was verified against the recorder: its layout entry is static; only
  `visible` moves.)
- **The provider is an override layer.** For icons especially: the app's/ runtime's
  provider *overrides* a widget's own fallback; it never has to own every icon.

---

## 3. Repositories and packaging

### 3.1 Topology (decided)

```
ags-platform/   ports + shared adapters (icons, events, preferences, notifier)
                + the event-contract client. Versioned, reusable.
ags-bar/        the status bar (instance `ags`)
ags-notifications/        notification overlay
ags-capture-tool/         capture UI + capture-tool backend
ags-clipboard/            clipboard overlay (instance `clipboard`)
ags-wallpaper-selector/   wallpaper selector
ags-icme/                 icon color mapping editor
ags-btop-theme-studio/    btop Theme Studio
                RULE: apps depend on the platform, never on each other.
contracts/      the event contract (JSON/XML) + generated bindings and the
                AGS app schemas. Consumed by the Python runtime AND ags-platform.
```

Rationale: the decoupling value comes from **dependency direction** (apps →
platform, never app → app), not from the repo count. A platform package + one
apps repo gives ~90% of the benefit; individual apps can be split out later
mechanically (copy the folder, depend on the published platform). Per-app repos
now would pay the multi-repo/version-skew tax before it is earned.

> **Update 2026-10-28 — per-app split complete.** EPIC-002 / REQ-008
> (AD-25/31/32) supersedes the “one apps repo” end state: the bar and six apps
> each have their own repo, installed from one `dotfiles-v3` app list
> (`dotfiles/provisioning/apps.yaml`) against one program tuple
> (`dotfiles/provisioning/program-tuple.yaml`). Engine `v0.1.23` retires the
> `ags-apps` monorepo role; only external publish/archive and host apply remain.
> Composition details: [`102-ags-app-consumption.md`](./102-ags-app-consumption.md).

### 3.2 Distribution (verified on the host)

AGS (v3.1.0) embeds **esbuild** for transpilation/bundling. Verified:

- A **bare specifier** (`import { x } from "mybar"`) resolves from
  `node_modules/` and is inlined by `ags bundle`. ✅
- **`ags run` resolves `node_modules` too** — a live two-module app ran
  (`RESOLVED:hello from mybar`, exit 0). ✅
- `ags bundle --alias name=./path` resolves a **vendored** directory (no
  `node_modules`). ✅
- `ags run` has **no `--alias`** flag (only `bundle` does).
- `ags`/`gnim` are **built-in aliases** — that is why the deployed spine runs
  with no `node_modules`. A third-party package gets no such alias.

**Decision:** the framework is found **by name via a `node_modules` shortcut**,
installed **as one unit**, and versioned. Provisioning installs the framework
once and creates the shortcut, instead of enumerating its files. `ags bundle`
remains the option for a single self-contained release artifact.

```bash
# illustrative deploy shape
~/.local/share/dotfiles/ags-platform/<version>/          # the framework, one unit
~/.local/share/dotfiles/config/ags/node_modules/ags-platform -> …/<version>
```

---

## 4. The ports

The entire coupling surface. Each port is an interface the platform defines and
a provider implements.

### 4.1 `IconProvider`

```ts
export type IconSource =
  | { readonly kind: "file"; readonly path: string }
  | { readonly kind: "name"; readonly name: string }   // themed symbolic icon

export interface BarMapping {
  readonly widget?: string
  readonly iconSize?: number
  /** state-key -> variant name. DATA (runtime-generated in dotfiles). */
  readonly states: Readonly<Record<string, string>>
}

export interface IconProvider {
  resolve(group: string, variant: string): IconSource | null
  /** Optional: only providers with a state->variant table implement it. */
  barMappings?(group: string): BarMapping | null
  hasGroup?(group: string): boolean
}
```

- **Runtime impl:** reads the generated `icons.json`, returns `{kind:"file"}`.
- **Baseline impl:** a symbolic/theme provider, returns `{kind:"name"}`.
- `resolve` is the **override**; a widget's own fallback covers a tableless
  provider (see §7).

### 4.2 `EventSource` / `EventHub`

```ts
export type EventPayload = { readonly [key: string]: unknown }

export interface EventSource {
  subscribe(topic: string, handler: (payload: EventPayload) => void): () => void
  current?(topic: string): EventPayload | null
  onRestart?(handler: () => void): () => void
  control?(jobId: string, action: string): void
}

export type EventMap = Record<string, unknown>

export interface EventHub<M extends EventMap> {
  select<T extends keyof M>(topic: T): Accessor<M[T] | null>   // reactive
  on<T extends keyof M>(topic: T, handler: (payload: M[T]) => void): () => void
  control(jobId: string, action: string): void                 // job control
}
```

- **Job control is first-class, not optional.** The recorder drives a
  runtime-hosted job via `Control(job_id, action)`; the hub must expose it.
- The pure **subscribe-before-read hydration + epoch/seq dedup** state machine
  (today `lib/event-bus-core.ts`) moves into the platform; the runtime supplies
  only the Gio transport and the topic/payload types.
- A baseline `NoEventSource` makes event-driven widgets inert.

### 4.3 `LayoutProvider`

```ts
export interface BarLayout {
  readonly version: 1
  readonly sections: {
    readonly start?: readonly BarEntry[]
    readonly center?: readonly BarEntry[]
    readonly end?: readonly BarEntry[]
  }
}

export interface BarEntry {
  readonly id: string
  readonly params?: Readonly<Record<string, unknown>>
}

export interface LayoutProvider {
  load(): BarLayout | null
}
```

- **Whole-layout replacement** (no partial merge): the first provider in the
  chain that returns non-null wins.
- Chain: **user › runtime › repo default**, and the **repo default is always
  non-null**, so the bar runs with nothing external.
- Layout is **placement only**; overlays/surfaces follow from capabilities, not
  from the layout.

### 4.4 `SurfaceSpec` + `SurfaceRegistry` + `PopupHost`

Content is surface-agnostic. Today `WifiContent`/`BluetoothContent` are already
mounted in two hosts (their popup **and** the settings panel); this formalises
it.

```ts
export interface SurfaceHostContext {
  readonly visible: Accessor<boolean>
  readonly ctx: BarContext
}

export interface SurfaceSpec {
  readonly id: string
  body(host: SurfaceHostContext): JSX.Element
  readonly width?: number
  readonly height?: number
  /** True while the body needs typed input; the host flips keymode. */
  readonly keyboard?: Accessor<boolean>
}

export interface SurfaceRegistry {
  get(id: string): SurfaceSpec | undefined
  all(): readonly SurfaceSpec[]
}
```

- **Mount policy: Option B.** A surface body is a **factory**; hosts mount it
  **only while visible** and tear it down when hidden. Because the overlay
  coordinator allows one overlay at a time, at most one instance is live — the
  shared-state races that bit the wifi/bt panels become structurally impossible.
  Durable state must live in an app-level service, not in the component.
- `PopupHost` is a **shipped primitive** (standardise popup behaviour): window +
  click-catcher + anchor margin + keyboard mode. This is the ~four-times-repeated
  chrome in `AudioPopup`/`WifiPopup`/`BatteryPopup`/`SettingsPanel`.

### 4.5 `Notifier`

```ts
export interface NotificationIntent {
  readonly key?: string          // stable id -> updates the same card in place
  readonly summary: string
  readonly body?: string
  readonly app?: string
  readonly icon?: IconSource
  readonly urgency?: "low" | "normal" | "critical"
  readonly timeoutMs?: number
  readonly progress?: { readonly value: number; readonly max: number }
}

export interface Notifier {
  post(intent: NotificationIntent): void
  dismiss?(key: string): void
}
```

- Senders post **intents**; they never construct a freedesktop call or emit a
  bespoke event.
- The **provider** routes: transient intent → freedesktop `Notify`; keyed/
  progress intent → the event-card path. Both already land in the same AGS
  notification window (the notifications app owns
  `org.freedesktop.Notifications`); only the wire differs, and the sender no
  longer knows which.

### 4.6 `Preferences`

```ts
export interface Preferences {
  /** Reactive value for a namespaced key, with a fallback when unset. */
  get<T>(namespace: string, key: string, fallback: T): Accessor<T>
}
```

- First adapter: the capture-tool config file (`bar_compact_controls`), read +
  watched behind the port. The widget asks; the adapter owns the file and the
  `FileMonitor` (fixing the module-scope-monitor GC trap).
- Degrades to the fallback when the file is absent (the "works with nothing"
  property).

### 4.7 `BarContext`

```ts
export interface BarContext<M extends EventMap = EventMap> {
  readonly overlays: OverlayCoordinator
  readonly hub: EventHub<M>
  readonly icons: IconProvider
  readonly surfaces: SurfaceRegistry
  readonly notifier: Notifier
  readonly preferences: Preferences
  readonly exec: (argv: readonly string[]) => Promise<void>
}
```

- **Injected, no module globals** (the existing `overlays` singleton becomes
  `ctx.overlays`). This is the difference between a testable framework and a set
  of files glued by imports.
- App-level **domain services** (e.g. the audio composition binding, the battery
  power service) are closed over **at registration**, not carried in
  `BarContext` — `BarContext` stays about platform concerns.

`OverlayCoordinator` is the existing `kit/overlay.ts` (`register/open/toggle/
close/closeAll`), unchanged — it was already domain-agnostic.

---

## 5. Widget shapes

Descriptor rendering outgrew one type. There are **four shapes**; all share one
**`Shell`** so anchoring/gestures/`visible`/tooltip can never diverge.

```ts
// shared shell: button, gestures, pointer-anchor record, tooltip, visible,
// class, stateClass, pixelSize
interface Shell<S> { /* id, read, tooltip?, visible?, class?, stateClass?, pixelSize?,
                       primary?, secondary?, scroll? */ }

interface DescriptorSpec<S>      extends Shell<S> { icon?: IconRef<S>; label?: (s: S) => string | null }
interface RichWidgetSpec<S>      extends Shell<S> { content: (s: S, ctx: BarContext) => JSX.Element }
interface CollectionSpec<I, S>   extends Shell<S> { items: (s: S) => readonly I[]; key: (i: I) => string;
                                                    item: (i: I, s: S, ctx: BarContext) => WidgetSpec<...> | JSX.Element }
interface ForeignCollectionSpec  { /* items from an adapter; adapter-supplied item renderer */ }
```

Where the real widgets land:

| Shape | Widgets |
|---|---|
| `DescriptorSpec` | network, battery, bluetooth, btop, thunderbird, settings, power-menu, audio-output, audio-mic |
| `RichWidgetSpec` | clock (two labels), recording (dot + timer + buttons) |
| `CollectionSpec` | workspaces |
| `ForeignCollectionSpec` | tray (other apps' SNI items) |

`popup(anchor, content)` and `hub.control(jobId, action)` are **`BarContext`
capabilities** any shape may call, **not** shapes. This removes the generic
"custom widget" catch-all: each irregular widget maps to a *named* concept.

---

## 6. Schemas

### 6.1 `Capability`

```ts
export type ParamKind =
  | { readonly type: "string" }
  | { readonly type: "number"; readonly min?: number; readonly max?: number }
  | { readonly type: "boolean" }
  | { readonly type: "enum"; readonly values: readonly string[] }
  // defined now, usable later; no schema change when adopted
  | { readonly type: "array"; readonly items: ParamKind; readonly maxItems?: number }
  | { readonly type: "object"; readonly fields: Readonly<Record<string, ParamDecl>> }

export interface ParamDecl {
  readonly kind: ParamKind
  /** Present -> optional; applied when the layout entry omits the param. */
  readonly default?: unknown
}

export interface Capability<P = Record<string, unknown>, S = unknown> {
  readonly id: string
  readonly params?: Readonly<Record<string, ParamDecl>>
  /** The icon groups + state keys this capability can emit (the §7 contract). */
  readonly icons?: readonly { group: string; states: readonly string[] }[]
  /** May this capability appear more than once in a layout? Default false. */
  readonly multi?: boolean
  create(params: P, ctx: BarContext): WidgetSpec<S>
}
```

`ParamKind` is recursive **by design**, even though v1 capabilities only use the
scalars — so adding structured params later is not a breaking schema change.
Forward-compat rule: an **unrecognised `type` is a warning, never a crash**, so a
newer layout degrades gracefully on an older bar.

### 6.2 Validation

Two **separate** validators (provisioning wants them distinct):

```ts
export function validateLayout(layout: BarLayout, capabilities: readonly Capability[]): ValidationResult
export function validateIcons(icons: IconProvider, capabilities: readonly Capability[]): ValidationResult

export type IssueCode =
  | "unknown-widget" | "duplicate-widget"
  | "unknown-param" | "missing-param" | "bad-param"
  | "missing-icon-key"

export interface BarIssue {
  readonly severity: "error" | "warning"
  readonly code: IssueCode
  readonly message: string
  readonly widgetId?: string
  readonly param?: string
  readonly iconGroup?: string
  readonly iconState?: string
}

export interface ValidationResult { readonly ok: boolean; readonly issues: readonly BarIssue[] }
```

**Policies (decided):**

- `unknown-param` → **error** (a typo'd param silently ignored is the bug this
  exists to catch).
- `duplicate-widget` → **error by default**, allowed when the capability declares
  `multi: true`.
- `missing-icon-key` → **error**, scoped: only for groups where the capability
  **declares `states`**. A capability on `iconByVariant` declares none and is not
  checked.

**Enforcement:** provisioning runs both and **fails install on any error**; the
bar runs the **same functions** at startup and **degrades** (skip unknown
widget, apply defaults, blank a missing glyph). Same rules, different
enforcement, so they cannot drift.

---

## 7. The uniform icon contract

Every icon, in every app, follows the network pattern — **no exceptions**
(audio volume and battery power-mode are the two current leaks to fix):

- **Code produces only a state key.** Pure: `networkIconState(reading) →
  "wifi-full"`, `levelVariant(...) → "volume-medium"`, `batteryStateKey(...) →
  "charging-75"`.
- **Data maps** `state key → variant → art` (the `bar_mappings.states` table).
- **Single-glyph groups** (btop, thunderbird) get an **identity fallback**
  (key `"btop"` → variant `"btop"`).
- **Capabilities declare** their groups + keys (`icons: [{group, states}]`);
  provisioning validates the provider covers them.

**Resolution chain** (the provider as override layer):

```
v = ref.variant(state)
  1. provider.barMappings(group)?.states[v] -> provider.resolve(group, variant) -> IconSource
  2. ref.fallback(v)                                                             -> { kind: "name", … }
  3. blank
```

`IconRef<S>`:

```ts
export interface IconRef<S> {
  readonly group: string
  readonly variant: (state: S) => string | null
  /** Last-resort resolution when the provider has no table for `group`. */
  readonly fallback?: (variant: string) => IconSource | null
}
```

Option **X** was chosen over a framework-wide canonical table: the capability
owns its own vocabulary and its own bare-desktop fallback, so the platform never
needs to know every domain.

---

## 8. Reactivity and surfaces (the hard-won bits)

- **The gnim widget tree is built statically.** A JSX ternary is evaluated once.
  Branch the *structure* only on **static** spec fields; drive everything
  time-varying through `createComputed` (icon, label, tooltip, `visible`,
  `stateClass`). Doc 100 §2.4/§5.
- **`class` accepts an accessor**, so a state-dependent class is
  `createComputed(() => …)`; `stateClass?: (state) => string | null` is the
  descriptor field for it (the recording `speedtesting` case).
- **A `Gtk.Button` holds one child** — wrap icon+label in one `<box>`.
- **Surfaces are factories mounted lazily** (§4.4). Durable state is external.

---

## 9. Baseline providers ("works with nothing")

The bar must run on a bare desktop with **no runtime, no `icons.json`, no hub**.
Four baselines:

| Need | Baseline | Degradation |
|---|---|---|
| layout | repo default (`layout.default.ts`) | always non-null |
| icons | symbolic `IconProvider` + capability fallback (§7) | system glyphs |
| events | `NoEventSource` | event widgets inert/hidden |
| notifications | `FreedesktopNotifier` (or `NoopNotifier`) | any desktop daemon |

No-runtime behaviour: workspaces + clock + launchers work; network/battery/
bluetooth show system symbols; recording stays hidden; tray is empty. Nothing
crashes; nothing blank that can be drawn.

---

## 10. Provisioning contract (runtime ↔ app)

**Side A — the runtime produces artifacts** (into the state dir):

```
~/.local/state/dotfiles/current/
  icons.json        # icon manifest: group -> variants + bar_mappings.states
  bar.json          # OPTIONAL layout override (BarLayout)
  colors.gtk.css    # palette
```

**Side B — the app declares what it expects** — a **pure module**
(`bar-manifest.ts`, no GJS) imported by *both* the app and the validator, so the
list of ids/params/icon-keys cannot drift from the code:

```ts
export const MANIFEST: CapabilityDecl[] = [
  { id: "network", params: {}, icons: [{ group: "network", states: [...] }] },
  …
]
```

**Versioning:** each artifact carries its own **`schemaVersion`** (one per
artifact, not per set). An unknown version → warning + degrade, never a crash.
Breaking schema changes mirror the event contract's Events1/Events2 pattern.

**Where validation runs:**

- **Install (strict):** a platform CLI
  `ags-bar-validate --manifest bar-manifest.json --icons icons.json --layout bar.json`
  runs `validateLayout` + `validateIcons` and **fails the install on error**.
- **Runtime (lenient):** the bar runs the same functions and degrades.

The runtime never imports the app; the app never parses runtime internals. The
**validator is the only place the two sides meet.**

---

## 11. Cross-app consolidation

The platform's ports are **desktop-wide seams**, not bar-specific:

- One **event-contract client** (the platform's hub core) replaces the three full
  copies + two bespoke parsers.
- One **icon registry** (`IconProvider` adapter) replaces the five copies.
- One **`Preferences`** provider for cross-app settings.
- All notification **senders** use `Notifier`; the **notifications app** becomes a
  consumer of the shared ports (icons, events, theme) and a **host** that renders
  cards. (Cards are *conceptually* surfaces — content rendered by a host — but
  their lifecycle — expiry, stacking, replace-by-key — is different enough that
  they stay their own concept for now.)

Bar-**specific** ports (`LayoutProvider`, `SurfaceSpec`, `PopupHost`) stay with
the bar, not the platform.

---

## 12. Ownership: runtime vs code

- **Runtime owns:** assets (icon art, palette), **events** (the topic vocabulary
  and the job lifecycle), and an **optional** layout override.
- **Code owns:** capabilities (read models, actions, rendering), and the
  **default** layout.
- **`BarContext`/providers** own delivery (overlays, surfaces, popups,
  notifications, preferences).

The recording case is the worked example: the bar's `recording` entry is
**static**; the runtime emits `capture.state` and the widget's `visible` reacts.
The runtime changes **state**, not **layout** — which is why the runtime does
*not* need to own composition to support the recorder.

---

## 13. Migration roadmap

Each step independently shippable and gated (`bar-typecheck`, `ags-typecheck`,
`ags-test`, `ags bundle`; provisioning tests for manifest changes).

1. **Kit completeness** — `stateClass` (done in the prototype), `content` on the
   rich shape, the `IconRef.fallback` chain.
2. **Reactive domain read models** — `domains/network`, then battery / bluetooth /
   audio, as Astal adapters (the prototype's `domains/network/read-model.ts` is
   the seed).
3. **Uniform icon contract** — migrate audio `volume`/`microphone` and battery
   `power-mode` to `iconByStateKey`; add their `bar_mappings` to `icons.json`;
   add the declared-`icons` validation.
4. **Hub consumer + job control** — migrate `recording` (a `RichWidgetSpec`) onto
   `EventHub` + `control`.
5. **Surfaces** — formalise the settings-embeds-panels model with
   `SurfaceSpec`/`PopupHost`; delete the duplicated popup chrome.
6. **Shapes** — move tray to `ForeignCollectionSpec`, workspaces to
   `CollectionSpec`, clock to `RichWidgetSpec`.
7. **Preferences + Notifier** — extract the capture config adapter; route senders
   through `Notifier`.
8. **Extract the platform** — move the ports + shared adapters + event client into
   `ags-platform`; make each app depend on it; enforce apps → platform only.
9. **Provisioning** — install the framework as one unit + `node_modules` shortcut;
   run `ags-bar-validate` at install; drop the per-file framework enumeration.

---

## 14. Open items / deferred

- **`contracts` repo promotion** — when the Python runtime consumes the event
  contract independently of the TS platform.
- **Notification cards as surfaces** — keep as a separate concept for now;
  revisit if the lifecycle unifies.
- **`ForeignCollectionSpec` naming** — `ForeignCollectionSpec` vs a folded
  `CollectionSpec` variant. Separate shape chosen (§5).
- **Per-app repo split** — deferred; mechanical once the platform boundary is
  stable.
- **`ags run` has no `--alias`** — the deployed install relies on the
  `node_modules` shortcut (verified working).

---

## Appendix A — evidence gathered

- **AGS** v3.1.0; embedded esbuild; `ags`/`gnim` built-in aliases.
- **Verified resolution:** `node_modules` bare specifier (bundle **and** run),
  `--alias` (bundle only).
- **Duplication counts:** 5 icon registries; 5 event-contract readers.
- **Key source references:**
  - descriptor kit: `dotfiles/config/ags/kit/{icon.ts,widget.tsx,overlay.ts}`
  - pure network rules: `dotfiles/config/ags/lib/network-icon.ts`
  - prototype read model: `dotfiles/config/ags/domains/network/read-model.ts`
  - audio hexagon (the model domain): `dotfiles/config/ags/audio/`
  - event contract: `contracts/event-contract.{json,xml}`,
    `dotfiles/config/ags/lib/event-bus-core.ts`
  - capture/recording: `dotfiles/config/ags/bar/widgets/recording.tsx`,
    `src/runtime/src/runtime/application/{capture,capture_host,jobs}.py`
  - notifications app: the standalone `ags-notifications` repo, installed at
    `<install>/apps/notifications/<tag>` and linked as
    `~/.config/ags-notifications` by `ags_apps_units`

## Appendix B — relation to doc 100

Doc 100 remains the findings + prototype log for the bar (the descriptor kit,
the gaps it exposed, the worked widgets). This doc (101) is where the bar's
descriptor model, the icon contract, and the cross-app duplication converge into
the platform architecture. Where the two differ, **101 is the design of record**;
100 is the provenance.

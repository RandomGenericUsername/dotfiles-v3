# 100 — AGS Bar Re-architecture

> **Status:** exploration / prototype. This document lives on the
> `bar-rearchitecture` branch. `master` keeps only the audio-panel work; the bar
> prototype and this design live here until we decide to land them.

This is the design-of-record **and** the findings log for re-architecting the AGS
status bar. It records what is wrong today, the target shape, the prototype that
proves the shape, and — importantly — the gaps the prototype exposed.

---

## 1. The problem

A status-bar widget in `dotfiles/config/ags/bar/widgets/*.tsx` currently does six
unrelated jobs in one file. Taking `network.tsx` as the example:

1. **Talks to the system** — `Network.get_default()`, `createBinding(...)`.
2. **Knows the domain rules** — `getNetworkStateKey`, the `ACTIVATED = 100`
   constant, the strength thresholds.
3. **Turns state into an icon** — `getNetworkIconPath` walks the icon manifest.
4. **Draws GTK** — `<button><box><image/><label/></box></button>`.
5. **Wires input** — a motion controller for the pointer, a right-click gesture,
   `onClicked`.
6. **Coordinates overlays** — "close settings, then toggle the Wi-Fi popup".

Multiplied across eleven widgets this produces:

- the same ~30-line pointer-tracker / anchor / icon-resolution block copy-pasted
  five times;
- icon-manifest navigation written five slightly different ways;
- mutual-exclusion logic scattered over five files (`app.tsx` even carries a
  comment enumerating every overlay it must remember to close);
- logic that can only be tested by rendering it on a live desktop.

**Goal:** give each of those six jobs exactly one owner.

---

## 2. The target architecture

### 2.1 The idea

Separate **what a widget is** (data) from **how it is drawn** (one renderer).
A widget becomes a filled-out *descriptor*; one generic component reads any
descriptor and draws it.

```
app.tsx            composition root: build bindings, register overlays, assemble the bar
──────────────────────────────────────────────────────────────────────────────────────
bar/Bar.tsx        renders a LIST of widget descriptors (knows no domain)
kit/               the framework — zero domain knowledge
  icon.ts          IconRef:      source (manifest group) + variant(state)
  widget.tsx       BarWidgetSpec + <BarWidgetButton>  (the generic renderer)
  overlay.ts       OverlayCoordinator: one open at a time, anchor, closeAll
  hub.ts           typed consumer of org.dotfiles.Events     [not built]
  surface.ts       SurfaceSpec: hostable panel content        [not built]
──────────────────────────────────────────────────────────────────────────────────────
domains/           one per feature: read model + actions + icon + widgets + surfaces
  network/ audio/ battery/ bluetooth/ capture/ tray/ workspaces/ clock/
```

### 2.2 Decisions taken

- **Widgets are declarative descriptors** rendered by the kit (not hand-written
  components). Rationale: maximum uniformity and it centralises the duplicated
  anchor/gesture/icon code.
- **The event hub is for cross-process events only** (`org.dotfiles.Events` —
  wallpaper, capture, clipboard, speedtest). In-process GObject bindings
  (AstalNetwork/AstalBattery/AstalWp) stay in per-domain **adapters** behind the
  read model. A hub does not wrap a lossless in-process binding for no gain.
- **A widget's functionality dispatches to its domain's actions bag**; the widget
  owns no policy, so the same actions are shared with the settings panel.

### 2.3 Contracts

**`IconRef<S>`** (`kit/icon.ts`) — an icon is *source + decision*, never a widget:

```ts
export interface IconRef<S> {
  readonly group: string                        // the icons.yaml group (the SOURCE)
  readonly variant: (state: S) => string | null // state -> variant name
}
// two constructors cover the real patterns:
iconByVariant("btop", () => "btop")             // always this glyph
iconByStateKey("network", networkIconState)     // state-key -> variant via bar_mappings
```

**`BarWidgetSpec<S>`** (`kit/widget.tsx`) — the descriptor:

```ts
export interface BarWidgetSpec<S> {
  readonly id: string
  readonly read: () => S                                // the domain read model
  readonly icon?: IconRef<S>
  readonly label?: (state: S) => string | null
  readonly tooltip?: (state: S) => string
  readonly visible?: (state: S) => boolean
  readonly class?: string
  readonly pixelSize?: number
  readonly primary?: (state: S, anchorX: number | null) => void
  readonly secondary?: (state: S) => void
  readonly scroll?: (state: S, dy: number) => void
}
```

**`OverlayEntry`** (`kit/overlay.ts`) — the coordinator's registry entry:

```ts
export interface OverlayEntry {
  readonly id: string
  readonly isOpen: () => boolean
  readonly open: (anchorX: number | null) => void
  readonly close: () => void
}
```

`dotfiles/config/ags/overlays.ts` is the **one file that names every overlay**
and registers it, replacing the enumerated "close everything" list that used to
live in `app.tsx`.

### 2.4 The reactivity rules (load-bearing)

- AGS/gnim builds the widget tree **statically**; a JSX ternary is evaluated
  once. So the renderer branches the *structure* only on **static** spec fields
  (has-icon? has-label?) and drives everything time-varying through
  `createComputed` (`icon`, `label`, `tooltip`, `visible`, and — see §5 —
  `stateClass`).
- Every spec field is a **function of state**, so the renderer can wrap it in a
  computed and get reactivity for free.
- **A `Gtk.Button` holds a single child.** The renderer wraps icon + label in one
  `<box>`. Emitting them as siblings silently drops the first child (this was a
  real, observed bug — see §5).

---

## 3. The prototype (what is implemented on this branch)

Live in the bar:

- `kit/icon.ts`, `kit/widget.tsx`, `kit/overlay.ts` — the framework.
- `overlays.ts` — registers the five existing overlays.
- `lib/network-icon.ts` — the network state→variant + label rules, extracted
  **pure** (no GTK/Gio) and unit-tested (`tests/ts/network-icon.test.ts`).
- `bar/widgets/network-descriptor.tsx` — the network indicator as a descriptor.
  **Added** to the bar beside the original `network.tsx` (not replacing it) so
  the two can be compared.
- `bar/widgets/{btop,thunderbird,settings,power-menu}.tsx` — rewritten as
  descriptors (these replaced the originals; they are visually identical).

`Bar.tsx` renders the descriptors through `<BarWidgetButton spec={...} />`.

### 3.1 A descriptor, in full (`btop`)

```ts
export const btopWidget: BarWidgetSpec<undefined> = {
  id: "btop",
  read: () => undefined,
  class: "btop-widget",
  icon: iconByVariant("btop", () => "btop"),
  tooltip: () => "System monitor (btop)",
  primary: () => { execAsync(["kitty", "--", "btop"]).catch(console.error) },
}
```

### 3.2 A stateful descriptor (`network`)

```ts
const network = Network.get_default()
const wifi = createBinding(network, "wifi")
const wired = createBinding(network, "wired")
const connectivity = createBinding(network, "connectivity")
function reading(): NetworkReading {
  return { wifi: wifi(), wired: wired(), connectivity: connectivity() }
}
export const networkWidget: BarWidgetSpec<NetworkReading> = {
  id: "network",
  read: reading,
  class: "network-widget",
  icon: iconByStateKey("network", networkIconState),
  label: networkLabel,
  primary: (_r, anchorX) => overlays.toggle("wifi", anchorX),
  secondary: () => { execAsync(["kitty", "--", "wifitui", "tui"]).catch(console.error) },
}
```

---

## 4. What the prototype proves

- A widget is expressible as **pure data** rendered by one component.
- The icon is `source + pure state→variant`; the manifest is navigated once.
- The duplicated pointer/anchor + gesture code collapses into the kit.
- The overlay-exclusion policy exists once (the coordinator), not N times.
- It **bundles and runs**: `ags bundle` inlines it; deployed to the host, the bar
  came up with no runtime errors and the descriptor network indicator renders
  beside the original.

Gates: `make bar-typecheck`, `make ags-typecheck`, `make ags-test` (68),
`ags bundle`, compositor-role test (25), verify-role test (71).

---

## 5. Gaps the prototype exposed (the valuable part)

The prototype is a **partial** reproduction. Comparing the descriptor against the
original widget on the live bar surfaced these, in order of severity:

### 5.1 `Gtk.Button` holds one child — fixed

The renderer emitted icon + label as sibling children; the label displaced the
icon and the button rendered blank for specs with both (network). Icon-only specs
(launchers) were fine. Fixed by wrapping the children in one `<box spacing={4}>`.

### 5.2 The kit cannot express a state-dependent CSS class — open

The original `network.tsx` toggles a `speedtesting` class while a speed test runs,
animating the button background:

```ts
createEffect(() => {
  if (speedTestRunning()) self.add_css_class("speedtesting")
  else self.remove_css_class("speedtesting")
})
```

The descriptor has nowhere to put this, because `class` is a **static string**.
This is a **kit gap**, not a descriptor-authoring mistake: the vocabulary must
cover every widget need. Detected live — the speed-test animation is missing on
the descriptor widget, which is how the two Wi-Fi glyphs can be told apart.

*Fix:* add `stateClass?: (state: S) => string | null` to `BarWidgetSpec<S>` and
build the `class` prop from a `createComputed` (gnim's `class` prop already
accepts an accessor — see `workspaces.tsx`). Then
`stateClass: (r) => r.speedTesting ? "speedtesting" : null`.

### 5.3 The read model is not reactive to the device's own properties — open

Instrumenting `read` showed it evaluated **once**. The original widget
re-resolved the icon on the Wi-Fi device's `notify::strength/state/enabled`; the
descriptor's read model only binds `Network.wifi` (the device *object*), which
does not fire when the device's *signal strength* changes. So the descriptor's
icon freezes until a hotplug/enable event.

This is the deepest lesson: **a descriptor is only as reactive as its read
model.** Subscribing to the system is the **domain adapter's** job — the analogue
of `audio/adapters/pipewire/pipewire-observation.ts`, which turns PipeWire
signals into a clean reactive model. The prototype skipped the domain layer and
put a naive `reading()` inline.

*Fix:* introduce a real `domains/network/` read model (an Astal adapter) that
subscribes to the device's property changes, and have the descriptor read from
it.

### 5.4 Not yet modelled

- **Surfaces** — the settings panel embedding the wifi/bt/audio panel content
  (see §6) is designed but not built.
- **Hub consumer** (`kit/hub.ts`) — event-driven widgets (recording, wallpaper,
  capture) are still hand-written.

---

## 6. Embedded components (the settings-panel case)

Not built, but the design: **content is surface-agnostic.**

- A **surface** is a hostable body: the Wi-Fi popup, the settings panel, the
  audio popup.
- The Wi-Fi panel content (the network list) is **one** component.
- The bar's Wi-Fi popup hosts it; the **settings panel hosts the same component**
  as a section.

So the settings panel is not a special case — it is a surface that **embeds**
other surfaces' content. This already happens informally (`WifiContent` /
`BluetoothContent` are used by both their popups and the settings views); the
architecture names it (`SurfaceSpec`) and makes it intentional.

---

## 7. Migration roadmap

1. **Kit completeness** — add `stateClass` (§5.2); add a `SurfaceSpec` host.
2. **Domain read models** — build `domains/network`, and the equivalents for
   battery / bluetooth / audio, as reactive Astal adapters (§5.3).
3. **Hub consumer** — `kit/hub.ts` on top of the existing contract-pinned
   `lib/event-bus-core.ts`; migrate `recording` first (228 lines → a descriptor).
4. **Surfaces** — formalise the settings-panel-embeds-panels model (§6).
5. **Migrate the remaining icon-bearing widgets** — battery, bluetooth, audio.
6. **Extract** — with each domain a self-contained module (state + actions +
   icon + widget + content), the eventual package split becomes mechanical.

Each step is independently shippable and gated by `bar-typecheck` +
`ags-typecheck` + `ags-test` + `ags bundle`.

---

## 8. Open decisions

- **Kit vocabulary boundary** — how many state-derived fields (`stateClass`,
  then what?) before it stops being a descriptor and starts being a mini-DSL.
- **Where `read` lives** — the descriptor currently builds its own Astal binding
  (`reading()`). It should read from a domain module instead; defining that seam
  is step 2.
- **Tray / workspaces** — the irregular widgets (dynamic children) need either a
  descriptor escape hatch or a distinct "collection widget" concept.
- **Anchor semantics** — the coordinator passes the icon x-centre; surfaces
  interpret it. Confirm this is enough for every overlay.

---

## Appendix — file map

| Concern | File |
|---|---|
| Icon = source + decision | `dotfiles/config/ags/kit/icon.ts` |
| Descriptor + renderer | `dotfiles/config/ags/kit/widget.tsx` |
| Overlay coordinator | `dotfiles/config/ags/kit/overlay.ts` |
| Overlay registrations | `dotfiles/config/ags/overlays.ts` |
| Pure network rules | `dotfiles/config/ags/lib/network-icon.ts` (+ its test) |
| Descriptor examples | `dotfiles/config/ags/bar/widgets/{network-descriptor,btop,thunderbird,settings,power-menu}.tsx` |
| Bar assembly | `dotfiles/config/ags/bar/Bar.tsx` |
| Composition root | `dotfiles/config/ags/app.tsx` |

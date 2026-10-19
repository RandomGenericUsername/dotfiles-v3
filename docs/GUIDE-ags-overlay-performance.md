# Guide — AGS overlay/surface open performance

> **Normative — conditional.** The open path below applies to an on-demand
> overlay surface **whose measured open-path build is significant** (tens of ms
> or more): spine **AD-24** (`ARCHITECTURE-SPINE.md`,
> architecture-ags-platform-2026-10-09). This guide is the how; the AD is the
> rule. **Measure first; adopt only where the measured build warrants it** — a
> light surface keeps its direct path. The primitive it prescribes *where
> required* is `overlayLifecycle` / `contentSignature` in `ags-platform`
> (`ports/overlay-lifecycle.ts`, `adapters/overlay-lifecycle.ts`).

## 1. The problem this fixes

An on-demand overlay — a layer-shell window that maps on a keybind and unmaps on
close — used to build its heavy content **synchronously in its `map` handler,
before presenting the surface**. The first frame cannot land until that build
finishes, so a large build means a blank window for hundreds of milliseconds.

Measured in `ags-apps` hypr-pano (`725ffdf`, 141-item clipboard history, warm
instance, instrumented bundle):

| Phase | Time |
| --- | --- |
| `map → first frame` (before) | **447–504 ms** |
| …of which the card rebuild | 426–451 ms |
| …of which `readHistory` | 0.3–0.6 ms |
| `present()` + `grab_focus()` | 0.1–0.4 ms |
| `map → first frame` (after, cold) | **5.5 ms** |
| `map → first frame` (after, warm) | **~1.0 ms** |

The rebuild is not the bug — doing it *on the map path* is.

## 2. Measure first — adopt only where required

The pattern is **not** a blanket rule. Before touching an overlay, **measure** its
open-path build (`map → first frame`, with the heavy phase split out from the
cheap one — see §5). Then decide:

- **Significant build (tens of ms or more)** → adopt the platform primitive
  (§4). hypr-pano (447–504 ms) is the proving case.
- **Light surface (single-digit ms)** → keep the **direct path**. Adding the
  present/hydrate/defer/skip indirection buys nothing when the build is already
  imperceptible, and it costs a per-surface controller, a content signature, and
  a deferred tick — indirection that then has to be maintained.

**Do not force it.** The bar is the counter-example: its surfaces' measured
open-path build is **2–15 ms**, so adopting the pattern there was churn and is
being **reverted**. A light surface that presents immediately should keep
presenting immediately.

## 3. The pattern: the four moves

**Present first. Hydrate cheap. Defer the build. Skip when unchanged.**

1. **Present** — put the surface on screen (and take focus) **first**, before any
   heavy work. The user sees the window immediately.
2. **Hydrate** — the cheap synchronous pass: read the source, set visibility,
   move the highlight. It **MUST NOT** construct or tear down heavy widgets. It
   must update whatever the content signature (`key()`) is derived from.
3. **Defer** — schedule the heavy build on an **idle callback**
   (`GLib.idle_add`, `PRIORITY_DEFAULT_IDLE`), off the map→first-frame path. The
   window is already up; the build fills it in.
4. **Skip + re-check** — skip the deferred build when the **content signature**
   is unchanged since the last build, and **re-check staleness inside the
   callback**: a keystroke or live push may have changed — or already rebuilt —
   the content between `map` and the idle, and an `unmap` cancels it.

Two things make the warm path work:

- The controller is created **once per surface** (per monitor) and **outlives a
  map/unmap cycle**.
- `close()` **MUST NOT** clear the remembered signature. The built content is
  still valid, so the next open of unchanged content is the ~1 ms warm path.
  Only a *changed* signature triggers a rebuild.

## 4. Use the platform primitive — do not copy the pattern

**Where the pattern applies** (§2), it is an injected primitive; re-implementing
it per app is exactly the copy-paste AD-2/AD-4 forbid. Supply the four effects;
the core owns their order and the skip/defer decision.

```ts
import { overlayLifecycle, contentSignature } from "ags-platform";

// ONE controller per surface, for its lifetime (not per map).
const life = overlayLifecycle({
  present: () => { win.visible = true; win.set_keymode("on-demand"); },
  hydrate: () => { items = readHistory(); win.visible = items.length > 0; },
  build: () => rebuildCards(items),          // the heavy work
  key: () => contentSignature(items.map((i) => `${i.kind}:${i.hash}`)),
});

// map handler
life.open();
// unmap handler
life.close();
// live update while mapped (a push, a keystroke)
life.refresh();
```

- `overlayLifecycle(hooks)` — the GLib-bound convenience
  (`GLib.idle_add`, `PRIORITY_DEFAULT_IDLE`).
- `createOverlayLifecycle(hooks, scheduler)` — the pure core, for tests with a
  stub scheduler and no desktop stack.
- `contentSignature(parts)` — the canonical `kind:hash` join (newline
  separated, so a token may contain punctuation without colliding two lists).

**Name it once, call it once.** The controller is per surface — calling a
factory in the `map` handler would discard the remembered signature and lose the
warm path. See the "why not `openOverlayLifecycle`" note in
`adapters/overlay-lifecycle.ts`.

## 5. Measurement discipline

- **Measure before/after on the live compositor.** The numbers are the point;
  a plausible-sounding reorder is not evidence. Instrument a copy of the app's
  window file (or a bundle) and time `map → first frame`, splitting out the
  heavy phase (e.g. the rebuild) from the cheap one (the read). **Decide from
  that number whether to adopt at all** (§2): a light build means the pattern
  does not apply.
- **Put the numbers in the commit.** The hypr-pano commit (`725ffdf`) records
  the before (447–504 ms) and after (5.5 ms cold / ~1 ms warm) inline — that is
  the evidence the AD cites.
- **Report cold and warm separately.** The first open pays the deferred build
  (still ~440 ms, now *after* the surface is up); a reopen of unchanged content
  pays nothing.
- **State the gates you ran** (`make <app>-typecheck`, the drift test,
  `ags bundle …`) with their exit codes, as `725ffdf` does.

## 6. The honest caveat

This fixes **time-to-surface**, not **time-to-content**. The heavy build still
runs — it just runs after the surface is visible instead of before it. If the
build is genuinely too slow *to be seen filling in*, that is a **separate
per-app concern**: chunk the build across idle ticks, virtualize a long list, or
cache the built widgets. `overlayLifecycle` does not do any of that, and no
amount of reordering will.

## 7. References

- Spine AD-24 — `_bmad-output/planning-artifacts/architecture/architecture-ags-platform-2026-10-09/ARCHITECTURE-SPINE.md`.
- The primitive — `ags-platform` `ports/overlay-lifecycle.ts` (pure core),
  `adapters/overlay-lifecycle.ts` (GLib binding + `overlayLifecycle`).
- The proving ground — `ags-apps` `725ffdf` (`perf(pano): show the overlay
  before rebuilding its cards`), hypr-pano `ui/PanoWindow.tsx`.
- Related invariants — AD-2 (injected context), AD-4 (frozen platform surface),
  AD-10 (surfaces are factories, mounted lazily: the bar's surfaces are torn down
  on hide, so the warm-skip half does not apply there).
- The counter-example — the **bar** (surfaces build in 2–15 ms): a light surface
  that should **not** adopt the pattern; its adoption is being reverted.

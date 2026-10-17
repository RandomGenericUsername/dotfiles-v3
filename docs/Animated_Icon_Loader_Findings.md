# Animated icon loader — findings

**Status:** investigation complete, decision deferred.
**Interim decision (2026-10-05):** ship `Gtk.Spinner`. Treat a bespoke loader as its
own piece of work.
**Scope:** why a loading indicator in this panel is hard, what was measured, and what
a proper treatment would have to decide.

> **Note (bar source moved):** the AGS bar source now lives in the external
> `ags-apps` repo and deploys as the pinned `bar-v0.1.1` unit — the `ags_apps`
> provisioning role symlinks its `bar/` subdir as the live `<install>/config/ags`.
> The in-repo `dotfiles/config/ags/` tree was retired; the `dotfiles/config/ags/`
> paths below are historical. The deployed consumer path `~/.config/ags/...` is
> unchanged.

Every claim below is tagged. **MEASURED** means it was run and observed on this machine.
**INFERRED** means reasoned from a measurement. **PROPOSED** means not yet built or tested.

---

## 1. Environment

| | | tag |
|---|---|---|
| AGS | `3.1.0` (`aylurs-gtk-shell-git` 3.1.2.r0.gbbee2f1-2) | MEASURED |
| project era | v3 / Astal+Gnim — `import app from "ags/gtk4/app"` | MEASURED |
| GTK | `4.22.5` | MEASURED |
| adapter | MediaTek, `A0:E7:0B:8B:36:7E` | MEASURED |

## 2. The decision, and why it is cheap

Ship `Gtk.Spinner`. It costs one line and no assets, because it is a **native** widget.

**MEASURED** — `Gtk.Spinner` is a real GType (`GtkSpinner`) with a `spinning` property:

```
Gtk.Spinner class             : Gtk_Spinner
Gtk.Spinner has its own GType : GtkSpinner
Gtk.Spinner spinning property : spinning
```

GTK advances it on its own frame clock and the compositor redraws once per display
refresh. It never touches the filesystem and never rasterises an SVG, so it is smooth at
60Hz or 120Hz for free.

The precedent already exists in this repo, and it is the whole pattern —
`components/wifi/WifiContent.tsx:366`:

```tsx
<Gtk.Spinner class="settings-spinner" visible={busy} spinning={busy} />
<label label="Connecting…" visible={busy} />
<label label="Connect" visible={createComputed(() => !busy())} />
```

Three properties of the pattern worth copying verbatim:

- **one boolean drives it** — `visible` and `spinning` bind to the same accessor;
- **labels swap by `visible`, both mounted** — never a JSX ternary (see §8);
- **CSS is size and colour only**:

```css
.settings-spinner { min-width: 14px; min-height: 14px; color: @color_13; }
```

The second precedent is at `WifiContent.tsx:589` (speedtest), same shape.

## 3. Why the supplied artwork cannot be smooth by the obvious route

Someone reaching for "just animate the SVG" will lose a day. Here is why, measured.

**MEASURED** — there is no widget-level rotation. `GObject.Object.list_properties` over
`GtkWidget` and `Gtk.Picture`:

```
widget rotate/transform props : []
Gtk.Picture rotate/transform  : []
```

Only `opacity` exists. So `transform: rotate()` in CSS has nothing to bind to, and no
`rotate` property can be animated.

**MEASURED** — the repo already records that CSS animation is not dependable here. The
`.rec-dot` rule in `style.css` says the pulse "uses `@keyframes` where the GTK theme
engine honors them and degrades to a static dot otherwise". A static dot is acceptable
for a record indicator. It is **not** acceptable for a scanning indicator, because a
still ring destroys the entire message the element exists to send.

`INFERRED` — therefore no animation technique that depends on GTK honouring `@keyframes`
can be load-bearing here.

## 4. The frame-swap approach, and the ceiling it has

The supplied pack (`~/Downloads/ags-spinners`) ships, per style: 12 animation frames
(`frame-00` … `frame-11`) plus one static `templates/<style>.svg`. Four styles: `ring`,
`dots`, `swoosh`, `double-ring`.

The pack's own README prescribes the frame sequence as the fallback when native rotation
is unavailable, at **100 ms/frame = 10 FPS**, 12 frames = a 1.2 s revolution.

**The important consequence, and the reason "just make it 120Hz" is not a question that
can be answered:** there are only 12 distinct images per revolution. Frame *count* is the
limit, not frame rate. Playing 12 images faster does not produce smoother motion, it
produces a strobe. Raising the refresh rate is not a knob on this approach; the approach
itself is the problem.

**MEASURED outcome when built in AGS:** visibly choppy, and worse — it regressed. The
owner reported it blinking roughly once a second and appearing/disappearing. Two causes,
both mine:

1. the helper held a `createEffect` that *read* `image.visible`, which its own
   `start()`/`stop()` *wrote* — a reactive feedback loop;
2. it had never been run against a live discovery scan before being put on the bar.

Lesson: an animation whose failure mode is "looks wrong" needs to be observed in motion
against real state, not unit-reasoned.

## 5. What *would* be smooth — measured, and cheap in one case

**MEASURED** — `GtkSnapshot` exposes transform entry points:

```
GtkSnapshot transform methods : ["append_scaled_texture","scale","scale_3d",
                                 "transform","transform_matrix","translate","translate_3d"]
```

`Gsk.Transform` is available as a type. So a **custom widget that applies a `GskTransform`
in its snapshot handler can rotate smoothly.** That is a real, viable path — and it is
genuinely more work: a custom widget class, not a one-liner.

**The asymmetry that matters, and it is specific to `dots`:**

**MEASURED** — `dots` frames differ from each other *only* in per-dot opacity. Frame 00
versus frame 01 of `dots` changes nothing but the `opacity` attribute on each circle;
`ring` and friends instead change a `transform`.

**INFERRED** — therefore `dots` never needs a rotation engine. Stack the 12 frames as 12
images and cycle their `opacity` at display rate: 12 cheap property writes per tick, no
file I/O, no rasterisation, smooth. That renders the supplied artwork at full refresh rate
using the repo's existing native `opacity` property.

**PROPOSED, untested:** the three arc styles cannot use that trick, because their motion
*is* rotation. For them the options are a custom snapshot-transform widget, or
`Gtk.Spinner`.

Summary of what is actually available:

| approach | smooth at display rate | cost |
|---|---|---|
| `Gtk.Spinner` | yes, native | ~1 line, zero assets |
| `dots` via stacked frames + opacity cycling | yes | small helper, no per-frame file I/O |
| arc styles via custom `GtkSnapshot.transform` widget | yes | a custom widget class |
| 12-file swap (what was built, then reverted) | **no** — 10fps, and it strobes if forced higher | discard |

## 6. Colour and theming — solved, and worth keeping

The pack's SVGs contain literal `$color1` / `$color2`. This project uses
`{{COLOR_FOREGROUND}}` in icon templates.

**Resolution:** map **both** placeholders to `{{COLOR_FOREGROUND}}`. The
active/inactive hierarchy survives because the frames already bake it in as `opacity`
and `stroke-dasharray`, so one token is the correct mapping for both. Mapping `$color2`
to a second colour slot would invent a theming mechanism the project does not have, which
the pack's own instructions forbid.

**MEASURED** — after rendering, the frames carry the live palette colour
(`fill="#c4c2c6"`), i.e. no hard-coded colour, and a wallpaper change re-tints them for
free through the existing pipeline.

Placement followed the existing convention, `<category>/<variant>/default/icon.svg`:

```
icon-templates/ui/spinner-<style>/frame-NN/default/icon.svg   ->  spinner-<style>-frame-NN.svg
icon-templates/ui/spinner-<style>/still/default/icon.svg      ->  spinner-<style>-still.svg
```

52 templates written (48 frames + 4 still).

## 7. A toolchain gap that will bite the next person

**MEASURED** — `icons.json` is what the AGS icon registry reads at runtime, and
**nothing in the toolchain writes it**:

- `dotfiles-runtime icons regenerate` re-renders every SVG into
  `~/.local/state/dotfiles/current/icons/` and repoints symlinks — it does **not** touch
  `icons.json`.
- `dotfiles-runtime reconcile` does not touch it either.

So `icons.json` is maintained by hand. The failure this produces is nasty and silent:

> a group added to `icons.yaml` renders to disk **perfectly** and is **invisible to the
> app**. The registry resolves `group -> variant -> output`, finds no group, the widget
> resolves to `null`, and nothing is drawn. There is no error anywhere.

That is the same failure class as three other bugs found in this same session: a dead
agent registration, a confirm button that could never be pressed, and a chevron whose
formula could never produce a visible change. **Implemented but invisible** is the
recurring theme, and it is worth treating as a category rather than three coincidences.

**Mitigation written:** `scripts/sync-icons-manifest.py` derives the manifest's group
entries from `icons.yaml`. It is additive (only named groups are replaced, everything
else passes through byte-for-byte, so hand-tuned entries survive) and it refuses to write
at all unless it can reproduce the file byte-for-byte at `json.dump(indent=2,
sort_keys=True)` — otherwise a whole-file reformat would bury a real change in noise.

**RECOMMENDATION:** make the runtime own `icons.json`. This is the actual fix; the script
is a bridge.

## 8. Two AGS idioms that cost real time here

**MEASURED** — JSX builds a **static** widget tree. A ternary is evaluated once, at
construction, and nothing subscribes to it:

```tsx
{confirming() ? <button>Unpair device</button> : <button>Unpair</button>}
```

This branch is chosen once and is permanent. The confirm buttons therefore never
existed, so `confirmUnpair` was unreachable and unpairing was impossible — with no error
anywhere. The fix is the idiom this codebase already uses **22 times**: mount both
branches and drive `visible` from a computed.

**MEASURED** — a boolean flag used as a formula can be structurally incapable of changing
anything:

```ts
expanded = manuallyToggled() || nearbyDevices().length > 0
```

Any device in range forces `true`, so flipping the flag changed nothing on either click.
The chevron was a dead control. Fixed with a tri-state (`boolean | null`, where `null`
means "no decision yet, fall back to auto").

Both are instances of the same hazard: **in AGS, an expression evaluated at build time is
not a binding.** If its inputs change later, nothing happens and nothing complains.

## 9. Defect in the supplied pack: `swoosh`

**MEASURED** — diffing the pack's own frames against each other, every frame differs from
`frame-00` in **exactly one line**: the bright arc's `transform="rotate(N 12 12)"`.

**The faint track never rotates.** A stationary 11-unit dash sits near 12 o'clock while
the arc sweeps past it, and at frame 0 the arc starts exactly on top of that dash. Rendered
at rest it is a bare crescent with a lump on it — not a spinner. This is a defect in the
supplied asset, not a transcription error; the mock's geometry was verified byte-equivalent
to `templates/swoosh.svg`.

**One-attribute fix, applied to the mock only:** remove `stroke-dasharray="11 43"` from
the track circle so it becomes a full faint ring and the arc reads as a comet travelling a
ring. The bright arc and its rotation are untouched.

**UNRESOLVED CONFLICT:** `ring` and `double-ring` have the same structural quirk — their
faint tracks also do not rotate. And because only the *mock's* frames were fixed, **the
mock no longer matches the pack.** Either the pack's frames get the same fix so mock and
shell agree, or the fix is dropped and the supplied art ships as-is. Not decided.

## 10. The indicator's trigger is a separate, still-open problem

Worth recording because the loader depends on it.

**MEASURED** — the `Scanning…` row is gated on `!hasDevices()`. The moment one device is
found, the only feedback in the panel disappears *while the scan is still running* — which
is most of a discovery's life. This is a one-line gate change needing no artwork and no
engine, and it is **not fixed**.

**MEASURED** — related: `bluetoothDiscovering` is a *local mirror* of BlueZ's `Discovering`
property, seeded at module load and updated only from `PropertiesChanged`; it is never
re-read. It was also used as a *gate* on whether to scan at all, and BlueZ's real value
desyncs on this machine (`StopDiscovery` answers "No discovery started" while `Discovering`
reads `1`). The gate has been removed; the mirror remains, and it is the honest thing for
an indicator to display — but if it ever lies again, the indicator will lie with it. A
loader that displays a stale boolean is worse than no loader.

## 11. What a proper treatment must decide

1. **`Gtk.Spinner` permanently, or bespoke artwork?** Interim answer: `Gtk.Spinner`.
2. **If bespoke:** `dots` is cheap and smooth via opacity cycling. The arc styles are not —
   they need a custom snapshot-transform widget. So a bespoke loader may mean bespoke
   *only* for one of the four styles.
3. **Size policy.** MEASURED working values: 13px chevron row (a text row cannot take
   16), 16px panel, 20px empty state. The pack requires 12/16/20/24 to stay crisp.
   MEASURED, load-bearing: an SVG/`Gtk.Image` with no explicit size falls back to its
   intrinsic default and renders enormous — this happened and was caught only by
   screenshotting.
4. **Static fallback.** Frame 0 must be visible whenever the animation is not running:
   reduced-motion, a renderer that captures at end-of-cycle, or assets that fail to load.
   A loading indicator that renders as *nothing* is worse than one that renders still.
5. **Does the runtime own `icons.json`?** See §7. This is the highest-value item here and
   is not really about loaders.
6. **Fix the pack's non-rotating tracks upstream, or drop the fix?**
7. **Should the loader be in the contrast guard** (`BAR_GROUPS` in
   `runtime/domain/icon_contrast.py`)? MEASURED: the installed runtime has **no**
   `"bluetooth"` entry, so bar glyphs are not contrast-retargeted on light wallpapers. A
   loader drawn on a surface rather than on wallpaper may not belong in that guard at all —
   worth deciding rather than inheriting.

## 12. Reproducing the measurements

```bash
# AGS + GTK versions
ags --version
gjs -c "const {Gtk}=imports.gi; Gtk.init(); print(Gtk.get_major_version()+'.'+Gtk.get_minor_version())"

# widget rotation: expect [] — this is the finding that forces the frame fallback
gjs -c "const {Gtk,GObject}=imports.gi; Gtk.init(); const w=new Gtk.Label();
print(GObject.Object.list_properties.call(w.constructor.\$gtype).map(p=>p.name)
  .filter(n=>/rotat|transform/i.test(n)))"

# GtkSpinner is native
gjs -c "const {Gtk}=imports.gi; Gtk.init(); print(new Gtk.Spinner().constructor.\$gtype.name)"

# the pack's own frames: only the arc rotates
diff ~/Downloads/ags-spinners/frames/swoosh/frame-00.svg \
     ~/Downloads/ags-spinners/frames/swoosh/frame-06.svg

# icons.json is not written by the toolchain
stat ~/.local/share/dotfiles/config/ags/icons.json
dotfiles-runtime icons regenerate && stat ~/.local/share/dotfiles/config/ags/icons.json
```

Probes used during this investigation are in `prototypes/` (`gtk-rotate-probe` logic is
inlined above; the rest are `agent-capability-probe.py`, `agent-held-invocation-gjs.js`,
`ags-agent-registration-probe.js`, `pairing-e2e-probe.py`).
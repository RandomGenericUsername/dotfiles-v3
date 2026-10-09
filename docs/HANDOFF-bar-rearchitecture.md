# HANDOFF — AGS Bar Re-architecture

> Read this first. It is the complete context for continuing this work with a
> fresh agent. It assumes **no** prior conversation.

---

## 0. TL;DR

We set out to find where the AGS status bar breaks the project's hexagonal
pattern, and to design a clean bar architecture. Along the way we:

1. **Finished the audio-panel migration** (a separate, completed fix) — now on
   `master`, in sync with `origin/master`.
2. **Designed and prototyped a bar re-architecture** — a *kit* that renders
   declarative *widget descriptors* — now on the `bar-rearchitecture` branch,
   with a full design doc and a live prototype in the host bar.

The bar work is **exploration**, not finished. The immediate next step is to
close the two gaps the prototype exposed (see §6).

---

## 1. Git state (read this carefully)

| Ref | Commit | Contents |
|---|---|---|
| `master` | `702c2f42` | Clean, **== `origin/master`**. Contains the 3 audio-panel commits only. No prototype. |
| `bar-rearchitecture` | `53245acf` | Contains **everything**: the 3 audio-panel commits + 3 bar-prototype commits + this design doc. |

Commit log (branch):

```
53245acf docs(ags): bar re-architecture findings + design (exploration)
67e8df95 fix(ags): wrap kit widget children in a box (GTK buttons hold one child)
9bb1f195 prototype(ags): overlay coordinator + network widget descriptor
35f14205 prototype(ags): bar widget descriptor kit (icon + BarWidgetButton)
702c2f42 test(provisioning): complete the verify fixture for the audio hexagon   ← master
078a52c3 refactor(ags): migrate the bar audio indicators to the composition binding
7c36e18c feat(ags): finish the audio panel redesign (transport group, spec, CI parity)
6d85b311 docs(openspec): propose finish-audio-panel-redesign                    ← session start
```

- **Working tree is clean** on both. Do not lose the branch.
- **The branch is not pushed.** Pushing needs the passphrase-protected
  `~/.ssh/personal` key (`ssh-add ~/.ssh/personal` first). Pushes from the agent
  environment fail (no agent, no askpass).
- The **live host bar still runs the prototype** (deployed to the spine — §5).
  It will revert on the next provision; ask before assuming.

**Recommended first move for the next agent:** `git checkout bar-rearchitecture`,
then read `docs/100-ags-bar-rearchitecture.md` (the full design doc) and the kit
files listed in §4.

---

## 2. What the project is (minimal background)

`dotfiles-v3` is a Linux desktop orchestrator with two domains:

- **Provisioning** (`src/provisioning`, Python + Ansible) — builds the machine.
- **Runtime** (`src/runtime`, Python hexagon) — derives wallpaper→palette→effects
  →icons and reconciles the desktop; publishes domain events over
  `org.dotfiles.Events`.

The **AGS bar** lives in `dotfiles/config/ags/`. It is a TypeScript/GJS/gnim
(AGS's reactive JSX) app. It is deployed *file-by-file* by the provisioning
`compositor_configs` role into a "spine" (`~/.local/share/dotfiles/config/ags`),
which `~/.config/ags` symlinks to.

Key architectural facts (already true, keep them):

- The bar is a **thin consumer** of the runtime's event bus via
  `lib/event-bus-core.ts` (pure, contract-pinned to `contracts/event-contract.*`)
  + `lib/event-bus.ts` (Gio seam).
- The **audio** feature is the most complete hexagon in-tree
  (`audio/{domain,application,adapters,presentation,composition}`).
- AGS is invoked via `ags` (on PATH). `ags bundle` transpiles **without**
  typechecking, so `bar-typecheck` / `ags-typecheck` are the real type gates.

---

## 3. The audio-panel work (DONE — on `master`)

Three commits, complete and tested:

- `7c36e18c` **finish the audio panel redesign** — added the
  `media-transport-panel` icon group, reconciled the `ags-audio-panel` spec/mock,
  fixed `ci-gates-parity` (7 per-target audio CI jobs; `ags-typecheck` a
  self-hosted gate).
- `078a52c3` **migrate the bar audio indicators to the composition binding** —
  split the 1648-line `audio/state.ts` into `audio/ui-state.ts` (surface state) +
  `audio/presentation/levels.ts` (pure `levelVariant`/`clampVolume`), added
  `audio/presentation/bar-indicators.ts`, repointed `bar/widgets/audio.tsx` at the
  binding, deleted `audio/state.ts` and the dead `services/mpris-service.ts`, and
  tracked the file set in the provisioning manifests. **Also fixed
  `tsconfig.bar.json`** (added `allowImportingTsExtensions` — it could not
  typecheck the audio hexagon's `.ts` imports) and corrected
  `tests/tsconfig.tests.json`'s purity-list paths (they were one level too high,
  so the list was vacuous).
- `702c2f42` **complete the verify fixture** — `_build_provisioned_layout` never
  wrote the audio hexagon files the redesign added to
  `verify_compositor_skeleton_files`; writing them fixed 2 pre-existing
  `TestVerifyRuntime` failures (`test_verify_role.py` now 71 passed).

**No open work here.** Do not re-open it unless something regresses.

---

## 4. The bar re-architecture (the current focus)

### 4.1 The problem (full findings)

A bar widget (`dotfiles/config/ags/bar/widgets/*.tsx`) does six jobs in one file:
system binding, domain rules, icon-manifest navigation, GTK drawing, input
wiring, and overlay exclusion. Across eleven widgets this duplicates a ~30-line
pointer/anchor/icon block five times, hides the domain rules in views, and
scatters the "one popup at a time" policy over five files (`app.tsx` even carries
a comment enumerating every overlay to close). Full write-up in
`docs/100-ags-bar-rearchitecture.md` §1.

### 4.2 The design (agreed)

Separate **what a widget is** (data) from **how it's drawn** (one renderer).

```
bar/Bar.tsx   →  renders a LIST of descriptors
kit/          →  framework, zero domain knowledge:
  icon.ts        IconRef { group, variant(state) }
  widget.tsx     BarWidgetSpec<S> + <BarWidgetButton>   ← the generic renderer
  overlay.ts     OverlayCoordinator { register, open, toggle, closeAll }
  hub.ts         typed org.dotfiles.Events consumer        [NOT BUILT]
  surface.ts     SurfaceSpec (hostable panel content)      [NOT BUILT]
domains/         one per feature: read model + actions + icon + widgets + content
```

**Decisions already taken (do not re-litigate without reason):**

1. Widgets are **declarative descriptors** rendered by the kit (not hand-written
   components).
2. The event **hub is for cross-process events only**; in-process GObject
   bindings (AstalNetwork/Battery/Wp) stay in per-domain **adapters** behind the
   read model.
3. A widget's functionality **dispatches to its domain's actions**; the widget
   owns no policy (so the settings panel can share the actions).

### 4.3 The prototype (implemented, on the branch)

Files (all under `dotfiles/config/ags/`):

| File | Role |
|---|---|
| `kit/icon.ts` | `IconRef<S>`; `iconByVariant` / `iconByStateKey`; `resolveIcon` |
| `kit/widget.tsx` | `BarWidgetSpec<S>` + the `<BarWidgetButton>` renderer |
| `kit/overlay.ts` | the overlay coordinator |
| `overlays.ts` | registers the 5 existing overlays (wifi/bluetooth/battery/settings/audio) once; imported by `app.tsx` |
| `lib/network-icon.ts` | network state→variant + label rules, **pure**, tested |
| `bar/widgets/network-descriptor.tsx` | network indicator as a descriptor; **added beside** the original `network.tsx` |
| `bar/widgets/{btop,thunderbird,settings,power-menu}.tsx` | rewritten as descriptors (these **replaced** the originals) |

`bar/Bar.tsx` renders the descriptors via `<BarWidgetButton spec={...} />`;
`app.tsx` imports `./overlays`.

### 4.4 What it proves

A widget is expressible as pure data; the icon is `source + pure state→variant`;
pointer/anchor + gestures collapse into the kit; overlay exclusion is central.
Validated: `bar-typecheck`, `ags-typecheck`, `ags-test` (68), `ags bundle`,
compositor-role test (25), verify-role test (71). Deployed live: the bar came up
with no runtime errors and the two Wi-Fi glyphs render side by side.

---

## 5. Environment specifics / gotchas (IMPORTANT)

- **Deploying to the host bar.** `~/.config/ags` → `~/.local/share/dotfiles/config/ags`
  (the spine). A running main AGS instance serves the bar. To deploy: back up the
  spine, `rsync` the repo `dotfiles/config/ags/` into it (the spine keeps extra
  files and its `colors.css` symlink — do **not** overwrite that), then restart
  the owning instance:
  ```bash
  # find the owner (cwd == spine), then:
  ags quit; sleep 1
  ( cd "$HOME" && nohup ags run --log-file ~/.local/state/ags/main.log >/dev/null 2>&1 & )
  ```
  Verify: `hyprctl layers | grep "1920 48"` (bar mapped) and check
  `~/.local/state/ags/main.log` for `ReferenceError|TypeError`.
  `scripts/deploy-audio-panel.sh` is a template for a scoped deploy (audio only).
  A spine backup from this session: `/tmp/opencode/spine-ags-backup-*.tgz`.
- **`openspec` CLI is NOT installed.** Write change artifacts by hand (follow
  `openspec/changes/finish-audio-panel-redesign/` as the format example).
- **`bar-typecheck` requires `allowImportingTsExtensions`** (already added to
  `dotfiles/config/ags/tsconfig.bar.json`) because the audio hexagon uses `.ts`
  imports (Node's native test runner needs them). Don't remove it.
- **Provisioning is per-file.** Every AGS source must be listed in
  `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`
  (`compositor_configs_skeleton_files`), mirrored in
  `verify/vars/main.yml` (`verify_compositor_skeleton_files`), and pinned by exact
  counts/lists in `test_compositor_configs_role.py` (the count is asserted!) and
  the `_build_provisioned_layout` fixture in `test_verify_role.py`. Adding a file
  means updating all four. **This is real friction and part of why the bar should
  become a package.**
- **gnim realities** (learned the hard way): the widget tree is built **statically**
  — a JSX ternary is evaluated once, so branch the *structure* only on static
  spec fields and drive everything time-varying through `createComputed`. And a
  **`Gtk.Button` holds a single child** — wrap icon+label in one `<box>`.
- **No desktop session for `ags run`?** There is one here (the host). Screenshots
  via `grim -g "x,y wxh" out.png` work; `convert … -scale 300%` to inspect.
- **Pushing is blocked** (passphrase key). The user pushes from their terminal.

---

## 6. Open work (the point of the handoff)

The prototype is a **partial** reproduction. Two gaps were found by comparing the
descriptor network widget against the original in the live bar — close these
first, because they are the proof that a descriptor can reproduce a widget
*fully*:

1. **Kit can't express a state-dependent CSS class.** The original toggles a
   `speedtesting` class while a speed test runs (animated background); the
   descriptor has nowhere to put it because `class` is a static string.
   *Fix:* add `stateClass?: (state: S) => string | null` to `BarWidgetSpec<S>` and
   build the `class` prop from a `createComputed` (gnim's `class` prop accepts an
   accessor — see `bar/widgets/workspaces.tsx`). Then the descriptor adds
   `stateClass: (r) => r.speedTesting ? "speedtesting" : null` and the read model
   includes `speedTesting` (from `services/speedtest-service.ts` `running`).

2. **The read model isn't reactive to the device's own properties.** Instrumenting
   `read` showed it evaluates once. `createBinding(network, "wifi")` fires when the
   *device object* changes, not when its *signal strength* changes — so the icon
   freezes. The original widget explicitly connected
   `notify::strength/state/enabled`. *Fix:* build a real `domains/network/` read
   model (an Astal adapter, like `audio/adapters/pipewire/pipewire-observation.ts`)
   that subscribes to the device's property changes.

3. **Then the rest of the roadmap** (in the design doc §7): a `kit/hub.ts` consumer
   (migrate `recording` — 228 lines — first); formalise **surfaces** so the
   settings panel embeds the wifi/bt/audio panels; migrate the remaining
   icon-bearing widgets (battery, bluetooth, audio); then the package split.

4. **Open design questions** (design doc §8): the kit-vocabulary boundary
   (how many state-derived fields before it's a DSL); where `read` lives (the
   descriptor should read from a domain module, not build its own binding);
   irregular widgets (tray/workspaces) need a descriptor escape hatch or a
   "collection widget" concept; anchor semantics for every overlay.

---

## 7. Validation commands

```bash
make bar-typecheck      # typecheck the whole ags tree (needs capture-types once)
make ags-typecheck      # audio/* focused (GIR typings; 0 errors in audio/*)
make ags-test           # pure-module unit tests (node --test + tsc)
make audio-panel-gates  # the audio suites + mock parity
make gates-ci           # CI-parity gate set
# provisioning:
uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py -q
# bundle check (catches import resolution, not types):
cd dotfiles/config/ags && ags bundle app.tsx /tmp/opencode/out.js   # exit 0
```

---

## 8. The user's working style (to match)

- Granular, safe, investigation-first; no big-bang. Each step independently
  shippable and gated.
- Wants things **verified by execution**, not by reading diffs.
- Wants the **host bar** to reflect changes (deploy + restart + eyeball).
- Deep architectural intent: eventually **decouple the monorepo into components**
  (but that is deferred; the bar design is the current focus).
- Prefers honest gap-reporting over silent fixes.

---

## 9. Pointers

- **Design + findings:** `docs/100-ags-bar-rearchitecture.md` (on this branch).
- **Prototype commits:** `35f14205`, `9bb1f195`, `67e8df95` (this branch).
- **Audio work:** `7c36e18c`, `078a52c3`, `702c2f42` (on `master`).
- **The design doc format precedent:** `openspec/changes/finish-audio-panel-redesign/`.
- **A complete in-tree hexagon to copy patterns from:** `dotfiles/config/ags/audio/`.
- **The runtime↔bar event contract:** `contracts/event-contract.{json,xml}` and
  `dotfiles/config/ags/lib/event-bus-core.ts`.

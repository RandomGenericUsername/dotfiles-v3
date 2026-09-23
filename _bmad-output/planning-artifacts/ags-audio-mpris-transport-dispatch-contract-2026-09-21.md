# Dispatch Contract — Per-App Media Transport Controls (MPRIS) for the AGS Audio Popup

- **Worktree/branch**: `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3-audio` @ `feat/pipewire-audio-ags`
- **Base commit (WP-A)**: `c86b338c` — audio popup graph-snapshot routing + brand app icons
- **Approved visual reference**: `_bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/mockups/key-audio-transport.html`
- **Status**: **COMPLETE.** All work packages landed (WP-A `c86b338c` · WP-B/WP-D `bffa66c4` · WP-C `56dfcc03` · WP-E `b0f22636` · regression fix `3eab5e94` · docs `16124e72`). Live gate + functional matrix passed; provisioning suites 81 passed; icon-contrast suites 32 passed; working tree clean.

> **HOW TO USE THIS DOCUMENT**
> This is the single source of truth. Each work package below is self-contained: an agent
> receives its WP section **verbatim** plus §0 (invariants), §1 (verified ground truth),
> and §2 (traps). Any deviation from a stated invariant is a defect, not a judgment call.
> If something in the code contradicts this document, **stop and report** — do not improvise.

---

## 0. Invariants (hard constraints — violating any is a defect)

| # | Invariant |
|---|-----------|
| I1 | **No polling of media state.** Reactive state comes only from D-Bus signals (`PropertiesChanged`, `Seeked`, `NameOwnerChanged`) + subscribe-before-read hydration. A render tick may interpolate a *display value* (position) locally; it must not re-read authoritative state on a timer. |
| I2 | **`wpctl`/`playerctl` are for ACTIONS only** (play/pause/next/prev/seek, set-default), never for reading state into the UI. |
| I3 | **Never use `wp.audio.*` collections** (`audio.speakers`/`streams`/etc.). They are empty/null on AstalWp r973. The PipeWire model is `wp.nodes` filtered by `media-class`, already in `audio/state.ts`. |
| I4 | **Never assign `node.is_default`** — read-only on this build. Default sink changes go through `wpctl set-default <id>`. |
| I5 | **`pw-dump` prop keys are DOTTED** (`media.class`, `application.name`, `application.icon-name`, `media.name`, `node.description`); Links carry `output-node-id`/`input-node-id` directly. |
| I6 | **Never hand-edit `dotfiles/config/ags/icons.json`.** It is generated from `icons.yaml` with `json.dumps(data, indent=2, sort_keys=True) + "\n"`. Regenerate + byte-verify. |
| I7 | **`ags bundle` exit 0 does NOT prove runtime safety.** The live gate (relaunch with captured log, zero `JS ERROR`/`ReferenceError`, layer mapped) is mandatory before declaring any WP done. |
| I8 | **Never edit the provisioning spine** (`~/.local/share/dotfiles/`) by hand — roles converge it. Never run two provisioning runs concurrently. |
| I9 | **Do not modify**: `BAR_GROUPS` in `src/runtime/src/runtime/domain/icon_contrast.py`; the recording widget `dotfiles/config/ags/bar/widgets/recording.tsx`; `wp.audio.*` anywhere; the untracked `docs/linux-wayland-pipewire-ags-audio-control.md`. |
| I10 | **Additive changes only** to `audio/state.ts` (do not restructure existing exports); the popup file may be edited but must keep its existing sections working. |
| I11 | **Pure logic has no GJS imports** and lives in a node-testable core (precedent: `dotfiles/config/ags/lib/event-bus-core.ts`, tested by `src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`, invoked as `node <file>.mjs`). |
| I12 | **Language/idiom**: TypeScript for AGS, no comments unless the surrounding file already comments densely (it does — match the house comment style: explain *why*, cite doc § where relevant). |

---

## 1. Verified ground truth (measured live on this machine — do NOT re-derive, do NOT contradict)

**AstalWp / PipeWire**

- `Wp.get_default().audio.*` collections are broken: `streams: 0`, `default-speaker: null`, property ids mis-registered (the `connected` warning). Working surface = `wp.nodes` + `media-class` enum (0 Unknown, 1 Audio_Source, 2 Audio_Sink, 3 Stream_Input, 4 Stream_Output).
- Defaults resolve via `wp.default_speaker.id` / `wp.default_microphone.id`, then matching the node — already implemented.
- `pw-dump` Node props observed live: `media.class = "Stream/Output/Audio"`, `application.name = "Google Chrome"`, `application.icon-name = "google-chrome"`, `application.process.binary = "chrome"`, `media.name = "Playback"`; sink node `media.class = "Audio/Sink"`, `node.description = "C-Media(R) Audio Analog Stereo"`.
- Link objects expose `output-node-id`, `input-node-id`, `state: "active"` directly.
- When audio is idle the sink node and all links legitimately disappear from the dump → snapshot maps go empty; UI must fall back to default-sink NAME (already implemented).

**MPRIS (measured live)**

- Session bus players: `org.mpris.MediaPlayer2.chromium.instance4925`, `org.mpris.MediaPlayer2.chromium.instance95550`, `org.mpris.MediaPlayer2.tidal-hifi`, and `org.mpris.MediaPlayer2.playerctld` (activatable proxy).
- `playerctl` is at `/usr/bin/playerctl` and **already provisioned** (`dotfiles/provisioning/packages.yaml` + both `group_vars`, verified).
- `playerctl -l` / `status` / `position` / `metadata` all work. Example live values: chromium.instance4925 `Paused`; tidal-hifi `Playing`, identity string `tidal-hifi`.
- **`AstalMpris` typelib is NOT installed** — importing `gi://AstalMpris?version=0.1` fails. Do not attempt to install it.
- MPRIS object path `/org/mpris/MediaPlayer2`, interface `org.mpris.MediaPlayer2.Player`.
  - Properties: `PlaybackStatus` (s: `Playing|Paused|Stopped`), `Metadata` (a{sv}: `mpris:trackid`, `mpris:length` int64 µs, `xesam:title`, `xesam:artist` as, `xesam:album`), `Position` (x µs, **read-only and NOT in `PropertiesChanged`**), `CanPlay`, `CanPause`, `CanSeek`, `CanGoNext`, `CanGoPrevious`.
  - Methods: `PlayPause`, `Play`, `Pause`, `Next`, `Previous`, `SetPosition(o trackid, x pos)`, `Seek(x offset)`.
  - Signals: `Seeked(x position)` (position jumps: seek/track change).
- Identity mapping observed: MPRIS suffix `chromium.instance4925` ↔ PipeWire `application.process.binary=chrome` / `application.name=Google Chrome`; `tidal-hifi` ↔ `tidal-hifi`.

**Provisioning / tests**

- `compositor_configs/vars/main.yml` enumerates AGS files (`ags-service-nm-client`, `ags-service-wifi`, `ags-service-bluetooth` ~line 178-180); `ags/audio` dir at line 104.
- `verify/vars/main.yml` lists AGS files (~line 393-395: `config/ags/app.tsx`, `style.css`, `icons.json`) and `verify_system_binaries` (~line 161).
- Unit tests: `src/provisioning/tests/unit/test_compositor_configs_role.py`, `test_verify_role.py`.
- Node test precedent: `src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`, run via that project's Makefile (`node $(DIR)/tests/<f>.mjs`).
- Runtime Python tests run with `uv run pytest` from `src/runtime`; provisioning tests from `src/provisioning`.

---

## 2. Traps (observed failures — agents must not repeat)

| Trap | Symptom | Guard |
|------|---------|-------|
| T1 | `ags bundle` passed but the bar showed "No output device"/empty Applications → I had rewritten `state.ts` onto `wp.audio.*`. | I3; do not touch the working model. |
| T2 | Runtime `ReferenceError: nodeName is not defined` thrown inside `For` — killed the Bar window (no layer surface). `ags bundle` exit 0. | I7 + a **symbol existence check** in every AGS WP (see §4 gate). |
| T3 | Snapshot parsed `media-class` (hyphenated) → matched nothing → routing stayed "Default". | I5; copy the exact dotted keys. |
| T4 | `node.is_default = true` silently did nothing. | I4. |
| T5 | Editing `icons.json` by hand desyncs from `icons.yaml`. | I6; regen + byte-verify. |
| T6 | Two provisioning runs against the same spine corrupt state. | I8. |
| T7 | `pw-dump` graph legitimately empties when idle — treating "no links" as a bug leads to wrong fixes. | Fallback to default-sink name is correct behaviour. |

---

## 3. Locked product decisions (owner-approved; the mockup is the contract)

| # | Item | Decision |
|---|------|----------|
| D1 | Master button | Lives in the **Output card**, between the name/meta block and `Change ›`. Controls the **most recently active player** (the one that most recently reported `Playing`). Glyph = `pause` when that player is Playing, else `play`. **Hidden** when there is no player. Tooltip: `Play/Pause — <identity> (most recent)`. |
| D2 | Per-app transport line | Rendered **only** when the stream has a matching MPRIS player. Layout: `⏮ ▶/⏸ ⏭ · seek slider · "m:ss / m:ss"`, placed **under** the volume `LevelLine`. |
| D3 | Prev/Next | Shown only when `CanGoPrevious`/`CanGoNext` true. |
| D4 | Seek | Slider shown only when `CanSeek`; commits on **slider release**, never per-tick. |
| D5 | Paused row | Dimmed fill, frozen knob (mock `.transport.paused`). |
| D6 | Subtitle | Hide when `media.name` is the generic `"Playback"` (case-insensitive). Show otherwise. |
| D7 | Output subview | Current default sink shows `✓` + active-row fill. Selecting a row calls `setDefaultSpeaker` (wpctl) and returns. |
| D8 | No-player rows | Unchanged (volume-only) — Discord case. |
| D9 | Time format | Combined `elapsed / duration`, e.g. `1:24 / 4:02`; elapsed-only when duration unknown. |
| D10 | Icons | New `media-transport` group with `play`, `pause`, `previous`, `next` (see WP-D). Recording widget keeps `capture-tool/*`. |

---

## 4. Global acceptance gate (every AGS WP runs this before "done")

```bash
# from dotfiles/config/ags
ags bundle app.tsx /tmp/ags-check.bundle.js --root . ; rm -f /tmp/ags-check.bundle.js
```
Then **symbol existence check** (catches T2-class defects the bundler misses):
- every identifier referenced in the edited files must be defined or imported in that file;
- every `export`/`import` name across `audio/*`, `services/*` must resolve.

Then the **live gate** (WP-F owns the formal run; B/C may run it on their own changes):
```bash
for p in $(pgrep -f "[a]gs run$"); do kill $p $(pgrep -P $p) 2>/dev/null; done; sleep 2
rm -f ~/.local/state/ags/bar.log
nohup ags run > ~/.local/state/ags/bar.log 2>&1 & sleep 7
wc -c ~/.local/state/ags/bar.log            # expect 0
rg -i "JS ERROR|ReferenceError|not defined" ~/.local/state/ags/bar.log || echo clean
hyprctl layers | rg "1920 48"               # expect the bar layer, a:1
```
For fast AGS dev iteration only, `cp` the changed file into `~/.config/ags/...`
(spine symlink target) — but the **authoritative** deploy is the provisioning role
(WP-E/WP-F). Never edit the spine by hand (I8).

---

## 5. Work Packages

### WP-A — Pre-flight commit ✅ DONE
`c86b338c` on `feat/pipewire-audio-ags`.

---

### WP-B — MPRIS service + pure core + node tests

**Deliverables**
1. `dotfiles/config/ags/services/mpris-core.ts` — pure, **no GJS imports** (I11).
2. `dotfiles/config/ags/services/mpris-service.ts` — GJS session-bus service.
3. `src/gui-tools/icon-color-mapping-editor/tests/mpris-core.test.mjs` — node tests.
   - **Register it in `src/gui-tools/icon-color-mapping-editor/Makefile`** by adding the line
     `node $(DIR)/tests/mpris-core.test.mjs` to the existing `test:` target (the file currently
     lists `contract.mjs`, `svg.mjs`, `model.mjs`, `diff.mjs`, `templates.mjs`,
     `event-contract-drift.mjs`, `icme-saved-smoke.mjs`). Do not restructure the target.
   - The test imports the core cross-tree, exactly as `event-contract-drift.mjs` does:
     `import * as mpris from "../../../../dotfiles/config/ags/services/mpris-core.ts";`
     (relative path from `src/gui-tools/icon-color-mapping-editor/tests/`).

**`mpris-core.ts` contract (exact exports)**
```ts
export const MPRIS_PREFIX = "org.mpris.MediaPlayer2."
export const MPRIS_EXCLUDED = ["playerctld"]          // proxy, never a row
export const ALIAS: Record<string, string>            // mpris identity -> icon-name slug space
export interface ParsedBusName { identity: string; instance: string | null }
export function parseBusName(busName: string): ParsedBusName
export interface TrackMeta { title: string; artist: string; album: string; lengthUs: number }
export function parseMetadata(raw: Record<string, unknown>): TrackMeta
export function formatClock(us: number): string        // "m:ss", "" when us<=0
export function interpolatePosition(baseUs: number, baseMs: number, playing: boolean, nowMs: number): number
export function identityMatches(identity: string, candidates: string[]): boolean
export function pickActivePlayer<T extends {identity:string; status:string; lastPlayingAt:number}>(players: T[]): T | null
```
- `ALIAS` maps observed identities: `chromium→google-chrome`, `chrome→google-chrome`, `google-chrome→google-chrome`, `tidal-hifi→tidal-hifi`, `brave-browser→brave-browser`, `firefox→firefox`, `spotify→spotify`, `youtube-music→youtube-music`. Unknown identities pass through unchanged.
- `identityMatches(identity, candidates)`: normalise both (`lowercase`, strip non-alphanumerics to `-`), apply `ALIAS` to **both** the identity **and** each candidate, return true on any equality. This is how a stream row is linked to its player.
  **RESOLVED (WP-B review, commit `bffa66c4`)**: the original wording applied `ALIAS` to the identity only, which failed to match a lone `application.process.binary` candidate (`chromium` vs `chrome`). Both sides now canonicalise through `ALIAS` (`chromium`/`chrome`/`google-chrome` → `google-chrome`), so a candidate from *either* snapshot field matches. Covered by tests `identity chromium links process binary chrome` and `identity chromium links either candidate field`.
- `pickActivePlayer`: highest `lastPlayingAt` among `status === "Playing"`; else highest `lastPlayingAt`; else first. Deterministic.
- `interpolatePosition`: `playing ? baseUs + (nowMs-baseMs)*1000 : baseUs`.

**`mpris-service.ts` contract** (as built in `bffa66c4` — WP-C consumes this API verbatim)
- Session bus: `Gio.bus_get_sync(Gio.BusType.SESSION, null)` (a *new* seam — `services/nm-client.ts` is system-bus; do not reuse it).
- Discovery: `ListNames` walk + `NameOwnerChanged` subscription (unfiltered rule; filter by `MPRIS_PREFIX` in the handler and drop `MPRIS_EXCLUDED`).
- Subscribe-before-read: install `PropertiesChanged` + `Seeked` before `GetAll` hydration.
- **`PropertiesChanged` handling includes the `invalidated` list** (resolved in review): a property announced as invalidated with no value in `changed` is treated as changed (value falls back to the prior value), and an invalidated `Position` triggers a one-shot `syncPosition`. Do not regress this.
- `TrackMeta.artist` joins `xesam:artist` (an array) with `", "`.
- Exports:
```ts
export interface MprisPlayer {
  busName: string; identity: string; instance: string | null
  status: "Playing"|"Paused"|"Stopped"
  metadata: TrackMeta
  canSeek: boolean; canGoNext: boolean; canGoPrevious: boolean; canPause: boolean
  positionUs: number; positionSyncedAtMs: number; lastPlayingAt: number
}
export const mprisPlayers: Accessor<MprisPlayer[]>
export const activePlayer: Accessor<MprisPlayer | null>   // pickActivePlayer(mprisPlayers())
export function resyncMpris(): void                        // one-shot: re-read position/flags
export function playPausePlayer(p: MprisPlayer): void
export function nextPlayer(p: MprisPlayer): void
export function previousPlayer(p: MprisPlayer): void
export function seekPlayer(p: MprisPlayer, absoluteUs: number): void
```
- Position sync points (only these): initial hydration · `Seeked` · transition to `Playing` · `Metadata` change. `positionSyncedAtMs` = monotonic ms (`GLib.get_monotonic_time()/1000`).
- Actions shell out with explicit targeting and `.catch(console.error)`:
  `playerctl -p <suffix>` where suffix is the bus name minus `MPRIS_PREFIX` (e.g. `chromium.instance4925`).
  - playPause → `play-pause`; next → `next`; previous → `previous`; seek → `position <seconds>` (absolute; convert µs→s).
  - Optimistic local flip of `status`/`positionUs`, reconciled by the next event.
- Bootstrap at module load, idempotent (`started` flag), like `bluetooth-service.ts`.

**Acceptance criteria**
- Node tests cover: bus-name parse (with/without instance, excluded), alias mapping, metadata parse (missing keys → safe defaults), `formatClock` (0, <60s, >10min, unknown), `interpolatePosition` (playing/paused/negative elapsed clamp), `identityMatches` (chromium↔google-chrome, case/punctuation, no-match), `pickActivePlayer` (most-recent-playing, fallback order, empty).
- `node src/gui-tools/icon-color-mapping-editor/tests/mpris-core.test.mjs` exits 0.
- Live smoke (read-only, may be a throwaway gjs script outside the repo): with a player active, `mprisPlayers()` reports ≥1 player with correct status/metadata; with none, it reports `[]` and no error.
- **No file outside WP-B's deliverables is modified.** No `wp.audio.*`, no `states.ts` changes.

**Depends on**: nothing. **Parallel with**: WP-D.

---

### WP-C — Wire into state + popup UI + CSS

**Deliverables**
1. `dotfiles/config/ags/audio/state.ts` — **additive** (I10):
   - import from `../services/mpris-service`;
   - `export function playerForStream(stream: unknown): MprisPlayer | null`
     — candidates = slug(`application.name`) from the graph snapshot `nodeApp`, plus `application.process.binary` (add `nodeBinary` to the snapshot if absent; capture it in the same `pw-dump` pass — do not add a second dump);
     — match via `identityMatches`; among matches prefer most-recent `Playing`, else first.
   - `export { activePlayer as masterPlayer }`.
2. `dotfiles/config/ags/audio/AudioPopup.tsx`:
   - `TransportLine({ stream })` per D2–D5, D9. Local display-position state; 1s interpolation tick **only while `popupVisible()` && status === "Playing"** (recording-widget pattern); seek commits on release (D4).
   - `StreamRow`: render `<TransportLine>` after `LevelLine` iff `playerForStream(stream)`.
   - Output card: master button per D1, using `masterPlayer()`.
   - `OutputDevicesView`: `✓` + active class per D7 (`defaultSpeaker()?.id === nodeOf(device)?.id`).
   - `streamSubtitle`: D6 filter.
   - Popup-open effect: one-shot `resyncMpris()` alongside `refreshStreamTargets()`.
   - Use `media-transport` icons (WP-D) for all transport/master glyphs (D10).
3. `dotfiles/config/ags/style.css`: `.audio-transport`, `.audio-transport.paused`, `.audio-time`, `.audio-master`, `.audio-check` — match the mockup's proportions (356px column, 5px track, 13px knob, 11px dim monospace-ish time).

**Acceptance criteria**
- Global acceptance gate (§4) passes; symbol existence check clean.
- Live: with tidal + Chrome playing, open the popup → two transport lines; master button visible, tooltip names the most-recent player; pause/resume/next/prev/seek all work; volume sliders and routing still work; Discord-style no-player row unchanged; `✓` in subview; playing → paused dims + freezes.
- No behavioural change to the existing output/input/recording sections when no player exists.
- `git diff` touches only the three deliverable files.

**Depends on**: WP-B (service API) and WP-D (icons, for the glyph paths). C may start on layout/CSS while waiting for D's rendered outputs, but must not hardcode paths other than `registry.resolve("media-transport", …)`.

---

### WP-D — `media-transport` icon group

**Deliverables**
1. `dotfiles/assets/icon-templates/media-transport/default/{play,pause,previous,next}.svg`
   - 1024×1024 viewBox; stroke/fill `{{COLOR_FOREGROUND}}`; match the mockup glyph geometry (triangle play; two bars pause; bar+triangle previous/next).
2. `dotfiles/config/icon-template-color-scheme-mappings/icons.yaml`: new group
```yaml
media-transport:
  color_mappings:
    COLOR_FOREGROUND: foreground
  variants:
    - name: play
      template: media-transport/default/play.svg
      output: media-transport-play.svg
    # pause / previous / next analogous
```
3. Regenerate `dotfiles/config/ags/icons.json` (I6) and byte-verify:
```bash
python3 - <<'PY'
import json,yaml
d=yaml.safe_load(open('dotfiles/config/icon-template-color-scheme-mappings/icons.yaml'))
open('dotfiles/config/ags/icons.json','w').write(json.dumps(d,indent=2,sort_keys=True)+"\n")
PY
```
   Expect a **pure addition** diff (no reordering of existing groups beyond sorted insert).

**Acceptance criteria**
- `itr list … --icon media-transport` lists 4 variants.
- `itr render … --icon media-transport --output-dir <tmp>` produces 4 SVGs whose fills survived literal substitution (foreground token resolved).
- `icons.json` regenerates to a diff containing only the new group.
- Group is **not** in `BAR_GROUPS` (do not touch that file — I9).

**Depends on**: nothing. **Parallel with**: WP-B.

---

### WP-E — Provisioning + provisioning tests

**Deliverables**
1. `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`: add **both** entries (the core is a separate file — I11 forbids GJS imports in it, so it cannot live inside the service file):
   ```yaml
   - { name: ags-service-mpris, source: dotfiles/config/ags/services/mpris-service.ts, dest: "{{ compositor_configs_spine_config_dir }}/ags/services/mpris-service.ts" }
   - { name: ags-service-mpris-core, source: dotfiles/config/ags/services/mpris-core.ts, dest: "{{ compositor_configs_spine_config_dir }}/ags/services/mpris-core.ts" }
   ```
   Place them after `ags-service-bluetooth` (~line 180).
2. `src/provisioning/ansible/roles/verify/vars/main.yml`: add the new AGS service/core files to the file list; confirm `playerctl` is covered by `verify_system_binaries` (it is provisioned — add only if missing).
   **RESOLVED (WP-E)**: `playerctl` was **not** actually in `verify_system_binaries` (only in `packages.yaml`); it was added there, pinned in `test_verify_role.py`, and stubbed in `_write_stub_binaries`. The two MPRIS files were added to `verify_compositor_skeleton_files`.
3. `src/provisioning/tests/unit/test_compositor_configs_role.py` + `test_verify_role.py`: expected lists updated.
   **Exact required edits in `test_compositor_configs_role.py` (this test asserts an EXACT count and list):**
   - `assert len(files) == 58` → `== 60` (line ~254); update its message text to mention the two MPRIS files.
   - Insert into the sorted `expected` list (line ~263), keeping sort order. **CORRECTED during WP-E**: both MPRIS sources sort *before* `nm-client.ts` (they sit after `bluetooth-service.ts`), not after it — the original note here was wrong. Final order: `…bluetooth-service.ts`, `mpris-core.ts`, `mpris-service.ts`, `nm-client.ts`, `wifi-service.ts…`. The `sources == expected` assertion is a **sorted** comparison — insert in sorted position or the test fails.
   **In `test_verify_role.py`:** the AGS file fixture (~line 2150) writes `app.tsx`/`style.css`/`icons.json`; add the MPRIS service/core paths the verify role now checks, and mirror any `ags/services` directory expectations (~line 2166).
4. Targeted role runs (never full bootstrap concurrently — I8):
```bash
cd src/provisioning/ansible
uv run ansible-playbook playbooks/assets.yaml            -e "install_dir=$HOME/.local/share/dotfiles"
uv run ansible-playbook playbooks/compositor-configs.yaml -e "install_dir=$HOME/.local/share/dotfiles"
```

**Acceptance criteria**
- Both unit test files pass.
- Both roles report `failed=0`.
- Spine `config/ags/services/mpris-service.ts` byte-identical to the repo file; spine `config/ags/icons.json` byte-identical to the repo file (proves the generation path).
- No spine file edited by hand.

**Depends on**: WP-C, WP-D (final file set).

---

### WP-F — Live gate, functional matrix, docs

**Deliverables**
1. Full §4 live gate, captured log.
2. Functional matrix executed and reported:
   | Case | Expected |
   |------|----------|
   | tidal playing, Chrome playing | two transport lines, correct glyphs/times |
   | per-row pause → resume | glyph flips, audio stops/starts, position freezes/resumes |
   | seek drag + release | audio jumps, times match, position resyncs |
   | next / previous | track changes (only where `CanGo*` true) |
   | master button | pauses most-recent player; tooltip names it |
   | pause via external source (playerctl CLI) | popup reflects it (event-driven) |
   | kill a player | its transport line disappears; volume/routing intact; no error |
   | no players at all | all rows volume-only; master hidden |
   | Discord (no player) | volume-only |
   | Output subview | `✓` on default sink; selecting another sets default (verify `wpctl status`) |
   | subtitle | "Playback" hidden; real title shown |
   | regression | volume sliders, mute, routing, input, recording all still work |
3. Docs: update `_bmad-output/planning-artifacts/ux-designs/ux-dotfiles-repo-v3-audio-2026-09-18/DESIGN.md` +
   `EXPERIENCE.md` with the new transport component + master button + subview check; append a
   `.memlog.md` entry (house convention).
4. Commit the whole feature (message: `feat(ags): per-app media transport controls (MPRIS)`).

**Acceptance criteria**
- Live log clean, layer mapped, matrix fully passing (or a defect list with evidence).
- Docs + memlog updated; feature committed on `feat/pipewire-audio-ags`.

**Depends on**: WP-B, WP-C, WP-D, WP-E.

---

## 6. Dispatch prompts (paste verbatim, one per agent)

Each dispatch = **this WP's section + §0 + §1 + §2 + §3 (as relevant) + §4**. Suggested prompt header:

> You are implementing **WP-<X> — <title>** for the AGS audio popup in the worktree
> `/home/inumaki/Development/dotfiles-new-architectures/dotfiles-repo-v3-audio` (branch
> `feat/pipewire-audio-ags`, base `c86b338c`). Read the attached dispatch contract sections
> §0 (invariants), §1 (ground truth), §2 (traps), §3 (locked decisions) before writing code.
> Invariants are hard constraints; if code contradicts the contract, STOP and report.
> Deliver only the files listed in your WP. Before declaring done, run the §4 acceptance
> gate and report the exact commands + outputs. Do not expand scope.

---

## 7. Out of scope (explicitly)

Media keybinds (XF86 already handled elsewhere) · album art · playlist/browse UI · master
next/prev · linking non-media browser streams · `playerctld` integration · any change to
`wp.audio.*`, `BAR_GROUPS`, or the recording widget.

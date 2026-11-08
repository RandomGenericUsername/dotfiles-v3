# 107 — Generations v3

> **Status:** **delivered** (RFC 2026-11-06; live 2026-11-08) — ticket
> `SKIN-PLANE-V3`, slug `generations-v3-rfc`. The cutover tuple is
> contracts `v0.8.0`, ags-platform `v1.0.1`, dotfiles-runtime `v1.0.4`,
> dotfiles-assets `v0.13.0`, dotfiles-provision `v0.1.48`, composition
> `v0.1.50`, with the seven app tags listed in the
> [epic](./epics/SKIN-PLANE-V3-generations.md#delivery-evidence).
>
> v3 ([`docs/107`](./107-generations-v3.md)) is the live plane. It replaces the
> v2 ([`docs/105-appearance-plane-v2.md`](./105-appearance-plane-v2.md))
> *multi-pointer* and *two-pipeline* mechanics with one committed generation and
> one convergence function; it keeps the v2 artifact interface (composed palette
> + skin + mode, one provider, one watched hop) and the v2 token vocabulary.
>
> Live evidence: `current -> generations/43d62e17…` (terminal, smart→dark),
> `doctor` clean, `verify` `ok=327 failed=0`, immutable app tags, watcher-driven
> mode changes without `wallpaper set`, and one `current` under concurrent
> writers.

## 0. Decisions (frozen)

1. **Generation is the unit.** `state/generations/<genHash>/` contains
   `manifest.json`, `palette/`, `appearance/<app>.css` + `tokens.json`,
   `icons/`, `effects/` and `wallpaper`. One commit pointer,
   `state/current -> generations/<genHash>`, is swapped with a **single atomic
   rename**. Every consumer reads through `current/`. Layer entries stay
   content-addressed and are referenced/reused by generations.
2. **One convergence implementation.** `converge(intent) -> generation` is the
   only mutation path, used by the daemon, the CLI, and skin/mode/wallpaper
   changes. Mutations are serialized through the daemon's job queue (the daemon
   owns `org.dotfiles.Events` jobs); the CLI submits and awaits `JobFinished`.
   When the daemon is unavailable, the CLI runs the **same function** under the
   **same exclusive lock**. One lock scope covers intent → derive → stage →
   commit → apply/ledger. There is no publish-then-fail path.
3. **Generation-bound apply/ack.** The refresh request carries `genHash`. The
   app applies `current/appearance/<app>.css` only after verifying
   `current/manifest.json` matches, or reads the generation directory directly.
   It answers `{"applied":"<genHash>"}`. The runtime records `applied` only on
   an exact match; a mismatch is retried on the next trigger or handled by the
   app's restart policy.
4. **Artifact locality.** Runtime writes **only** under `state/`; never under
   `<install>/` or `<install>/apps/<tag>/`. The platform reads
   `$XDG_STATE_HOME/dotfiles/current/appearance/<configDir>.css` and watches
   `current` (one hop). Provisioning provides writable stable links for
   **non-runtime** consumers only; verify asserts there are no runtime files
   inside app tags.
5. **No polling as correctness.** Use inotify for `desired.json`/`current`;
   D-Bus `NameOwnerChanged` for AGS registration; systemd `JobRemoved` /
   `--wait` for restarts. No sleep-loops as a success condition. A timeout is
   an abort/report bound, never a "probably ready" signal.
6. **Lane policy is explicit.** Each app declares `live` or `restart`; exactly
   one is enforced. Unit-managed affects *how* a restart happens, not *whether*
   it happens. A failed live refresh never silently becomes a restart.
7. **Mode is a generation input.** `mode` remains part of the intent and of the
   generation identity. A mode change is an ordinary generation change, not a
   special `wallpaper set` side effect.
8. **No workarounds.** No second pointer, no second pipeline, no "apply
   whatever is current" ack, and no retry loop that hides a missing event.

## 1. Findings and evidence

All file references below are from the sibling pinned repos as of the
2026-11-06 investigation; the live host observations are from the same
machine. The findings are the reason the frozen decisions above are not
optional.

### 1.1 Multi-pointer skew

`state/current` is a directory of independent symlinks, not a generation. The
runtime repoints each family separately:

- `dotfiles-runtime/src/runtime/adapters/seeder.py:660-764` —
  `repoint_current_symlinks()` writes wallpaper links, then eight palette
  artifacts one at a time, then `effects`, then `icons`. Each call is atomic
  for **that entry** (`seeder.py:92-106`), not for the set.
- `dotfiles-runtime/src/runtime/application/reconcile.py:308-326` — reconcile
  calls `repoint_current_symlinks()`, then `publish_appearance()`, then
  `repoint_consumer_symlinks()`. These are three separate instants inside the
  same lock but visible to readers between syscalls.
- `dotfiles-runtime/src/runtime/adapters/seeder.py:766-807` —
  `publish_appearance()` repoints `current/appearance` and writes the per-app
  convenience links after the palette/effects/icons set already moved.

Live host state confirms the shape (2026-11-06):

```text
$ ls -l ~/.local/state/dotfiles/current
colors.yaml      -> cache/palettes/0797.../colors.yaml
effects          -> cache/effects/1a3d...
icons            -> cache/icons/e539...
appearance       -> cache/appearance/09ea...
wallpaper.png    -> cache/wallpapers/fb1c.../wallpaper.png
```

A consumer can read palette `N` and appearance `N+1` (or effects/icons from a
third generation). The v2 appearance generation is composed from a palette, so
"palette is a layer, appearance is a layer" is not a consistency model: it is a
guess about which instant the reader won.

**Consequence:** a reader must be able to name and verify one generation. The
fix is not a shorter repoint loop; it is one commit pointer.

### 1.2 Two convergence pipelines

There are two independent mutation paths:

- **Daemon:** `dotfiles-runtime/src/runtime/cli/main.py:2096-2240` composes
  `_run_reactive_converge()`; `main.py:2533-2541` calls it on a watch trigger.
  The composite is `CheckInputs → RegenerateStale → Reconcile → declarative`
  (`src/runtime/application/converge.py:80-101`).
- **CLI:** `dotfiles-runtime/src/runtime/cli/main.py:3336-3453` runs
  `_run_reconcile()` directly and then `_run_converge()`. `wallpaper set`
  separately composes `ApplyWallpaperUseCase` + `ReconcileDesktopStateUseCase`
  in `main.py:649-737`.
- `reconcile --regenerate-stale` builds yet another composition
  (`main.py:1542-1635`) and delegates to `RegenerateStaleUseCase`.

The two paths mutate the same state and do not share a transaction.

**Mode-change evidence (live).** With the daemon stopped:

```text
$ printf 'mode=light' ...                 # desired.json mode -> light
$ dotfiles-runtime reconcile --regenerate-stale
$ echo $?
0
$ grep '^mode:' ~/.local/state/dotfiles/current/colors.yaml
mode: dark
```

The rc=0 is not a convergence success. `CheckInputs` hashes only the producer
template set (`dotfiles-runtime/src/runtime/adapters/invalidation.py:140-173`);
mode is not a stale input. When nothing is stale, `RegenerateStaleUseCase`
returns before it reconciles
(`src/runtime/application/regenerate.py:88-97`). Reconcile itself can detect a
mode-key change (`src/runtime/application/reconcile.py:498-518`), but the
`--regenerate-stale` path never reaches it. Only `wallpaper set` regenerated
light because its apply path constructs the producer with the resolved mode
(`main.py:658-662`) and runs the themed phase (`main.py:704-737`).

**Concurrent daemon + CLI evidence (live).** The two paths use different lock
files: the seeding path uses `.seed.lock` (`main.py:772`) and the appearance
refresh uses `.appearance-operation.lock`
(`src/runtime/adapters/appearance_ledger.py:58-94`). A concurrent run produced:

```text
reconcile succeeded, converge failed: wallpaper set already in progress (lock held)
```

That is the two-pipeline defect in one line: one path had already published and
the other failed after it. A successful CLI must not leave a half-applied
desktop, and a second path must not be able to race the first one's lock.

### 1.3 Ack is not generation-bound

The transport still accepts `{"ok":true}` with no generation identity:

- `contracts/ags-app-refresh.md:64-78` defines `{"ok":true}` as applied and has
  no `genHash` field.
- `ags-platform/ports/palette-refresh.ts:110-125` encodes `applied` as exactly
  `{"ok":true}`.
- `ags-platform/ports/appearance-refresh.ts:58-90` ignores the requested hash
  except for its own idempotence cache. It always calls
  `appearance.apply()`, which re-reads **whatever `current` is**.
- `ags-platform/ports/appearance.ts:878-918` and `:967-974` read
  `appearanceCssPath`/`tokensPath` through `current`; there is no
  `manifest.json` generation check.
- `dotfiles-runtime/src/runtime/adapters/ags_app_refresh.py:151-190` decodes
  `{ok:true}` as `applied`, and the ledger records the **requested** hash.
- `dotfiles-runtime/src/runtime/adapters/ags_app_refresh.py:592-599` sends
  `palette-refresh <appearance-hash>`; the app never has to prove which
  generation it read.

Live evidence: after requesting appearance `aeba…`, the notifications app
answered `{"ok":true}`, but a screenshot/render still showed the old provider
until the unit was restarted. The app had applied "current at handler time",
which was not the requested generation; the runtime had no way to tell.

**Consequence:** an ack must be a statement about a named generation. A boolean
is not falsifiable.

### 1.4 Runtime writes into immutable app tags

`publish_appearance()` writes a convenience link into the install spine:

- `dotfiles-runtime/src/runtime/adapters/seeder.py:790-804` —
  `dest = install_spine / "config" / config_dir / "appearance.css"` then
  `_repoint_symlink(dest, pointer / f"{config_dir}.css")`.
- `dotfiles-provision/ansible/roles/ags_apps_units/tasks/_one.yml:150-162` —
  provisioning makes `<install>/config/<spineLink>` a symlink to
  `<install>/apps/<installDir>/<tag>` and the XDG link to the spine link.
- `dotfiles-runtime/src/runtime/adapters/seeder.py:92-106` — `_repoint_symlink`
  writes at `current_path`; when its parent is a symlink into a tag, the write
  lands **inside the tag**.

Live evidence (2026-11-06):

```text
$ ls -l ~/.local/share/dotfiles/apps/notifications/v0.4.0/appearance.css
... -> /home/inumaki/.local/state/dotfiles/current/appearance/ags-notifications.css

$ readlink -f ~/.local/share/dotfiles/config/ags-notifications
/home/inumaki/.local/share/dotfiles/apps/notifications/v0.4.0
```

This is an AD-37 violation and a concrete immutability break: the runtime
authored `appearance.css` inside a released tag. The adapter watches
`current/appearance` but reads the per-app path through
`$XDG_CONFIG_HOME/<configDir>/appearance.css`
(`ags-platform/adapters/appearance-scope.ts:57-74`,
`ags-platform/adapters/appearance.ts:56-67`). The read path therefore goes
through the tag even though the watch path is state. v3 moves both the write
and the read to `state/`.

### 1.5 Polling and timeouts used as correctness

The current paths use bounded retry/sleep loops where an event exists:

- `dotfiles-runtime/src/runtime/adapters/appearance_ledger.py:58-94` —
  the appearance-operation lock retries `flock` with `time.sleep(0.05)` until a
  10 s deadline.
- `dotfiles-runtime/src/runtime/adapters/ags_reloader.py:86-96, 572-588,
  757-770, 772-828` — quit release, launch-lock and name-registration waits
  are `20 × 0.25 s` / `100 × 0.1 s` polls. Registration success is inferred
  from a repeated `ags list`, not from the bus event that actually fires.
- `dotfiles-runtime/src/runtime/adapters/gtk4_app_reloader.py:308-319` — restart
  liveness is a sleep poll.

These are not merely inefficient: they are the success condition. A slow but
correct start is a failure; a fast but wrong process can pass the poll. v3 uses
the kernel/bus/systemd event and keeps only an abort bound.

### 1.6 Mixed lane policy

Lane policy is split across two vocabularies:

- Composition `dotfiles/provisioning/apps.yaml:32-59` marks bar and
  notifications `launch: always`; the other five are `launch: on-demand`.
  `launch` says who starts the app, not how a refresh is applied.
- Each app's `app.manifest.json` declares `mode` (`live` or `restart`):
  `ags-notifications/app.manifest.json:1-7` is `live`;
  `ags-bar/app.manifest.json:1-7` is `restart`.
- The runtime dispatches on that field
  (`dotfiles-runtime/src/runtime/adapters/ags_app_refresh.py:363-364`,
  `:449`) and validates the pair
  (`src/runtime/adapters/ags_app_discovery.py:340-350`).
- Unit-managed restarts were added later as a separate path:
  `src/runtime/adapters/ags_reloader.py:492-533` chooses
  `systemctl --user restart <unit>` when a unit exists, otherwise the raw
  `ags quit`/`ags run` path.

So notifications is unit-managed + live, the bar is unit-managed + restart, and
the on-demand apps are launcher-managed + live. The same "restart" word means
two different operations depending on provisioning, and the composition list
does not declare the refresh lane at all. v3 makes the three axes explicit:
`refresh` (`live|restart`), `supervision` (`unit|launcher`), and `launch`
(`always|on-demand`).

## 2. Generation model

### 2.1 Layout

Everything below is under the single runtime state root
`$XDG_STATE_HOME/dotfiles/` (`state_root` in the existing code):

```text
state/
  cache/                                  # content-addressed layer entries (existing store)
    palettes/<paletteHash>/...
    effects/<effectsHash>/...
    icons/<iconsHash>/...
    wallpapers/<wallpaperHash>/wallpaper.png
  generations/
    <genHash>/
      manifest.json                       # written last; the self-check
      palette -> ../../cache/palettes/<paletteHash>
      effects -> ../../cache/effects/<effectsHash>
      icons   -> ../../cache/icons/<iconsHash>
      wallpaper/
        wallpaper.png -> ../../../cache/wallpapers/<wallpaperHash>/wallpaper.png
      appearance/
        tokens.json                       # mode-resolved v2 tokens
        ags.css
        ags-notifications.css
        ...                               # one <configDir>.css per target
      # compatibility aliases inside the SAME generation (never pointers)
      colors.yaml -> palette/colors.yaml
      colors.gtk.css -> palette/colors.gtk.css
      colors.adw.css -> palette/colors.adw.css
      colors.conf -> palette/colors.conf
      colors.sequences -> palette/colors.sequences
      colors.rasi -> palette/colors.rasi
      colors.kitty -> palette/colors.kitty
      colors.btop.theme -> palette/colors.btop.theme
      wallpaper.png -> wallpaper/wallpaper.png
      wallpaper-<monitor>.png -> wallpaper/wallpaper.png
  current -> generations/<genHash>         # ONE atomic commit pointer
  appearance-ledger.json                   # per-app apply/ack state
  converge.lock                            # the single operation lock
  staging/                                 # crash-recoverable staging only
```

The compatibility aliases are **inside** the generation. They are not a second
pointer and cannot skew: resolving `current/colors.yaml` and
`current/appearance/ags.css` from the same `current` inode lands in the same
generation. During migration they preserve the existing consumer vocabulary;
after migration they may be dropped once every consumer reads the v3 paths.

The layer entries remain the existing content-addressed store. A generation
does not copy palette/icons/effects/wallpaper bytes; it references immutable
entries. Only `appearance/*` and `manifest.json` are generation-specific real
files (the composed sheet depends on palette + skin + mode).

### 2.2 `manifest.json`

```json
{
  "schemaVersion": 3,
  "generationHash": "<sha256>",
  "createdAt": "2026-11-06T00:00:00Z",
  "intent": {
    "wallpaper": "<wallpaperHash>",
    "palette": "<paletteHash>",
    "skin": "glass",
    "mode": "light"
  },
  "layers": {
    "palette": { "hash": "<paletteHash>", "path": "palette" },
    "effects": { "hash": "<effectsHash>", "path": "effects" },
    "icons": { "hash": "<iconsHash>", "path": "icons" },
    "wallpaper": { "hash": "<wallpaperHash>", "path": "wallpaper" }
  },
  "appearance": {
    "tokens": "appearance/tokens.json",
    "configDirs": {
      "ags": "appearance/ags.css",
      "ags-notifications": "appearance/ags-notifications.css"
    },
    "artifactHash": "<sha256>"
  }
}
```

Rules:

- The directory name **is** `generationHash`. The manifest's
  `generationHash` must equal the directory basename and the target basename of
  `current`.
- `generationHash` is a canonical hash of the intent, layer hashes, mode and
  the composed appearance artifact hash. It does not include timestamps.
- The manifest is written last inside staging. A directory without a valid
  manifest is never a generation.
- Consumers verify the manifest (generation hash, layer references, artifact
  digests) before reading. A mismatch fails closed: keep the previous provider,
  report, and retry on the next generation event.
- `configDirs` is the only app-list input; the platform still carries no app
  list.

### 2.3 Commit transaction

The commit is one lock scope and one visible rename:

1. **Acquire** the single exclusive lock (`converge.lock`) through the daemon's
   job queue or the CLI fallback.
2. **Read intent** (`desired.json`) and snapshot the input identities
   (wallpaper bytes, skin manifest/templates, mode). An invalid intent fails
   before any mutation.
3. **Derive/reuse layers** into content-addressed entries. Derivation may use
   staging inside `cache/`; an orphaned cache entry is harmless and GC-able.
4. **Stage the generation** under `state/generations/.staging-<pid>-<uuid>/` on
   the same filesystem. Write layer links, composed appearance sheets and
   `tokens.json`; write `manifest.json` last; `fsync` files and directories.
5. **Publish the immutable generation:** `rename(staging, generations/<genHash>)`.
   If the target already exists, validate it and discard the staging copy
   (content-addressed reuse).
6. **Commit the pointer:** create `current.tmp.<pid> -> generations/<genHash>`
   and `rename(current.tmp…, current)`, then `fsync` `state/`. This is the only
   visible transition; readers see the old generation or the new one, never a
   mix.
7. **Apply/ledger:** send generation-bound refresh requests to live apps,
   restart the restart lane, and write one ledger record per app. These results
   are recorded against `generationHash`; a deferred/failed app is retried on
   the next trigger. The generation is already authoritative; an apply failure
   cannot repoint back to the previous generation.
8. **Release** the lock. The next job/trigger sees a complete generation or the
   same complete generation (idempotent).

"One lock scope" means the old split of derivation-outside-the-lock,
repoint-inside, reload-outside is gone. Derivation may be expensive, but it is
part of the serialized convergence, not a separate publish phase. This is the
price of "no publish-then-fail"; it is a deliberate tradeoff (see §6).

### 2.4 Crash recovery

| Crash point | Visible state | Recovery |
| --- | --- | --- |
| before generation rename | old `current`; staging under `generations/.staging-*` | old generation stays; startup/converge removes stale staging older than grace |
| after generation rename, before `current` rename | old `current`; complete orphan `generations/<gen>` | old generation stays; GC may retain/remove the orphan; next converge reuses it by hash |
| during `current` rename | old or new `current` (rename is atomic) | no repair needed; manifest check validates the new target |
| after `current` rename, before ledger | new `current`; ledger names the old generation | next trigger sees `ledger.generation != current` and refreshes every app; no rollback |
| during apply/restart | new `current`; some apps old, some new | app event/retry converges to `current`; restart lane retries per policy; ledger records deferred, never `applied` |
| during GC | retained generations intact; object removal may be partial | sweep is journaled; only unreferenced objects older than grace are removed; next sweep completes |

A partially written generation is never visible because `current` only points
at a directory whose manifest was written last and whose rename completed. A
torn staging directory is never treated as a generation.

### 2.5 One convergence function, daemon queue and fallback

The application layer exposes exactly one function:

```text
converge(intent) -> ConvergeResult {
  generation: <genHash>,
  committed: bool,
  degraded: bool,
  app_results: [...]
}
```

The daemon is the default executor because it already owns the event surface
and must serialize all mutations:

- The daemon owns a **converge job queue** over the existing
  `org.dotfiles.Events` job surface (`JobStarted`/`JobFinished`). A job carries
  the intent revision/hash and returns the committed `genHash` plus per-app
  status.
- The CLI preflights the well-known name once. If the daemon owns it, the CLI
  **subscribes to `JobFinished` before submitting**, submits one converge job,
  and waits for the matching `job_id`/`genHash`. It does not poll state files.
- Queue policy: an identical intent/generation is coalesced; the newest queued
  intent supersedes older queued (not running) intents; a running job is never
  cancelled mid-commit. A job is idempotent and safe to retry by intent hash.
- If the daemon is not on the bus, the CLI acquires the **same**
  `converge.lock` and calls the **same** `converge(intent)` implementation.
  It does not run a second implementation, and it does not silently start a
  daemon. If the daemon disappears after a job was submitted, the CLI reports
  the typed failure and re-checks the commit; it does not run the fallback
  concurrently with a possibly-live job.
- The lock is a kernel `flock`: blocking acquire, no retry loop, released by
  process death. The daemon job queue and the fallback share the lock path and
  ordering. There is no nested `.seed.lock`/appearance lock.

### 2.6 Generation-bound refresh protocol

The transport may keep the existing AGS request channel, but the payload and
ack change (contracts next version):

```text
request:  ["appearance-refresh", "<genHash>"]
response: {"applied":"<genHash>"}
          | {"deferred":"reason","genHash":"<genHash>"}
          | {"failed":"reason","retryable":true|false,"genHash":"<genHash>"}
```

The app handler must:

1. Resolve the requested generation. It may stat `current` and verify
   `current/manifest.json.generationHash == genHash`; if the pointer moved, it
   returns `deferred` (retryable) and does not apply the old/new mix.
2. Prefer reading `generations/<genHash>/appearance/<configDir>.css` and
   `appearance/tokens.json` directly. The generation is immutable, so this
   removes the check-then-read window. If it reads through `current`, it must
   verify the manifest again after reading and retry on a mismatch.
3. Validate and install the sheet (one provider, USER priority, last), then
   run only app-owned derived work.
4. Answer with the exact `genHash` it applied. A cached `applied` is keyed by
   `genHash`, not by a boolean.

The runtime records `applied` only when the ack's `applied` equals the
requested `genHash` and the current generation still matches. A stale ack is a
`deferred`/retry, not success. For a restart-lane app, the runtime restarts the
app only after the generation is committed; if `current` moves during the
restart, the per-app result is downgraded to `deferred`, as the current code
already does for the whole ledger
(`dotfiles-runtime/src/runtime/adapters/ags_app_refresh.py:474-500`).

### 2.7 Artifact locality and immutability

Runtime-owned paths are exactly:

```text
state/cache/<kind>/<hash>/...
state/generations/<genHash>/...
state/current
state/appearance-ledger.json
state/converge.lock
state/staging/...
```

The runtime never writes:

- `<install>/apps/<installDir>/<tag>/` (immutable app tag);
- `<install>/config/...` (install spine; provisioning owns its shape);
- `$XDG_CONFIG_HOME/<configDir>/appearance.css` (there is no such runtime
  convenience link in v3).

The platform reads the state path directly:

```text
$XDG_STATE_HOME/dotfiles/current/appearance/<configDir>.css
$XDG_STATE_HOME/dotfiles/current/appearance/tokens.json
```

and watches `$XDG_STATE_HOME/dotfiles/current` (or its parent, for the atomic
rename event). This is one hop from state to the generation; the app tag is
never in the read path.

Provisioning may create **writable stable links for non-runtime consumers**,
for example `~/.config/gtk-4.0/colors.css ->
$XDG_STATE_HOME/dotfiles/current/palette/colors.adw.css`. Those links are
provisioning-owned and stable; the runtime never repoints them. App source
links (`~/.config/<configDir> -> <install>/config/<configDir> ->
<install>/apps/<tag>`) remain for app code and static assets.

`verify`/`deploy-coverage` must assert:

- no runtime artifact (`appearance.css`, `colors*`, `tokens.json`, generation
  pointer) exists inside any `<install>/apps/<installDir>/<tag>/`;
- every non-runtime stable link resolves through `current/`, not through a
  generation-specific path;
- the state root contains no symlink into an app tag.

### 2.8 Lane policy

Each app declares three independent axes:

| Axis | Values | Owner | Meaning |
| --- | --- | --- | --- |
| `refresh` | `live` \| `restart` | app manifest (and mirrored in the composition app list) | exactly one apply path for an appearance change |
| `supervision` | `unit` \| `launcher` | provisioning/app list | who owns the process lifecycle |
| `launch` | `always` \| `on-demand` | composition app list | whether login starts it |

Rules:

- `live` means the app has a generation-bound refresh handler and must not be
  restarted for an appearance change.
- `restart` means the app has no refresh handler; it is restarted. A failed
  live refresh never falls back to restart. A restart failure is a retry, not a
  lane switch.
- `supervision: unit` changes only *how* the restart is performed
  (`systemctl --user restart`, `ExecStop=ags quit -i`, `Restart=on-failure`).
  `supervision: launcher` uses the serialized AGS quit/launch path. The
  `refresh` decision is already made before supervision is consulted.
- `launch` is not a lane. An on-demand app can be `live`; an always-on app can
  be `restart`.
- A mode change is a normal generation change for every lane. There is no
  "mode-only" path and no wallpaper-set-only workaround.

### 2.9 Event-driven rules (no polling)

| Wait | Required mechanism | Forbidden |
| --- | --- | --- |
| `desired.json` change | inotify watch on the intent file/parent | mtime polling |
| new generation | inotify `MOVED_TO` on `current` (or parent) | polling `current` symlink |
| app registration | D-Bus `NameOwnerChanged` (already a platform constant, `ags-platform/ports/event-client.ts:37-40`) | repeated `ags list` |
| systemd restart | `systemctl --user restart --wait` or `JobRemoved` | sleep/name polls |
| lock acquisition | blocking kernel `flock` | bounded `flock` retry loop |
| watch overflow/lost event | one full rescan triggered by the overflow event | sleep-and-retry |

A timeout may exist only to abort/report (for example a D-Bus call deadline).
It must not be used to decide that an app is ready, that a restart succeeded, or
that a generation is committed.

### 2.10 Garbage collection

- **Retain** the active generation, the newest `keep` generations, any pinned
  generation, and any generation named by an `applied`/`deferred` ledger entry
  that may still be retried.
- **Grace:** do not remove anything younger than `grace` (default 24 h) or
  newer than the last successful commit.
- **Mark-and-sweep:** enumerate retained generations and staging manifests;
  collect referenced layer hashes; remove unreferenced `cache/` entries older
  than grace. Never remove a referenced entry, even if old.
- **Order:** prune generations only while holding `converge.lock`; remove
  generation directories before their now-unreferenced objects. A reader that
  already opened an old generation keeps working on POSIX; a reader that still
  resolves through the pruned path gets a retryable missing-generation result.
- **Staging:** remove stale `generations/.staging-*` and cache staging older
  than grace at startup or at the next converge, never by a background timer.
- **Never** delete user files, app tags, or install-spine links.

## 3. Migration waves

Each wave is a separate repo/ticket/release. This RFC changes no pins.

| Wave | Repo | Scope | Acceptance |
| --- | --- | --- | --- |
| 0 | `contracts` | Generation manifest + `genHash` identity; generation-bound refresh v3; `refresh`/`supervision` vocabulary; deprecate boolean ack | Schema tests; an ack without `genHash` is invalid; lane vocabulary has exactly one refresh value |
| 1 | `dotfiles-runtime` | Objects -> generations; one commit rename; `converge(intent)`; daemon job queue + fallback lock; event-driven readiness; mode as input; GC | Concurrency/crash-injection/stale-ack tests; no second mutation path; mode change without wallpaper set |
| 2 | `ags-platform` | Generation-bound apply/ack; read `state/current/appearance/...`; watch `current`; `NameOwnerChanged` registration | Stale-gen request never applies; mismatch answers deferred; no config/tag read path |
| 3 | apps (`ags-bar`, `ags-notifications`, `ags-capture-tool`, `ags-clipboard`, `ags-wallpaper-selector`, `ags-icme`, `ags-btop-theme-studio`) | Implement the v3 handler or restart lane; declare `refresh`/`supervision`; remove convenience-link assumptions | Each app conformance test; bar restart only; notifications live with unit supervision |
| 4 | `dotfiles-provision` | State directories; stable non-runtime links; remove any runtime link ownership; mirror lane fields; verify immutability | Verify rejects a runtime file in a tag and a non-resolving stable link |
| 5 | `dotfiles-v3` | Consume the wave tags (separate cutover ticket); docs 106 live; gates | `make ci-gates-parity`, `make deploy-coverage`; acceptance suite green |
| 6 | all | Remove v2 `cache/appearance/<hash>` pointer family, old `.seed.lock`/appearance lock usage, per-app `appearance.css` convenience links, and any migration aliases after the compatibility window | Doctor reports zero legacy pointers; no consumer reads a removed path |

The v3 runtime should be able to read a v2 generation during wave 1 (compat
window) but must never write the multi-pointer family again. The cutover ticket
is the only place that changes pins/tags.

## 4. Acceptance tests

All tests are generation-level and fail closed.

| Id | Test | Setup | Expected |
| --- | --- | --- | --- |
| A-1 | Concurrent convergence | N CLI calls plus an active daemon, same and different intents | exactly one commit per intent; readers never see mixed palette/appearance/icons; queue coalesces identical intents; final `current` is the last completed intent |
| A-2 | Crash injection | kill after stage, after generation rename, during `current` rename, after `current` rename before ledger, during apply | old or new complete generation only; no partial manifest; staging cleaned by grace; ledger mismatch triggers refresh, never a rollback |
| A-3 | Stale ack | app answers `{"applied":"<oldGen>"}` or `{"ok":true}` | runtime does not record applied; app retried on next trigger; restart lane restarts only per policy; mismatch is observable in the ledger |
| A-4 | Immutable tags | run wallpaper/skin/mode changes and all lanes | `apps/<tag>` file list, mtimes and bytes unchanged; verify fails if a runtime artifact is planted in a tag |
| A-5 | Mode change with apps open | all seven apps open; set `desired.json mode=light`; trigger converge | live apps repaint without restart; bar restarts once; `current/manifest.json.intent.mode == light`; `current/palette/colors.yaml` is light; no `wallpaper set` required |
| A-6 | Multi-pointer skew impossible | reader samples `current` while commits run | each sample resolves one `genHash`; palette/appearance/icons all from that generation; no cross-generation pair |
| A-7 | Daemon fallback | stop the daemon; run the same CLI converge | same function under `converge.lock`; rc=0 only with a committed generation; concurrent CLI calls serialize; no second pipeline |
| A-8 | Event-driven readiness | fake watches/events; AGS name and systemd job events | success is declared only after the event; no `sleep`/`ags list` poll in correctness paths; a timeout never counts as success |
| A-9 | GC safety | retain/active/pinned/grace combinations; slow reader | active/pinned/referenced generations stay; only unreferenced entries older than grace are removed; reader gets a retryable error, never a torn read |
| A-10 | Restart lane split | bar (restart + unit) and notifications (live + unit) | bar restarted via systemd; notifications live handler applied with the same `genHash`; a live failure never becomes a restart |

## 5. Evidence index

Commands used for the code references (read-only; run from the workspace):

```sh
cd ../dotfiles-runtime
sed -n '660,807p' src/runtime/adapters/seeder.py
sed -n '308,326p;358,430p' src/runtime/application/reconcile.py
sed -n '140,173p' src/runtime/adapters/invalidation.py
sed -n '88,97p' src/runtime/application/regenerate.py
sed -n '649,737p;2096,2240p;2533,2541p;3336,3453p' src/runtime/cli/main.py
sed -n '58,94p' src/runtime/adapters/appearance_ledger.py
sed -n '86,96p;572,588p;757,770p;772,828p' src/runtime/adapters/ags_reloader.py

cd ../contracts
sed -n '64,78p' ags-app-refresh.md

cd ../ags-platform
sed -n '110,125p' ports/palette-refresh.ts
sed -n '58,90p' ports/appearance-refresh.ts
sed -n '878,918p;967,974p' ports/appearance.ts
sed -n '57,74p' adapters/appearance-scope.ts
sed -n '56,67p' adapters/appearance.ts

cd ../dotfiles-provision
sed -n '150,162p' ansible/roles/ags_apps_units/tasks/_one.yml

cd ../ags-notifications
sed -n '1,7p' app.manifest.json
sed -n '53,70p' app.tsx

cd ../ags-bar
sed -n '1,7p' app.manifest.json
```

Live observations (2026-11-06):

```sh
ls -l ~/.local/state/dotfiles/current
ls -l ~/.local/share/dotfiles/apps/notifications/v0.4.0/appearance.css
readlink -f ~/.local/share/dotfiles/config/ags-notifications
```

## 6. Risks and tradeoffs

| Id | Risk / tradeoff | Why it matters | Handling |
| --- | --- | --- | --- |
| R-1 | **Daemon availability.** The default serializer is a daemon; if it hangs, the CLI must not run a concurrent fallback. | Two executors can create two commits. | D-Bus name ownership is the source of truth; subscribe before submit; fallback only after a confirmed no-owner preflight; the shared flock is the last line; a hung daemon is stopped by systemd, not bypassed. |
| R-2 | **Job-queue semantics are new.** The current hub has client-owned progress jobs, not a daemon converge queue. | A wrong completion signal can report success before commit. | Add a typed converge job with `generationHash` in `JobFinished`; subscribe-before-submit; idempotent intent hash; queue coalescing tests. |
| R-3 | **Long lock scope.** Derivation is now inside the one lock. | A slow producer/effects run blocks other mutations. | Accept for correctness; report progress via `JobProgress`; separate read-only inspection remains lock-free; use a producer timeout that aborts, not a publish-and-retry. |
| R-4 | **GC vs slow readers.** Pruning a generation while an app still reads it. | A path-based reader can see a dangling path. | Keep active/newest/pinned/ledger-referenced + grace; prune under the lock; readers prefer `generations/<genHash>` and treat missing as retryable; POSIX open-file behavior covers already-open readers. |
| R-5 | **Compatibility links.** Provisioning-created stable links and in-generation aliases can drift or be user-edited. | Non-runtime consumers can read a stale path if a link is wrong. | Verify resolves every stable link through `current`; links are provisioning-owned and never repointed by runtime; remove aliases after the compatibility window. |
| R-6 | **Event loss/overflow.** inotify or D-Bus signals can be missed. | A missed commit/registration event stalls convergence. | Watch overflow triggers one full rescan; generation/hash comparison makes rescan idempotent; subscribe-before-read for event sources; never use sleep as a substitute. |
| R-7 | **Generation size and disk.** Each appearance sheet is a real file; generations accumulate. | Wallpaper/effects/icon data is reused, but appearance sheets grow with apps. | Content-addressed layers; keep-N; compress only if measured; GC is part of converge, not an unbounded background job. |
| R-8 | **Mode `smart`.** The producer projects the final mode; an unstable projection loops. | Mode is in `genHash`, so oscillation creates generations. | Record the winning mode in the manifest; one intent snapshot per converge; doctor compares `manifest.intent.mode` to the palette mode and reports divergence. |
| R-9 | **App-side read policy.** Reading through `current` after a manifest check is TOCTOU. | A commit can land between check and read. | Mandate direct `generations/<genHash>/...` reads, or re-verify after read and retry; the direct read is the compatibility path for apps that cannot hold a directory fd. |
| R-10 | **Restart-lane truth.** A restart can succeed while the generation moved. | The app may start on a newer generation than the ledger requested. | Ledger records the generation at restart; if `current` moved, downgrade to deferred and refresh again; never record `applied` for a generation that was not verified. |
| R-11 | **Migration window.** v2 readers and v3 generation paths coexist for one release. | A consumer can read a v2 pointer as if it were a v3 manifest. | Version the manifest (`schemaVersion: 3`); v3 consumers reject v2; v2 consumers keep their frozen behavior; no dual writes after the wave-1 release. |
| R-12 | **No rollback by design.** A committed generation with a failed apply is not rolled back. | The pointer is authoritative and apps catch up eventually. | Surface `degraded` in the CLI result and ledger; retry on the next trigger; the operator can commit the previous generation by re-running converge with the old intent, not by a hidden reverse pointer. |

## 7. Scope of this ticket

- Documentation only. No runtime, platform, provisioning or app code is
  changed here, and no pin/tag is moved.
- v2 remains the live plane. The v3 cutover is a later composition ticket that
  consumes the wave releases.
- The acceptance tests in §4 are the contract for that cutover; they are not
  claimed as executed by this RFC.

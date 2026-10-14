# one-event-client

## Why

Spine **AD-5** fixes **one event client** for every event consumer: the moved
`DomainEventBusCore` plus an injected `EventBusTransport`, where
**subscribe-before-read hydration + `(epoch, seq)` dedup lives**, `control(jobId,
action)` is first-class, and the **restart/hydration contract is mandatory** —
every consumer resets on `JobsCleared(epoch)` and treats a `(0, 0)` hydration as
"no state yet". Spine **AD-4** corrects the port surface: `EventSource.subscribe`
**returns an unsubscribe handle** (today it returns `void`), and
`EventHub.select<T>(topic): Accessor<M[T] | null>` is kept (new machinery; no
current implementation). Doc 101 §4.2 defines the port; §13 step 4 ("Hub consumer
+ job control") is this step.

Today the pure state machine lives at `dotfiles/config/ags/lib/event-bus-core.ts`
and is **copy-pasted** into the app trees, so the one client does not exist yet:

- Four `DomainEventBusCore` copies:
  `dotfiles/config/ags/lib/event-bus-core.ts` plus
  `src/gui-tools/{hypr-pano,icon-color-mapping-editor,wallpaper-selector}/lib/event-bus-core.ts`.
- The bar's copy exposes no `EventSource`/`EventHub` port and `subscribe`
  returns `void`; there is no `select`.

Evidence:
`ls dotfiles/config/ags/lib/event-bus-core.ts src/gui-tools/*/lib/event-bus-core.ts`
→ 4 files;
`grep -n "subscribe(topic: string, handler: TopicHandler): void\|onRestart(handler: RestartHandler): void" dotfiles/config/ags/lib/event-bus-core.ts`
→ `subscribe(...): void`, `onRestart(...): void`;
`grep -rn "EventHub\|EventSource" dotfiles/config/ags --include=*.ts --include=*.tsx | grep -v node_modules`
→ no matches.

Verify:
`ls dotfiles/config/ags/lib/event-bus-core.ts src/gui-tools/*/lib/event-bus-core.ts`;
`grep -n "subscribe(topic: string, handler: TopicHandler): void" dotfiles/config/ags/lib/event-bus-core.ts`;
`grep -rn "EventHub\|EventSource" dotfiles/config/ags --include=*.ts --include=*.tsx | grep -v node_modules`.

## What Changes

### Move the state machine into a platform seam with an injected transport (AD-5)

- New `dotfiles/config/ags/platform/event-client.ts`: the pure
  `DomainEventBusCore` state machine (subscribe-before-read hydration,
  `(epoch, seq)` dedup, `JobsCleared(epoch)` reset, `(0, 0)` = "no state yet"),
  the contract literals, and the `EventBusTransport` seam — **no `gi://`, no
  `ags`**. `lib/event-bus-core.ts` is **deleted** (moved, not copied).
- `EventSource`/`EventHub` are exposed exactly as corrected: `subscribe(...)`
  and `onRestart(...)` **return unsubscribe handles**; `EventHub` adds
  `select<T>(topic): ReadAccessor<M[T] | null>` (built on an **injected**
  reactive runtime, reusing the one reactive vocabulary in
  `domains/reactive.ts`) and first-class `control(jobId, action)`.

### The bar consumes the single client, with no behaviour change

- `lib/event-bus.ts` keeps the Gio transport (`GioEventBusTransport`) but imports
  the state machine from `../platform/event-client` and constructs the one
  `domainEvents` client with the injected `agsRuntime`.
- `bar/widgets/recording.tsx` is **not migrated to `select`**; it keeps
  `subscribe`/`onRestart`/`control`, so the rendered indicator is byte-for-byte
  the same behaviour.

### Tests prove the mandatory contract (pure, no GTK)

- New `tests/ts/event-client.test.ts` drives the seam with a scripted fake
  transport: subscribe-before-read hydration order, `(epoch, seq)` dedup
  (equal/lower dropped, epoch bump wins), **unsubscribe**, and a restart reset
  (emit `JobsCleared`, assert the `select` accessor resets to `null` and the
  topic re-hydrates).
- The executed contract gate
  (`src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`) is
  repointed at the new module path so the bar's literals stay pinned to
  `contracts/event-contract.{json,xml}`.

### One registered source (deploy manifest)

- `platform/event-client.ts` is registered in
  `compositor_configs_skeleton_files` and mirrored in the verify role, and
  `lib/event-bus-core.ts` is dropped from both, so a fresh provision deploys the
  seam and `make deploy-coverage` stays green.

## Out of scope

- **No app-local copy migration.** The three `src/gui-tools/**` copies stay
  (the `ags-apps` epic owns them, AD-20 step 8). They keep their own
  `DomainEventBusCore`; this change does not touch them.
- **No consumer migration to `select`.** `recording.tsx` keeps `subscribe`; the
  reactive `select` surface is exposed and tested but no bar widget is rewritten
  onto it (that is AD-8/§13 step 4's shape work, not this step).
- **No `NoEventSource` baseline.** AD-18's inert baseline adapter is the
  platform-extraction/baseline step, not this one.
- **No contract codegen (AD-6).** The literals remain hand-pinned by the
  executed drift gate; generating them is the contracts step.
- **No platform package extraction (AD-17/AD-20).** The seam lands in-place
  under `dotfiles/config/ags/platform/`; the versioned unit + `node_modules`
  shortcut is a later step.
- **No runtime/Python change.** `runtime/adapters/bar_subscriber.py` is the
  runtime's own consumer; it is not the bar's client.

## Impact

- New: `dotfiles/config/ags/platform/event-client.ts`,
  `dotfiles/config/ags/tests/ts/event-client.test.ts`.
- Deleted: `dotfiles/config/ags/lib/event-bus-core.ts` (moved).
- Edited: `dotfiles/config/ags/lib/event-bus.ts`,
  `dotfiles/config/ags/tests/tsconfig.tests.json`,
  `src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`,
  `src/provisioning/ansible/roles/compositor_configs/vars/main.yml`,
  `src/provisioning/ansible/roles/verify/vars/main.yml`,
  `src/provisioning/tests/unit/test_compositor_configs_role.py`,
  `src/provisioning/tests/unit/test_verify_role.py`.
- No behaviour change on a provisioned host: the bar's one client is the same
  state machine it runs today.

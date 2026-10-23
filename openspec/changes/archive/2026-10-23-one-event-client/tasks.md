# Tasks

## 1. Plan (commit 1)

- [x] 1.1 Author the change: `proposal.md`, this `tasks.md`, and
  `specs/ags-event-client/spec.md` with ADDED Requirements + Scenarios citing
  AD-4/AD-5 and doc 101 §4.2/§13 step 4.
  Verify: `openspec validate one-event-client --type change` → valid.
  - `openspec validate one-event-client --type change` →
    `Change 'one-event-client' is valid`.

## 2. The platform seam (AD-5, AD-4)

- [x] 2.1 Move the pure state machine to `platform/event-client.ts`: contract
  literals, `asUint`/`isNewer`/`parseTopicState`, the injected
  `EventBusTransport`, and `DomainEventBusCore` with subscribe-before-read
  hydration, `(epoch, seq)` dedup, `JobsCleared(epoch)` reset, and `(0, 0)` =
  "no state yet". No `gi://`, no `ags`.
  Verify: `grep -nE "^import .*(gi://|\"ags\")" dotfiles/config/ags/platform/event-client.ts` → no matches.
  - `grep -nE "^import .*(gi://|\"ags\")" dotfiles/config/ags/platform/event-client.ts`
    → no matches (exit 1). The only import is `import type { ReadAccessor,
    ReactiveRuntime } from "../domains/reactive"` (type-only, pure).
- [x] 2.2 Expose `EventSource` (subscribe/onRestart return unsubscribe handles)
  and `EventHub` (`select<T>(topic): ReadAccessor<M[T] | null>` built on an
  injected reactive runtime; first-class `control(jobId, action)`).
  Verify: `grep -n "subscribe(topic: string, handler: TopicHandler): () => void\|select<T extends keyof EventMap>\|interface EventHub" dotfiles/config/ags/platform/event-client.ts`.
  - `72:export interface EventSource {`, `73:  subscribe(topic: string, handler:
    TopicHandler): () => void;`, `80:export interface EventHub<M extends
    EventMap> {`, `81:  select<T extends keyof M>(topic: T):
    ReadAccessor<M[T] | null>;`, `153:  subscribe(...): () => void`,
    `168:  select<T extends keyof M>(...)`. `onRestart` returns a handle too
    (`platform/event-client.ts:191`).
- [x] 2.3 Delete the moved `lib/event-bus-core.ts`.
  Verify: `test ! -e dotfiles/config/ags/lib/event-bus-core.ts` → exit 0.
  - `test ! -e dotfiles/config/ags/lib/event-bus-core.ts` → exit 0 (the file was
    `git rm`'d; the state machine now lives only in `platform/event-client.ts`).

## 3. The bar consumes the single client (no behaviour change)

- [x] 3.1 Repoint `lib/event-bus.ts` at `../platform/event-client` and construct
  the one `domainEvents` client with the injected `agsRuntime`.
  Verify: `grep -n "platform/event-client\|agsRuntime" dotfiles/config/ags/lib/event-bus.ts`.
  - `18:import { agsRuntime } from "../domains/astal";`,
    `35:} from "../platform/event-client";`,
    `131:export const domainEvents = new DomainEventBusCore(new
    GioEventBusTransport(), agsRuntime);`.
- [x] 3.2 Keep `bar/widgets/recording.tsx` on `subscribe`/`onRestart`/`control`
  (no `select` migration) so the rendered indicator is unchanged.
  Verify: `grep -n "domainEvents.subscribe\|domainEvents.onRestart\|domainEvents.control" dotfiles/config/ags/bar/widgets/recording.tsx`.
  - `98:  domainEvents.subscribe("capture.state", (_topic, payload) => {`,
    `112:  domainEvents.onRestart(reset)`,
    `123:    if (jobId !== null) domainEvents.control(jobId, action)`. The file is
    byte-identical to before.

## 4. Tests prove the mandatory contract (pure, no GTK)

- [x] 4.1 Add `tests/ts/event-client.test.ts` with a scripted fake transport:
  subscribe-before-read hydration order; `(epoch, seq)` dedup (equal/lower
  dropped, epoch bump wins); unsubscribe; and a restart reset (`JobsCleared`
  resets the `select` accessor to `null` and re-hydrates).
  Verify: `make ags-test` → `fail 0` and the new suite passes.
  - `node --import ./dotfiles/config/ags/tests/ts/resolve-hooks.mjs --test
    dotfiles/config/ags/tests/ts/event-client.test.ts` → `tests 11, pass 11,
    fail 0`; the restart test asserts the accessor is `null` DURING the restart
    and `idle` after re-hydration. `make ags-test` → `tests 108, suites 14,
    pass 108, fail 0`.
- [x] 4.2 Register `../platform/event-client.ts` in
  `tests/tsconfig.tests.json`'s explicit purity list.
  Verify: `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
  - `make ags-test` → `OK: 0 type errors in the ags pure-module unit tests`.
- [x] 4.3 Repoint the executed contract gate
  (`src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`) at
  the new module path.
  Verify: `node src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs` → `event-contract drift + bar hydration agree`.
  - `node src/gui-tools/icon-color-mapping-editor/tests/event-contract-drift.mjs`
    → `event-contract drift + bar hydration agree` (all `ok`, no failures).

## 5. Deploy registration (hard constraint)

- [x] 5.1 Register `platform/event-client.ts` in
  `compositor_configs_skeleton_files` and drop the moved `lib/event-bus-core.ts`;
  mirror both in the verify role.
  Verify: `make deploy-coverage` → `PASS`.
  - `make deploy-coverage` → `reachable AGS modules from
    dotfiles/config/ags/app.tsx: 78`, `deployed AGS sources in the manifest: 91`,
    `PASS`. The `ags/platform` dest dir was also added to
    `compositor_configs_config_dirs` (the playbook test caught that `template`
    does not create dest parents).
- [x] 5.2 Update the two provisioning structural tests that pin the skeleton
  list (`test_compositor_configs_role.py`, `test_verify_role.py`), including the
  `_build_provisioned_layout` fixture that writes the simulated install.
  Verify: `uv run --directory src/provisioning pytest tests/unit/test_compositor_configs_role.py tests/unit/test_verify_role.py` → pass.
  - `... test_compositor_configs_role.py -k "playbook_executes or playbook_leaves
    or skeleton_files_templated"` → `3 passed`; the same file minus those two slow
    playbook tests → `25 passed, 2 deselected`.
  - `... test_verify_role.py -q` → `72 passed`. The runtime criterion-7 test
    caught that `_build_provisioned_layout` still wrote
    `ags/lib/event-bus-core.ts`; the fixture now writes
    `ags/platform/event-client.ts` (the simulated machine matches the mirror).

## 6. Verify

- [x] 6.1 All gates green: `make ags-test` (fail 0, 0 type errors),
  `make ags-typecheck` (PASS), `make bar-typecheck` (OK), `make gates-ci`
  (exit 0), `make deploy-coverage` (PASS).
  - `make ags-test` → `tests 108, pass 108, fail 0`, `0 type errors`.
  - `make ags-typecheck` → `PASS (with GIR typings, 0 errors in the extracted
    bar tree …, 29 third-party, 34 in tests/, 0 exempt)`.
  - `make bar-typecheck` → `OK: 0 errors in dotfiles/config/ags`.
  - `make gates-ci` → `EXIT=0`.
  - `make deploy-coverage` → `PASS`.
- [x] 6.2 The change validates and the tree is clean.
  Verify: `openspec validate one-event-client --type change` → valid;
  `git status --porcelain` → empty after the implementation commit.
  - `openspec validate one-event-client --type change` → valid;
    `git status --porcelain` → empty after the implementation commit.

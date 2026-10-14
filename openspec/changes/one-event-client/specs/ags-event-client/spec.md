# ags-event-client (delta)

## ADDED Requirements

### Requirement: One event client, one state machine

There SHALL be exactly one domain-event client implementation in the bar tree:
the moved `DomainEventBusCore` in `platform/event-client.ts`. It SHALL hold the
subscribe-before-read hydration state machine, the `(epoch, seq)` dedup, and the
contract literals, and SHALL take its bus access through an **injected**
`EventBusTransport`. No bar consumer SHALL re-implement the state machine.

Source: spine **AD-5**; doc 101 §4.2.

#### Scenario: the transport is injected, not a global

- **WHEN** the client is constructed with a scripted fake transport
- **THEN** it reads topic state and sends control actions through that fake and
  never opens a bus of its own

#### Scenario: the module is pure

- **WHEN** the platform seam is imported by the pure test project
- **THEN** no module reachable from it imports `gi://*` or `ags`

### Requirement: `EventSource.subscribe` returns an unsubscribe handle

`subscribe(topic, handler)` SHALL return a handle that removes exactly that
handler, and `onRestart(handler)` SHALL likewise return a handle that removes
that restart handler. Calling the handle twice SHALL be a no-op.

Source: spine **AD-4** (port correction); doc 101 §4.2.

#### Scenario: unsubscribing stops delivery

- **WHEN** a handler is subscribed and then its returned handle is called
- **THEN** a subsequent domain event on that topic is not delivered to it

#### Scenario: the topic baseline survives unsubscription

- **WHEN** the last handler for a topic unsubscribes and a newer event arrives
- **THEN** the client does not crash and a later subscriber starts from the
  current `(epoch, seq)` baseline

### Requirement: `EventHub.select` returns a reactive accessor

The client SHALL expose `EventHub.select<T>(topic): ReadAccessor<M[T] | null>`,
built on an **injected** reactive runtime, and first-class
`control(jobId, action)`. Before any state is known the accessor SHALL read
`null`.

Source: spine **AD-4**; doc 101 §4.2.

#### Scenario: the accessor reflects the latest payload

- **WHEN** a topic is selected and a domain event for it is dispatched
- **THEN** the accessor returns that event's payload

#### Scenario: no state yet reads null

- **WHEN** a topic is selected and the transport hydrates `(0, 0)` with no
  payload
- **THEN** the accessor returns `null` (there is no state yet)

### Requirement: The restart/hydration contract is mandatory

Every consumer SHALL reset on `JobsCleared(epoch)`: the client SHALL clear the
per-topic `(epoch, seq)` baselines, reset every selected accessor to `null`, run
the restart handlers, and then re-hydrate every tracked topic. A replayed
`JobsCleared` at or below the last epoch SHALL be ignored, and a `(0, 0)`
hydration SHALL mean "no state yet" rather than an empty payload.

Source: spine **AD-5** (mandatory restart contract); doc 101 §4.2.

#### Scenario: `JobsCleared` resets then re-hydrates

- **WHEN** the hub emits `JobsCleared(newEpoch)` after a topic held state
- **THEN** the selected accessor resets to `null`, the restart handlers run, and
  the topic re-hydrates to its current payload under the new epoch

#### Scenario: a replayed restart is ignored

- **WHEN** `JobsCleared` arrives with an epoch at or below the last epoch seen
- **THEN** no reset runs and no accessor is cleared

#### Scenario: `(0, 0)` hydration is not delivered as state

- **WHEN** hydration returns `_epoch = 0`, `_seq = 0`, and no payload members
- **THEN** nothing is delivered and the topic's baseline is `(0, 0)`

### Requirement: Dedup compares `(epoch, seq)`, never `seq` alone

The client SHALL accept a domain event only when its `(epoch, seq)` is greater
than the hydrated baseline lexicographically, so an epoch bump wins even when
`seq` resets, and an at-or-below pair is dropped as stale/replayed.

Source: spine **AD-5**; contract `delivery`.

#### Scenario: an epoch bump wins over a lower seq

- **WHEN** the baseline is `(4, 9)` and an event with `(5, 1)` arrives
- **THEN** it is delivered and the baseline advances to `(5, 1)`

#### Scenario: an equal pair is stale

- **WHEN** an event repeats the hydrated `(epoch, seq)`
- **THEN** it is dropped

### Requirement: The bar consumes the one client with no behaviour change

The bar's `domainEvents` SHALL be the single client from the platform seam. The
recording indicator SHALL keep using `subscribe`/`onRestart`/`control`, so the
rendered indicator is unchanged.

Source: spine **AD-5**; doc 101 §13 step 4.

#### Scenario: the recording indicator is unchanged

- **WHEN** `bar/widgets/recording.tsx` is compared before and after
- **THEN** it still subscribes to `capture.state`, resets on restart, and sends
  control actions through the hub

### Requirement: A new bar source is registered for deployment

`platform/event-client.ts` SHALL be registered in
`compositor_configs_skeleton_files` and mirrored in the verify role, so a fresh
provision deploys it; the moved `lib/event-bus-core.ts` SHALL be dropped from
both.

Source: spine **AD-17** (per-file placement); `deploy-coverage` gate.

#### Scenario: deploy coverage is green

- **WHEN** `make deploy-coverage` runs
- **THEN** every AGS module reachable from `app.tsx` is registered, including
  the new platform seam

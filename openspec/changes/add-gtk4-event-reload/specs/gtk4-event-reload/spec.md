## ADDED Requirements

### Requirement: `wallpaper.state` carries an additive `trigger` discriminator

The `wallpaper.state` topic payload SHALL include a `trigger` string field
(`set` | `regenerate` | `reconcile` | `reactive`) identifying which
palette-affecting operation produced the transition. The field SHALL be
optional in the contract schema so existing publishers and consumers remain
valid, and it SHALL stay on `org.dotfiles.Events1` (additive, non-breaking).
The publisher SHALL emit `done`/`error` with `trigger` from **all** paths that
can change the active palette: `wallpaper set`, standalone `reconcile`, and the
daemon reactive converge. `icons regenerate` SHALL publish
`trigger="regenerate"`.

#### Scenario: wallpaper set publishes trigger=set

- **GIVEN** a hub is serving `org.dotfiles.Events1`
- **WHEN** `dotfiles-runtime wallpaper set <img>` completes
- **THEN** the `wallpaper.state done` payload contains `trigger="set"`
- **AND** a consumer that ignores `trigger` still accepts the payload (schema
  `additionalProperties` unchanged, no required-field addition)

#### Scenario: reconcile and reactive converge are not silent

- **GIVEN** a palette-affecting standalone `reconcile` (or daemon reactive
  converge) completes
- **WHEN** the transition is published
- **THEN** a `wallpaper.state done` with the matching `trigger` is delivered
- **AND** subscribers therefore see every palette change, not only `set`

#### Scenario: contract drift tests stay pinned

- **GIVEN** the updated contract files
- **WHEN** the runtime embedded-schema tests and both GJS
  `event-contract-drift` tests run
- **THEN** they pass with `trigger` present and still pass when it is absent

### Requirement: GTK4 app restarts are driven by a hub consumer binding

A new consumer binding (`gtk4_app_subscriber`) SHALL implement the same
protocol as `BarSubscriber`: register match rules before reading
`GetTopicState` (subscribe-before-read hydration), discard any `DomainEvent`
whose `(epoch, seq)` is not greater than the hydrated baseline, re-hydrate on
`JobsCleared`/`NameOwnerChanged` without replaying stale events, and
structurally validate payloads (size and depth) before dispatch. It SHALL read
contract constants from `contracts/event-contract.json` at import time and SHALL
NOT import `runtime.domain`/`runtime.ports`.

#### Scenario: subscribe-before-read prevents a lost race

- **GIVEN** the subscriber starts while a `wallpaper.state` event is in flight
- **WHEN** it registers match rules and then reads topic state
- **THEN** the racing event is either delivered after the rule was installed or
  superseded by the hydrated `(epoch, seq)` baseline
- **AND** no event is dispatched twice

#### Scenario: hub restart re-hydrates

- **GIVEN** the subscriber is hydrated at epoch N
- **WHEN** the hub restarts (`JobsCleared(epoch N+1)`)
- **THEN** the subscriber re-hydrates the baseline and resumes dispatch
- **AND** does not replay pre-restart events

### Requirement: Restarts fire only for palette-affecting done transitions

On `wallpaper.state done`, the subscriber SHALL restart the allowlisted GTK4
apps only when `trigger` is `set`, `reconcile`, or `reactive`. When `trigger`
is `regenerate` (icons-only), the subscriber SHALL skip the restart and log
the decision; `applying`, `visible`, and `error` transitions SHALL never
trigger a restart.

#### Scenario: contrast toggle does not restart apps

- **GIVEN** `power-options-gtk` and `hyprmod` are running
- **WHEN** the user presses the contrast toggle (`icons regenerate`,
  `trigger="regenerate"`)
- **THEN** neither app is killed or relaunched
- **AND** the skip is logged with the topic and trigger

#### Scenario: wallpaper change restarts apps

- **GIVEN** `power-options-gtk` and `hyprmod` are running
- **WHEN** a `wallpaper set` publishes `done` with `trigger="set"`
- **THEN** both are restarted and their new instances read the repointed
  `~/.config/gtk-4.0/colors.css`

### Requirement: Restart primitive is race-free and safety-bounded

The restart primitive SHALL target only the explicit allowlist
(`power-options-gtk`, `hyprmod`) and never wildcard-discover arbitrary GTK4
apps. For each target it SHALL send SIGTERM (graceful, equivalent to the user
closing the window), wait until the old pid is gone (bounded poll), escalate to
SIGKILL on timeout, wait again, and only then relaunch with the original argv
detached. A restart that cannot be confirmed live after relaunch SHALL be
reported as a failure. No target running SHALL be a vacuous success. The
per-target state-safety rationale SHALL be recorded in the module docstring,
and the `skip_apps` opt-out SHALL remain honored.

#### Scenario: relaunch waits for the old single-instance owner

- **GIVEN** a running single-instance `GApplication` target
- **WHEN** the restart primitive runs
- **THEN** it does not spawn the replacement until the old pid has exited
  (or has been SIGKILLed and reaped)
- **AND** the replacement does not forward activation to the dying old instance

#### Scenario: allowlist and skip list are respected

- **GIVEN** an arbitrary GTK4 app (not allowlisted) is running
- **WHEN** a palette-affecting `done` fires
- **THEN** that app is never discovered or restarted
- **AND** an allowlisted app present in `skip_apps` is left running

#### Scenario: no targets is a no-op

- **GIVEN** neither target is running
- **WHEN** a palette-affecting `done` fires
- **THEN** the subscriber completes with success and no process is spawned

### Requirement: The daemon hosts the subscriber; degraded mode has an escape hatch

The subscriber SHALL run inside `dotfiles-runtime daemon run` (the always-on
service that owns the hub) as a background consumer with its own bus
connection; no new process, systemd unit, or provisioning role SHALL be added.
When the daemon/hub is absent, automatic restart SHALL not occur and this SHALL
be documented. A `dotfiles-runtime gtk4 restart` command SHALL expose the same
restart primitive for manual/degraded use and SHALL exit non-zero on any
restart failure.

#### Scenario: daemon hosts a live consumer

- **GIVEN** `dotfiles-runtime daemon run` is active
- **WHEN** a `wallpaper set` publishes `done` with `trigger="set"`
- **THEN** the daemon-hosted subscriber restarts the running allowlisted apps
- **AND** stopping the daemon stops the automatic behavior

#### Scenario: manual escape hatch works without a hub

- **GIVEN** the daemon is stopped and the apps are running
- **WHEN** the user runs `dotfiles-runtime gtk4 restart`
- **THEN** the allowlisted apps are restarted via the same primitive
- **AND** a restart failure yields a non-zero exit

### Requirement: The inline GTK4 reloader leaves the swap reload chain

`_build_reloaders` SHALL NOT include `Gtk4AppReloader`; the pinned synchronous
consumer order remains Hyprland, AGS, Hyprpaper, terminal, kitty.
`wallpaper.state done` SHALL mean the synchronous reload chain completed;
event-driven consumers (the GTK4 restart subscriber, and ICME's live refresh)
act on `done` afterwards. This clarifies — and supersedes in the GTK4 case — the
`wallpaper-set-visible-first` statement that `done` implies all consumers have
reloaded.

#### Scenario: chain no longer restarts GTK4 apps

- **GIVEN** a `wallpaper set` with the daemon stopped
- **WHEN** the synchronous reload chain runs
- **THEN** no GTK4 app is killed by the chain
- **AND** `reload_failures` never names `Gtk4AppReloader`
- **AND** with the daemon running the apps are restarted by the subscriber,
  after `done`

#### Scenario: composition tests pin the new list

- **GIVEN** the updated `_build_reloaders`
- **WHEN** the CLI composition tests run
- **THEN** they assert Hyprland/AGS/Hyprpaper/terminal/kitty presence and
  `Gtk4AppReloader` absence in the injected reloader list

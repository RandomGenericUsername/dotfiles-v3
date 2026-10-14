# ags-domain-read-models (delta)

## ADDED Requirements

### Requirement: A domain read model is an injectable adapter returning a reactive accessor

Each domain read model SHALL be a factory that takes its runtime dependency (the
Astal service or the domain's source) as a parameter and returns a reactive
`ReadAccessor` of a plain reading. The factory SHALL NOT read a module-scope
service singleton.

Source: spine **AD-2**; doc 101 §13 step 2.

#### Scenario: the injected service drives the reading

- **WHEN** a read model is constructed with a fake service
- **THEN** its accessor returns the snapshot of that service, not of any global

#### Scenario: a service change republishes

- **WHEN** the injected service reports a property change
- **THEN** the accessor returns a reading that reflects the new property value

### Requirement: Domain services are closed over at registration, never carried in `BarContext`

The Astal binding of a read model SHALL close over the injected service and the
injected reactive runtime when it is constructed. The read models SHALL NOT be
added to `BarContext`, and a widget SHALL NOT construct a service it does not
own.

Source: spine **AD-2**.

#### Scenario: the adapter closes over the Astal service

- **WHEN** the Astal adapter factory is called with no argument
- **THEN** it binds the default Astal service and the AGS runtime, and returns a
  read model with no reference to `BarContext`

#### Scenario: the reactive primitive is a port

- **WHEN** the read models are imported by the pure test project
- **THEN** no module reachable from a pure read model imports `ags` or `gi://*`,
  because the reactive primitive arrives as a parameter

### Requirement: The read model publishes an inert reading; the state key is the boundary

A read model SHALL publish a plain, inert reading (numbers, strings, booleans,
and plain objects) and SHALL NOT publish Astal/GObject objects. Code SHALL derive
the icon/behaviour state key from the reading through a pure mapping, so meaning
stays in code and looks stay in data.

Source: spine **AD-3**; doc 101 §12.

#### Scenario: the reading carries no runtime objects

- **WHEN** a reading is inspected
- **THEN** it contains only plain data, so a pure state-key function can consume
  it without the desktop stack

### Requirement: The audio read model consumes the existing hexagon, not a rewrite

The audio read model SHALL project the existing audio hexagon's view model
(`audio/presentation/bar-indicators`) rather than re-deriving audio policy, and
the hexagon's domain/ports/adapters SHALL be left intact.

Source: spine **AD-2**, **AD-3**; doc 101 §13 step 2.

#### Scenario: the audio reading is the bar-indicator projection

- **WHEN** the audio read model is constructed over a source returning an
  `AudioPanelViewModel`
- **THEN** its accessor returns the same `projectBarIndicators` result the bar
  renders today

### Requirement: A read model is testable without the desktop stack

The pure core of each read model SHALL be exercisable by `make ags-test` with a
fake device and a fake reactive runtime, with no live Astal and no `ags` import
on the path.

Source: spine **AD-2**; doc 101 §13 step 2.

#### Scenario: a fake device proves reactivity

- **WHEN** the read-model unit tests run under `node --test`
- **THEN** each of network, battery, bluetooth, and audio publishes an initial
  reading and republishes after its fake device changes

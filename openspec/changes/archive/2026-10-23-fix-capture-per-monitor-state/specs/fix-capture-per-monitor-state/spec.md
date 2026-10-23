## ADDED Requirements

### Requirement: The live UI state SHALL have exactly one owner for the whole application

The screenshot and recording selection state SHALL be created ONCE by the composition
root and injected into every `ClassicWindow` it constructs. `ClassicWindow` SHALL NOT
allocate state of its own, and the state parameter SHALL be required.

Rationale: `capture-ui.json`, the settings config and the
last-used > settings > constants precedence chain are all per-application, while
`app.tsx` builds one window per monitor. A window that allocated its own copy would be a
second owner of one value; `save()` serialises the whole object, so whichever window
saved last would overwrite the other's fresher fields with stale ones. Reproduced
headlessly against the real `glibUiStateStore`: a selection saved from one monitor's
window was destroyed by the other monitor's window, and the persisted value flapped
depending on which window the capture was pressed in.

#### Scenario: Every window constructed by the composition root shares one state

- **WHEN** `app.tsx` iterates `app.get_monitors()` and constructs one window per monitor
- **THEN** every window receives the SAME state object, created once before the loop, and
  a mutation made through any window is observable through every other

#### Scenario: A window cannot come into existence without being told which state it mutates

- **WHEN** `ClassicWindow` is called
- **THEN** the state is a required parameter with no default, so no call site can
  silently fall back to allocating a private copy

#### Scenario: A window never allocates the state itself

- **WHEN** `ui/classic/ClassicWindow.tsx` is inspected
- **THEN** it contains no `screenshot`/`recording` object literal built from
  `DEFAULT_SCREENSHOT`/`DEFAULT_RECORDING`; the objects it mutates are the ones it was
  handed

### Requirement: The shared state SHALL be seeded by a pure factory, not a hidden singleton

`domain/ui-state.ts` SHALL export `createUiState(): UiState`, returning fresh copies of
the first-run constants. It SHALL NOT memoise: sharing is the composition root's
decision, made once and visible at the call site.

Rationale: if the factory returned the `DEFAULT_*` constants themselves, the first
window's mutations would become the defaults every later window starts from. If it were
a module-level singleton, every window would share by accident — invisible at the call
site, and impossible for a test to give its own state.

#### Scenario: Mutating a state cannot corrupt the first-run defaults

- **WHEN** a state from `createUiState()` is mutated
- **THEN** `DEFAULT_SCREENSHOT` and `DEFAULT_RECORDING` are unchanged

#### Scenario: Two calls yield two independent states

- **WHEN** `createUiState()` is called twice
- **THEN** the two results are distinct objects, so nothing shares implicitly

### Requirement: The shared state SHALL still be mutated in place, never rebound

`applyStateToUi()` SHALL continue to `Object.assign` the loaded values INTO the shared
objects rather than replacing them.

Rationale: the three pages were handed the exact objects the window was constructed
with, so a rebind would leave every page mutating an object the window had already
replaced — a silent "the setting stopped sticking" failure. Identity stability is also
what makes one shared object safe for N windows, so the reload mitigation and the
shared-ownership fix reinforce each other rather than substituting for one another.

#### Scenario: The reload preserves object identity

- **WHEN** a window maps and `applyStateToUi()` runs
- **THEN** the state objects the pages hold are the same objects afterwards, carrying
  the freshly loaded values

#### Scenario: A capture uses the current shared value

- **WHEN** a capture is triggered from any window
- **THEN** the request is built from the shared state's current values, and the value
  persisted is that same current value — never a stale per-window copy

### Requirement: Persistence and precedence SHALL be unchanged by state sharing

The state file path, its JSON shape, the missing-is-silent / corrupt-is-loud
degradation, the two save call sites and the three-tier precedence rule SHALL all behave
exactly as before.

Rationale: the defect is ownership, not persistence. Widening the change into the store
or the on-disk contract would alter behaviour the refactor spec requires to stay put.

#### Scenario: One state file, written from whichever window captures

- **WHEN** a capture is triggered
- **THEN** `uiStateStore.save()` writes the shared state to the same single
  `capture-ui.json`, in the same shape, with the same degradation on failure

#### Scenario: Precedence is still last-used over settings over constants

- **WHEN** the window maps
- **THEN** the reload still resolves through `configDefaults(settingsStore.load())` and
  the store's merge, unchanged

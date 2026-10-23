# ags-platform-package (delta)

## ADDED Requirements

### Requirement: One in-place `ags-platform` package

The platform's ports, its shared adapters and the one event client SHALL
consolidate into a single package root in-place in `dotfiles-v3`, with a package
identity and one public entry point. The package SHALL depend on no app.

Source: spine **AD-17**, **AD-20**; doc 101 §3, §13 step 8.

#### Scenario: the package has an identity and an entry point

- **WHEN** the package root is inspected
- **THEN** it contains a `package.json` naming `ags-platform` and an `index.ts`
  entry point, and both are registered for deployment

#### Scenario: the package is one directory, not three

- **WHEN** the platform seams are located
- **THEN** the ports and the shared adapters live under the one package root
  (`platform/ports/` and `platform/adapters/`), not scattered across
  `dotfiles/config/ags/{platform,lib,domains,kit}`

### Requirement: Ports and adapters are separated inside the package

The package SHALL hold the pure ports under `ports/` and the host-bound adapters
under `adapters/`. A port SHALL NOT import `gi://*` or `ags`; an adapter MAY.

Source: spine **AD-4**, **AD-5**, **AD-11**, **AD-12**, **AD-13**; doc 101 §4.

#### Scenario: the ports stay pure

- **WHEN** the files under `platform/ports/` are searched for `gi://` or `ags`
  imports
- **THEN** no port imports either

#### Scenario: the adapters bind the ports to the host

- **WHEN** the files under `platform/adapters/` are inspected
- **THEN** the Gio transport, the Gio file monitor, the freedesktop notify call,
  the palette CSS apply and the gnim reactive runtime are supplied there, not in
  the ports

### Requirement: Dependency direction is one-way

`contracts ← ags-platform ← ags-apps` SHALL hold: the package SHALL import
nothing from the bar or any app, and no app SHALL import another app. The
bar-specific ports — `LayoutProvider`, `SurfaceSpec`/`SurfaceRegistry`/
`PopupHost`, the Shell + four shapes, the overlay coordinator — SHALL stay in the
bar, not the package.

Source: spine **AD-1**; doc 101 §3.1, §11.

#### Scenario: the package imports no app

- **WHEN** the package files are searched for imports of `../bar/`,
  `../components/`, `../settings-panel/`, `../services/`, `../audio/` or
  `../domains/<domain>/`
- **THEN** none is present

#### Scenario: the bar-specific ports are not in the package

- **WHEN** the package is searched for `LayoutProvider`, `SurfaceSpec`,
  `PopupHost` or the Shell
- **THEN** none is present (they remain under `dotfiles/config/ags/kit` and
  `dotfiles/config/ags/bar`)

#### Scenario: no app imports another app

- **WHEN** `src/gui-tools/*` is searched for imports of a sibling app's tree
- **THEN** none is present; each app keeps its own local copies in this change

### Requirement: No module globals for cross-cutting capabilities

The package's cross-cutting seams SHALL be injectable: the event client SHALL
take an `EventBusTransport` and a reactive runtime by injection, the preferences
port a `PreferencesSource`, the notifier a `NotifierSinks`, the theme a `CssSink`.
The package SHALL NOT introduce a module-scope singleton for overlays, icons,
events, notifier, preferences or theme.

Source: spine **AD-2**; doc 101 §4.7.

#### Scenario: the event client's transport is injected

- **WHEN** the event client is constructed with a scripted fake transport and a
  fake reactive runtime
- **THEN** it reads state, sends control and builds `select` accessors through
  them, and the pure test project can import it with no GTK

#### Scenario: the ports' host seams are injected

- **WHEN** the preferences, notifier and theme ports are imported by the pure
  test project
- **THEN** each takes its file/monitor, wire and CSS sinks as parameters and no
  module reaches for a global host object

### Requirement: Structurally consumable by the other apps

The package SHALL declare an `exports` map so a `node_modules` shortcut (AD-17)
can resolve the package and its subpaths by bare specifier from every
`config/ags*`. The other apps' migration SHALL NOT be performed here, and nothing
they still need SHALL be deleted.

Source: spine **AD-17**, **AD-20**; doc 101 §3.2, §11.

#### Scenario: the package declares its subpath surface

- **WHEN** the package's `package.json` is read
- **THEN** it declares `exports` for the entry point and the port/adapter subpaths

#### Scenario: the bridge keeps the app copies

- **WHEN** the five apps are inspected after this change
- **THEN** their local `lib/{event-bus-core,event-bus,theme,icon-registry}.ts`
  copies still exist and still typecheck (nothing was deleted that they use)

### Requirement: Registered for deployment; a fresh provision resolves

Every new/relocated package file SHALL be registered in
`compositor_configs_skeleton_files` and mirrored in the verify role; stale
entries for the moved sources SHALL be removed; the new destination directories
SHALL be declared. `make deploy-coverage` SHALL pass and a fresh provision SHALL
still resolve every import.

Source: spine **AD-17**, **AD-19**; the `deploy-coverage` gate.

#### Scenario: deploy coverage is green

- **WHEN** `make deploy-coverage` runs
- **THEN** every AGS module reachable from `app.tsx` — including each package
  file — is registered in `compositor_configs_skeleton_files`

#### Scenario: no manifest entry points at a moved source

- **WHEN** the manifests are searched for the old source paths
  (`dotfiles/config/ags/{lib/event-bus,lib/theme,kit/icon,domains/reactive}.ts`)
- **THEN** no entry is present (each was relocated, not duplicated)

### Requirement: Every migration step leaves the tree green

The change SHALL leave `make ags-test`, `make ags-typecheck`,
`make bar-typecheck`, `make gates-ci` and `make deploy-coverage` green, and the
bar SHALL still bundle.

Source: spine **AD-19**; doc 101 §13.

#### Scenario: the gates pass

- **WHEN** the five gates are run
- **THEN** each reports success (no errors in the extracted tree)

#### Scenario: the bar still bundles

- **WHEN** `ags bundle dotfiles/config/ags/app.tsx /tmp/extract.js --gtk 4` runs
- **THEN** it exits 0 (every relative import resolves after the move)

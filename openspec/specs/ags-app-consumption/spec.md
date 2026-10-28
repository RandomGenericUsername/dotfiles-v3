# ags-app-consumption Specification

## Purpose
Defines how the dotfiles composition consumes independently pinned AGS app repos
with one owner per app, a single program tuple, and a reversible cutover.

## Requirements

### Requirement: One program tuple per install

The composition SHALL name exactly one `ags-platform`, one `contracts` and one
`dotfiles-assets` tag in `program-tuple.yaml` for the install generation.
Every standalone app and the remaining legacy unit SHALL resolve that tuple.

#### Scenario: Tuple record is single-valued
- **WHEN** the composition is validated
- **THEN** exactly one tuple record exists and every app entry references the same tuple

#### Scenario: Missing tuple rejects install
- **WHEN** the tuple record is absent or names an unknown tag
- **THEN** deploy coverage fails and no app is installed against a different platform

### Requirement: The app list is the single ownership source

The composition SHALL declare every AGS app in `apps.yaml` with `owner:
legacy|standalone` and the deployment metadata needed to create and verify its
surfaces.

#### Scenario: One owner per app
- **WHEN** the list is validated
- **THEN** every app has exactly one owner and no app, instance or config link appears twice

#### Scenario: Unknown owner rejects
- **WHEN** an entry has an owner other than `legacy` or `standalone`
- **THEN** deploy coverage fails naming the entry

### Requirement: App surfaces are derived from the list

The composition SHALL derive the install directory, config/spine/XDG/bin links,
launcher, autostart entry and bar palette pointer from the app entry; it SHALL
not maintain a second per-app list.

#### Scenario: A standalone entry installs its declared surfaces
- **WHEN** an app entry is `standalone` and its tag is installed
- **THEN** every declared link/launcher/autostart surface resolves to that app

#### Scenario: A legacy entry is not double-deployed
- **WHEN** an app entry is `legacy`
- **THEN** the standalone role does not create its surfaces and the old role remains the only owner

### Requirement: Cutover is a reversible epoch

A per-app cutover SHALL quiesce the old instance, flip ownership in the app list,
install and start the new unit, and verify identity plus every ownership surface.

#### Scenario: Successful cutover
- **WHEN** an app flips from `legacy` to `standalone`
- **THEN** the old process/name is gone, the new unit is running, and exactly one owner exists on every surface

#### Scenario: Failed cutover rolls back
- **WHEN** the new unit fails verification
- **THEN** the list flips back to `legacy`, the old unit is restarted, and no duplicate or missing owner remains

### Requirement: No monorepo remains at completion

When the last app moves, the composition SHALL remove the `ags-apps` pin and
role and SHALL not deploy an empty meta repo.

#### Scenario: Final topology
- **WHEN** all apps are `standalone`
- **THEN** deploy coverage shows no `ags-apps` pin, no legacy role and no duplicate surface

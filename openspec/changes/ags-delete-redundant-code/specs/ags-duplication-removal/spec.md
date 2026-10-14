# ags-duplication-removal (delta)

## ADDED Requirements

### Requirement: No app-local copy of a shared seam remains

After the platform is consumed, the repo SHALL contain no app-local copy of a platform seam: no `icon-registry.ts`, no `event-bus-core.ts`/`event-bus.ts`, no `theme.ts`, and no bespoke event reader. Every consumer SHALL use the platform adapters.

Source: spine **AD-5**, **AD-7**, **AD-13**; doc 101 §11.

#### Scenario: the duplicate seams are gone

- **WHEN** the repo is searched after consumption
- **THEN** `find -name icon-registry.ts` returns nothing
- **AND** `find -name 'event-bus*.ts'` returns only the platform import
- **AND** `find -name theme.ts` returns nothing

### Requirement: Popup chrome is owned by one primitive

All popups SHALL use `PopupHost`; the duplicated click-catcher / anchor-margin / keymode chrome SHALL NOT be re-implemented per popup.

Source: spine **AD-10**.

#### Scenario: one chrome implementation

- **WHEN** the repo is searched for the popup chrome markers
- **THEN** they appear only in `PopupHost`

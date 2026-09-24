# AGS restart versus live theme refresh

## Decision

Use a live CSS refresh when a running AGS app only needs the generated wallpaper palette. Restart an app when its code, process state, or cached non-CSS data must be rebuilt.

The notification overlay follows the live-refresh path. `AgsReloader` continues its existing reload operation for the bar and other eligible AGS apps, but skips `ags-notifications`, `ags-icme`, and `ags-wallpaper-selector`. This lets the notification remain visible through wallpaper reconciliation.

## Why `app.apply_css()` is not the refresh API

In the installed AGS GTK4 implementation, `app.apply_css(css)` creates a new `Gtk.CssProvider`, adds it to the display, and retains it in AGS's provider list. Repeating that call for each wallpaper adds providers instead of replacing the old palette. `app.reset_css()` removes registered providers from the display, but is not a safe palette-only replacement mechanism: it also affects the app stylesheet and AGS retains its provider records.

The three palette-aware apps therefore own one dedicated palette provider. On refresh they:

```ts
const next = new Gtk.CssProvider()
next.load_from_path("~/.config/ags/colors.css")
Gtk.StyleContext.add_provider_for_display(display, next, Gtk.STYLE_PROVIDER_PRIORITY_USER)
if (paletteProvider !== null)
  Gtk.StyleContext.remove_provider_for_display(display, paletteProvider)
paletteProvider = next
```

The real helper expands the config path, detects CSS parse errors, and adds the new provider before removing the previous provider. The app's base stylesheet remains independently installed through `app.start({ css: style })`.

## Wallpaper notification data flow

```text
wallpaper set
  ├─ wallpaper.state: applying ──────────> show indeterminate progress card
  ├─ set new wallpaper visibly
  ├─ wallpaper.state: visible ───────────> update card text; keep progress moving
  ├─ derive/apply palette and reconcile consumers (existing runtime sequence)
  ├─ wallpaper.state: done ──────────────> refresh palette CSS; show completion
  └─ wallpaper.state: error ─────────────> show failure
```

The overlay subscribes to the existing `org.dotfiles.Events` D-Bus signal. At startup it subscribes first, then calls `GetTopicState` once so an operation already in progress is not missed. If the event hub starts later, D-Bus `NameOwnerChanged` triggers one more state read. There is no polling of the runtime.

The card's picture glyph and completed-step check-circle follow the repository icon pipeline: their SVG templates live under `dotfiles/assets/icon-templates/`, their `wallpaper-progress` variants are authored in `icons.yaml`, and ITR renders them into `current/icons/` using the active palette. The assets role deploys the templates and mappings; compositor provisioning generates the shared AGS `icons.json`; the notification's icon registry resolves those manifest entries. On `done`, the card reloads both icons after the runtime has repointed `current/`, so the running images reflect the new palette.

`wallpaper.state` keeps its existing `state` lifecycle (`applying`, `visible`, `done`, `error`) and adds an optional `stage` field for `wallpaper set` progress:

| Event stage | Published at | Checklist row made active |
| --- | --- | --- |
| `setting_wallpaper` | Before the visible swap | Setting the wallpaper |
| `generating_palette` | After wallpaper visibility is confirmed | Generating the color palette |
| `palette_generated` | Immediately after `ensure_palette()` succeeds | Confirms palette generation is complete |
| `preparing_appearance_assets` | Before effects and icons are ensured | Preparing effects and icons |
| `appearance_assets_ready` | After effects/icons handling and desired state persistence | Updating desktop consumers |
| `reconciling_consumers` | After apply-state derivation, immediately before reconcile | Updating desktop consumers |
| `finished` | After reconcile returns | All rows complete |

The palette event is emitted by an optional progress callback at the application use-case boundary. The command adapts it to the event bus. It is informational and cannot change derivation, locking, reconcile ownership, or operation order. Existing subscribers can ignore the optional field; the prior `state` values are unchanged. The notification's GTK timer only pulses the indeterminate bar while a card is active.

The event contract contains named stages, not a numeric completion ratio. The bar is therefore indeterminate during work and complete on `done`; it does not invent a percentage. The checklist identifies actual runtime boundaries. Effects and icon generation may use cache hits or degrade gracefully, so the row says they were processed rather than claiming that every output was freshly generated. The terminal event includes `reload_failures`; the card marks the consumer step as failed when that list is non-empty. The command still exits non-zero for those failures.

## Runtime and reconcile impact

The reconcile engine, its actor/lock, wallpaper command, and order of wallpaper/palette/consumer work are unchanged. The runtime change adds optional milestone reporting at existing wallpaper-set boundaries and adds the notification app to the existing AGS restart skip set in `runtime/adapters/ags_reloader.py`. Reporting does not drive or coordinate the pipeline.

Provisioning still deploys the notification app as a session-critical AGS instance. Its restart list behavior is unchanged: provisioned code changes can restart/relaunch that instance. The skip applies to the runtime's wallpaper-driven reload cycle, not to deployment or session startup.

## App-by-app rule

| App | Wallpaper behavior | Runtime reload decision |
| --- | --- | --- |
| Notifications | CSS tokens plus live progress card | Skip restart; replace owned palette provider in place |
| Wallpaper selector | Existing wallpaper event subscriber and palette-aware UI | Skip restart; replace owned palette provider in place |
| ICME | Existing wallpaper event subscriber and palette-aware UI | Skip restart; replace owned palette provider in place |
| Hypr-pano | Caches palette-derived icon data and GTK image snapshots | Keep restart until it has an app-specific data refresh path |
| Capture tool | Event-sensitive capture UI and generated image assets | Keep existing lifecycle until its state/assets are proven refreshable in place |
| AGS bar | Session-wide widgets and services | Keep the existing bar reload behavior |

This is not a blanket rule against restarting AGS. CSS is only one layer of app state. Use live CSS replacement when the palette is the only stale input; keep a restart where code, cached data, or process-level state also needs rebuilding.

## Deployment and validation

Provisioning deploys each new TypeScript module alongside the app files. The notification app is on `AgsReloader`'s skip list so the active card survives the wallpaper cycle. AGS bundle checks validate the notification, wallpaper-selector, and ICME entry points; provisioning tests pin the deployed file lists and destination directories; runtime tests pin the notification skip behavior.

## Design Decisions

### D1: Icon loading via extended icons.yaml (not separate manifest)

**Decision:** Add `bar_mappings` sections to the existing `icons.yaml` file
rather than creating a separate `icon-manifest.ts` or `icons.yaml`-equivalent.

**Rationale:** `icons.yaml` is already the source of truth for what icons exist.
Adding `bar_mappings` keeps the vocabulary (what icons exist) and the consumer
mapping (when to use which icon) in the same file. Adding a new icon variant
requires editing one file, not two.

**ITR impact:** None — ITR reads `variants` + `color_mappings` and ignores
unknown keys. The `bar_mappings` key is additive.

### D2: Astal libraries for reactive data (not polling)

**Decision:** Use Astal libraries (`gi://AstalBattery`, `gi://AstalHyprland`,
`gi://AstalNetwork`) with `createBinding()` for reactive data, instead of
`createPoll()` or `GLib.timeout_add`.

**Rationale:** The AGS docs explicitly state "Avoid polling when possible. You
should use events and signals whenever possible." Astal libraries wrap DBus
proxies (UPower, NetworkManager) and Hyprland IPC, which emit GObject signals
on state changes. `createBinding()` subscribes to these signals — the widget
updates automatically when state changes, with zero background processing.

**Exception:** The clock widget uses AGS's `interval(1000, ...)` utility, which
is the accepted pattern for time displays (no external data source to watch).

### D3: IconRegistry reads icons.json (not icons.yaml at runtime)

**Decision:** The provisioning pipeline converts `icons.yaml` → `icons.json`
at apply time. The bar's `IconRegistry` imports the JSON file (esbuild inlines
it at bundle time).

**Rationale:** GJS/Gnim has no built-in YAML parser. Parsing YAML at runtime
would require a dependency. JSON is natively supported and esbuild handles it
as an import. The YAML→JSON conversion is a trivial provisioning step.

### D4: Dual-path icon resolution (current/ → generated/)

**Decision:** `IconRegistry.resolve()` checks `$XDG_STATE_HOME/dotfiles/current/icons/`
first, falls back to `$XDG_DATA_HOME/dotfiles/generated/icons/`.

**Rationale:** Before Phase 2 runtime lands, icons exist only at
`generated/icons/` (provisioning-owned). After Phase 2, the runtime seeder
creates `current/icons/` symlinks. The dual-path approach makes the bar work
now and transition seamlessly.

### D5: AGS bar reload is process restart (not hot-reload)

**Decision:** After a wallpaper change triggers palette/icon regeneration, the
AGS process must be restarted (`ags quit` + `ags run`) for the new icons to
take effect.

**Rationale:** AGS v2 has NO native hot-reload (verified from source
`cli/cmd/run.go:145` — `// TODO: watch and restart`). The reload adapter is
part of the Phase 2 runtime's `ags_reloader` adapter. Within a single session,
the reactive bindings auto-update (battery level changes, workspace switches),
but icon file changes require a process restart.

### D6: Widget icon size normalization via CSS

**Decision:** All `Gtk.Image` widgets displaying SVG icons use
`min-width: 24px; min-height: 24px` CSS rules.

**Rationale:** SVG icon templates have inconsistent viewBox dimensions
(battery=1024x1024, wifi=96x96, ethernet=72x72). GTK4's Image widget scales
SVGs to fit the allocated size regardless of intrinsic viewBox. CSS-enforced
sizing normalizes rendering across all icon categories.

### D7: Centerbox layout with start/center/end slots

**Decision:** The bar uses AGS's `centerbox` with three slots:
- `$type="start"`: workspaces
- `$type="center"`: clock
- `$type="end"`: battery, network, power-menu

**Rationale:** This is the standard status bar layout pattern. The centerbox
ensures the clock stays centered regardless of left/right widget widths.

### D8: Workspaces hardcoded to 5

**Decision:** The workspaces widget renders exactly 5 buttons (1–5), matching
the Hyprland keybinding config (`bind = $mod, 1-5, workspace, 1-5`).

**Rationale:** Dynamic workspace count would require reading the Hyprland config
file at runtime, which adds complexity. The current config uses 5 static
workspaces. This can be made dynamic in a future iteration.

## Architecture Alignment

| Architecture Invariant | How This Change Aligns |
|----------------------|----------------------|
| AD-17 (consumer wiring) | Bar reads from `current/icons/` with Phase 1 fallback |
| AGS reload (process restart) | Reload adapter is Phase 2 concern; bar works within session |
| Config-in-spine | `~/.config/ags` symlink into install spine, unchanged |
| Provisioning owns install spine | New files in `config/ags/` deployed by compositor_configs |
| Phase 2 cache transparency | `current/icons/` → `cache/icons/<ih>/` managed by runtime |

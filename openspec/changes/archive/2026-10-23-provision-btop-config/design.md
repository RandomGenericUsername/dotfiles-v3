## Context

Three facts about btop's config resolution shape this change.

**1. Theme selection is discovery-relative, not path-relative.**
`Theme::setTheme` (`btop_theme.cpp:451-471`):

```cpp
const auto theme = Config::getS("color_theme");
for (const fs::path p : themes) {          // themes == what updateThemes() found
    if (p == theme or p.filename() == theme or p.stem() == theme or ...)
        theme_path = p;
}
if (theme == "Default" or theme_path.empty() ? Default_theme : loadFile(theme_path))
```

An absolute path outside the scanned directories leaves `theme_path` empty and
falls back to `Default_theme` **silently**. So the theme must physically live in
one of: `--themes-dir`, `$XDG_CONFIG_HOME/btop/themes`, or the system dir.

**2. Symlinks work.** `updateThemes` (`:430-442`) filters on
`file.path().extension() == ".theme"` and `access(path, R_OK) != -1`. The first is
lexical on the link's own name; the second follows the chain. btop never calls
`canonical`, so a symlink into the content-addressed palette cache is invisible to
it. Verified against a real 3-hop chain.

**3. btop writes its config on exit.** `save_config_on_exit` defaults `true`
(`:379`) and `Config::write()` truncates the file (`:840`,
`std::ios::trunc`). Its log goes to `$XDG_STATE_HOME/btop.log` (`:873`), outside
the spine, so that needs no handling.

Precedents: `kitty_config` (role shape, `install_dir` seam, `state: directory`,
no `become`) and the Hyprland `colors.lua` parser (consumers reading `current/`
directly). Neither maps cleanly onto btop, which is why this is a role **plus** a
consumer pointer rather than a rendered include.

## Goals / Non-Goals

**Goals**
- A provisioned `btop.conf` selects `csg-minimal.theme` by default.
- All three generated themes are visible in btop's theme menu.
- A wallpaper change is reflected on the next btop launch.
- Provisioning never loses a user's config silently, and btop never rewrites the
  spine-owned file.

**Non-Goals**
- The CSG formats or the runtime artifact set (sibling changes).
- Reloading a running btop.
- Any btop display tuning.

## Decisions

### D1. Symlink the themes directory into the spine, not the whole `~/.config/btop` blindly
`config_links` already owns the `~/.config/<name>` → `<install>/config/<name>`
pattern with a migrate-then-backup guard, so `btop` joins
`config_links_managed_dirs`. The `themes/` subdirectory is then created by the
role and populated by the runtime's consumer pointers. This is the established
config-in-spine mechanism, not a new one.

### D2. Consumer pointers, not a rendered `btop.conf` include
kitty's `include <abs path>` has no btop equivalent (D1 above), so the role cannot
point btop at `current/` directly. Instead three `ConsumerPointer` entries place
the artifacts in the spine's `themes/` dir, which is exactly the shape the seeder
already supports. **This means adding btop to the pinned consumer table in
`adapters/consumer_path_spec.py`, which is contract data transcribed in
`shared-data-contract.md`** — coordinate, never re-decide.

### D3. `save_config_on_exit = false` is mandatory
Without it btop truncates and rewrites the provisioning-owned, git-tracked
`btop.conf` through the spine symlink on every quit, and UI changes made by the
user land in version control. Verified in source (`:379`, `:836-845`). This is the
one setting in the whole change that is not cosmetic.

### D4. `<install>/config/btop/themes/` must be created by provisioning
`repoint_consumer_symlinks` skips a pointer with a warning when the destination
parent is missing and **never mkdirs** into the spine (`seeder.py:757-763`, rule
`skip_on_missing_parent`). So the role creates the directory explicitly. Note
this is a *subdirectory*: unlike the GTK consumer dirs there is no seeding need,
because there is no pre-existing user content to preserve — only btop's own
`btop.conf`, which the config_links backup guard handles at the parent level.

### D5. Default to `csg-minimal`
Selected by the user. It is the most wallpaper-faithful of the three, so a fresh
machine gets a theme that looks like the wallpaper; the other two are one menu
selection away.

### D6. Ship stock btop values otherwise
`graph_symbol`, `presets`, `update_ms`, `proc_sorting`, and the rest stay at btop
's own defaults. The user's explicit preference; keeps the diff auditable and the
surface small.

### D7. No reload — apply on next launch
btop resolves its theme once at startup and exposes no reload signal. Restarting a
foreground TUI (losing scroll, selection, and any in-flight interaction) in
response to a wallpaper change is a UX decision deferred to a later change. The
existing `Gtk4AppReloader` pattern is the likely template for it.

## Risks

- **Config-links parity tests.** `config_links_managed_dirs` and
  `verify_managed_link_dirs` are compared **exactly** by
  `test_verify_managed_link_dirs`; both lists must gain `btop` together.
- **Backup guard on first provision.** If `~/.config/btop` exists as a real dir,
  `config_links` moves it aside to a timestamped backup. On this host the
  directory exists (created by btop) but holds no user-authored content beyond a
  possibly generated `btop.conf`.
- **`theme_background`.** Left at btop's default `true`, so the theme's `main_bg`
  is used. Setting it `false` would force a transparent background regardless of
  the theme file.

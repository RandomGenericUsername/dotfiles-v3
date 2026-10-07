## Why

btop cannot be themed the way kitty is. kitty `include`s the runtime palette by
absolute path; btop cannot. `Theme::setTheme` (`btop_theme.cpp:451-471`) resolves
`color_theme` **only against the themes it discovered while scanning its theme
directories at startup**, matching on full path, filename, or stem. An absolute
path to a file outside those directories does **not** load — it silently falls
back to `Default_theme` with no error.

So btop needs a **real file inside `~/.config/btop/themes/`**. Today that
directory exists but is empty and there is no `btop.conf` at all — btop runs on
its built-in `Default` theme.

Symlinks are sufficient and verified: `Theme::updateThemes` (`:430-442`) selects
entries with `file.path().extension() == ".theme"` and
`access(path, R_OK) != -1`. Both predicates are lexical or link-following —
`.extension()` reads the link's own name, `access()` follows the chain — and btop
never canonicalizes. A full 3-hop chain (spine → `current/` → content-addressed
cache entry) was verified to satisfy both.

## What Changes

- A new `btop_config` provisioning role (mirroring `kitty_config`):
  - Renders `btop.conf` into the config-in-spine with `color_theme =
    "csg-minimal.theme"` and `save_config_on_exit = false`.
  - Creates `<install>/config/btop/` and `<install>/config/btop/themes/`.
- `config_links` links `~/.config/btop` → `<install>/config/btop`.
- A `BtopConsumerPathSpec` (or an extension of the existing static table) places
  `colors.btop-minimal.theme`, `colors.btop-balanced.theme`, and
  `colors.btop-full.theme` into `<install>/config/btop/themes/` as pointers at
  `current/`, so all three appear in btop's theme menu.
- `btop` joins the package manifest and `verify` asserts the config, the themes
  directory, and the three theme files.

## Non-goals

- **No CSG format and no runtime artifact set** — those are the sibling changes.
- **No reloader.** The theme applies on the next btop launch; btop resolves its
  theme once at startup.
- **No keybindings, layout, or graph-symbol tuning.** `btop.conf` otherwise ships
  stock btop values (the user's explicit choice).
- **No editing of a user's hand-written `btop.conf`.** Provisioning owns the file;
  `local.conf`-style overrides are out of scope since btop has no include
  mechanism — a user who wants custom values edits `btop.conf` and accepts that a
  re-provision overwrites it.

## Open risk (flagged, not resolved here)

`save_config_on_exit = false` is **required**, not cosmetic. btop defaults it to
`true` (`btop_config.cpp:379`) and `Config::write()` truncates and rewrites the
whole config file on exit (`:836-845`). Because `~/.config/btop` is a symlink into
the spine, the default would let btop overwrite the provisioning-owned,
git-tracked `btop.conf` through the symlink, and any change made in btop's UI
would land in version control.

## Context

The `color-scheme-generator` CLI has a `dump-config` command that writes resolved settings to a file. Currently it requires the full path including filename (e.g. `--output ./settings.toml`). The sibling project `wallpaper-effects-generator` handles this correctly — passing `--output ./` auto-appends `settings.toml`.

The root cause is a missing `pathlib.Path.suffix` check that distinguishes directory paths from file paths.

A secondary issue: `dump-config` doesn't forward `config_path` and `cli_overrides` to the config resolver, unlike every other command (`generate`, `info`, `show`).

`dump-templates` has a similar issue — it accepts `--output` as a directory but doesn't auto-create the default template dir structure. It also has an XDG path inconsistency (`~/.config/color-scheme-generator/templates` vs the resolver's `~/.config/color-scheme/templates`).

## Goals / Non-Goals

**Goals:**

- `dump-config --output ./` writes to `./settings.toml` instead of erroring
- `dump-config --output ./custom.toml` uses the exact path as-is
- `dump-config` respects `--config` and CLI overrides from the global callback
- `dump-templates --output ./` writes templates into `./templates/` (or similar sensible default)
- `dump-templates` fallback XDG path matches what the template resolver actually looks for

**Non-Goals:**

- Changing the `generate` command's output handling (already works differently)
- Refactoring the config resolver architecture
- Changing the `wallpaper-effects-generator` project

## Decisions

**Decision 1: Use `.suffix` check (same pattern as WEG)**

Instead of a more complex approach (e.g. `is_dir()`, custom type resolver), use the same lightweight `pathlib.Path.suffix` heuristic that WEG uses. It's simple, proven, and handles the common cases:

```python
if output_path.suffix != ".toml":
    output_path = output_path / "settings.toml"
```

**Decision 2: Forward `config_path` and `cli_overrides` to resolver**

Match the pattern used by `generate`, `info`, and `show`:

```python
config_path = ctx.obj.get("config_path")
cli_overrides = ctx.obj.get("cli_overrides", {})
settings = config_resolver.resolve(explicit_path=config_path, cli_overrides=cli_overrides)
```

**Decision 3: Fix `dump-templates` XDG path to match resolver**

Change the fallback from `~/.config/color-scheme-generator/templates` to `~/.config/color-scheme/templates` to match `TemplateDirResolver`'s XDG strategy.

## Risks / Trade-offs

- [Low] The `.suffix` heuristic is imperfect — a directory named `something.toml` would be treated as a file. This is an edge case unlikely in practice.
- [Low] Changing `dump-templates` fallback path is a breaking change for anyone relying on the old fallback path. Mitigation: this is a fallback only used when resolver fails, and the resolver almost never fails (it falls through to bundled defaults).

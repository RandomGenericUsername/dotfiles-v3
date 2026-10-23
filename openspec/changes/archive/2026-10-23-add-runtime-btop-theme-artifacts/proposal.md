## Why

Once CSG emits the three btop artifacts (`add-csg-btop-theme-formats`), the
runtime must actually request them and carry them through the palette cache and
the `current/` pointer, so a consumer can reach them. Today `csg_adapter` requests
`conf`/`gtk.css`/`adw.css`/`sequences`/`rasi`/`kitty` and knows nothing of btop,
so nothing the runtime exposes can ever reach `~/.config/btop/themes/`.

## What Changes

- `csg_adapter` requests `--format btop-minimal.theme`, `--format
  btop-balanced.theme`, and `--format btop-full.theme`, and includes all three in
  the hashed outputs.
- The three artifacts join the palette artifact set
  (`PALETTE_ARTIFACT_NAMES`), the reconcile expected-artifacts / `current/`
  symlink set, and the cache-entry `artifact_hashes`. Existing palette entries
  become incomplete and self-heal (evicted + re-derived) via
  `ensure_palette_entry_complete`.
- `contracts/schemas/meta.schema.json` gains the three `artifact_hashes` keys.

## Non-goals

- **No CSG change** — the formats are the sibling change.
- **No reloader.** btop loads its theme at startup and exposes no reload signal.
  A running instance keeps its colours until relaunch; this is a deliberate
  deferral, not an omission (see design D5 of the CSG change).
- **No `btop.conf`, no `config_links` entry, no consumer pointer.** That is
  `provision-btop-config`. This change only makes the artifacts exist and be
  reachable at `current/`.
- **No change to any other consumer's artifact set.**

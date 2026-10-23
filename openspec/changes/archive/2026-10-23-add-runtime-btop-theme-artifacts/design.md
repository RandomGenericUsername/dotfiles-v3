## Context

The palette artifact set is threaded through five places, and each has a
completeness or contract consequence:

| Site | Role |
|---|---|
| `adapters/csg_adapter.py:280-298` | `--format` flags requested from CSG |
| `adapters/csg_adapter.py:351-359` | existence assert on produced outputs |
| `adapters/csg_adapter.py:368-376` | `PaletteArtifacts` construction |
| `application/derive.py:291-299` | `PALETTE_ARTIFACT_NAMES` — the **completeness oracle** |
| `application/reconcile.py:497-505, 540-546, 601-607` | three hardcoded lists (expected-symlink skip, stale-prune, `_build_expected_targets`) |
| `adapters/seeder.py:657-665` | the `current/` artifact loop |
| `adapters/seeder.py:485-493` | `load_palette_entry` rebuilds `PaletteArtifacts` from `meta.json` |
| `domain/models.py:50-60` | the `PaletteArtifacts` dataclass |
| `contracts/schemas/meta.schema.json:47-67` | closed `required` + `properties`, `additionalProperties: false` |

## Goals / Non-Goals

**Goals**
- All three btop artifacts are requested, hashed, cached, and reachable via
  `current/colors.btop-*.theme`.
- The palette contract schema stays truthful.
- Existing cache entries self-heal with no manual migration.

**Non-Goals**
- Reloading a running btop (no signal exists).
- Distributing the themes to `~/.config/btop/themes/` (provisioning's job).
- Any btop-specific policy logic.

## Decisions

### D1. The contract schema update MUST land in the same commit as the runtime change
`contracts/schemas/meta.schema.json` declares `artifact_hashes` with
`additionalProperties: false` and a closed `required` list. Adding the keys to the
runtime without the schema makes every newly written `meta.json` fail
`make contracts-check` (`Makefile:17-19`, which runs
`tests/unit/test_contract_schema_conformance.py`). Conversely, adding them to the
schema without the runtime makes every *existing* `meta.json` fail the now-stricter
`required` list. The two are therefore a single atomic change, and this is the
one ordering constraint in the whole effort.

### D2. Adding to `PALETTE_ARTIFACT_NAMES` is the self-healing mechanism
`ensure_palette_entry_complete` (`application/derive.py:302+`) uses that tuple as
its completeness oracle, so existing entries that lack the three new artifacts are
evicted and re-derived on the next converge — no migration step, no manual
invalidation.

### D3. No consumer pointer here
btop cannot be given a `current/`-relative include the way kitty is; its
`setTheme` resolves `color_theme` **only against the themes it discovered at
startup** (`btop_theme.cpp:451-471`), and an absolute path outside those
directories silently falls back to `Default_theme` with no error. btop therefore
needs a real file inside `~/.config/btop/themes/`, which is a provisioning
concern. This change stops at `current/`.

Note the deliberate divergence from Hyprland: `config/hypr/colors.lua:14-27`
parses `current/colors.conf` directly at `dofile` time, but btop has no such
hook, so `current/` exposure alone is not sufficient for it.

### D4. Defer the reloader, deliberately
btop resolves its theme once at startup. Killing and relaunching a running btop
inside its terminal window is plausible but is a UX decision with real
consequences (losing scroll position, selection, and any in-flight interaction),
and it is out of scope for palette distribution. Recorded as a decision so it is
not read as an oversight.

## Risks

- **Cache churn.** Every existing palette entry becomes incomplete and is
  re-derived once. Self-healing, but the first converge after this change does
  real work.
- **`meta.json` compatibility.** Any reader outside the listed sites that
  enumerates `artifact_hashes` strictly will need the same update. Verified
  `load_palette_entry` and `contracts-check` are the two consumers.

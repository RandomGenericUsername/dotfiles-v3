## 1. Preference store (pure domain + adapter — hexagonal split is MANDATORY)

Layering-gate constraint (`tests/architecture/test_layering.py` bans
`pathlib`/I/O in `runtime/domain/`, cf. the `icon_contrast_sampler` fix):
file I/O lives ONLY in the adapter; the domain module is pure functions.

- [x] 1.1 New pure `src/runtime/src/runtime/domain/icon_contrast_policy.py`:
  `parse(text) -> prefs`, `serialize(prefs) -> text`, `lookup(prefs, hash)
  -> bool|None`, `resolve(*, flag, stored, default=True) -> (enabled,
  source)`; NO `pathlib`, NO file I/O, mypy-strict; unit tests (roundtrip,
  precedence table flag>store>default, absent⇒None)
- [x] 1.2 New `src/runtime/src/runtime/adapters/icon_contrast_prefs_store.py`:
  read + atomic temp+rename write; corrupt file ⇒ empty prefs + warning
  (never raises into the pipeline); unit tests (corrupt-tolerant,
  missing-file-OK, atomic-write shape)
- [x] 1.3 Governing-hash helper `governing_wallpaper_hash(input_path) -> str`:
  direct file ⇒ its content hash; WEG artifact (existing `_is_weg_artifact`
  check) ⇒ effects cache meta `source_wallpaper_hash`; unresolvable ⇒
  content hash + warning (default ON applies); unit tests (direct, variant
  with meta, variant without meta, corrupt meta)

## 2. Pipeline + CLI

- [x] 2.1 `DerivationPipeline.ensure_icons` (and `RegenerateIcons` path)
  takes `contrast_enabled: bool`; `False` ⇒ spine passthrough (no overlay,
  pre-guard key, `contrast.policy.enabled==false` recorded); update/extend
  `test_derive_icon_contrast_overlay.py` + integration file
- [x] 2.2 `wallpaper set --contrast {auto,on,off}` (default `auto`):
  `on`/`off` persist the choice for the wallpaper hash before deriving;
  CLI tests incl. persistence assertions
- [x] 2.3 New `icons regenerate [--contrast ...]`: `RegenerateIconsUseCase`
  (load current — fail loud on absent/corrupt → ensure icons from live
  palette → repoint icons + consumer links → history append with
  `trigger="regenerate"` + `details.layers={icons:1}` → AGS-only reload →
  `applying`/`done` events, never `visible`); CLI + integration
  tests (live-toggle scenario, no-flicker assertions: wallpaper/palette
  hashes unchanged, only icons entry + AGS reloaded)
- [x] 2.4 New `icons preference [HASH] [--set on|off]` accessor (show
  resolved `{hash,enabled,source}` plain/JSON; set persists+prints);
  missing store file is NOT an error; CLI tests for show/set/default-source
- [x] 2.5 `meta.json: contrast.policy{source,enabled}` additive; old metas
  valid; `inspect`/`doctor` wording ("guard OFF via per-wallpaper
  preference" etc.); contract conformance tests updated

## 3. Verification

- [x] 3.1 `src/runtime` full suite green + `make contracts-check` green
- [ ] 3.2 Manual: opt-out wallpaper renders spine icons; live toggle flips
  bar icons without pixel change; reboot preserves prefs

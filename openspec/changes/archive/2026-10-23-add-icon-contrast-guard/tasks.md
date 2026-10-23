## 1. Dependency (provisioning installs, runtime executes) — Agent C

- [x] 1.1 `src/runtime/pyproject.toml` — add `Pillow>=10,<12` to `dependencies`
  (keep alphabetical-ish order with existing entries); `uv lock` / `uv sync`
  inside `src/runtime` to refresh `uv.lock`
- [x] 1.2 Verify zero Ansible changes needed: confirm `cli_tools` role loop
  (`tasks/main.yml:81-105` + `vars/main.yml:52-56`) already covers
  `dotfiles-runtime` via `uv tool install --force`; record this as the
  provisioning proof in the task comment (no `packages.yaml`, `assets.yaml`,
  `filesystem.yaml`, container-image change)
- [x] 1.3 Verify `dotfiles-runtime` tool env imports PIL after reinstall;
  verify runtime spawns no installer subprocess (grep guard for
  `pip`/`uv tool` — must be absent)

## 2. Domain service (pure, no I/O beyond injected paths) — Agent A

- [x] 2.1 New `src/runtime/src/runtime/domain/icon_contrast.py`:
  `hex_to_rgb`, `relative_luminance`, `contrast_ratio` (WCAG 2.1),
  `pick_best_token(backdrop_hex, current_token, palette: dict[str,str]) -> (token, ratio_before, ratio_after)`,
  `decide_overrides(palette, backdrop_hex, groups_config, threshold) -> dict[(group, placeholder), new_token]`
  with candidate set ∩ palette-resident only, literal `#` passthrough, ties keep original
- [x] 2.2 Backdrop sampler `sample_top_strip_luminance(wallpaper: Path, band_px=48) -> float | None`
  (PIL use-site import, `convert("RGB")`, resize-safe averaging, `None` on any failure —
  never raises); palette fallback `background` hex
- [x] 2.3 Constants: `BAR_GROUPS` allowlist
  (`battery, network, btop, thunderbird, tray, ui, power-menu, email-client, wallpaper-selector`),
  `PLACEHOLDERS = (COLOR_FOREGROUND, COLOR_JOIN)`, `DEFAULT_THRESHOLD = 4.5`
- [x] 2.4 Unit tests `src/runtime/tests/unit/test_icon_contrast.py`: known WCAG
  vectors (black/white = 21.0), light-wallpaper flip, dark-wallpaper no-op,
  literal passthrough, missing-`surface` tolerance, tie keeps original,
  sampler `None`-on-corrupt, threshold boundary
- [x] 2.5 `ruff check` + `ruff format --check` + `mypy --strict` clean for the new module

## 3. Pipeline integration (overlay + effective hash + meta) — Agent B

- [x] 3.1 `application/derive.py::ensure_icons` — after resolving spine
  `templates_dir`/`mappings_path` and loading palette `colors.yaml` + wallpaper
  pixels: run contrast service → build staging overlay (file case: patched
  `icons.yaml`; dir case: replicate dir, patch only `icons.yaml`) with
  deterministic serialization; pass overlay path to `self._itr.render`
- [x] 3.2 Effective-hash change: `m_h` = hash of overlay (file → `hash_file`,
  dir → `canonical_hash_dir`); keep `ih = sha256(peh || t_h || m_h)`; overlay
  build happens before `target = cache_entry_path(...)` so hit/miss uses `ih`
- [x] 3.3 `adapters/seeder.py` — additive `contrast` field in icons `meta.json`
  (`backdrop_source`, `threshold`, `decisions[]`); loader tolerates absent field
  (old entries stay valid)
- [x] 3.4 Config plumbing: threshold + allowlist overridable via
  `RUNTIME__ICON_CONTRAST__*` env (defaults threshold `4.5`, groups = D5 list);
  document in code + `doctor`/`inspect` wording
- [x] 3.5 Tests: unit `test_derive_icon_contrast_overlay.py` (overlay content,
  scope guard — accent variants/`bar_mappings` preserved, deterministic bytes);
  integration `test_icon_contrast_overlay_integration.py` (light fixture flips,
  dark fixture no-op, corrupt image degrades, cache-hit second run invokes no
  `itr`); existing `test_wallpaper_set_capstone_integration.py` +
  `test_itr_adapter_integration.py` stay green

## 4. Docs + verification — Agent C

- [x] 4.1 `docs/Adding an Icon — ITR and Provisioning Pipeline.md` — new
  `§ Contrast guard` (why, allowlist, backdrop sampled→palette, overlay +
  effective hash, threshold config, `meta.json: contrast` inspection)
- [x] 4.2 Full `src/runtime` suite green: `uv run --directory src/runtime pytest -q`;
  `contracts-check` (`make contracts-check`) green (meta additive only)
- [x] 4.3 Manual proof on host: dark wallpaper → `color15` kept; light
  wallpaper → dark token picked; `ls current/icons/*.svg` + `grep fill=` shows
  picked hex; bar screenshots attached to change review

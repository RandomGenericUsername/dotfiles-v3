// P5 drill-down window: level 1 wallpaper grid (search + quick-apply),
// level 2 per-wallpaper variant gallery (breadcrumb + Back).
//
// Built imperatively with `createEffect` reactivity (same pattern as the
// ICME `EditorWindow`); only the top-level `<window>` shell is JSX. Cards
// are plain boxes with a click gesture (never nested buttons): the tile
// drills down, the inner Apply button applies directly.

import { Astal, Gdk, Gtk } from "ags/gtk4";
import app from "ags/gtk4/app";
import GdkPixbuf from "gi://GdkPixbuf?version=2.0";
import GLib from "gi://GLib?version=2.0";
import Pango from "gi://Pango?version=1.0";
import { createEffect, createState } from "ags";
import { applyWallpaper } from "../lib/apply";
import { getContrastPref, regenerateIcons, setContrastPref } from "../lib/contrast";
import { domainEvents, WALLPAPER_STATE_TOPIC } from "../lib/event-bus";
import { reloadIconManifest, resolveIcon } from "../lib/icon-registry";
import {
  DEFAULT_CONTRAST_ENABLED,
  cachedContrastPref,
  contrastScopeLabel,
  filterWallpapers,
  isRealHash,
  isWallpaperLive,
  stemOf,
  variantsFor,
  type SelectorModel,
  type VariantEntry,
  type WallpaperEntry,
} from "../lib/model";
import { loadModel, loadModelSmart } from "../lib/scan";
import { cachedTexture, generateThumb, thumbTexture } from "../lib/thumbnails";

const WINDOW_NAME = "wallpaper-selector-window";

function hideWindow(): void {
  const window = app.get_window(WINDOW_NAME);
  if (window) window.visible = false;
}

export function WallpaperSelectorWindow(gdkmonitor: Gdk.Monitor) {
  const [model, setModel] = createState<SelectorModel | null>(null);
  const [query, setQuery] = createState("");
  const [selected, setSelected] = createState<WallpaperEntry | null>(null);
  const [status, setStatus] = createState("Ready.");
  const [busy, setBusy] = createState(false);

  // Busy = a local set in flight OR the last observed `wallpaper.state`
  // being `applying`/`visible`. Event-driven so an apply started elsewhere
  // (or the regenerate arm) locks the Apply controls too.
  let localApply = false;
  let eventBusy = false;

  // Apply controls are recreated per render; `clearFlow` resets the list and
  // `refreshBusy` re-asserts sensitivity on every busy transition.
  const applyControls: Gtk.Button[] = [];

  // L1 contrast swatches, per rendered card: the swatch is BOTH indicator and
  // control (user request), so a toggle must repaint every visible card for
  // that wallpaper (and the L2 checkbox when drilled). Reset in `clearFlow`.
  const glyphUpdaters: { hash: string; update: () => void }[] = [];

  // Resolved contrast prefs cached by governing wallpaper hash (cheap map
  // read at render time). `prefEpoch` invalidates in-flight lookups when a
  // `done`/`error` rescan clears the map.
  const contrastPrefs = new Map<string, boolean>();
  // Explicit choices for NEVER-APPLIED wallpapers (placeholder hash, no
  // store entry possible yet). Persisted by the runtime at set time via
  // `wallpaper set --contrast on|off` (governing content hash).
  const pendingContrast = new Map<string, boolean>();
  let prefEpoch = 0;
  let syncingContrast = false;
  let deferredRegenerate: { hash: string; name: string; enabled: boolean } | null = null;

  // Magnifier from the shared ITR-rendered `ui` group (palette-tinted),
  // stock symbolic fallback — the hypr-pano search row, verbatim pattern.
  function searchUiIcon(): Gtk.Widget {
    const path = resolveIcon("ui", "search");
    if (path !== null) {
      try {
        const pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(path, 18, 18);
        const picture = Gtk.Picture.new_for_paintable(Gdk.Texture.new_for_pixbuf(pixbuf));
        picture.set_content_fit(Gtk.ContentFit.CONTAIN);
        picture.set_size_request(18, 18);
        picture.set_halign(Gtk.Align.CENTER);
        picture.set_valign(Gtk.Align.CENTER);
        picture.add_css_class("ws-ui-icon");
        return picture;
      } catch (error) {
        console.error(`wallpaper-selector: cannot load search icon ${path}: ${error}`);
      }
    }
    const fallback = Gtk.Image.new_from_icon_name("system-search-symbolic");
    fallback.set_pixel_size(18);
    fallback.set_halign(Gtk.Align.CENTER);
    fallback.set_valign(Gtk.Align.CENTER);
    return fallback;
  }

  const search = new Gtk.Entry({
    placeholder_text: "Search wallpapers…",
    hexpand: true,
  });
  search.add_css_class("ws-search");
  search.connect("changed", () => {
    setQuery(search.get_text());
    renderGrid();
  });
  const searchRow = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 });
  searchRow.append(searchUiIcon());
  searchRow.append(search);

  const titleLabel = new Gtk.Label({ css_classes: ["ws-title"], xalign: 0 });

  const crumbBox = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    css_classes: ["ws-crumb"],
    spacing: 12,
    visible: false,
  });
  const crumbThumb = new Gtk.Picture({ css_classes: ["ws-crumb-thumb"] });
  crumbThumb.set_size_request(84, 52);
  crumbThumb.set_content_fit(Gtk.ContentFit.COVER);
  crumbThumb.set_valign(Gtk.Align.CENTER);
  const crumbText = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, hexpand: true });
  const crumbName = new Gtk.Label({ css_classes: ["ws-crumb-name"], xalign: 0 });
  const crumbSub = new Gtk.Label({ css_classes: ["ws-crumb-sub"], xalign: 0 });
  crumbText.append(crumbName);
  crumbText.append(crumbSub);
  const backButton = new Gtk.Button({ label: "◀ Back", css_classes: ["ws-back"] });
  backButton.set_valign(Gtk.Align.CENTER);
  backButton.connect("clicked", () => goBack());
  crumbBox.append(crumbThumb);
  crumbBox.append(crumbText);
  crumbBox.append(backButton);

  // L2 primary control (mock §2): the checkbox lives directly under the
  // crumb header so attribution to the drilled wallpaper is unambiguous.
  // The sublabel always names the file (OFF never reads as "missing").
  const contrastCheck = new Gtk.CheckButton({ css_classes: ["ws-contrast-check"] });
  const contrastLabel = new Gtk.Label({
    label: "Auto high-contrast icons",
    css_classes: ["ws-contrast-label"],
    xalign: 0,
  });
  const contrastSub = new Gtk.Label({
    css_classes: ["ws-contrast-sub"],
    xalign: 0,
    wrap: true,
  });
  const contrastDefer = new Gtk.Label({
    label: "saved — will apply when ready",
    css_classes: ["ws-defer"],
    xalign: 0,
    visible: false,
  });
  const contrastText = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, hexpand: true });
  contrastText.append(contrastLabel);
  contrastText.append(contrastSub);
  contrastText.append(contrastDefer);
  const contrastRow = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 10,
    css_classes: ["ws-contrast-row"],
    visible: false,
  });
  contrastRow.append(contrastCheck);
  contrastRow.append(contrastText);
  contrastCheck.connect("toggled", () => onContrastToggled());

  // Non-homogeneous: Gtk.Picture reports the full paintable as its natural
  // size, which would stretch every card to the largest image (2 giant
  // columns). Children size to their requests instead (208px thumbs).
  const flow = new Gtk.FlowBox({
    selection_mode: Gtk.SelectionMode.NONE,
    column_spacing: 12,
    row_spacing: 12,
    homogeneous: false,
    max_children_per_line: 4,
  });
  const scrolled = new Gtk.ScrolledWindow({
    hexpand: true,
    vexpand: true,
    css_classes: ["ws-scroll"],
  });
  scrolled.set_child(flow);

  const statusLabel = new Gtk.Label({ css_classes: ["ws-status"], xalign: 0, wrap: true });
  createEffect(() => statusLabel.set_label(status()));

  const root = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["ws-root", "ws-panel"],
    spacing: 10,
  });
  // Empty-state banner lives OUTSIDE the FlowBox (mock): a FlowBox child
  // never reliably fills the row, so the banner is a plain block sibling
  // toggled against the scrolled grid — full width, centered text.
  const emptyBanner = new Gtk.Label({ css_classes: ["ws-empty"], xalign: 0.5 });
  emptyBanner.set_halign(Gtk.Align.FILL);
  emptyBanner.set_hexpand(true);
  const emptyWrap = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
  emptyWrap.append(emptyBanner);
  emptyWrap.set_visible(false);
  emptyWrap.set_hexpand(true);
  emptyWrap.set_halign(Gtk.Align.FILL);
  root.append(searchRow);
  root.append(crumbBox);
  root.append(contrastRow);
  root.append(titleLabel);
  root.append(scrolled);
  root.append(emptyWrap);
  root.append(statusLabel);

  // Async thumbnail pump: the grid renders INSTANTLY with empty pictures
  // and thumbs stream in off the critical path (a cold cache decodes ~5s
  // for the full spine — that must never block map/show). Cache hits apply
  // synchronously; misses decode a few per idle tick. `thumbGen` invalidates
  // queued items across re-renders (scroll/search/drill).
  let thumbGen = 0;
  let thumbQueue: { picture: Gtk.Picture; path: string; gen: number }[] = [];
  let thumbPumpScheduled = false;

  function pumpThumbs(): boolean {
    const batch = thumbQueue.splice(0, 3);
    for (const item of batch) {
      if (item.gen !== thumbGen) continue;
      const texture = generateThumb(item.path, GRID_DIM);
      if (texture !== null && item.gen === thumbGen) item.picture.set_paintable(texture);
    }
    if (thumbQueue.length > 0) return true;
    thumbPumpScheduled = false;
    return false;
  }

  function scheduleThumbPump(): void {
    if (thumbPumpScheduled || thumbQueue.length === 0) return;
    thumbPumpScheduled = true;
    GLib.idle_add(GLib.PRIORITY_LOW, pumpThumbs);
  }

  // Display sizes drive decode sizes: Gtk.Picture reports the full paintable
  // as its natural size, so thumbs are decoded at (near-)display size to
  // keep FlowBox columns tight (4 across ≈ 208px cards).
  const GRID_DIM = 208;
  const CRUMB_DIM = 96;

  function thumbPictureAsync(path: string, width: number, height: number): Gtk.Picture {
    const picture = new Gtk.Picture({ css_classes: ["ws-thumb", "ws-thumb-loading"] });
    picture.set_size_request(width, height);
    picture.set_content_fit(Gtk.ContentFit.COVER);
    const hit = cachedTexture(path, GRID_DIM);
    if (hit !== null) {
      picture.set_paintable(hit);
      picture.remove_css_class("ws-thumb-loading");
    } else {
      thumbQueue.push({ picture, path, gen: thumbGen });
      scheduleThumbPump();
    }
    return picture;
  }

  function clearFlow(): void {
    thumbGen++;
    thumbQueue = [];
    thumbPumpScheduled = false;
    applyControls.length = 0;
    glyphUpdaters.length = 0;
    let child = flow.get_first_child();
    while (child !== null) {
      const next = child.get_next_sibling();
      flow.remove(child);
      child = next;
    }
  }

  function showEmpty(text: string | null): void {
    // Empty states bypass the FlowBox entirely (see emptyWrap note): hide
    // the grid and show the banner, or vice versa.
    if (text === null) {
      emptyWrap.set_visible(false);
      scrolled.set_visible(true);
    } else {
      emptyBanner.set_label(text);
      scrolled.set_visible(false);
      emptyWrap.set_visible(true);
    }
  }

  function placeholder(text: string): void {
    showEmpty(text);
  }

  function thumbPicture(path: string, width: number, height: number): Gtk.Picture {
    return thumbPictureAsync(path, width, height);
  }

  function liveBadge(): Gtk.Label {
    const badge = new Gtk.Label({ label: "LIVE", css_classes: ["ws-live"] });
    badge.set_halign(Gtk.Align.END);
    badge.set_valign(Gtk.Align.START);
    return badge;
  }

  // ── Contrast checkbox + busy/deferral wiring (D2/D3) ──────────────────

  function refreshBusy(): void {
    const current = localApply || eventBusy;
    if (current !== busy()) setBusy(current);
    if (current) root.add_css_class("ws-busy");
    else root.remove_css_class("ws-busy");
    for (const control of applyControls) control.set_sensitive(!current);
  }

  /** Cache invalidation on done/error: the store may have moved (a set
   * persists its governing hash) and in-flight lookups must be dropped. */
  function invalidateContrastPrefs(): void {
    prefEpoch++;
    contrastPrefs.clear();
  }

  function syncContrastControl(hash: string, enabled: boolean): void {
    const w = selected();
    if (w === null || w.hash !== hash) return;
    syncingContrast = true;
    contrastCheck.set_active(enabled);
    syncingContrast = false;
  }

  /** Resolve (and cache) a hash's pref. A user flip that already populated
   * the cache wins over a late lookup result.
   *
   * Non-real hashes (never-applied wallpapers) short-circuit to the
   * default-ON policy: the runtime store is keyed by content hash, so no
   * entry can exist yet, and `icons preference` rejects placeholders —
   * shelling it would spam CRITICAL logs on every hover. The explicit
   * choice is carried by `pendingContrast` and handed to `wallpaper set
   * --contrast` at apply time. */
  async function loadContrastPref(hash: string): Promise<boolean | null> {
    if (!isRealHash(hash)) return DEFAULT_CONTRAST_ENABLED;
    if (contrastPrefs.has(hash)) return contrastPrefs.get(hash) as boolean;
    const epoch = prefEpoch;
    try {
      const pref = await getContrastPref(hash);
      if (epoch !== prefEpoch) return null;
      if (!contrastPrefs.has(hash)) {
        contrastPrefs.set(hash, pref.enabled);
        syncContrastControl(hash, pref.enabled);
      }
      return contrastPrefs.get(hash) as boolean;
    } catch (error) {
      console.error(`wallpaper-selector: contrast preference lookup failed: ${error}`);
      return null;
    }
  }

  function isLiveTarget(w: WallpaperEntry): boolean {
    const m = model();
    return isWallpaperLive(w, m === null ? [] : variantsFor(m, w.hash));
  }

  async function runRegenerate(
    hash: string,
    name: string,
    enabled: boolean,
  ): Promise<void> {
    const policy = enabled ? "on" : "off";
    contrastDefer.set_visible(false);
    setStatus(`contrast ${policy} for ${name} · refreshing icons…`);
    try {
      await regenerateIcons(enabled);
      setStatus(`contrast ${policy} for ${name} · icons refreshed`);
    } catch (error) {
      setStatus(`failed: ${error}`);
    }
  }

  /** Busy cleared: fire a deferred regenerate, if one is queued. */
  function flushDeferredRegenerate(): void {
    if (localApply || eventBusy) return;
    const pending = deferredRegenerate;
    if (pending === null) return;
    deferredRegenerate = null;
    void runRegenerate(pending.hash, pending.name, pending.enabled);
  }

  async function persistContrast(w: WallpaperEntry, enabled: boolean): Promise<void> {
    if (!isRealHash(w.hash)) {
      // Never-applied wallpaper: there is no content hash yet, so the
      // store cannot hold an entry. Remember the choice and hand it to
      // `wallpaper set --contrast` at apply time (the runtime persists it
      // under the governing hash it computes).
      pendingContrast.set(w.hash, enabled);
      contrastDefer.set_visible(false);
      setStatus(`saved · applies when ${w.name} is set`);
      return;
    }
    try {
      await setContrastPref(w.hash, enabled);
    } catch (error) {
      setStatus(`failed: ${error}`);
      return;
    }
    if (!isLiveTarget(w)) {
      // Non-live: persist only — the set will resolve it via `auto`. Do not
      // touch a regenerate already queued for the live wallpaper.
      contrastDefer.set_visible(false);
      setStatus(`saved · applies next time ${w.name} is set`);
      return;
    }
    if (localApply || eventBusy) {
      // Live but busy: queue the regenerate; it fires on done/error.
      deferredRegenerate = { hash: w.hash, name: w.name, enabled };
      contrastDefer.set_visible(true);
      setStatus("saved — will apply when ready");
      return;
    }
    await runRegenerate(w.hash, w.name, enabled);
  }

  function onContrastToggled(): void {
    if (syncingContrast) return;
    const w = selected();
    if (w === null) return;
    const enabled = contrastCheck.get_active();
    contrastPrefs.set(w.hash, enabled);
    for (const g of glyphUpdaters) if (g.hash === w.hash) g.update();
    void persistContrast(w, enabled);
  }

  /** L1 swatch toggle: indicator AND control on the main grid. Flips the
   * resolved pref optimistically, repaints every card for that wallpaper,
   * mirrors the L2 checkbox if drilled, then persists via the shared path
   * (live ⇒ icons regenerate; never-applied ⇒ carried to the next set). */
  function onSwatchToggled(w: WallpaperEntry): void {
    const enabled = !cachedContrastPref(contrastPrefs, w.hash);
    contrastPrefs.set(w.hash, enabled);
    for (const g of glyphUpdaters) if (g.hash === w.hash) g.update();
    syncContrastControl(w.hash, enabled);
    void persistContrast(w, enabled);
  }

  function wallpaperCard(w: WallpaperEntry): Gtk.Widget {
    const card = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["ws-card"] });
    const overlay = new Gtk.Overlay();
    overlay.set_child(thumbPicture(w.path, 208, 130));
    if (w.live) overlay.add_overlay(liveBadge());

    // L1 swatch: CSS-drawn (never the U+25D0/U+25CB text glyphs) and now a
    // TOGGLE as well as an indicator (user request) — clicking it flips the
    // high-contrast mode for this wallpaper without leaving the grid. Apply
    // shares the same pill. Children stay visible; ONLY the toolbar is
    // toggled on hover (GTK does not inherit visibility from a parent, so a
    // child marked visible:false would never reappear).
    const dot = new Gtk.Box({ css_classes: ["dot"] });
    // Fixed 15px swatch (mock): centering + no expand keeps the Box at its
    // size request instead of filling the button's content area (which made
    // it read as a fat 28px blob).
    dot.set_size_request(15, 15);
    dot.set_halign(Gtk.Align.CENTER);
    dot.set_valign(Gtk.Align.CENTER);
    dot.set_hexpand(false);
    dot.set_vexpand(false);
    const glyph = new Gtk.Button({ css_classes: ["ws-contrast-glyph"] });
    glyph.set_child(dot);
    glyph.set_valign(Gtk.Align.FILL);
    glyph.connect("clicked", () => onSwatchToggled(w));
    const quick = new Gtk.Button({
      label: "Apply",
      css_classes: ["ws-quick", "ws-hover-item"],
    });
    quick.connect("clicked", () => doApply(w.path, w.name, w.hash));
    const hoverbar = new Gtk.Box({
      orientation: Gtk.Orientation.HORIZONTAL,
      css_classes: ["ws-hoverbar"],
      visible: false,
    });
    hoverbar.set_halign(Gtk.Align.END);
    hoverbar.set_valign(Gtk.Align.END);
    hoverbar.append(glyph);
    hoverbar.append(quick);
    overlay.add_overlay(hoverbar);
    applyControls.push(quick);

    function updateGlyph(): void {
      const on = cachedContrastPref(contrastPrefs, w.hash);
      if (on) {
        glyph.add_css_class("on");
        glyph.remove_css_class("off");
      } else {
        glyph.add_css_class("off");
        glyph.remove_css_class("on");
      }
      glyph.set_tooltip_text(
        `High-contrast ${on ? "ON" : "OFF"} for ${w.name} — click to turn ${on ? "off" : "on"}`,
      );
    }
    updateGlyph();
    glyphUpdaters.push({ hash: w.hash, update: updateGlyph });

    const motion = new Gtk.EventControllerMotion();
    motion.connect("enter", () => {
      hoverbar.set_visible(true);
      updateGlyph();
      // Cheap map read now; resolve the stored pref for the swatch.
      void loadContrastPref(w.hash).then(() => updateGlyph());
    });
    motion.connect("leave", () => hoverbar.set_visible(false));
    card.add_controller(motion);

    const name = new Gtk.Label({ label: w.name, css_classes: ["ws-card-name"], xalign: 0 });
    const sub = new Gtk.Label({
      label: w.variantCount === 1 ? "1 variant" : `${w.variantCount} variants`,
      css_classes: ["ws-card-sub"],
      xalign: 0,
    });
    if (w.variantCount === 0) sub.set_label("no variants");
    card.append(overlay);
    card.append(name);
    card.append(sub);
    const click = new Gtk.GestureClick();
    click.connect("pressed", (_gesture, _nPress, x, y) => {
      // Presses landing on the hover toolbar are owned by its children:
      // Apply applies, the swatch drills. Everything else on the card
      // drills too. Coordinates arrive in card space.
      if (hoverbar.get_visible()) {
        const [, hx, hy] = card.translate_coordinates(hoverbar, x, y);
        if (hx >= 0 && hy >= 0 && hx < hoverbar.get_width() && hy < hoverbar.get_height()) {
          return;
        }
      }
      drill(w);
    });
    card.add_controller(click);
    return card;
  }

  function variantCard(parent: WallpaperEntry, v: VariantEntry): Gtk.Widget {
    // Flat tile matching the mock: bare thumbnail, name + pill Apply in one
    // row beneath (no card chrome, no full-width button). No "original"
    // tile: the original applies from the main grid's quick-Apply.
    const card = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["ws-variant"] });
    // Deliberately NO click gesture on the thumbnail: only the Apply pill
    // sets the wallpaper (a press anywhere else must be inert).
    const picture = thumbPicture(v.path, 208, 130);
    const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 });
    const name = new Gtk.Label({
      label: v.live ? `${v.name} · LIVE` : v.name,
      css_classes: ["ws-variant-name"],
      xalign: 0,
      hexpand: true,
      ellipsize: Pango.EllipsizeMode.END,
    });
    const apply = new Gtk.Button({ label: "Apply", css_classes: ["ws-variant-apply"] });
    apply.connect("clicked", () => doApply(v.path, v.name, parent.hash));
    applyControls.push(apply);
    row.append(name);
    row.append(apply);
    card.append(picture);
    card.append(row);
    return card;
  }

  function renderGrid(): void {
    const m = model();
    setSelected(null);
    searchRow.set_visible(true);
    crumbBox.set_visible(false);
    contrastRow.set_visible(false);
    contrastDefer.set_visible(false);
    titleLabel.set_label("WALLPAPERS");
    showEmpty(null);
    clearFlow();
    if (m === null) {
      placeholder("Loading…");
      refreshBusy();
      return;
    }
    const list = filterWallpapers(m.wallpapers, query());
    if (list.length === 0) {
      placeholder(
        m.wallpapers.length === 0
          ? "No wallpapers in the install spine."
          : "No wallpapers match.",
      );
      refreshBusy();
      return;
    }
    for (const w of list) flow.append(wallpaperCard(w));
    refreshBusy();
  }

  function drill(w: WallpaperEntry): void {
    // Busy never blocks browsing/drill-down (browse-live, set-locked): only
    // the Apply controls are locked.
    setSelected(w);
    setQuery("");
    search.set_text("");
    searchRow.set_visible(false);
    crumbBox.set_visible(true);
    const m = model();
    const variants = m === null ? [] : variantsFor(m, w.hash);
    const parentTex = thumbTexture(w.path, CRUMB_DIM);
    if (parentTex !== null) crumbThumb.set_paintable(parentTex);
    crumbName.set_label(w.name);
    crumbSub.set_label(
      variants.length === 0
        ? "no variants yet"
        : `${variants.length === 1 ? "1 variant" : `${variants.length} variants`}${w.live ? " · LIVE" : ""}`,
    );
    titleLabel.set_label(`VARIANTS · ${w.name.toUpperCase()}`);
    showEmpty(null);
    clearFlow();
    for (const v of variants) flow.append(variantCard(w, v));
    if (variants.length === 0) {
      placeholder(`No variants yet — they are generated the first time ${stemOf(w.name)} is applied.`);
    }

    // L2 primary checkbox: reflect the cached pref, then resolve the store.
    contrastRow.set_visible(true);
    contrastSub.set_label(
      `for ${w.name} · ${contrastScopeLabel(variants.length)} · stored per wallpaper`,
    );
    syncingContrast = true;
    contrastCheck.set_active(cachedContrastPref(contrastPrefs, w.hash));
    syncingContrast = false;
    contrastDefer.set_visible(deferredRegenerate?.hash === w.hash);
    void loadContrastPref(w.hash);
    refreshBusy();
    setStatus(`Variants · ${w.name}. Back returns to the grid.`);
  }

  function goBack(): void {
    renderGrid();
    setStatus("Wallpapers — pick one to see its variants.");
  }

  // Hidden-instance warmup (preload). The instance is long-lived; right
  // after startup an idle callback runs the smart scan plus thumbnail
  // decode for all wallpapers (+ live variants) so the first toggle renders
  // from memory. Opens only ever pay stat validation.
  let mapped = false;
  let warmed = false;

  function warmup(): boolean {
    try {
      setModel(loadModelSmart());
      const m = model();
      if (m !== null) {
        for (const w of m.wallpapers) generateThumb(w.path, GRID_DIM);
        const live = m.wallpapers.find((w) => w.live);
        if (live !== undefined) {
          for (const v of variantsFor(m, live.hash)) generateThumb(v.path, GRID_DIM);
        }
      }
      warmed = true;
      if (mapped) renderGrid();
    } catch (error) {
      console.error(`wallpaper-selector: warmup failed: ${error}`);
    }
    return false;
  }

  function rescan(): void {
    try {
      setModel(loadModelSmart());
    } catch (error) {
      setStatus(`Failed to scan: ${error}`);
      return;
    }
    if (selected() !== null) {
      const m = model();
      const still = m?.wallpapers.find((w) => w.hash === (selected() as WallpaperEntry).hash);
      if (still !== undefined) {
        drill(still);
        return;
      }
    }
    renderGrid();
  }

  async function doApply(
    path: string,
    label: string,
    contrastHash?: string,
  ): Promise<void> {
    if (localApply || eventBusy) return;
    localApply = true;
    refreshBusy();
    setStatus(`applying ${label}…`);
    // Local flag (not the `status` state): state getters may lag the setter,
    // and the collapse decision must be deterministic.
    let ok = false;
    let explicit: "on" | "off" | undefined;
    try {
      // Persist-then-set: the checkbox state for the focused wallpaper must
      // land in the store BEFORE `wallpaper set` runs, so its `auto`
      // resolution is identical with or without explicit flag threading.
      // Resolve from the store first when the swatch was never hovered
      // (L1 quick-Apply) so the default-ON fallback can't clobber a
      // stored OFF.
      if (contrastHash !== undefined) {
        if (isRealHash(contrastHash)) {
          const resolved = contrastPrefs.has(contrastHash)
            ? (contrastPrefs.get(contrastHash) as boolean)
            : await loadContrastPref(contrastHash);
          await setContrastPref(
            contrastHash,
            resolved ?? cachedContrastPref(contrastPrefs, contrastHash),
          );
        } else if (pendingContrast.has(contrastHash)) {
          // Never-applied wallpaper with an explicit choice: thread the
          // policy so the runtime persists it under the governing hash it
          // computes at set time (no GUI-side hashing).
          explicit = pendingContrast.get(contrastHash) ? "on" : "off";
        }
      }
      await applyWallpaper(path, explicit);
      if (contrastHash !== undefined) pendingContrast.delete(contrastHash);
      setStatus(`done · ${label}`);
      ok = true;
    } catch (error) {
      setStatus(`failed: ${error}`);
    } finally {
      localApply = false;
      refreshBusy();
      flushDeferredRegenerate();
      rescan();
      // Collapse on success (stays open on failure so the error is seen).
      // The runtime no longer restarts this instance (skip list), so no
      // reloader will pop the window back open afterwards.
      if (ok) hideWindow();
    }
  }

  // Live palette refresh (event-driven, no restart): the runtime skips this
  // instance on purpose, so re-apply the generated stylesheet plus the
  // re-rendered search icon whenever a set lands.
  function refreshChrome(): void {
    try {
      app.apply_css(`${GLib.get_user_config_dir()}/ags/colors.css`);
    } catch (error) {
      console.error(`wallpaper-selector: style refresh failed: ${error}`);
    }
    reloadIconManifest();
    const old = searchRow.get_first_child();
    if (old !== null) searchRow.remove(old);
    searchRow.prepend(searchUiIcon());
  }

  function onWallpaperEvent(payload: Record<string, unknown>): void {
    const state = payload["state"];
    if (state === "applying") {
      eventBusy = true;
      refreshBusy();
      setStatus("wallpaper.state → applying…");
    } else if (state === "visible") {
      // New intermediate (Agent A): pixels swapped, theming still in
      // flight. Busy like `applying`, but honest about what is on screen.
      eventBusy = true;
      refreshBusy();
      setStatus("wallpaper.state → visible · theming…");
      // Collapse as soon as the wallpaper is actually on screen instead of
      // blocking the view for the whole derivation (visible-first). Only for
      // a set THIS instance initiated — an external set must never dismiss
      // the window. The process keeps running; `done`/`error` still rescans
      // and unlocks the controls.
      if (localApply) hideWindow();
    } else if (state === "done") {
      eventBusy = false;
      refreshBusy();
      invalidateContrastPrefs();
      rescan();
      refreshChrome();
      setStatus("wallpaper.state → done · LIVE refreshed");
      flushDeferredRegenerate();
    } else if (state === "error") {
      eventBusy = false;
      refreshBusy();
      invalidateContrastPrefs();
      rescan();
      refreshChrome();
      setStatus("wallpaper.state → error");
      flushDeferredRegenerate();
    }
  }

  try {
    domainEvents.subscribe(WALLPAPER_STATE_TOPIC, (_topic, payload) =>
      onWallpaperEvent(payload),
    );
  } catch (error) {
    console.error(`wallpaper-selector: event bus unavailable: ${error}`);
  }

  // Schedule hidden warmup after startup settles.
  GLib.idle_add(GLib.PRIORITY_LOW, () => {
    if (!warmed) warmup();
    return false;
  });

  // On-demand instance (no autostart slot): the window starts SHOWN so the
  // first SUPER+W press presents it immediately (ICME pattern). Capture and
  // pano start hidden because they autostart at login.
  return (
    <window
      visible
      name={WINDOW_NAME}
      class="wallpaper-selector-window"
      title="Wallpaper Selector"
      gdkmonitor={gdkmonitor}
      anchor={0}
      halign={Gtk.Align.CENTER}
      valign={Gtk.Align.CENTER}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      default_width={960}
      default_height={640}
      $={(self) => {
        // Capture phase: Escape must be seen BEFORE the focused search
        // entry consumes it (same pattern as hypr-pano).
        const keys = new Gtk.EventControllerKey();
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE);
        keys.connect("key-pressed", (_c, keyval) => {
          if (keyval === Gdk.KEY_Escape) {
            self.hide();
            return true;
          }
          return false;
        });
        self.add_controller(keys);
        // Every toggle-open re-scans: the spine, the effects gallery and
        // current.json may all have moved while the window was hidden.
        self.connect("map", () => {
          mapped = true;
          // Every toggle-open lands on the main grid: clear any drilled-in
          // selection first, or opens would stick on the last L2 view.
          // Every toggle-open re-scans: the spine, the effects gallery and
          // current.json may all have moved while the window was hidden.
          setSelected(null);
          if (!localApply && !eventBusy) {
            rescan();
            setStatus("Wallpapers — pick one to see its variants.");
          }
          // ON_DEMAND (like pano/capture/icme) so the dialog never grabs
          // the keyboard from other apps; present + focus put the cursor in
          // search on show, rofi-style.
          self.present();
          search.grab_focus();
        });
        self.connect("unmap", () => {
          mapped = false;
        });
      }}
    >
      {root}
    </window>
  );
}

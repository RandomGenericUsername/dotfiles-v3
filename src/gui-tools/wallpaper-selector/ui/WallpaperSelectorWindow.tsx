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
import { domainEvents, WALLPAPER_STATE_TOPIC } from "../lib/event-bus";
import { reloadIconManifest, resolveIcon } from "../lib/icon-registry";
import {
  filterWallpapers,
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
  const [applying, setApplying] = createState(false);

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

  function wallpaperCard(w: WallpaperEntry): Gtk.Widget {
    const card = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["ws-card"] });
    const overlay = new Gtk.Overlay();
    overlay.set_child(thumbPicture(w.path, 208, 130));
    if (w.live) overlay.add_overlay(liveBadge());
    const quick = new Gtk.Button({ label: "Apply", css_classes: ["ws-quick"], visible: false });
    quick.set_halign(Gtk.Align.END);
    quick.set_valign(Gtk.Align.END);
    quick.connect("clicked", () => doApply(w.path, w.name));
    overlay.add_overlay(quick);
    const motion = new Gtk.EventControllerMotion();
    motion.connect("enter", () => {
      if (!applying()) quick.set_visible(true);
    });
    motion.connect("leave", () => quick.set_visible(false));
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
      // The quick-Apply button lives inside the card: a press landing on it
      // must apply, not drill (the button's own clicked handler applies).
      // Coordinates arrive in card space — translate into the button.
      const [, qx, qy] = card.translate_coordinates(quick, x, y);
      if (qx >= 0 && qy >= 0 && qx < quick.get_width() && qy < quick.get_height()) return;
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
    apply.connect("clicked", () => doApply(v.path, v.name));
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
    titleLabel.set_label("WALLPAPERS");
    showEmpty(null);
    clearFlow();
    if (m === null) {
      placeholder("Loading…");
      return;
    }
    const list = filterWallpapers(m.wallpapers, query());
    if (list.length === 0) {
      placeholder(
        m.wallpapers.length === 0
          ? "No wallpapers in the install spine."
          : "No wallpapers match.",
      );
      return;
    }
    for (const w of list) flow.append(wallpaperCard(w));
  }

  function drill(w: WallpaperEntry): void {
    if (applying()) return;
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

  async function doApply(path: string, label: string): Promise<void> {
    if (applying()) return;
    setApplying(true);
    setStatus(`applying ${label}…`);
    // Local flag (not the `status` state): state getters may lag the setter,
    // and the collapse decision must be deterministic.
    let ok = false;
    try {
      await applyWallpaper(path);
      setStatus(`done · ${label}`);
      ok = true;
    } catch (error) {
      setStatus(`failed: ${error}`);
    } finally {
      setApplying(false);
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
    if (state === "applying") setStatus("wallpaper.state → applying…");
    else if (state === "done") {
      rescan();
      refreshChrome();
      setStatus("wallpaper.state → done · LIVE refreshed");
    } else if (state === "error") {
      rescan();
      refreshChrome();
      setStatus("wallpaper.state → error");
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
          if (!applying()) {
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

import { Gdk, Gtk } from "ags/gtk4";
import Rsvg from "gi://Rsvg?version=2.0";
import Pango from "gi://Pango?version=1.0";
import { createEffect, createState, type Accessor } from "ags";
import type {
  GroupMappingView,
  MappingShow,
  VariantMappingView,
} from "../lib/itr";
import type { PendingEdit, ShapeSelection, VocabularyPendingEdit } from "../lib/model";
import { previewMappings } from "../lib/model";
import { substitute } from "../lib/substitute";
import {
  extractShapes,
  mapClickToPixbuf,
  rewriteWithIdColors,
  shapeIdFromPixel,
  withHatchDefs,
  withHighlight,
  type ShapeInfo,
} from "../lib/svg";
import { templatePendingKey, type TemplatePendingEdit } from "../lib/templates";

const HOVER_COLOR = "#8fb8f5";
const SELECT_COLOR = "#6ea8fe";
const HIGHLIGHT_WIDTH = 24;
const CARD_SIZE = 150;

function pixbufForSvg(svg: string): GdkPixbuf.Pixbuf {
  const handle = Rsvg.Handle.new_from_data(new TextEncoder().encode(svg));
  const pixbuf = handle.get_pixbuf();
  if (pixbuf === null) throw new Error("librsvg refused the preview svg");
  return pixbuf;
}

/** Merged token table for one variant with pending edits applied. */
function mappingsFor(
  groupName: string,
  variant: VariantMappingView,
  pending: ReadonlyMap<string, PendingEdit>,
  vocabPending: ReadonlyMap<string, VocabularyPendingEdit>,
): Record<string, string> {
  return previewMappings(
    variant.mappings.map((entry) => ({
      placeholder: entry.placeholder,
      token: entry.token,
      origin: entry.origin,
    })),
    groupName,
    variant.variant,
    pending,
    vocabPending,
  );
}

function hasVariantOverride(
  view: VariantMappingView,
  groupName: string,
  pending: ReadonlyMap<string, PendingEdit>,
): boolean {
  if (view.mappings.some((entry) => entry.origin === "variant")) return true;
  for (const edit of pending.values()) {
    if (edit.group === groupName && edit.variant === view.variant) return true;
  }
  return false;
}

export interface PreviewProps {
  show: Accessor<MappingShow | null>;
  groupName: Accessor<string>;
  activeVariant: Accessor<string>;
  pending: Accessor<ReadonlyMap<string, PendingEdit>>;
  vocabPending: Accessor<ReadonlyMap<string, VocabularyPendingEdit>>;
  templatePending?: Accessor<ReadonlyMap<string, TemplatePendingEdit>>;
  newPlaceholders?: Accessor<ReadonlyMap<string, string>>;
  selection: Accessor<ShapeSelection | null>;
  showGroup: Accessor<boolean>;
  barBackground: Accessor<boolean>;
  onSelectVariant(variant: string): void;
  onSelectShape(selection: ShapeSelection | null): void;
  onToggleGroup(): void;
  onToggleBackdrop(): void;
  onClose(): void;
  diffContent: Gtk.Widget;
}

interface VariantRender {
  view: VariantMappingView;
  texture: Gdk.Texture;
  idPixbuf: GdkPixbuf.Pixbuf;
  shapes: ShapeInfo[];
  hasOverride: boolean;
}

interface CardWidgets {
  card: Gtk.Box;
  picture: Gtk.Picture;
  badge: Gtk.Label;
  click: Gtk.GestureClick;
  motion: Gtk.EventControllerMotion | null;
}

export function Preview(props: PreviewProps) {
  const [hover, setHover] = createState<string | null>(null);
  // ID pass depends on geometry only: cache per group/variant across rebuilds.
  const idCache = new Map<string, { pixbuf: GdkPixbuf.Pixbuf; shapes: ShapeInfo[] }>();
  // Latest render data per variant for hit-testing.
  const renders = new Map<string, VariantRender>();
  // Persistent card widgets per variant: created once, never destroyed on
  // state changes (only paintables, sizes, and classes update). Destroying a
  // widget mid-gesture segfaults; this design avoids it entirely.
  const cards = new Map<string, CardWidgets>();

  const currentGroup = (): GroupMappingView | undefined =>
    props.show()?.groups.find((g) => g.group === props.groupName());

  const listedVariants = (): VariantMappingView[] => {
    const current = currentGroup();
    if (!current) return [];
    if (!props.showGroup()) {
      const active = current.variants.find((v) => v.variant === props.activeVariant());
      return active ? [active] : current.variants.slice(0, 1);
    }
    return current.variants;
  };

  function renderVariant(
    group: GroupMappingView,
    show: MappingShow,
    view: VariantMappingView,
    isActive: boolean,
  ): VariantRender {
    const mappings = mappingsFor(group.group, view, props.pending(), props.vocabPending());
    const newPhs = props.newPlaceholders?.() ?? new Map();
    for (const [name, token] of newPhs) {
      mappings[name] = token;
    }

    const staged = props.templatePending?.() ?? new Map();
    let body = view.svg_body;
    const shapes = extractShapes(view.svg_body);
    for (const s of shapes) {
      const edit = staged.get(templatePendingKey(view.template_path, s.id));
      if (edit) {
        const re = new RegExp(`\\b${s.paintAttr}\\s*=\\s*"([^"]*)"`);
        const replacement = `${s.paintAttr}="{{${edit.newPlaceholder}}}"`;
        const elem = s.element.replace(re, replacement);
        body = body.replace(s.element, () => elem);
      }
    }

    let svg = withHatchDefs(substitute(body, mappings, show.palette));
    if (isActive) {
      const selection = props.selection();
      const hovered = hover();
      if (hovered !== null) {
        const [hoverVariant, hoverId] = hovered.split(":");
        if (hoverVariant === view.variant) {
          const shape = shapes.find((s) => s.id === Number(hoverId));
          if (shape) svg = withHighlight(svg, shape, HOVER_COLOR, HIGHLIGHT_WIDTH);
        }
      }
      if (selection && selection.variantName === view.variant) {
        const shape = shapes.find((s) => s.id === Number(selection.shapeId));
        if (shape) svg = withHighlight(svg, shape, SELECT_COLOR, HIGHLIGHT_WIDTH);
      }
    }
    const cacheKey = `${group.group}:${view.variant}`;
    let cached = idCache.get(cacheKey);
    if (!cached) {
      cached = {
        pixbuf: pixbufForSvg(rewriteWithIdColors(view.svg_body)),
        shapes,
      };
      idCache.set(cacheKey, cached);
    }
    const rendered: VariantRender = {
      view,
      texture: Gdk.Texture.new_for_pixbuf(pixbufForSvg(svg)),
      idPixbuf: cached.pixbuf,
      shapes: cached.shapes,
      hasOverride: hasVariantOverride(view, group.group, props.pending()),
    };
    renders.set(view.variant, rendered);
    return rendered;
  }

  function shapeAt(
    variantName: string,
    widget: Gtk.Widget,
    x: number,
    y: number,
  ): ShapeInfo | null {
    const rendered = renders.get(variantName);
    if (!rendered) return null;
    const alloc = widget.get_allocation();
    const point = mapClickToPixbuf(
      x,
      y,
      alloc.width,
      alloc.height,
      rendered.idPixbuf.get_width(),
      rendered.idPixbuf.get_height(),
    );
    if (point === null) return null;
    const pixels = rendered.idPixbuf.get_pixels();
    const stride = rendered.idPixbuf.get_rowstride();
    const channels = rendered.idPixbuf.get_n_channels();
    const offset = point.py * stride + point.px * channels;
    const id = shapeIdFromPixel(
      pixels[offset],
      pixels[offset + 1],
      pixels[offset + 2],
      channels === 4 ? pixels[offset + 3] : 255,
    );
    if (id === 0) return null;
    return rendered.shapes.find((shape) => shape.id === id) ?? null;
  }

  // ---- static skeleton ----
  const breadcrumb = new Gtk.Label({
    css_classes: ["template-path"],
    halign: Gtk.Align.START,
    ellipsize: Pango.EllipsizeMode.END,
    max_width_chars: 60,
  });
  const modeBadge = new Gtk.Label({ css_classes: ["mode", "templated"] });
  const progressText = new Gtk.Label({ css_classes: ["progress-text"] });
  const progressBar = new Gtk.ProgressBar({ css_classes: ["progress-bar"] });
  progressBar.set_size_request(80, 6);
  const progressBox = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 6,
    css_classes: ["progress"],
  });
  progressBox.append(progressText);
  progressBox.append(progressBar);

  const spacer = new Gtk.Box({ hexpand: true });
  const groupToggle = new Gtk.Button({ label: "Show whole group", css_classes: ["toggle"] });
  groupToggle.connect("clicked", () => {
    setHover(null);
    props.onToggleGroup();
  });
  const backdropToggle = new Gtk.Button({ label: "Bar background", css_classes: ["toggle"] });
  backdropToggle.connect("clicked", () => props.onToggleBackdrop());
  const closeButton = new Gtk.Button({ label: "Close", css_classes: ["toggle"] });
  closeButton.connect("clicked", () => props.onClose());

  const bar = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    css_classes: ["canvas-bar"],
    spacing: 10,
  });
  bar.append(breadcrumb);
  bar.append(modeBadge);
  bar.append(progressBox);
  bar.append(spacer);
  bar.append(groupToggle);
  bar.append(backdropToggle);
  bar.append(closeButton);

  const strip = new Gtk.FlowBox({
    homogeneous: false,
    column_spacing: 14,
    row_spacing: 14,
    min_children_per_line: 3,
    selection_mode: Gtk.SelectionMode.NONE,
  });
  const scroller = new Gtk.ScrolledWindow({
    hscrollbar_policy: Gtk.PolicyType.NEVER,
    vscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    hexpand: true,
    vexpand: true,
  });
  scroller.set_child(strip);

  const canvas = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["canvas"],
    hexpand: true,
    vexpand: true,
  });
  canvas.append(scroller);

  const diff = new Gtk.Box({ css_classes: ["diff"] });
  const diffScroll = new Gtk.ScrolledWindow({
    hscrollbar_policy: Gtk.PolicyType.NEVER,
    vscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    hexpand: true,
  });
  diffScroll.set_max_content_height(170);
  diffScroll.set_child(props.diffContent);
  diff.append(diffScroll);

  const root = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, hexpand: true, vexpand: true });
  root.append(bar);
  root.append(canvas);
  root.append(diff);

  const backdropProvider = new Gtk.CssProvider();
  canvas.get_style_context().add_provider(
    backdropProvider,
    Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
  );

  function ensureCard(view: VariantMappingView): CardWidgets {
    let widgets = cards.get(view.variant);
    if (widgets) return widgets;
    const picture = new Gtk.Picture({ content_fit: Gtk.ContentFit.CONTAIN });
    picture.set_size_request(CARD_SIZE, CARD_SIZE);
    const click = new Gtk.GestureClick();
    click.connect("pressed", (_gesture: object, _presses: number, x: number, y: number) => {
      if (view.variant === props.activeVariant()) {
        const shape = shapeAt(view.variant, picture, x, y);
        if (shape === null) {
          props.onSelectShape(null);
        } else {
          const staged = props.templatePending?.().get(templatePendingKey(view.template_path, shape.id));
          const placeholder = staged?.newPlaceholder ?? shape.placeholder;
          props.onSelectShape({
            variantName: view.variant,
            shapeId: String(shape.id),
            placeholder,
            literal: shape.literal ?? null,
            paintAttr: shape.paintAttr,
          });
        }
      } else {
        setHover(null);
        props.onSelectVariant(view.variant);
      }
    });
    picture.add_controller(click);
    const motion = new Gtk.EventControllerMotion();
    motion.connect("motion", (_controller: object, x: number, y: number) => {
      if (view.variant !== props.activeVariant()) return;
      const shape = shapeAt(view.variant, picture, x, y);
      const key = shape ? `${view.variant}:${shape.id}` : null;
      if (key !== hover()) setHover(key);
    });
    motion.connect("leave", () => setHover(null));
    picture.add_controller(motion);
    const card = new Gtk.Box({
      orientation: Gtk.Orientation.VERTICAL,
      css_classes: ["vcard"],
    });
    card.append(new Gtk.Label({ label: view.variant, css_classes: ["vname"] }));
    card.append(picture);
    const badge = new Gtk.Label({ label: "variant override", css_classes: ["badge"] });
    card.append(badge);
    strip.append(card);
    widgets = { card, picture, badge, click, motion };
    cards.set(view.variant, widgets);
    return widgets;
  }

  function dropMissingCards(variants: VariantMappingView[]): void {
    for (const [name, widgets] of cards) {
      if (!variants.some((v) => v.variant === name)) {
        strip.remove(widgets.card);
        cards.delete(name);
      }
    }
  }

  // Chrome: breadcrumb, mode badge, progress meter, toggles, backdrop.
  createEffect(() => {
    const show = props.show();
    const group = currentGroup();
    if (!show || !group) return;
    const active = group.variants.find((v) => v.variant === props.activeVariant());
    if (active) {
      breadcrumb.set_label(active.template_path);
      const shapes = extractShapes(active.svg_body);
      const staged = props.templatePending?.() ?? new Map();
      let unassigned = 0;
      for (const s of shapes) {
        const edit = staged.get(templatePendingKey(active.template_path, s.id));
        const ph = edit?.newPlaceholder ?? s.placeholder;
        if (ph === null) unassigned++;
      }
      const total = shapes.length;
      const assigned = total - unassigned;
      if (unassigned > 0) {
        modeBadge.set_label(`bare — ${unassigned} unassigned`);
        modeBadge.set_css_classes(["mode", "bare"]);
        progressBox.set_visible(true);
        progressText.set_label(`assigned ${assigned}/${total}`);
        progressBar.set_fraction(total > 0 ? assigned / total : 0);
      } else {
        modeBadge.set_label("templated");
        modeBadge.set_css_classes(["mode", "templated"]);
        progressBox.set_visible(false);
      }
    }
    groupToggle.set_css_classes(props.showGroup() ? ["toggle", "on"] : ["toggle"]);
    backdropToggle.set_css_classes(props.barBackground() ? ["toggle", "on"] : ["toggle"]);
    if (props.barBackground()) {
      const barBg = show.palette["background"] ?? "#16181d";
      backdropProvider.load_from_string(`.canvas.bar-bg { background-color: ${barBg}; }`);
      if (!canvas.get_css_classes().includes("bar-bg")) {
        canvas.set_css_classes([...canvas.get_css_classes(), "bar-bg"]);
      }
    } else {
      canvas.set_css_classes(canvas.get_css_classes().filter((c) => c !== "bar-bg"));
    }
  });

  // Paint: textures, sizes, classes, badges. Widgets persist; only paintables
  // and properties update, so in-flight gestures are never orphaned (§4.6).
  createEffect(() => {
    const show = props.show();
    const group = currentGroup();
    if (!show || !group) return;
    props.pending();
    props.vocabPending();
    props.templatePending?.();
    props.newPlaceholders?.();
    props.selection();
    hover();
    const active = props.activeVariant();
    const variants = listedVariants();
    dropMissingCards(variants);
    for (const view of variants) {
      const isActive = view.variant === active;
      const rendered = renderVariant(group, show, view, isActive);
      const widgets = ensureCard(view);
      widgets.picture.set_paintable(rendered.texture);
      widgets.picture.set_size_request(CARD_SIZE, CARD_SIZE);
      widgets.card.set_css_classes(isActive ? ["vcard", "main"] : ["vcard"]);
      widgets.badge.set_visible(rendered.hasOverride);
    }
  });

  return root;
}

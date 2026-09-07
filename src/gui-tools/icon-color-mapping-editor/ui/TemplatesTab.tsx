import { Gdk, Gtk } from "ags/gtk4";
import Rsvg from "gi://Rsvg?version=2.0";
import Pango from "gi://Pango?version=1.0";
import { createEffect, createState, type Accessor } from "ags";
import { templateAnalyze, type MappingShow } from "../lib/itr";
import type { EditorInputs } from "../lib/inputs";
import type {
  ManifestPending,
  TemplateMode,
  TemplatePendingEdit,
  WorkingShape,
} from "../lib/templates";
import {
  applyTemplateEdit,
  bareProgress,
  buildTreeEntries,
  describeTemplatePending,
  isValidPlaceholderName,
  mappingsForTemplate,
  modeOf,
  paintValueOf,
  renderPreviewBody,
  templatePathsFrom,
  workingFrom,
  type TemplateTreeEntry,
} from "../lib/templates";
import { renderPendingMarkup } from "../lib/diff";
import { substitute } from "../lib/substitute";
import {
  extractShapes,
  mapClickToPixbuf,
  rewriteWithIdColors,
  shapeIdFromPixel,
  withHighlight,
  type ShapeInfo,
} from "../lib/svg";

const SELECT_COLOR = "#6ea8fe";
const HIGHLIGHT_WIDTH = 24;
const CARD_SIZE = 340;

function pixbufForSvg(svg: string): GdkPixbuf.Pixbuf {
  const handle = Rsvg.Handle.new_from_data(new TextEncoder().encode(svg));
  const pixbuf = handle.get_pixbuf();
  if (pixbuf === null) throw new Error("librsvg refused the preview svg");
  return pixbuf;
}

export interface TemplatesTabProps {
  show: Accessor<MappingShow | null>;
  inputs: Accessor<EditorInputs>;
  templatePending: Accessor<ReadonlyMap<string, TemplatePendingEdit>>;
  newPlaceholders: Accessor<ReadonlyMap<string, string>>;
  manifestPendings: Accessor<ReadonlyArray<ManifestPending>>;
  onStageTemplate(edit: TemplatePendingEdit): void;
  onStageNewPlaceholder(name: string, token: string): void;
  onStageManifest(entry: ManifestPending): void;
  onSave(): void;
  onRevert(): void;
  onDialogOpenChange?(open: boolean): void;
}

type Choice =
  | { kind: "existing"; ph: string }
  | { kind: "new"; name: string; token: string }
  | null;

export function TemplatesTab(props: TemplatesTabProps) {
  const [modes, setModes] = createState<Map<string, TemplateMode>>(new Map());
  const [working, setWorking] = createState<Map<string, WorkingShape[]>>(new Map());
  const [selectedPath, setSelectedPath] = createState<string | null>(null);
  const [selectedId, setSelectedId] = createState<number | null>(null);
  const [choice, setChoice] = createState<Choice>(null);
  const [newName, setNewName] = createState("");
  const [loadError, setLoadError] = createState<string | null>(null);
  const [texture, setTexture] = createState<Gdk.Texture | null>(null);
  const [idPixbuf, setIdPixbuf] = createState<GdkPixbuf.Pixbuf | null>(null);
  const [idShapes, setIdShapes] = createState<ShapeInfo[]>([]);

  function currentShapes(): WorkingShape[] {
    const path = selectedPath();
    return path ? (working().get(path) ?? []) : [];
  }

  function currentMappings(): Record<string, string> {
    const path = selectedPath();
    if (!path) return {};
    return mappingsForTemplate(props.show(), path, props.newPlaceholders());
  }

  function hexOfToken(token: string): string | null {
    const palette = props.show()?.palette ?? {};
    return token.startsWith("#") ? token : (palette[token] ?? null);
  }

  function shapeHex(shape: WorkingShape): string | null {
    if (shape.ph !== null) {
      const token = currentMappings()[shape.ph];
      if (token === undefined) return null;
      return hexOfToken(token);
    }
    return shape.literal ?? null;
  }

  function workingBody(): string {
    const path = selectedPath();
    if (!path) return "";
    const show = props.show();
    if (show) {
      for (const group of show.groups) {
        for (const variant of group.variants) {
          if (variant.template_path === path) return variant.svg_body;
        }
      }
    }
    return "";
  }

  function previewSvg(): string {
    const body = workingBody();
    const shapes = currentShapes();
    if (body === "") return "";
    const mappings = currentMappings();
    const palette = props.show()?.palette ?? {};
    const painted = renderPreviewBody(body, shapes, (s) =>
      s.ph !== null ? `{{${s.ph}}}` : s.literal,
    );
    let svg = substitute(painted, mappings, palette);
    const sel = selectedId();
    if (sel !== null) {
      const info = extractShapes(body).find((s) => s.id === sel);
      if (info) svg = withHighlight(svg, info, SELECT_COLOR, HIGHLIGHT_WIDTH);
    }
    return svg;
  }

  async function loadAll(): Promise<void> {
    const paths = templatePathsFrom(props.show());
    const modesNext = new Map<string, TemplateMode>();
    const workingNext = new Map<string, WorkingShape[]>();
    try {
      for (const path of paths) {
        const analysis = await templateAnalyze(path);
        modesNext.set(path, analysis.mode);
        workingNext.set(path, analysis.shapes.map(workingFrom));
      }
      setModes(modesNext);
      setWorking(workingNext);
      if (!selectedPath() && paths.length > 0) {
        setSelectedPath(paths[0]);
        setSelectedId(null);
      }
      setLoadError(null);
    } catch (error) {
      setLoadError(String(error));
    }
  }

  createEffect(() => {
    props.show();
    void loadAll();
  });

  function selectTemplate(entry: TemplateTreeEntry): void {
    setSelectedPath(entry.path);
    setSelectedId(null);
    setChoice(null);
    setNewName("");
  }

  function chooseTemplatePath(): void {
    const dialog = new Gtk.FileChooserNative({
      title: "Template file",
      action: Gtk.FileChooserAction.OPEN,
      modal: true,
    });
    props.onDialogOpenChange?.(false);
    dialog.connect("response", (_dialog: object, response: number) => {
      if (response === Gtk.ResponseType.ACCEPT) {
        const file = dialog.get_file()?.get_path();
        if (file) void loadSingle(file);
      }
      dialog.destroy();
      props.onDialogOpenChange?.(true);
    });
    dialog.show();
  }

  async function loadSingle(path: string): Promise<void> {
    try {
      const analysis = await templateAnalyze(path);
      const modesNext = new Map(modes());
      modesNext.set(path, analysis.mode);
      setModes(modesNext);
      const workingNext = new Map(working());
      workingNext.set(path, analysis.shapes.map(workingFrom));
      setWorking(workingNext);
      setSelectedPath(path);
      setSelectedId(null);
      setChoice(null);
      setNewName("");
    } catch (error) {
      setLoadError(String(error));
    }
  }

  function assign(): void {
    const path = selectedPath();
    const sel = selectedId();
    const ch = choice();
    const shapes = currentShapes();
    if (!path || sel === null || !ch) return;
    const target = shapes.find((s) => s.id === sel);
    if (!target) return;

    const oldValue = paintValueOf(target);
    const existing = props.templatePending().get(`${path}\u0000${sel}`);
    const edit: TemplatePendingEdit = {
      templatePath: path,
      shapeId: sel,
      attr: target.attr,
      oldValue: existing?.oldValue ?? oldValue,
      newPlaceholder: ch.kind === "existing" ? ch.ph : ch.name,
    };
    props.onStageTemplate(edit);
    if (ch.kind === "new") {
      props.onStageNewPlaceholder(ch.name, ch.token);
    }
    // Brand-new files (not referenced by the manifest) gain a manifest entry.
    const manifestPaths = new Set(templatePathsFrom(props.show()));
    if (!manifestPaths.has(path)) {
      const entry = manifestEntryFor(path, props.inputs().templateRoot, props.inputs().iconsYaml);
      const alreadyStaged = props.manifestPendings().some(
        (m) => m.group === entry.group && m.variant === entry.variant,
      );
      if (!alreadyStaged) props.onStageManifest(entry);
    }
    const newWorking = applyTemplateEdit(shapes, edit);
    const workingNext = new Map(working());
    workingNext.set(path, newWorking);
    setWorking(workingNext);
    const modesNext = new Map(modes());
    modesNext.set(path, modeOf(newWorking));
    setModes(modesNext);
    setChoice(null);
  }

  // --- preview widgets ---
  const picture = new Gtk.Picture({ content_fit: Gtk.ContentFit.CONTAIN });
  picture.set_size_request(CARD_SIZE, CARD_SIZE);

  function shapeAt(x: number, y: number): number | null {
    const buf = idPixbuf();
    const shapes = idShapes();
    if (!buf || shapes.length === 0) return null;
    const alloc = picture.get_allocation();
    const point = mapClickToPixbuf(
      x,
      y,
      alloc.width,
      alloc.height,
      buf.get_width(),
      buf.get_height(),
    );
    if (point === null) return null;
    const pixels = buf.get_pixels();
    const stride = buf.get_rowstride();
    const channels = buf.get_n_channels();
    const offset = point.py * stride + point.px * channels;
    const id = shapeIdFromPixel(
      pixels[offset],
      pixels[offset + 1],
      pixels[offset + 2],
      channels === 4 ? pixels[offset + 3] : 255,
    );
    if (id === 0) return null;
    return shapes.find((s) => s.id === id)?.id ?? null;
  }

  const click = new Gtk.GestureClick();
  click.connect("pressed", (_g: object, _n: number, x: number, y: number) => {
    setSelectedId(shapeAt(x, y));
    setChoice(null);
  });
  picture.add_controller(click);

  createEffect(() => {
    const body = workingBody();
    const shapes = currentShapes();
    const sel = selectedId();
    props.newPlaceholders();
    setTexture(
      body === "" ? null : Gdk.Texture.new_for_pixbuf(pixbufForSvg(previewSvg())),
    );
    setShapesForHitTest(body);
  });

  function setShapesForHitTest(body: string): void {
    const info = extractShapes(body);
    setIdShapes(info);
    setIdPixbuf(body === "" ? null : pixbufForSvg(rewriteWithIdColors(body)));
  }

  // --- left column ---
  const filePath = new Gtk.Label({
    css_classes: ["path", "rw"],
    xalign: 0,
    ellipsize: Pango.EllipsizeMode.END,
    hexpand: true,
  });
  const pick = new Gtk.Button({ label: "⋯", css_classes: ["pick"] });
  pick.connect("clicked", chooseTemplatePath);
  const pathRow = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 });
  pathRow.append(filePath);
  pathRow.append(pick);

  const tree = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["tree"] });

  function rebuildTree(): void {
    let child = tree.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      tree.remove(child);
      child = next;
    }
    const entries = buildTreeEntries(props.inputs().templateRoot, modes());
    let lastGroup: string | null = null;
    for (const entry of entries) {
      if (entry.group !== lastGroup) {
        tree.append(new Gtk.Label({ label: entry.group, css_classes: ["group"], xalign: 0 }));
        lastGroup = entry.group;
      }
      const badge = new Gtk.Label({
        label: entry.mode === "bare" ? "bare" : "templated",
        css_classes: ["badge", entry.mode === "bare" ? "b" : "t"],
      });
      const button = new Gtk.Button({ css_classes: ["item"] });
      const inner = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 });
      const label = new Gtk.Label({ label: entry.label, xalign: 0, hexpand: true });
      inner.append(label);
      inner.append(badge);
      button.set_child(inner);
      button.connect("clicked", () => selectTemplate(entry));
      tree.append(button);
    }
  }

  createEffect(() => {
    modes();
    props.inputs();
    rebuildTree();
  });

  // --- center column ---
  const fileLabel = new Gtk.Label({ css_classes: ["file"], xalign: 0 });
  const modeBadge = new Gtk.Label({ css_classes: ["mode"] });
  const progressText = new Gtk.Label({ label: "", css_classes: ["progress-text"] });
  const progressBar = new Gtk.LevelBar({ css_classes: ["progress-bar"] });
  progressBar.set_show_value(false);
  const progressWrap = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["progress"],
  });
  progressWrap.append(progressText);
  progressWrap.append(progressBar);

  const canvasBar = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 10,
    css_classes: ["canvas-bar"],
  });
  canvasBar.append(fileLabel);
  canvasBar.append(modeBadge);
  const spacer = new Gtk.Box({ hexpand: true });
  canvasBar.append(spacer);
  canvasBar.append(progressWrap);

  const canvas = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["canvas"],
    hexpand: true,
    vexpand: true,
  });
  canvas.append(picture);

  const diffLabel = new Gtk.Label({
    css_classes: ["diff-text"],
    xalign: 0,
    wrap: true,
    selectable: true,
  });
  const diffBox = new Gtk.Box({ css_classes: ["diff"] });
  diffBox.append(diffLabel);

  createEffect(() => {
    const pending = props.templatePending();
    const newPh = props.newPlaceholders();
    const manifest = props.manifestPendings();
    const w = working();
    if (pending.size === 0 && newPh.size === 0 && manifest.length === 0) {
      diffLabel.set_text("— no changes —");
      return;
    }
    const rows = describeTemplatePending({
      templatePendings: pending,
      newPlaceholders: newPh,
      manifestPendings: manifest,
      workingByPath: w,
    });
    diffLabel.set_markup(renderPendingMarkup(rows));
  });

  // --- right column ---
  const selShape = kvRow("Shape");
  const selPaint = kvRow("Paints with");
  const selRes = kvRow("Resolves to");
  const selUse = kvRow("Used by");
  const selInfo = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["sel-info"] });
  for (const row of [selShape, selPaint, selRes, selUse]) selInfo.append(row.row);

  const curChip = new Gtk.Box({ css_classes: ["chip"] });
  curChip.set_size_request(20, 20);
  const curLabel = new Gtk.Label({ label: "select a shape", css_classes: ["label"] });
  const curRow = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8, css_classes: ["current"] });
  curRow.append(curChip);
  curRow.append(curLabel);

  const phList = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 4, css_classes: ["phlist"] });
  const newNameEntry = new Gtk.Entry({ css_classes: ["newph-input"] });
  newNameEntry.set_placeholder_text("COLOR_COUNTOUR");
  const newErr = new Gtk.Label({ css_classes: ["err"], xalign: 0 });
  const newTokLabel = new Gtk.Label({ css_classes: ["toklabel"], xalign: 0 });
  const mini = new Gtk.Grid({ column_spacing: 4, row_spacing: 4, css_classes: ["mini"] });

  const assignBtn = new Gtk.Button({ label: "Assign", css_classes: ["btn", "primary"], hexpand: true });
  assignBtn.connect("clicked", assign);

  const revertBtn = new Gtk.Button({ label: "Revert", css_classes: ["btn"], hexpand: true });
  revertBtn.connect("clicked", () => {
    setChoice(null);
    setNewName("");
    props.onRevert();
    void loadAll();
  });
  const saveBtn = new Gtk.Button({ label: "Save templates", css_classes: ["btn", "primary"], hexpand: true });
  saveBtn.connect("clicked", () => void props.onSave());

  const right = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["col", "right"] });
  right.append(new Gtk.Label({ label: "Selection", css_classes: ["icme-pane-title"] }));
  right.append(selInfo);
  right.append(new Gtk.Label({ label: "Assign placeholder", css_classes: ["icme-pane-title"] }));
  const assignBox = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["assign"] });
  assignBox.append(curRow);
  assignBox.append(phList);
  const newPhBox = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["newph"] });
  newPhBox.append(new Gtk.Label({ label: "…or a new placeholder", xalign: 0, css_classes: ["toklabel"] }));
  newPhBox.append(newNameEntry);
  newPhBox.append(newErr);
  newPhBox.append(newTokLabel);
  newPhBox.append(mini);
  assignBox.append(newPhBox);
  const assignBar = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8, css_classes: ["assignbar"] });
  assignBar.append(assignBtn);
  assignBox.append(assignBar);
  right.append(assignBox);
  const footer = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8, css_classes: ["footer"] });
  footer.append(revertBtn);
  footer.append(saveBtn);
  right.append(footer);

  const left = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["col", "left"] });
  left.append(new Gtk.Label({ label: "Template file (edited by tool)", css_classes: ["icme-pane-title"] }));
  left.append(pathRow);
  left.append(new Gtk.Label({ label: "Templates", css_classes: ["icme-pane-title"] }));
  const treeScroll = new Gtk.ScrolledWindow({
    hscrollbar_policy: Gtk.PolicyType.NEVER,
    vscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    hexpand: true,
    vexpand: true,
  });
  treeScroll.set_child(tree);
  left.append(treeScroll);
  const hint = new Gtk.Label({
    label:
      "<b>Bare SVG</b> = a downloaded icon with real hex colors and no " +
      "<code>{{…}}</code> placeholders. Click each shape to assign an existing " +
      "or new placeholder.",
    css_classes: ["hint"],
    xalign: 0,
    wrap: true,
    use_markup: true,
  });
  left.append(hint);

  const center = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["col", "center"],
    hexpand: true,
    vexpand: true,
  });
  center.append(canvasBar);
  const canvasScroll = new Gtk.ScrolledWindow({
    hscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    vscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    hexpand: true,
    vexpand: true,
  });
  canvasScroll.set_child(canvas);
  center.append(canvasScroll);
  center.append(diffBox);

  const root = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    css_classes: ["app"],
    hexpand: true,
    vexpand: true,
  });
  root.append(left);
  root.append(center);
  root.append(right);

  // --- reactive chrome ---
  createEffect(() => {
    const path = selectedPath();
    const shapes = currentShapes();
    fileLabel.set_label(path ?? "");
    const mode = modeOf(shapes);
    modeBadge.set_label(mode === "bare" ? "bare — assign placeholders" : "templated");
    modeBadge.set_css_classes(["mode", mode]);
    const prog = bareProgress(shapes);
    if (mode === "bare") {
      progressWrap.set_visible(true);
      progressText.set_label(`assigned ${prog.assigned}/${prog.total}`);
      progressBar.set_value(prog.total > 0 ? prog.assigned / prog.total : 0);
    } else {
      progressWrap.set_visible(false);
    }
    picture.set_paintable(texture());
    filePath.set_label(path ?? "…");
  });

  createEffect(() => {
    const shapes = currentShapes();
    const sel = selectedId();
    const shape = shapes.find((s) => s.id === sel) ?? null;
    selShape.value.set_label(shape ? String(shape.id) : "—");
    selPaint.value.set_label(
      !shape ? "—" : shape.ph !== null ? `{{${shape.ph}}}` : (shape.literal ?? "—"),
    );
    selRes.value.set_label(
      !shape
        ? "—"
        : shape.ph !== null
          ? `${currentMappings()[shape.ph] ?? "unmapped"} · ${shapeHex(shape) ?? "—"}`
          : "(literal color)",
    );
    selUse.value.set_label(
      !shape ? "—" : shape.ph !== null ? `usage ×${usageCount(shape.ph)}` : "this template only",
    );
    if (!shape) {
      curChip.set_css_classes(["chip", "missing"]);
      curLabel.set_label("select a shape");
    } else {
      const hex = shapeHex(shape);
      const provider = new Gtk.CssProvider();
      provider.load_from_string(`.chip-cur { background-color: ${hex ?? "#333"}; }`);
      curChip.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
      curChip.set_css_classes(["chip", "chip-cur"]);
      curLabel.set_label(shape.ph !== null ? `{{${shape.ph}}}` : `literal ${shape.literal}`);
    }
  });

  createEffect(() => {
    const shapes = currentShapes();
    const sel = selectedId();
    const shape = shapes.find((s) => s.id === sel) ?? null;
    const mapping = currentMappings();
    const names = [...new Set([...Object.keys(mapping), ...props.newPlaceholders().keys()])].sort();
    let child = phList.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      phList.remove(child);
      child = next;
    }
    for (const name of names) {
      const token = mapping[name];
      const hex = hexOfToken(token ?? "");
      const isCur = shape?.ph === name;
      const isNew = props.newPlaceholders().has(name);
      const picked = choice()?.kind === "existing" && choice()?.ph === name;
      const chip = new Gtk.Box({ css_classes: ["chip"] });
      chip.set_size_request(20, 20);
      const provider = new Gtk.CssProvider();
      provider.load_from_string(`.chip-ph { background-color: ${hex ?? "#444"}; }`);
      chip.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
      chip.set_css_classes(["chip", "chip-ph"]);
      const nameLabel = new Gtk.Label({ label: `{{${name}}}`, css_classes: ["name"] });
      const tokLabel = new Gtk.Label({ label: `${token ?? "unmapped"} · ${hex ?? "—"}`, css_classes: ["tok"] });
      const text = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
      text.append(nameLabel);
      text.append(tokLabel);
      const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 9 });
      row.append(chip);
      row.append(text);
      if (isCur) row.append(new Gtk.Label({ label: "current", css_classes: ["cur"] }));
      if (isNew) row.append(new Gtk.Label({ label: "new", css_classes: ["cur", "new"] }));
      const useLabel = new Gtk.Label({ label: `×${usageCount(name)}`, css_classes: ["use"] });
      row.append(useLabel);
      const button = new Gtk.Button({
        css_classes: ["phrow", ...(picked ? ["picked"] : [])],
      });
      button.set_child(row);
      button.connect("clicked", () => {
        setChoice({ kind: "existing", ph: name });
        setNewName("");
      });
      phList.append(button);
    }
  });

  createEffect(() => {
    const raw = newName();
    const name = raw.trim().toUpperCase();
    const valid = isValidPlaceholderName(name);
    newErr.set_label(name && !valid ? "A–Z, 0–9 and _ only (e.g. COLOR_COUNTOUR)" : "");
    newTokLabel.set_label(
      valid ? `Vocabulary default for ${name} (defaults.yaml)` : "Vocabulary default (defaults.yaml)",
    );
    let child = mini.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      mini.remove(child);
      child = next;
    }
    const palette = props.show()?.palette ?? {};
    const colorKeys = Object.keys(palette)
      .filter((k) => /^color\d+$/.test(k))
      .sort((a, b) => Number(a.slice(5)) - Number(b.slice(5)));
    colorKeys.forEach((token, i) => {
      const picked = choice()?.kind === "new" && choice()?.token === token;
      const cell = new Gtk.Button({
        css_classes: ["cell", ...(picked ? ["picked"] : [])],
      });
      cell.set_tooltip_text(`${token} ${palette[token]}`);
      const fill = new Gtk.Box({ hexpand: true, vexpand: true });
      const provider = new Gtk.CssProvider();
      provider.load_from_string(`.mini-fill { background-color: ${palette[token]}; }`);
      fill.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
      fill.set_css_classes(["mini-fill"]);
      cell.set_child(fill);
      cell.connect("clicked", () => {
        if (valid) setChoice({ kind: "new", name, token });
      });
      mini.attach(cell, i % 8, Math.floor(i / 8), 1, 1);
    });
    const sel = selectedId();
    const shapes = currentShapes();
    const shape = shapes.find((s) => s.id === sel) ?? null;
    const ch = choice();
    assignBtn.set_sensitive(
      shape !== null && ch !== null && (ch.kind === "existing" || (ch.kind === "new" && valid)),
    );
  });

  newNameEntry.connect("changed", () => {
    setChoice(null);
    setNewName(newNameEntry.get_text());
  });

  function usageCount(ph: string): number {
    let count = 0;
    for (const shapes of working().values()) {
      count += shapes.filter((s) => s.ph === ph).length;
    }
    return count;
  }

  return root;
}

function manifestEntryFor(
  templatePath: string,
  templateRoot: string,
  manifestPath: string,
): ManifestPending {
  let rel = templatePath;
  if (templateRoot !== "" && templatePath.startsWith(templateRoot)) {
    rel = templatePath.slice(templateRoot.length).replace(/^\/+/, "");
  }
  const parts = rel.split("/").filter(Boolean);
  const file = parts.pop() ?? "icon.svg";
  return {
    manifestPath,
    group: parts[1] ?? parts[0] ?? file,
    variant: parts[2] ?? parts[1] ?? "default",
    template: rel,
    output: file,
  };
}

function kvRow(label: string): { row: Gtk.Box; value: Gtk.Label } {
  const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 });
  row.append(new Gtk.Label({ label, css_classes: ["kv-key"], xalign: 0 }));
  const value = new Gtk.Label({ label: "—", css_classes: ["kv-value"], xalign: 1, hexpand: true });
  row.append(value);
  return { row, value };
}

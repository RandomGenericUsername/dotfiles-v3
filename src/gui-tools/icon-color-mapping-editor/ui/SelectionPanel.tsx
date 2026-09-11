import { Gtk } from "ags/gtk4";
import { createEffect, createState, type Accessor } from "ags";
import type { MappingShow } from "../lib/itr";
import type { ShapeSelection } from "../lib/model";
import { extractShapes, usageCount } from "../lib/svg";
import {
  isValidPlaceholderName,
  templatePendingKey,
  type TemplatePendingEdit,
} from "../lib/templates";

export interface CurrentToken {
  token: string;
  hex: string | null;
}

export interface SelectionPanelProps {
  show: Accessor<MappingShow | null>;
  groupName: Accessor<string>;
  activeVariant: Accessor<string>;
  selection: Accessor<ShapeSelection | null>;
  currentToken: Accessor<CurrentToken | null>;
  templatePending: Accessor<ReadonlyMap<string, TemplatePendingEdit>>;
  newPlaceholders: Accessor<ReadonlyMap<string, string>>;
  inspectorMode: Accessor<"mapping" | "template">;
  onSetInspectorMode(mode: "mapping" | "template"): void;
  onSelectShapeId(shapeId: string): void;
  onStageTemplate(edit: TemplatePendingEdit): void;
  onStageNewPlaceholder(name: string, token: string): void;
}

function kvRow(label: string): { row: Gtk.Box; value: Gtk.Label } {
  const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 });
  row.append(new Gtk.Label({ label, css_classes: ["kv-key"], xalign: 0 }));
  const value = new Gtk.Label({ label: "—", css_classes: ["kv-value"], xalign: 1, hexpand: true });
  row.append(value);
  return { row, value };
}

function isColorValue(value: string | undefined): value is string {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
}

type Choice =
  | { kind: "existing"; ph: string }
  | { kind: "new"; name: string; token?: string }
  | null;

export function SelectionPanel(props: SelectionPanelProps) {
  const [choice, setChoice] = createState<Choice>(null);
  const [newName, setNewName] = createState("");

  const root = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["sel-panel"],
  });
  root.append(new Gtk.Label({ label: "Selection", css_classes: ["icme-pane-title"] }));

  const shape = kvRow("Shape");
  const placeholder = kvRow("Placeholder");
  const reassignBtn = new Gtk.Button({
    label: "Reassign ➔",
    css_classes: ["quick-reassign-btn"],
  });
  reassignBtn.connect("clicked", () => props.onSetInspectorMode("template"));
  placeholder.row.append(reassignBtn);

  const mapsTo = kvRow("Maps to");
  const usedBy = kvRow("Used by");
  root.append(shape.row);
  root.append(placeholder.row);
  root.append(mapsTo.row);
  root.append(usedBy.row);

  // Segmented Mode Navigation: [ Color Mapping | Shape Placeholder ]
  const nav = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    css_classes: ["inspector-nav"],
    spacing: 4,
  });
  const tabBtnMapping = new Gtk.Button({
    label: "Color Mapping",
    css_classes: ["inspector-tab-btn", "active"],
    hexpand: true,
  });
  const tabBtnTemplateBox = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 4,
    halign: Gtk.Align.CENTER,
  });
  tabBtnTemplateBox.append(new Gtk.Label({ label: "Shape Placeholder" }));
  const bareDot = new Gtk.Box({ css_classes: ["badge-dot"] });
  bareDot.set_visible(false);
  tabBtnTemplateBox.append(bareDot);

  const tabBtnTemplate = new Gtk.Button({
    css_classes: ["inspector-tab-btn"],
    hexpand: true,
  });
  tabBtnTemplate.set_child(tabBtnTemplateBox);

  tabBtnMapping.connect("clicked", () => props.onSetInspectorMode("mapping"));
  tabBtnTemplate.connect("clicked", () => props.onSetInspectorMode("template"));
  nav.append(tabBtnMapping);
  nav.append(tabBtnTemplate);
  root.append(nav);

  // Template Sub-Pane (Visible when inspectorMode === "template")
  const templatePane = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
  root.append(templatePane);

  const bareNotice = new Gtk.Label({
    label: "⚠️ Bare shape: paints with literal hex color. Assign a placeholder below.",
    css_classes: ["bare-notice"],
    wrap: true,
    xalign: 0,
  });
  bareNotice.set_visible(false);
  templatePane.append(bareNotice);

  templatePane.append(new Gtk.Label({ label: "Assign placeholder", css_classes: ["icme-pane-title"] }));
  const phList = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 4, css_classes: ["phlist"] });
  templatePane.append(phList);

  // New Placeholder section
  const newPhBox = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["newph"] });
  newPhBox.append(new Gtk.Label({ label: "…or a new placeholder", css_classes: ["icme-pane-title"], xalign: 0 }));

  const newNameEntry = new Gtk.Entry({ css_classes: ["newph-input"] });
  newNameEntry.set_placeholder_text("COLOR_COUNTOUR");
  newPhBox.append(newNameEntry);

  const newErr = new Gtk.Label({ css_classes: ["err"], xalign: 0 });
  newPhBox.append(newErr);

  const newTokLabel = new Gtk.Label({
    label: "Vocabulary default (defaults.yaml)",
    css_classes: ["toklabel"],
    xalign: 0,
  });
  newPhBox.append(newTokLabel);

  const mini = new Gtk.Grid({ column_spacing: 3, row_spacing: 3, css_classes: ["mini"] });
  newPhBox.append(mini);

  const assignBtn = new Gtk.Button({
    label: "Assign Placeholder to Shape",
    css_classes: ["btn", "primary"],
    sensitive: false,
  });
  const assignBar = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, css_classes: ["assignbar"] });
  assignBar.append(assignBtn);
  newPhBox.append(assignBar);

  templatePane.append(newPhBox);

  // Shapes list
  root.append(new Gtk.Label({ label: "Shapes", css_classes: ["icme-pane-title"] }));
  const shapeList = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2 });
  root.append(shapeList);

  const shapeButtons = new Map<string, Gtk.Button>();
  let builtKey = "";

  function activeBody(): { bodies: string[]; body: string; templatePath: string } | null {
    const show = props.show();
    const group = show?.groups.find((g) => g.group === props.groupName());
    const view = group?.variants.find((v) => v.variant === props.activeVariant());
    if (!group || !view) return null;
    return {
      bodies: group.variants.map((v) => v.svg_body),
      body: view.svg_body,
      templatePath: view.template_path,
    };
  }

  function defaultToken(): string {
    const palette = props.show()?.palette ?? {};
    const keys = Object.keys(palette)
      .filter((k) => /^color\d+$/.test(k))
      .sort((a, b) => Number(a.slice(5)) - Number(b.slice(5)));
    return keys[0] ?? "color1";
  }

  function assign(): void {
    const sel = props.selection();
    const ch = choice();
    const active = activeBody();
    if (!sel || !ch || !active) return;
    const shapeIdNum = Number(sel.shapeId);
    const shape = extractShapes(active.body).find((s) => s.id === shapeIdNum);
    if (!shape) return;

    const staged = props.templatePending().get(templatePendingKey(active.templatePath, shape.id));
    const oldValue =
      staged?.oldValue ??
      (shape.placeholder !== null ? `{{${shape.placeholder}}}` : (shape.literal ?? ""));
    const isNew = ch.kind === "new";
    const edit: TemplatePendingEdit = {
      templatePath: active.templatePath,
      shapeId: shape.id,
      attr: shape.paintAttr,
      oldValue,
      newPlaceholder: isNew ? ch.name : ch.ph,
    };
    props.onStageTemplate(edit);
    if (isNew) {
      props.onStageNewPlaceholder(ch.name, ch.token ?? defaultToken());
    }
    setChoice(null);
    setNewName("");
    newNameEntry.set_text("");
    props.onSetInspectorMode("mapping");
  }

  assignBtn.connect("clicked", () => assign());
  newNameEntry.connect("activate", () => {
    const name = newNameEntry.get_text().trim().toUpperCase();
    if (!props.selection() || !isValidPlaceholderName(name)) return;
    if (choice()?.kind === "existing") return;
    const token = choice()?.kind === "new" ? choice()?.token : undefined;
    setChoice({ kind: "new", name, token });
    setNewName(name);
    assign();
  });

  newNameEntry.connect("changed", () => {
    const text = newNameEntry.get_text();
    if (choice()?.kind === "new") {
      const token = choice()?.token;
      setChoice(text.trim() === "" ? null : { kind: "new", name: text.trim().toUpperCase(), token });
    } else {
      setChoice(null);
    }
    setNewName(text);
  });

  const MINI_COLUMNS = 8;
  const miniCells = new Map<string, Gtk.Button>();

  function rebuildMini(palette: Record<string, string>): void {
    let child = mini.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      mini.remove(child);
      child = next;
    }
    miniCells.clear();
    const indexed = Object.keys(palette)
      .filter((k) => /^color\d+$/.test(k) && isColorValue(palette[k]))
      .sort((a, b) => Number(a.slice(5)) - Number(b.slice(5)));
    indexed.forEach((token, i) => {
      const button = new Gtk.Button({
        css_classes: ["cell"],
        tooltip_text: `${token} ${palette[token]}`,
      });
      const fill = new Gtk.Box({
        css_classes: ["fill", `fill-${token}`, "mini-fill"],
        hexpand: true,
        vexpand: true,
      });
      const provider = new Gtk.CssProvider();
      provider.load_from_string(`.fill-${token} { background-color: ${palette[token]}; }`);
      fill.get_style_context().add_provider(
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
      );
      button.set_child(fill);
      button.connect("clicked", () => {
        const name = newName().trim().toUpperCase();
        if (!isValidPlaceholderName(name)) return;
        setChoice({ kind: "new", name, token });
      });
      mini.attach(button, i % MINI_COLUMNS, Math.floor(i / MINI_COLUMNS), 1, 1);
      miniCells.set(token, button);
    });
  }

  function currentMappings(): Record<string, string> {
    const table: Record<string, string> = {};
    const show = props.show();
    if (show) {
      const group = show.groups.find((g) => g.group === props.groupName());
      const view = group?.variants.find((v) => v.variant === props.activeVariant());
      if (view) {
        for (const entry of view.mappings) {
          table[entry.placeholder] = entry.token;
        }
      }
    }
    for (const [name, token] of props.newPlaceholders()) {
      table[name] = token;
    }
    return table;
  }

  function hexOfToken(token: string): string | null {
    const palette = props.show()?.palette ?? {};
    return token.startsWith("#") ? token : (palette[token] ?? null);
  }

  function rebuildPhList(): void {
    let child = phList.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      phList.remove(child);
      child = next;
    }
    const sel = props.selection();
    const active = activeBody();
    const mapping = currentMappings();
    const names = [...new Set([...Object.keys(mapping), ...props.newPlaceholders().keys()])].sort();

    for (const name of names) {
      const token = mapping[name];
      const hex = token ? hexOfToken(token) : null;
      const isCur = sel?.placeholder === name;
      const isNew = props.newPlaceholders().has(name);
      const picked = choice()?.kind === "existing" && choice()?.ph === name;

      const chip = new Gtk.Box({ css_classes: ["chip"] });
      chip.set_size_request(20, 20);
      if (hex) {
        const provider = new Gtk.CssProvider();
        provider.load_from_string(`.chip-ph-${name} { background-color: ${hex}; }`);
        chip.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
        chip.set_css_classes(["chip", `chip-ph-${name}`]);
      } else {
        chip.set_css_classes(["chip", "missing"]);
      }

      const nameLabel = new Gtk.Label({ label: `{{${name}}}`, css_classes: ["name"], xalign: 0 });
      const tokLabel = new Gtk.Label({
        label: `${token ?? "unmapped"} · ${hex ?? "—"}`,
        css_classes: ["tok"],
        xalign: 0,
      });
      const text = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
      text.append(nameLabel);
      text.append(tokLabel);

      const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 9 });
      row.append(chip);
      row.append(text);
      if (isCur) row.append(new Gtk.Label({ label: "current", css_classes: ["cur"] }));
      if (isNew) row.append(new Gtk.Label({ label: "new", css_classes: ["cur", "new"] }));

      const count = active ? usageCount(active.bodies, name).shapes : 0;
      const useLabel = new Gtk.Label({
        label: `×${count}`,
        css_classes: ["use"],
        hexpand: true,
        xalign: 1,
      });
      row.append(useLabel);

      const button = new Gtk.Button({
        css_classes: ["phrow", ...(picked ? ["picked"] : [])],
      });
      button.set_child(row);
      button.connect("clicked", () => {
        setChoice({ kind: "existing", ph: name });
        newNameEntry.set_text("");
        setNewName("");
      });
      phList.append(button);
    }
  }

  function rebuildList(body: string, templatePath: string): void {
    let child = shapeList.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      shapeList.remove(child);
      child = next;
    }
    shapeButtons.clear();
    const staged = props.templatePending();
    for (const info of extractShapes(body)) {
      const override = staged.get(templatePendingKey(templatePath, info.id));
      const ph = override?.newPlaceholder ?? info.placeholder;
      const label = ph ? `${info.id} · {{${ph}}}` : `${info.id} · literal ${info.literal ?? "color"}`;
      const button = new Gtk.Button({ label, css_classes: ["shape-item"] });
      button.connect("clicked", () => props.onSelectShapeId(String(info.id)));
      shapeList.append(button);
      shapeButtons.set(String(info.id), button);
    }
  }

  createEffect(() => {
    const palette = props.show()?.palette;
    if (palette) rebuildMini(palette);
  });

  createEffect(() => {
    props.show();
    props.activeVariant();
    props.newPlaceholders();
    props.selection();
    choice();
    rebuildPhList();
  });

  createEffect(() => {
    const raw = newName();
    const name = raw.trim().toUpperCase();
    const valid = isValidPlaceholderName(name);
    newErr.set_label(name && !valid ? "A–Z, 0–9 and _ only (e.g. COLOR_COUNTOUR)" : "");
    newTokLabel.set_label(
      valid ? `Vocabulary default for ${name} (defaults.yaml)` : "Vocabulary default (defaults.yaml)",
    );
    const ch = choice();
    for (const [token, cell] of miniCells) {
      const picked = ch?.kind === "new" && ch.token === token;
      cell.set_css_classes(picked ? ["cell", "picked"] : ["cell"]);
    }
  });

  createEffect(() => {
    const sel = props.selection();
    const ch = choice();
    const raw = newName();
    const name = raw.trim().toUpperCase();
    const valid = isValidPlaceholderName(name);
    assignBtn.set_sensitive(
      sel !== null && (ch?.kind === "existing" || (valid && (ch === null || ch.kind === "new"))),
    );
  });

  createEffect(() => {
    const mode = props.inspectorMode();
    tabBtnMapping.set_css_classes(mode === "mapping" ? ["inspector-tab-btn", "active"] : ["inspector-tab-btn"]);
    tabBtnTemplate.set_css_classes(mode === "template" ? ["inspector-tab-btn", "active"] : ["inspector-tab-btn"]);
    templatePane.set_visible(mode === "template");
  });

  createEffect(() => {
    const active = activeBody();
    const selection = props.selection();
    const current = props.currentToken();
    const staged = props.templatePending();
    if (!active) {
      shape.value.set_label("—");
      placeholder.value.set_label("—");
      mapsTo.value.set_label("—");
      usedBy.value.set_label("—");
      reassignBtn.set_visible(false);
      bareNotice.set_visible(false);
      bareDot.set_visible(false);
      return;
    }
    const stagedFp = [...staged.entries()]
      .map(([k, v]) => `${k}>${v.newPlaceholder}`)
      .join("|");
    const key = `${props.groupName()}:${props.activeVariant()}:${stagedFp}`;
    if (key !== builtKey) {
      rebuildList(active.body, active.templatePath);
      builtKey = key;
    }
    const selectedId =
      selection?.variantName === props.activeVariant() ? selection.shapeId : null;
    for (const [id, button] of shapeButtons) {
      button.set_css_classes(id === selectedId ? ["shape-item", "active"] : ["shape-item"]);
    }

    if (!selection || selection.variantName !== props.activeVariant()) {
      shape.value.set_label("—");
      placeholder.value.set_label("—");
      mapsTo.value.set_label("—");
      usedBy.value.set_label("—");
      reassignBtn.set_visible(false);
      bareNotice.set_visible(false);
      bareDot.set_visible(false);
      tabBtnMapping.set_sensitive(true);
      return;
    }

    shape.value.set_label(selection.shapeId);
    const isBare = selection.placeholder === null;

    if (isBare) {
      placeholder.value.set_label(`literal ${selection.literal ?? "color"}`);
      mapsTo.value.set_label("(static color — no placeholder)");
      usedBy.value.set_label("this shape only");
      reassignBtn.set_visible(false);
      bareNotice.set_visible(true);
      bareDot.set_visible(true);
      tabBtnMapping.set_sensitive(false);
      props.onSetInspectorMode("template");
    } else {
      placeholder.value.set_label(`{{${selection.placeholder}}}`);
      reassignBtn.set_visible(true);
      bareNotice.set_visible(false);
      bareDot.set_visible(false);
      tabBtnMapping.set_sensitive(true);

      if (current) {
        mapsTo.value.set_label(current.hex ? `${current.token} · ${current.hex}` : current.token);
      } else {
        mapsTo.value.set_label("—");
      }
      const usage = usageCount(active.bodies, selection.placeholder);
      usedBy.value.set_label(`${usage.shapes} shapes across ${usage.variants} variants`);
    }
  });

  return root;
}

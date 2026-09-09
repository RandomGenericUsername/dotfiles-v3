import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import type { MappingShow } from "../lib/itr";
import type { ShapeSelection } from "../lib/model";
import { extractShapes, usageCount } from "../lib/svg";
import { templatePendingKey, type TemplatePendingEdit } from "../lib/templates";

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
  onSelectShapeId(shapeId: string): void;
}

function kvRow(label: string): { row: Gtk.Box; value: Gtk.Label } {
  const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 });
  row.append(new Gtk.Label({ label, css_classes: ["kv-key"], xalign: 0 }));
  const value = new Gtk.Label({ label: "—", css_classes: ["kv-value"], xalign: 1, hexpand: true });
  row.append(value);
  return { row, value };
}

export function SelectionPanel(props: SelectionPanelProps) {
  const root = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["sel-panel"],
  });
  root.append(new Gtk.Label({ label: "Selection", css_classes: ["icme-pane-title"] }));

  const shape = kvRow("Shape");
  const placeholder = kvRow("Placeholder");
  const mapsTo = kvRow("Maps to");
  const usedBy = kvRow("Used by");
  root.append(shape.row);
  root.append(placeholder.row);
  root.append(mapsTo.row);
  root.append(usedBy.row);

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

  function rebuildList(body: string, templatePath: string): void {
    let child = shapeList.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      shapeList.remove(child);
      child = next;
    }
    shapeButtons.clear();
    // Staged (unsaved) template edits win, mirroring selectShapeId: the list
    // must show the placeholder a color pick would actually target.
    const staged = props.templatePending();
    for (const info of extractShapes(body)) {
      const override = staged.get(templatePendingKey(templatePath, info.id));
      const ph = override?.newPlaceholder ?? info.placeholder;
      const label = ph ? `${info.id} · {{${ph}}}` : `${info.id} · static`;
      const button = new Gtk.Button({ label, css_classes: ["shape-item"] });
      if (ph === null) {
        button.set_sensitive(false);
      } else {
        button.connect("clicked", () => props.onSelectShapeId(String(info.id)));
      }
      shapeList.append(button);
      shapeButtons.set(String(info.id), button);
    }
  }

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
    if (!selection || selection.variantName !== props.activeVariant() || !current) {
      shape.value.set_label("—");
      placeholder.value.set_label("—");
      mapsTo.value.set_label("—");
      usedBy.value.set_label("—");
      return;
    }
    shape.value.set_label(selection.shapeId);
    placeholder.value.set_label(`{{${selection.placeholder}}}`);
    mapsTo.value.set_label(current.hex ? `${current.token} · ${current.hex}` : current.token);
    const usage = usageCount(active.bodies, selection.placeholder);
    usedBy.value.set_label(`${usage.shapes} shapes across ${usage.variants} variants`);
  });

  return root;
}

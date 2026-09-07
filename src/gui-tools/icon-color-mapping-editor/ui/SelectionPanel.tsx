import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import type { MappingShow } from "../lib/itr";
import type { ShapeSelection } from "../lib/model";
import { extractShapes, usageCount } from "../lib/svg";

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

  function activeBody(): { bodies: string[]; body: string } | null {
    const show = props.show();
    const group = show?.groups.find((g) => g.group === props.groupName());
    const view = group?.variants.find((v) => v.variant === props.activeVariant());
    if (!group || !view) return null;
    return { bodies: group.variants.map((v) => v.svg_body), body: view.svg_body };
  }

  function rebuildList(body: string): void {
    let child = shapeList.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      shapeList.remove(child);
      child = next;
    }
    shapeButtons.clear();
    for (const info of extractShapes(body)) {
      const label = info.placeholder
        ? `${info.id} · {{${info.placeholder}}}`
        : `${info.id} · static`;
      const button = new Gtk.Button({ label, css_classes: ["shape-item"] });
      if (info.placeholder === null) {
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
    if (!active) {
      shape.value.set_label("—");
      placeholder.value.set_label("—");
      mapsTo.value.set_label("—");
      usedBy.value.set_label("—");
      return;
    }
    const key = `${props.groupName()}:${props.activeVariant()}`;
    if (key !== builtKey) {
      rebuildList(active.body);
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

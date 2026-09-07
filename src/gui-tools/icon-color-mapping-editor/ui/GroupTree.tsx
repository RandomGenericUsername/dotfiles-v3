import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import type { MappingShow } from "../lib/itr";

export interface GroupTreeProps {
  show: Accessor<MappingShow | null>;
  groupName: Accessor<string>;
  activeVariant: Accessor<string>;
  onSelectGroup(group: string): void;
  onSelectVariant(variant: string): void;
}

export function GroupTree(props: GroupTreeProps) {
  const root = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["tree"],
  });
  root.append(new Gtk.Label({ label: "Group / variants", css_classes: ["icme-pane-title"] }));
  const list = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2 });
  root.append(list);

  const rows = new Map<string, Gtk.Button>();
  let builtFor: MappingShow | null = null;

  function rebuild(show: MappingShow): void {
    let child = list.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      list.remove(child);
      child = next;
    }
    rows.clear();
    for (const group of show.groups) {
      const header = new Gtk.Label({
        label: group.group,
        css_classes: ["group"],
        xalign: 0,
      });
      list.append(header);
      for (const variant of group.variants) {
        const key = `${group.group}:${variant.variant}`;
        const button = new Gtk.Button({
          label: variant.variant,
          css_classes: ["item"],
        });
        button.connect("clicked", () => {
          if (group.group !== props.groupName()) {
            props.onSelectGroup(group.group);
          }
          props.onSelectVariant(variant.variant);
        });
        list.append(button);
        rows.set(key, button);
      }
    }
    builtFor = show;
  }

  // Structure only when the loaded data changes; selection paints classes.
  createEffect(() => {
    const show = props.show();
    if (show && show !== builtFor) rebuild(show);
  });
  createEffect(() => {
    const group = props.groupName();
    const variant = props.activeVariant();
    for (const [key, button] of rows) {
      const [rowGroup, rowVariant] = key.split(":");
      const active = rowGroup === group && rowVariant === variant;
      button.set_css_classes(active ? ["item", "active"] : ["item"]);
    }
  });

  return root;
}

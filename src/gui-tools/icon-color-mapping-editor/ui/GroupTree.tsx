import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import type { MappingShow } from "../lib/itr";
import { extractShapes } from "../lib/svg";
import { templatePendingKey, type TemplatePendingEdit } from "../lib/templates";

export interface GroupTreeProps {
  show: Accessor<MappingShow | null>;
  groupName: Accessor<string>;
  activeVariant: Accessor<string>;
  templatePending?: Accessor<ReadonlyMap<string, TemplatePendingEdit>>;
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
  const badges = new Map<string, Gtk.Label>();
  let builtFor: MappingShow | null = null;

  function rebuild(show: MappingShow): void {
    let child = list.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      list.remove(child);
      child = next;
    }
    rows.clear();
    badges.clear();
    for (const group of show.groups) {
      const header = new Gtk.Label({
        label: group.group,
        css_classes: ["group"],
        xalign: 0,
      });
      list.append(header);
      for (const variant of group.variants) {
        const key = `${group.group}:${variant.variant}`;
        const rowBox = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 });
        const nameLabel = new Gtk.Label({ label: variant.variant, xalign: 0, hexpand: true });
        const badge = new Gtk.Label({ css_classes: ["badge"] });
        rowBox.append(nameLabel);
        rowBox.append(badge);

        const button = new Gtk.Button({ css_classes: ["item"] });
        button.set_child(rowBox);
        button.connect("clicked", () => {
          if (group.group !== props.groupName()) {
            props.onSelectGroup(group.group);
          }
          props.onSelectVariant(variant.variant);
        });
        list.append(button);
        rows.set(key, button);
        badges.set(key, badge);
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
    const show = props.show();
    const staged = props.templatePending?.() ?? new Map();

    for (const [key, button] of rows) {
      const [rowGroup, rowVariant] = key.split(":");
      const active = rowGroup === group && rowVariant === variant;
      button.set_css_classes(active ? ["item", "active"] : ["item"]);

      const badge = badges.get(key);
      if (badge && show) {
        const g = show.groups.find((grp) => grp.group === rowGroup);
        const v = g?.variants.find((vnt) => vnt.variant === rowVariant);
        if (v) {
          const shapes = extractShapes(v.svg_body);
          let unassigned = 0;
          for (const s of shapes) {
            const override = staged.get(templatePendingKey(v.template_path, s.id));
            const ph = override?.newPlaceholder ?? s.placeholder;
            if (ph === null) unassigned++;
          }
          if (unassigned > 0) {
            badge.set_label(`bare (${unassigned})`);
            badge.set_css_classes(["badge", "b"]);
          } else {
            badge.set_label("templated");
            badge.set_css_classes(["badge", "t"]);
          }
        }
      }
    }
  });

  return root;
}

import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import type { MappingShow } from "../lib/itr";
import type { Scope, ShapeSelection } from "../lib/model";

export interface ScopeSwitchProps {
  scope: Accessor<Scope>;
  show: Accessor<MappingShow | null>;
  groupName: Accessor<string>;
  activeVariant: Accessor<string>;
  selection: Accessor<ShapeSelection | null>;
  onScope(scope: Scope): void;
}

export function ScopeSwitch(props: ScopeSwitchProps) {
  const root = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["scope-block"],
  });
  root.append(new Gtk.Label({ label: "Edit scope", css_classes: ["icme-pane-title"] }));

  const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 });
  const buttons: Record<Scope, Gtk.Button> = {
    group: new Gtk.Button({ label: "Whole group", css_classes: ["toggle"], hexpand: true }),
    variant: new Gtk.Button({ label: "This variant only", css_classes: ["toggle"], hexpand: true }),
    vocabulary: new Gtk.Button({ label: "All icons", css_classes: ["toggle"], hexpand: true }),
  };
  (Object.keys(buttons) as Scope[]).forEach((scope) => {
    buttons[scope].connect("clicked", () => props.onScope(scope));
    row.append(buttons[scope]);
  });
  root.append(row);

  const hint = new Gtk.Label({
    css_classes: ["scope-hint"],
    xalign: 0,
    wrap: true,
  });
  root.append(hint);
  const warn = new Gtk.Label({
    css_classes: ["scope-warn"],
    xalign: 0,
    wrap: true,
  });
  root.append(warn);

  createEffect(() => {
    const scope = props.scope();
    const show = props.show();
    const selection = props.selection();
    for (const [name, button] of Object.entries(buttons) as [Scope, Gtk.Button][]) {
      button.set_css_classes(name === scope ? ["toggle", "on"] : ["toggle"]);
    }
    const placeholder = selection?.placeholder ?? null;
    const locked = placeholder === null;
    row.set_sensitive(!locked);
    if (!show || placeholder === null) {
      hint.set_label("");
      warn.set_label("");
      warn.set_visible(false);
      return;
    }
    const group = show.groups.find((g) => g.group === props.groupName());
    const variantCount = group?.variants.length ?? 0;
    const shadowers = show.shadows[placeholder] ?? [];
    const affected = show.groups.length - shadowers.length;
    if (scope === "group") {
      hint.set_label(
        `Changes ${props.groupName()}.color_mappings.${placeholder} — affects all ${variantCount} variants.`,
      );
      warn.set_visible(false);
    } else if (scope === "variant") {
      hint.set_label(
        `Adds a color_mappings override on variant "${props.activeVariant()}" only.`,
      );
      warn.set_visible(false);
    } else {
      hint.set_label(
        `Changes defaults.${placeholder} in defaults.yaml — affects all ${affected} icon groups that don't override it.`,
      );
      if (shadowers.length > 0) {
        const names = shadowers.join(", ");
        if (shadowers.includes(props.groupName())) {
          warn.set_label(
            `${props.groupName()} overrides ${placeholder}, so this edit will not change the preview. Shadowing: ${names}.`,
          );
        } else {
          warn.set_label(`Shadowing: ${names}.`);
        }
        warn.set_visible(true);
      } else {
        warn.set_visible(false);
      }
    }
  });

  return root;
}

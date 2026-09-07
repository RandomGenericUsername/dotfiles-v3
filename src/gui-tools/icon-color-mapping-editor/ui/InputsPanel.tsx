import { Gtk } from "ags/gtk4";
import Pango from "gi://Pango?version=1.0";
import { createEffect, type Accessor } from "ags";
import type { EditorInputs } from "../lib/inputs";

export interface InputsPanelProps {
  inputs: Accessor<EditorInputs>;
  pendingCount: Accessor<number>;
  onChange(inputs: EditorInputs): void;
}

function choosePath(
  title: string,
  dirOnly: boolean,
  onPick: (path: string) => void,
): void {
  const dialog = new Gtk.FileChooserNative({
    title,
    action: dirOnly
      ? Gtk.FileChooserAction.SELECT_FOLDER
      : Gtk.FileChooserAction.OPEN,
    modal: true,
  });
  dialog.connect("response", (_dialog: object, response: number) => {
    if (response === Gtk.ResponseType.ACCEPT) {
      const path = dialog.get_file()?.get_path();
      if (path) onPick(path);
    }
    dialog.destroy();
  });
  dialog.show();
}

interface InputRow {
  label: string;
  row: Gtk.Box;
  path: Gtk.Label;
  pick: Gtk.Button;
  get: (inputs: EditorInputs) => string;
  put: (inputs: EditorInputs, path: string) => EditorInputs;
  dirOnly: boolean;
}

export function InputsPanel(props: InputsPanelProps) {
  const root = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["inputs"],
  });
  root.append(new Gtk.Label({ label: "Inputs", css_classes: ["icme-pane-title"] }));

  const rows: InputRow[] = [
    {
      label: "SVG template root (read-only)",
      row: new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL }),
      path: new Gtk.Label({ css_classes: ["path"], xalign: 0 }),
      pick: new Gtk.Button({ label: "⋯", css_classes: ["pick"] }),
      get: (inputs) => inputs.templateRoot,
      put: (inputs, path) => ({ ...inputs, templateRoot: path }),
      dirOnly: true,
    },
    {
      label: "Icons manifest (edited by tool)",
      row: new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL }),
      path: new Gtk.Label({ css_classes: ["path", "rw"], xalign: 0 }),
      pick: new Gtk.Button({ label: "⋯", css_classes: ["pick"] }),
      get: (inputs) => inputs.iconsYaml,
      put: (inputs, path) => ({ ...inputs, iconsYaml: path }),
      dirOnly: false,
    },
    {
      label: "Color scheme (read-only)",
      row: new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL }),
      path: new Gtk.Label({ css_classes: ["path"], xalign: 0 }),
      pick: new Gtk.Button({ label: "⋯", css_classes: ["pick"] }),
      get: (inputs) => inputs.colorScheme,
      put: (inputs, path) => ({ ...inputs, colorScheme: path }),
      dirOnly: false,
    },
  ];

  for (const item of rows) {
    const title = new Gtk.Label({
      label: item.label,
      css_classes: ["input-label"],
      xalign: 0,
    });
    const line = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 });
    item.path.set_ellipsize(Pango.EllipsizeMode.END);
    item.path.set_max_width_chars(28);
    item.path.set_hexpand(true);
    line.append(item.path);
    line.append(item.pick);
    item.pick.connect("clicked", () =>
      choosePath(item.label, item.dirOnly, (path) =>
        props.onChange(item.put(props.inputs(), path)),
      ),
    );
    item.row.append(title);
    item.row.append(line);
    root.append(item.row);
  }

  createEffect(() => {
    const inputs = props.inputs();
    const locked = props.pendingCount() > 0;
    for (const item of rows) {
      const path = item.get(inputs);
      item.path.set_label(path);
      item.path.set_tooltip_text(path);
      item.pick.set_sensitive(!locked);
    }
  });

  return root;
}

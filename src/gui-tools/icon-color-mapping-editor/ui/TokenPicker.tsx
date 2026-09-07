import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";

export interface TokenPickerProps {
  palette: Accessor<Record<string, string>>;
  missingTokens: Accessor<string[]>;
  placeholder: Accessor<string | null>;
  currentToken: Accessor<string | null>;
  onPick(token: string): void;
}

function isIndexed(token: string): boolean {
  return /^color\d+$/.test(token);
}

function isColorValue(value: string | undefined): value is string {
  return typeof value === "string" && /^#[0-9a-fA-F]{6}$/.test(value);
}

export function TokenPicker(props: TokenPickerProps) {
  const root = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["picker"],
  });
  const heading = new Gtk.Label({ css_classes: ["picker-title"], xalign: 0, wrap: true });
  root.append(heading);

  const grid = new Gtk.Grid({
    column_spacing: 6,
    row_spacing: 6,
    css_classes: ["token-grid"],
  });
  root.append(grid);
  const named = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 4 });
  root.append(named);

  let builtPalette: Record<string, string> | null = null;
  let builtMissing: string[] | null = null;
  const swatches = new Map<string, Gtk.Button>();
  const TOKEN_COLUMNS = 6;

  function swatchButton(token: string, hex: string): Gtk.Button {
    const button = new Gtk.Button({ css_classes: ["cell"], tooltip_text: `${token} ${hex}` });
    const fill = new Gtk.Box({
      css_classes: ["fill", `fill-${token}`],
      hexpand: true,
      vexpand: true,
    });
    const provider = new Gtk.CssProvider();
    provider.load_from_string(`.fill-${token} { background-color: ${hex}; }`);
    fill.get_style_context().add_provider(
      provider,
      Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    );
    button.set_child(fill);
    button.connect("clicked", () => {
      if (props.placeholder() !== null) props.onPick(token);
    });
    return button;
  }

  function namedRow(token: string, hex: string | null): Gtk.Box {
    const row = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 9 });
    const chip = new Gtk.Box({ css_classes: ["chip"] });
    chip.set_size_request(20, 20);
    if (hex) {
      const provider = new Gtk.CssProvider();
      provider.load_from_string(`.chip-${token} { background-color: ${hex}; }`);
      chip.get_style_context().add_provider(
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
      );
      chip.set_css_classes(["chip", `chip-${token}`]);
    } else {
      chip.set_css_classes(["chip", "missing"]);
    }
    const name = new Gtk.Label({ label: token, css_classes: ["ph"] });
    const value = new Gtk.Label({
      label: hex ?? "missing token",
      css_classes: ["tok"],
    });
    row.append(chip);
    row.append(name);
    row.append(value);
    if (!hex) {
      const tag = new Gtk.Label({ label: "not in colors.yaml", css_classes: ["tag"] });
      row.append(tag);
    }
    return row;
  }

  function rebuild(palette: Record<string, string>, missing: string[]): void {
    let child = grid.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      grid.remove(child);
      child = next;
    }
    swatches.clear();
    const indexed = Object.keys(palette)
      .filter((token) => isIndexed(token) && isColorValue(palette[token]))
      .sort((a, b) => Number(a.slice(5)) - Number(b.slice(5)));
    indexed.forEach((token, i) => {
      const button = swatchButton(token, palette[token] as string);
      grid.attach(button, i % TOKEN_COLUMNS, Math.floor(i / TOKEN_COLUMNS), 1, 1);
      swatches.set(token, button);
    });
    child = named.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      named.remove(child);
      child = next;
    }
    const namedTokens = Object.keys(palette)
      .filter((token) => !isIndexed(token) && isColorValue(palette[token]))
      .sort();
    for (const token of namedTokens) {
      const row = namedRow(token, palette[token]);
      const button = new Gtk.Button({ css_classes: ["named-row"] });
      button.set_child(row);
      const current = token;
      button.connect("clicked", () => {
        if (props.placeholder() !== null) props.onPick(current);
      });
      named.append(button);
      swatches.set(token, button);
    }
    for (const token of [...missing].sort()) {
      if (token in palette) continue;
      const row = namedRow(token, null);
      row.set_sensitive(false);
      named.append(row);
    }
    builtPalette = palette;
    builtMissing = missing;
  }

  createEffect(() => {
    const palette = props.palette();
    const missing = props.missingTokens();
    if (palette !== builtPalette || missing !== builtMissing) {
      rebuild(palette, missing);
    }
    const placeholder = props.placeholder();
    const current = props.currentToken();
    if (placeholder === null) {
      heading.set_label("Select a shape to change its color");
    } else {
      heading.set_label(`Set {{${placeholder}}} to which palette token?`);
    }
    const off = placeholder === null;
    grid.set_sensitive(!off);
    named.set_sensitive(!off);
    for (const [token, button] of swatches) {
      const classes = button.get_css_classes().filter((c) => c !== "current");
      if (token === current) classes.push("current");
      button.set_css_classes(classes);
    }
  });

  return root;
}

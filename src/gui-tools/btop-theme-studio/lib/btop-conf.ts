// Parse btop's REAL layout config (`btop.conf`).
//
// btop's layout is not a file: it is `shown_boxes` plus a `presets` string of
// `box:P:G` groups in `btop.conf`. Geometry is computed at runtime by
// `Draw::calcSizes()`; there is no layout template to consume. The studio
// therefore parses the real config and lays its schematic out from the preset
// box set — it never invents geometry (design D2).
//
// Ported from the working prototype (`prototype/studio_server.py`) and locked
// against btop's own `--default-config` output by a test.

export interface Preset {
  /** Preset index; 0 is btop's "all boxes shown" rule. */
  readonly index: number;
  readonly label: string;
  /** Box name → grid position hint (`box:P:G`); presence means "shown". */
  readonly boxes: Readonly<Record<string, number>>;
}

export interface BtopConf {
  readonly color_theme: string | null;
  readonly shown_boxes: readonly string[];
  readonly presets_raw: string;
  readonly presets: readonly Preset[];
}

/** The btop "preset 0" rule: every box is shown. */
export const ALL_BOXES: readonly string[] = ["cpu", "gpu", "mem", "net", "disks", "proc"];

/**
 * Parse the `presets` string into ordered presets.
 *
 * Format: whitespace-separated groups; each group is comma-separated
 * `box:P:G` entries. Preset 0 is implicit — btop's rule is "all boxes shown".
 * btop's own rule also mirrors cpu's position onto gpu when gpu is not
 * explicitly listed, which the prototype reproduces; keep that.
 */
export function parsePresets(raw: string): Preset[] {
  const presets: Preset[] = [
    {
      index: 0,
      label: "Preset 0 — all boxes shown (btop rule)",
      boxes: Object.fromEntries(ALL_BOXES.map((box) => [box, 0])),
    },
  ];
  let index = 0;
  for (const group of raw.trim().split(/\s+/).filter(Boolean)) {
    index += 1;
    const boxes: Record<string, number> = {};
    for (const entry of group.split(",")) {
      const parts = entry.split(":");
      const name = parts[0];
      if (!name) continue;
      const position = parts[1] && /^\d+$/.test(parts[1]) ? Number(parts[1]) : 0;
      boxes[name] = position;
    }
    if ("cpu" in boxes && !("gpu" in boxes)) boxes.gpu = boxes.cpu;
    presets.push({ index, label: `Preset ${index} — ${group}`, boxes });
  }
  return presets;
}

/** Parse the `shown_boxes` space-separated value into box names. */
export function parseShownBoxes(raw: string): string[] {
  return raw.trim().split(/\s+/).filter(Boolean);
}

/** Read one `key = "value"` setting out of a btop.conf body. */
function setting(text: string, key: string): string | null {
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const [name, ...rest] = trimmed.split("=");
    if (name.trim() !== key) continue;
    let value = rest.join("=").trim();
    if (value.startsWith('"') && value.endsWith('"')) value = value.slice(1, -1);
    return value;
  }
  return null;
}

/** Parse a full btop.conf body into the fields the schematic consumes. */
export function parseBtopConf(text: string): BtopConf {
  const shown = setting(text, "shown_boxes") ?? "cpu mem net proc";
  const presetsRaw = setting(text, "presets") ?? "";
  return {
    color_theme: setting(text, "color_theme"),
    shown_boxes: parseShownBoxes(shown),
    presets_raw: presetsRaw,
    presets: parsePresets(presetsRaw),
  };
}

/** The preset at `index`, falling back to preset 0 when absent. */
export function presetAt(conf: BtopConf, index: number): Preset {
  return conf.presets.find((preset) => preset.index === index) ?? conf.presets[0];
}

/** The box names a preset shows, in schematic order. */
export function presetBoxes(conf: BtopConf, index: number): string[] {
  const boxes = presetAt(conf, index).boxes;
  return ALL_BOXES.filter((box) => box in boxes);
}

/** The caption naming the shown boxes (used under the schematic). */
export function presetCaption(conf: BtopConf, index: number): string {
  return presetBoxes(conf, index).join(" ");
}

// The component schematic (design D2, capability `btop-theme-studio`).
//
// btop's interface is drawn as labelled boxes (cpu · cpu-detail · gpu · mem ·
// net · disks · proc), each drawn element tagged by the theme key(s) that paint
// it. The box set follows the selected preset parsed from btop's real config;
// selecting a key highlights every element it paints. The studio never invents
// geometry — it renders the preset's box set.
//
// The per-element key associations mirror the mock's `data-k` tags and are
// cross-checked against the generated key→widget map by tests.

import { presetBoxes, type BtopConf } from "./btop-conf.ts";
import { modulesFor } from "./key-map.ts";
import { roleSuffix } from "./theme-keys.ts";

export interface SchematicElement {
  readonly id: string;
  readonly box: string;
  /** Theme keys that paint this element. */
  readonly keys: readonly string[];
  readonly label: string;
  /** Which drawn module the element belongs to (for coverage). */
  readonly module: string;
}

export interface Schematic {
  readonly boxes: readonly string[];
  readonly elements: readonly SchematicElement[];
  /** Element ids highlighted for the selected key. */
  readonly highlighted: readonly string[];
  /** Modules the selected key paints that the preset hides. */
  readonly hiddenModules: readonly string[];
  readonly caption: string;
}

/** Static per-box element spec: the keys each element is painted by. */
interface ElementSpec {
  readonly id: string;
  readonly keys: readonly string[];
  readonly label: string;
}

const SURFACE_KEYS = ["main_bg", "main_fg", "title", "hi_fg", "selected_bg", "selected_fg", "inactive_fg", "graph_text"];
const CHROME_KEYS = ["meter_bg", "proc_misc", "cpu_box", "mem_box", "net_box", "proc_box", "div_line"];

function gradient(family: string): string[] {
  return [`${family}_start`, `${family}_mid`, `${family}_end`];
}

const BOX_ELEMENTS: Readonly<Record<string, readonly ElementSpec[]>> = {
  cpu: [
    { id: "cpu-box-outline", keys: ["cpu_box"], label: "cpu box outline" },
    { id: "cpu-title", keys: ["title"], label: "box title" },
    { id: "cpu-total", keys: [...gradient("cpu"), "meter_bg", "graph_text"], label: "cpu total meter + graph" },
    { id: "cpu-cores", keys: [...gradient("cpu"), "meter_bg", "inactive_fg"], label: "per-core graphs" },
    { id: "cpu-temp", keys: [...gradient("temp")], label: "cpu / core temperature" },
    { id: "cpu-watts", keys: [...gradient("cached")], label: "cpu watts / P-state" },
    { id: "gpu-util", keys: [...gradient("cpu"), "meter_bg"], label: "GPU utilisation" },
    { id: "battery", keys: [...gradient("cpu"), "meter_bg"], label: "battery" },
  ],
  gpu: [
    { id: "gpu-box-outline", keys: ["mem_box"], label: "gpu box outline" },
    { id: "gpu-title", keys: ["title"], label: "box title" },
    { id: "gpu-meter", keys: [...gradient("cpu"), "meter_bg"], label: "gpu utilisation meter" },
    { id: "gpu-vram", keys: [...gradient("free"), ...gradient("used")], label: "gpu VRAM" },
    { id: "gpu-watts", keys: [...gradient("cached")], label: "gpu power draw" },
    { id: "gpu-temp", keys: [...gradient("temp")], label: "gpu temperature" },
  ],
  mem: [
    { id: "mem-box-outline", keys: ["mem_box"], label: "mem box outline" },
    { id: "mem-title", keys: ["title"], label: "box title" },
    { id: "mem-used", keys: [...gradient("used"), "meter_bg"], label: "used meter" },
    { id: "mem-available", keys: [...gradient("available"), "meter_bg"], label: "available meter" },
    { id: "mem-cached", keys: [...gradient("cached"), "meter_bg"], label: "cached meter" },
    { id: "mem-free", keys: [...gradient("free"), "meter_bg"], label: "free meter" },
    { id: "mem-leaders", keys: ["div_line"], label: "row leaders" },
  ],
  net: [
    { id: "net-box-outline", keys: ["net_box"], label: "net box outline" },
    { id: "net-title", keys: ["title"], label: "box title" },
    { id: "net-tabs", keys: ["main_fg", "selected_bg", "selected_fg", "inactive_fg"], label: "sync / auto / zero tabs" },
    { id: "net-download-graph", keys: [...gradient("download"), "graph_text"], label: "download graph" },
    { id: "net-download", keys: [...gradient("download"), "meter_bg"], label: "download subbox" },
    { id: "net-upload", keys: [...gradient("upload"), "meter_bg"], label: "upload subbox" },
  ],
  disks: [
    { id: "disks-box-outline", keys: ["cpu_box"], label: "disks box outline" },
    { id: "disks-title", keys: ["title"], label: "box title" },
    { id: "disks-rows", keys: ["main_fg", "div_line"], label: "disk rows + IO%" },
    { id: "disks-used", keys: [...gradient("used"), "meter_bg"], label: "used meter" },
    { id: "disks-available", keys: [...gradient("available"), "meter_bg"], label: "available (%busy) meter" },
    { id: "disks-free", keys: [...gradient("free"), "meter_bg"], label: "free meter" },
  ],
  proc: [
    { id: "proc-box-outline", keys: ["proc_box"], label: "proc box outline" },
    { id: "proc-title", keys: ["title"], label: "box title" },
    { id: "proc-tabs", keys: ["hi_fg", "selected_bg", "inactive_fg"], label: "proc tabs / header" },
    { id: "proc-cpu-bars", keys: [...gradient("process")], label: "process cpu bars" },
    { id: "proc-state", keys: ["proc_pause_bg", "proc_follow_bg", "proc_banner_bg", "proc_banner_fg", "followed_bg", "followed_fg"], label: "pause / follow state" },
    { id: "proc-footer", keys: ["proc_misc"], label: "proc counts / status line" },
  ],
};

// Surface/chrome keys that paint across every box are associated with the
// topbar and each box title, so selecting them highlights broadly (as the
// spec's cpu-family scenario expects for cpu, and as the map dictates for the
// all-boxes keys).
const TOPBAR: readonly ElementSpec[] = [
  { id: "topbar-chrome", keys: ["cpu_box", "title", "div_line", "main_fg", "inactive_fg"], label: "top bar" },
  { id: "topbar-battery", keys: [...gradient("cpu"), "meter_bg"], label: "top bar battery" },
];

const MODULE_OF_BOX: Readonly<Record<string, string>> = {
  cpu: "cpu",
  gpu: "gpu",
  mem: "mem",
  net: "net",
  disks: "disks",
  proc: "proc",
};

function elementSpecs(box: string): readonly ElementSpec[] {
  return [...(BOX_ELEMENTS[box] ?? [])];
}

/**
 * Build the schematic for a preset + selected key.
 *
 * `hiddenModules` is derived from the GENERATED map (not the element tags), so
 * the "where it shows" warning is source-derived: a key paints whatever the map
 * says, regardless of which elements happen to be tagged.
 */
export function buildSchematic(conf: BtopConf, presetIndex: number, selected: string | null): Schematic {
  const boxes = presetBoxes(conf, presetIndex);
  const elements: SchematicElement[] = [];
  for (const spec of TOPBAR) {
    elements.push({ ...spec, box: "topbar", module: "cpu" });
  }
  for (const box of boxes) {
    const module = MODULE_OF_BOX[box] ?? box;
    for (const spec of elementSpecs(box)) {
      elements.push({ ...spec, box, module });
    }
  }

  const highlighted = selected
    ? elements.filter((element) => element.keys.includes(selected)).map((element) => element.id)
    : [];

  const hiddenModules = selected
    ? modulesFor(selected).filter((module) => !boxes.includes(module))
    : [];

  const caption = `btop schematic — preset ${presetIndex} · boxes: ${boxes.join(" ")}`;
  return { boxes, elements, highlighted, hiddenModules, caption };
}

/**
 * The warning shown when a selected key paints a module the current preset
 * hides (spec scenario: `available_*` while `disks` is not shown).
 */
export function hiddenModuleWarning(selected: string, hiddenModules: readonly string[]): string | null {
  if (!selected || hiddenModules.length === 0) return null;
  return (
    `This key paints ${hiddenModules.join(", ")}, which the current preset does not show — ` +
    "so the change will not be visible here."
  );
}

/** True when `key` is a surface/chrome key the map attributes to every box. */
export function isSurfaceOrChrome(key: string): boolean {
  return SURFACE_KEYS.includes(key) || CHROME_KEYS.includes(key);
}

/** The gradient family of a selected gradient key, else null. */
export function selectedFamily(key: string | null): string | null {
  if (!key) return null;
  return roleSuffix(key) ? key.slice(0, -roleSuffix(key)!.length) : null;
}

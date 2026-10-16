import { Astal, Gdk, Gtk } from "ags/gtk4";
import GLib from "gi://GLib?version=2.0";
import { createEffect, createState } from "ags";
import { execAsync } from "ags/process";
import {
  DEFAULT_CONTROLS,
  FIXED_FILL_LEVELS,
  type PreviewControls,
} from "../lib/preview";
import { parseBtopConf, presetAt } from "../lib/btop-conf";
import { buildSchematic, hiddenModuleWarning } from "../lib/schematic";
import { KEY_GROUPS, NAMED_TOKENS } from "../lib/theme-keys";
import {
  GRADIENT_LIMIT_NOTE,
  type Palette,
  type Scope,
  type SaveTarget,
  type Theme,
  addMiddleColour,
  applyPick,
  createTheme,
  deleteTheme,
  diagnose,
  diffEdits,
  duplicateTheme,
  effectiveMap,
  fixReserveSurface,
  fixTransparentMeters,
  forkTheme,
  generatedDefaultMap,
  markActive,
  parseTheme,
  resolveHex,
  serializeTheme,
} from "../lib/theme-model";
import {
  actionLabel,
  divergenceCaveat,
  generatedInstalledWarning,
  resolvedPath,
  targetHint,
} from "../lib/targets";

// ── file helpers (the ONLY I/O in the studio; the lib/ layer stays pure) ────

function readFile(path: string): string | null {
  try {
    const [ok, bytes] = GLib.file_get_contents(path);
    if (!ok) return null;
    return new TextDecoder().decode(bytes as Uint8Array);
  } catch {
    return null;
  }
}

function writeFile(path: string, text: string): void {
  const parent = path.slice(0, path.lastIndexOf("/"));
  GLib.mkdir_with_parents(parent, 0o755);
  GLib.file_set_contents(path, text);
}

function repoRoot(): string {
  return GLib.getenv("BTOP_STUDIO_REPO_ROOT") || `${GLib.get_home_dir()}/.dotfiles`;
}

function installDir(): string {
  return GLib.getenv("BTOP_STUDIO_INSTALL_DIR") || `${GLib.get_user_data_dir()}/dotfiles`;
}

function stateHome(): string {
  return GLib.getenv("XDG_STATE_HOME") || `${GLib.get_home_dir()}/.local/state`;
}

function configHome(): string {
  return GLib.getenv("XDG_CONFIG_HOME") || `${GLib.get_home_dir()}/.config`;
}

function loadConfText(): string {
  return (
    readFile(`${installDir()}/config/btop/btop.conf`) ??
    readFile(`${configHome()}/btop/btop.conf`) ??
    'shown_boxes = "cpu mem net proc"\npresets = ""\n'
  );
}

function loadPalette(): Palette {
  const text = readFile(`${stateHome()}/dotfiles/current/colors.yaml`);
  const background = text?.match(/background:\s*"(#[0-9a-fA-F]{6})"/)?.[1] ?? "#0b0b1a";
  const foreground = text?.match(/foreground:\s*"(#[0-9a-fA-F]{6})"/)?.[1] ?? "#c2c2c5";
  const all = [...(text?.matchAll(/-\s*"(#[0-9a-fA-F]{6})"/g) ?? [])].map((m) => m[1]);
  const colors = all.slice(0, 16);
  const ramp: string[] = [];
  for (const colour of colors) if (ramp[ramp.length - 1] !== colour) ramp.push(colour);
  return {
    background,
    foreground,
    cursor: foreground,
    ramp: ramp.length ? ramp : [background, foreground],
    colors: colors.length ? colors : [background, foreground],
  };
}

function loadGeneratedMap(): Record<string, string> {
  const text = readFile(`${stateHome()}/dotfiles/current/colors.btop.theme`);
  return text ? parseTheme(text) : generatedDefaultMap();
}

function initialLibrary(): Theme[] {
  return [
    { id: "generated", name: "colors.btop", kind: "generated", active: true, map: loadGeneratedMap() },
  ];
}

// ── the window ──────────────────────────────────────────────────────────────

export function StudioWindow(gdkmonitor: Gdk.Monitor) {
  const [confText] = createState(loadConfText());
  const [palette, setPalette] = createState<Palette>(loadPalette());
  const [themes, setThemes] = createState<Theme[]>(initialLibrary());
  const [currentId, setCurrentId] = createState("generated");
  const [selected, setSelected] = createState<string | null>("meter_bg");
  const [scope, setScope] = createState<Scope>("key");
  const [pending, setPending] = createState<ReadonlyMap<string, string>>(new Map());
  const [target, setTarget] = createState<SaveTarget>("repo");
  const [preset, setPreset] = createState(0);
  const [controls, setControls] = createState<PreviewControls>(DEFAULT_CONTROLS);
  const [highlight, setHighlight] = createState(true);
  const [status, setStatus] = createState("");
  let themeSeq = 1;

  const conf = () => parseBtopConf(confText());
  const current = () => themes().find((t) => t.id === currentId()) ?? themes()[0];
  const effective = () => effectiveMap(current().map, pending());

  // ── library actions ──────────────────────────────────────────────────────
  function addTheme(theme: Theme): void {
    setThemes([...themes(), theme]);
    setCurrentId(theme.id);
    setPending(new Map());
  }

  function fork(): void {
    const base = current();
    const name = base.kind === "generated" ? "colors.btop-fork" : `${base.name}-copy`;
    addTheme(forkTheme(base, `t${themeSeq}`, name, palette()));
    themeSeq += 1;
  }

  function duplicate(): void {
    const base = current();
    addTheme(duplicateTheme(base, `t${themeSeq}`, `${base.name}-copy`));
    themeSeq += 1;
  }

  function newTheme(): void {
    addTheme(createTheme(`t${themeSeq}`, `btop-custom-${themeSeq}`, generatedDefaultMap()));
    themeSeq += 1;
  }

  function remove(): void {
    if (current().kind === "generated") {
      setStatus("colors.btop follows the wallpaper — fork it instead of deleting.");
      return;
    }
    const next = deleteTheme({ themes: themes() }, current().id).themes;
    setThemes([...next]);
    setCurrentId(next[0].id);
    setPending(new Map());
  }

  function pick(value: string): void {
    const key = selected();
    if (!key) return;
    setPending(applyPick(pending(), key, value, scope(), current().map));
  }

  function setActive(): void {
    setThemes(markActive({ themes: themes() }, current().id).themes);
    const path = `${repoRoot()}/dotfiles/config/btop/active-theme`;
    writeFile(path, `${current().name}\n`);
    setStatus(`Active theme recorded in the repo setting (${path}).`);
  }

  function applyFix(kind: "reserve" | "transparent"): void {
    const next = kind === "reserve" ? fixReserveSurface(effective()) : fixTransparentMeters(effective());
    const edits = new Map(pending());
    for (const key of Object.keys(next)) {
      if (current().map[key] !== next[key]) edits.set(key, next[key]);
    }
    setPending(edits);
  }

  function save(): void {
    const theme = current();
    const ctx = { repoRoot: repoRoot(), installDir: installDir() };
    const path = resolvedPath(theme, target(), ctx).replace(" (pointer)", "");
    const text = serializeTheme(effective());
    try {
      writeFile(path, text);
      setPending(new Map());
      if (target() === "installed") {
        void execAsync(["bash", "-lc", "pkill -USR2 btop 2>/dev/null || true"]).catch(() => {});
        setStatus(`Saved to ${path} and reloaded btop (SIGUSR2).`);
      } else {
        setStatus(`Saved to repo: ${path} — deployed by bootstrap on the next provision.`);
      }
    } catch (error: unknown) {
      setStatus(`Save failed: ${error}`);
    }
  }

  // ── widgets ──────────────────────────────────────────────────────────────
  const root = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, css_classes: ["studio-root"], hexpand: true, vexpand: true });
  const left = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["studio-left"], spacing: 6 });
  const center = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["studio-center"], spacing: 6, hexpand: true, vexpand: true });
  const right = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, css_classes: ["studio-right"], spacing: 6 });
  root.append(left);
  root.append(center);
  root.append(right);

  // Left: save target + library + key tree.
  const targetRow = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 4 });
  const repoBtn = new Gtk.Button({ label: "Repo", css_classes: ["toggle"] });
  const instBtn = new Gtk.Button({ label: "Installed", css_classes: ["toggle"] });
  repoBtn.connect("clicked", () => setTarget("repo"));
  instBtn.connect("clicked", () => setTarget("installed"));
  targetRow.append(repoBtn);
  targetRow.append(instBtn);
  const targetPath = new Gtk.Label({ xalign: 0, wrap: true, css_classes: ["path"] });
  const targetHintLabel = new Gtk.Label({ xalign: 0, wrap: true, css_classes: ["hint"] });
  const caveat = new Gtk.Label({ xalign: 0, wrap: true, css_classes: ["warn"] });
  left.append(new Gtk.Label({ label: "Save target", xalign: 0, css_classes: ["h2"] }));
  left.append(targetRow);
  left.append(targetPath);
  left.append(targetHintLabel);
  left.append(caveat);

  const libBox = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2, css_classes: ["lib"] });
  left.append(new Gtk.Label({ label: "Themes — ★ = used by btop", xalign: 0, css_classes: ["h2"] }));
  left.append(libBox);
  const libActions = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 4 });
  const newBtn = new Gtk.Button({ label: "+ New", css_classes: ["toggle"] });
  const dupBtn = new Gtk.Button({ label: "Duplicate", css_classes: ["toggle"] });
  const forkBtn = new Gtk.Button({ label: "Fork", css_classes: ["toggle"] });
  const delBtn = new Gtk.Button({ label: "Delete", css_classes: ["toggle"] });
  const activeBtn = new Gtk.Button({ label: "★ Active", css_classes: ["toggle"] });
  newBtn.connect("clicked", newTheme);
  dupBtn.connect("clicked", duplicate);
  forkBtn.connect("clicked", fork);
  delBtn.connect("clicked", remove);
  activeBtn.connect("clicked", setActive);
  for (const button of [newBtn, dupBtn, forkBtn, delBtn, activeBtn]) libActions.append(button);
  left.append(libActions);

  const treeScroll = new Gtk.ScrolledWindow({ vexpand: true, hscrollbar_policy: Gtk.PolicyType.NEVER });
  const tree = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 1, css_classes: ["tree"] });
  treeScroll.set_child(tree);
  left.append(new Gtk.Label({ label: "Keys — all 48", xalign: 0, css_classes: ["h2"] }));
  left.append(treeScroll);

  // Center: preset chips, controls, schematic, diagnosis, diff.
  const presetBar = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 4, css_classes: ["pbar"] });
  const controlsBar = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6, css_classes: ["canvas-bar"] });
  const loadScale = new Gtk.Scale({ orientation: Gtk.Orientation.HORIZONTAL, adjustment: new Gtk.Adjustment({ lower: 0, upper: 100, step_increment: 5 }) });
  loadScale.set_value(DEFAULT_CONTROLS.load);
  loadScale.set_size_request(120, -1);
  loadScale.connect("value-changed", () => setControls({ ...controls(), load: Math.round(loadScale.get_value()), fixedFill: null }));
  const fillButtons: Gtk.Button[] = [];
  for (const level of FIXED_FILL_LEVELS) {
    const button = new Gtk.Button({ label: `${level}%`, css_classes: ["toggle"] });
    button.connect("clicked", () => setControls({ ...controls(), fixedFill: level }));
    fillButtons.push(button);
    controlsBar.append(button);
  }
  const backdropBtn = new Gtk.Button({ label: "Neutral bg", css_classes: ["toggle"] });
  backdropBtn.connect("clicked", () => setControls({ ...controls(), backdrop: controls().backdrop === "theme" ? "neutral" : "theme" }));
  const highlightBtn = new Gtk.Button({ label: "Highlight", css_classes: ["toggle", "on"] });
  highlightBtn.connect("clicked", () => setHighlight(!highlight()));
  const reserveBtn = new Gtk.Button({ label: "Reserve surface for meters", css_classes: ["toggle"] });
  const transparentBtn = new Gtk.Button({ label: "Transparent meters", css_classes: ["toggle"] });
  reserveBtn.connect("clicked", () => applyFix("reserve"));
  transparentBtn.connect("clicked", () => applyFix("transparent"));
  controlsBar.append(new Gtk.Label({ label: "load" }));
  controlsBar.append(loadScale);
  controlsBar.append(backdropBtn);
  controlsBar.append(highlightBtn);
  controlsBar.append(reserveBtn);
  controlsBar.append(transparentBtn);
  center.append(presetBar);
  center.append(controlsBar);
  const canvas = new Gtk.ScrolledWindow({ vexpand: true, hexpand: true });
  const canvasInner = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 6, css_classes: ["canvas"] });
  canvas.set_child(canvasInner);
  center.append(canvas);
  const diag = new Gtk.Label({ xalign: 0, wrap: true, css_classes: ["diag"] });
  const diff = new Gtk.Label({ xalign: 0, wrap: true, css_classes: ["diff"] });
  center.append(diag);
  center.append(diff);

  // Live preview — the REAL btop binary. The shipped app reuses the tested
  // pty + terminal-emulator engine (live/btop_live.py) rather than embedding
  // VTE: behaviorally identical per the `btop-live-preview` spec, and it keeps
  // the one preview implementation that has fixture/SIGUSR2/side-effect tests.
  const liveBar = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 });
  const liveBtn = new Gtk.Button({ label: "Refresh live preview (real btop)", css_classes: ["toggle"] });
  const liveLabel = new Gtk.Label({ xalign: 0, css_classes: ["live"] });
  liveBar.append(liveBtn);
  center.append(liveBar);
  const liveScroll = new Gtk.ScrolledWindow({ vexpand: true, hexpand: true });
  const liveFrame = new Gtk.Label({ xalign: 0, css_classes: ["live-frame"] });
  liveScroll.set_child(liveFrame);
  center.append(liveScroll);

  function refreshLive(): void {
    const theme = current();
    const tmp = `${GLib.get_tmp_dir()}/btop-studio-preview.theme`;
    writeFile(tmp, serializeTheme(effective()));
    const engine = `${GLib.get_current_dir()}/live/btop_live.py`;
    const cmd = `uv run --with pyte python3 ${engine} --theme ${tmp} --once`;
    liveBtn.set_label("Rendering real btop…");
    void execAsync(["bash", "-lc", cmd])
      .then((out: string) => {
        try {
          const parsed = JSON.parse(out) as { frame_text?: string };
          liveFrame.set_label(parsed.frame_text ?? "(empty frame)");
          setStatus(`Live preview rendered by the real btop binary (${theme.name}).`);
        } catch {
          liveFrame.set_label(out);
        }
      })
      .catch((error: unknown) => {
        liveFrame.set_label(`Live preview failed: ${error}`);
      })
      .finally(() => liveBtn.set_label("Refresh live preview (real btop)"));
  }
  liveBtn.connect("clicked", refreshLive);

  // Right: selection, gradient, picker, scope, footer.
  const selInfo = new Gtk.Label({ xalign: 0, wrap: true, css_classes: ["hint"] });
  const gradBox = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 3 });
  const picker = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 4, css_classes: ["picker"] });
  const scopeRow = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 4 });
  const scopeButtons = new Map<Scope, Gtk.Button>();
  for (const [value, label] of [["key", "This key"], ["role", "Same role"], ["all", "All keys"]] as [Scope, string][]) {
    const button = new Gtk.Button({ label, css_classes: ["toggle"] });
    button.connect("clicked", () => setScope(value));
    scopeButtons.set(value, button);
    scopeRow.append(button);
  }
  const statusLabel = new Gtk.Label({ xalign: 0, wrap: true, css_classes: ["status"] });
  const footer = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 6 });
  const revertBtn = new Gtk.Button({ label: "Revert", css_classes: ["btn"] });
  const saveBtn = new Gtk.Button({ label: "Save", css_classes: ["btn", "primary"], hexpand: true });
  revertBtn.connect("clicked", () => setPending(new Map()));
  saveBtn.connect("clicked", save);
  footer.append(revertBtn);
  footer.append(saveBtn);
  right.append(new Gtk.Label({ label: "Selection", xalign: 0, css_classes: ["h2"] }));
  right.append(selInfo);
  right.append(new Gtk.Label({ label: `Gradient — ${GRADIENT_LIMIT_NOTE}`, xalign: 0, wrap: true, css_classes: ["h2"] }));
  right.append(gradBox);
  right.append(new Gtk.Label({ label: "Palette", xalign: 0, css_classes: ["h2"] }));
  right.append(picker);
  right.append(new Gtk.Label({ label: "Edit scope", xalign: 0, css_classes: ["h2"] }));
  right.append(scopeRow);
  right.append(statusLabel);
  right.append(footer);

  // ── renders ──────────────────────────────────────────────────────────────
  function clear(box: Gtk.Box): void {
    let child = box.get_first_child();
    while (child) {
      const next = child.get_next_sibling();
      box.remove(child);
      child = next;
    }
  }

  function renderTree(): void {
    clear(tree);
    for (const group of KEY_GROUPS) {
      tree.append(new Gtk.Label({ label: group.name, xalign: 0, css_classes: ["group"] }));
      for (const key of group.keys) {
        const button = new Gtk.Button({ label: key, css_classes: ["item"] });
        button.connect("clicked", () => setSelected(key));
        tree.append(button);
      }
    }
  }

  function renderPresets(): void {
    clear(presetBar);
    for (const item of conf().presets) {
      const button = new Gtk.Button({ label: `${item.index}`, css_classes: ["pchip"] });
      button.connect("clicked", () => setPreset(item.index));
      presetBar.append(button);
    }
    presetBar.append(new Gtk.Label({ label: presetAt(conf(), preset()).label, xalign: 0, css_classes: ["hint"] }));
  }

  function renderLibrary(): void {
    clear(libBox);
    for (const theme of themes()) {
      const button = new Gtk.Button({
        label: `${theme.active ? "★ " : ""}${theme.name}  (${theme.kind})`,
        css_classes: ["titem"],
      });
      button.connect("clicked", () => {
        setCurrentId(theme.id);
        setPending(new Map());
      });
      libBox.append(button);
    }
  }

  function renderSchematic(): void {
    clear(canvasInner);
    const schematic = buildSchematic(conf(), preset(), selected());
    canvasInner.append(new Gtk.Label({ label: schematic.caption, xalign: 0, css_classes: ["caption"] }));
    const warning = hiddenModuleWarning(selected(), schematic.hiddenModules);
    if (warning) canvasInner.append(new Gtk.Label({ label: `⚠ ${warning}`, xalign: 0, wrap: true, css_classes: ["warn"] }));
    const grid = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 8 });
    for (const boxName of schematic.boxes) {
      const column = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL, spacing: 2, css_classes: ["bbox"] });
      column.append(new Gtk.Label({ label: boxName, xalign: 0, css_classes: ["btitle"] }));
      for (const element of schematic.elements.filter((e) => e.box === boxName)) {
        const lit = highlight() && schematic.highlighted.includes(element.id);
        column.append(new Gtk.Label({ label: element.label, xalign: 0, css_classes: lit ? ["el", "hl"] : ["el"] }));
      }
      grid.append(column);
    }
    canvasInner.append(grid);
  }

  function renderDiagnosis(): void {
    const lines = diagnose(effective(), palette()).map(
      (item) => `${item.level === "error" ? "⛔" : item.level === "warn" ? "⚠" : "✓"} ${item.message}`,
    );
    diag.set_label(lines.join("\n") || "✓ no meter-contrast problems");
  }

  function renderDiff(): void {
    const entries = diffEdits(current().map, pending());
    if (!entries.length) {
      diff.set_label("Pending edits — nothing written until you save\n— no changes —");
      return;
    }
    const path = resolvedPath(current(), target(), { repoRoot: repoRoot(), installDir: installDir() });
    diff.set_label(
      `Pending edits — nothing written until you save\n${path}\n` +
        entries.map((e) => `- ${e.key}="${e.from}"\n+ ${e.key}="${e.to}"`).join("\n"),
    );
  }

  function renderPicker(): void {
    clear(picker);
    const key = selected();
    if (!key) return;
    const grid = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 3, css_classes: ["swatches"] });
    const paletteNow = palette();
    const addSwatch = (value: string, hex: string, title: string): void => {
      const button = new Gtk.Button({ tooltip_text: title, css_classes: ["swatch"] });
      const fill = new Gtk.Box({ hexpand: true, vexpand: true });
      const provider = new Gtk.CssProvider();
      provider.load_from_string(`.sw-${key}-${value.replace(/[^a-z0-9]/gi, "")} { background-color: ${hex}; }`);
      fill.get_style_context().add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION);
      fill.set_css_classes([`sw-${key}-${value.replace(/[^a-z0-9]/gi, "")}`]);
      button.set_child(fill);
      button.set_size_request(22, 18);
      button.connect("clicked", () => pick(value));
      grid.append(button);
    };
    paletteNow.ramp.forEach((hex, i) => addSwatch(`ramp[${i}]`, hex, `ramp[${i}] ${hex}`));
    paletteNow.colors.forEach((hex, i) => addSwatch(hex, hex, `color${i} ${hex}`));
    for (const token of NAMED_TOKENS) {
      const hex = token === "background" ? paletteNow.background : paletteNow.foreground;
      addSwatch(token, hex, `${token} ${hex}`);
    }
    picker.append(grid);
    const transparent = new Gtk.Button({ label: "transparent (empty value)", css_classes: ["toggle"] });
    transparent.connect("clicked", () => pick(""));
    picker.append(transparent);
    const hexRow = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 4 });
    const entry = new Gtk.Entry({ placeholder_text: "#rrggbb", hexpand: true });
    const colourButton = new Gtk.ColorButton();
    const applyColour = (): void => {
      const value = entry.get_text();
      if (/^#[0-9a-fA-F]{6}$/.test(value)) pick(value);
    };
    entry.connect("activate", applyColour);
    colourButton.connect("color-set", () => {
      const rgba = colourButton.get_rgba();
      const hex = `#${[rgba.red, rgba.green, rgba.blue].map((v) => Math.round(v * 255).toString(16).padStart(2, "0")).join("")}`;
      entry.set_text(hex);
      pick(hex);
    });
    hexRow.append(entry);
    hexRow.append(colourButton);
    picker.append(hexRow);
  }

  function renderGradient(): void {
    clear(gradBox);
    const key = selected();
    if (!key || !key.match(/_(start|mid|end)$/)) return;
    const family = key.replace(/_(start|mid|end)$/, "");
    const map = effective();
    for (const stop of ["start", "mid", "end"]) {
      const stopKey = `${family}_${stop}`;
      const value = map[stopKey] ?? "";
      const label = `${stopKey}: ${value === "" ? "empty (2-stop)" : resolveHex(value, palette())}`;
      const button = new Gtk.Button({ label, css_classes: ["toggle"] });
      button.connect("clicked", () => setSelected(stopKey));
      gradBox.append(button);
    }
    if (map[`${family}_mid`] === "" || map[`${family}_mid`] === undefined) {
      const add = new Gtk.Button({ label: "＋ add middle colour (make it a 3-stop)", css_classes: ["toggle"] });
      add.connect("clicked", () => {
        const next = addMiddleColour(effective(), family);
        const edits = new Map(pending());
        edits.set(`${family}_mid`, next[`${family}_mid`]);
        setPending(edits);
      });
      gradBox.append(add);
    }
  }

  function renderTarget(): void {
    const theme = current();
    targetPath.set_label(resolvedPath(theme, target(), { repoRoot: repoRoot(), installDir: installDir() }));
    targetHintLabel.set_label(targetHint(target()));
    caveat.set_label(divergenceCaveat(target()) ?? generatedInstalledWarning(theme, target()) ?? "");
    repoBtn.set_css_classes(target() === "repo" ? ["toggle", "on"] : ["toggle"]);
    instBtn.set_css_classes(target() === "installed" ? ["toggle", "on"] : ["toggle"]);
    saveBtn.set_label(actionLabel(target()));
  }

  function renderSelection(): void {
    const theme = current();
    const key = selected();
    selInfo.set_label(
      `Theme: ${theme.name} (${theme.kind})\nKey: ${key ?? "—"}\n` +
        `Value: ${key ? (effective()[key] ?? "") : "—"}\nResolved: ${key ? resolveHex(effective()[key], palette()) : "—"}`,
    );
    for (const [value, button] of scopeButtons) {
      button.set_css_classes(scope() === value ? ["toggle", "on"] : ["toggle"]);
    }
    highlightBtn.set_css_classes(highlight() ? ["toggle", "on"] : ["toggle"]);
    backdropBtn.set_css_classes(controls().backdrop === "neutral" ? ["toggle", "on"] : ["toggle"]);
    for (const [i, level] of FIXED_FILL_LEVELS.entries()) {
      fillButtons[i].set_css_classes(controls().fixedFill === level ? ["toggle", "on"] : ["toggle"]);
    }
  }

  function renderAll(): void {
    renderTarget();
    renderLibrary();
    renderTree();
    renderPresets();
    renderSchematic();
    renderDiagnosis();
    renderDiff();
    renderPicker();
    renderGradient();
    renderSelection();
  }

  createEffect(renderAll);

  return (
    <window
      visible
      name="btop-theme-studio-window"
      class="btop-theme-studio"
      title="btop Theme Studio"
      gdkmonitor={gdkmonitor}
      anchor={0}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      default_width={1400}
      default_height={900}
      $={(self) => {
        const keys = new Gtk.EventControllerKey();
        keys.connect("key-pressed", (_c, keyval) => {
          if (keyval === Gdk.KEY_Escape) {
            self.hide();
            return true;
          }
          return false;
        });
        self.add_controller(keys);
      }}
    >
      {root}
    </window>
  );
}

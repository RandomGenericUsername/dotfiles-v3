import { Astal, Gdk, Gtk } from "ags/gtk4";
import app from "ags/gtk4/app";
import { createEffect, createState } from "ags";
import {
  manifestRegister,
  mappingSet,
  mappingSetDefault,
  mappingShow,
  templateSetPlaceholder,
  type MappingShow,
} from "../lib/itr";
import {
  defaultsPathFor,
  mtimeOf,
  resolveInputs,
  type EditorInputs,
} from "../lib/inputs";
import type {
  PendingEdit,
  Scope,
  ShapeSelection,
  VocabularyPendingEdit,
} from "../lib/model";
import { resolveToken, upsertPending } from "../lib/model";
import { templatePendingKey, type ManifestPending, type TemplatePendingEdit } from "../lib/templates";
import { extractShapes } from "../lib/svg";
import { DiffPane } from "./DiffPane";
import { GroupTree } from "./GroupTree";
import { InputsPanel } from "./InputsPanel";
import { Preview } from "./Preview";
import { ScopeSwitch } from "./ScopeSwitch";
import { SelectionPanel, type CurrentToken } from "./SelectionPanel";
import { TemplatesTab } from "./TemplatesTab";
import { TokenPicker } from "./TokenPicker";

// Shell window hosting the editor. Owns session state, pending edits, and the
// save pipeline. One centered overlay window on the given monitor (same
// layer-shell pattern as the capture dialog).
export function EditorWindow(gdkmonitor: Gdk.Monitor) {
  const [show, setShow] = createState<MappingShow | null>(null);
  const [loadError, setLoadError] = createState<string | null>(null);
  const [inputs, setInputs] = createState<EditorInputs>(resolveInputs());
  const [groupName, setGroupName] = createState("");
  const [activeVariant, setActiveVariant] = createState("");
  const [selection, setSelection] = createState<ShapeSelection | null>(null);
  const [scope, setScope] = createState<Scope>("group");
  const [pending, setPending] = createState<ReadonlyMap<string, PendingEdit>>(new Map());
  const [vocabPending, setVocabPending] = createState<
    ReadonlyMap<string, VocabularyPendingEdit>
  >(new Map());
  const [showGroup, setShowGroup] = createState(true);
  const [barBackground, setBarBackground] = createState(false);
  const [currentToken, setCurrentToken] = createState<CurrentToken | null>(null);
  const [saving, setSaving] = createState(false);
  const [saveError, setSaveError] = createState<string | null>(null);
  const [stale, setStale] = createState(false);
  const [activeTab, setActiveTab] = createState<"mappings" | "templates">("mappings");
  const [templatePending, setTemplatePending] = createState<
    ReadonlyMap<string, TemplatePendingEdit>
  >(new Map());
  const [newPlaceholders, setNewPlaceholders] = createState<ReadonlyMap<string, string>>(
    new Map(),
  );
  const [manifestPendings, setManifestPendings] = createState<ReadonlyArray<ManifestPending>>(
    [],
  );
  const templateMtimes = new Map<string, number | null>();
  let loadedMtimes: { icons: number | null; defaults: number | null } = {
    icons: null,
    defaults: null,
  };

  function snapshotMtimes(next: EditorInputs): void {
    loadedMtimes = {
      icons: mtimeOf(next.iconsYaml),
      defaults: mtimeOf(defaultsPathFor(next.iconsYaml)),
    };
  }

  async function refreshShow(): Promise<void> {
    const next = inputs();
    const loaded = await mappingShow({
      iconsYaml: next.iconsYaml,
      templateDir: next.templateRoot,
      colorScheme: next.colorScheme,
    });
    setShow(loaded);
    setLoadError(null);
    snapshotMtimes(next);
    const group = loaded.groups.find((g) => g.group === groupName()) ?? loaded.groups[0];
    if (group) {
      setGroupName(group.group);
      const view =
        group.variants.find((v) => v.variant === activeVariant()) ?? group.variants[0];
      if (view) setActiveVariant(view.variant);
    }
  }

  function load(next: EditorInputs): void {
    setInputs(next);
    setShow(null);
    setLoadError(null);
    setSelection(null);
    setPending(new Map());
    setVocabPending(new Map());
    setTemplatePending(new Map());
    setNewPlaceholders(new Map());
    setManifestPendings([]);
    templateMtimes.clear();
    setSaveError(null);
    setStale(false);
    refreshShow().catch((error: unknown) => setLoadError(String(error)));
  }

  function totalPending(): number {
    return (
      pending().size +
      vocabPending().size +
      templatePending().size +
      newPlaceholders().size +
      manifestPendings().length
    );
  }

  function stageTemplate(edit: TemplatePendingEdit): void {
    const next = new Map(templatePending());
    next.set(templatePendingKey(edit.templatePath, edit.shapeId), edit);
    setTemplatePending(next);
    templateMtimes.set(edit.templatePath, mtimeOf(edit.templatePath));
  }

  function stageNewPlaceholder(name: string, token: string): void {
    const next = new Map(newPlaceholders());
    next.set(name, token);
    setNewPlaceholders(next);
  }

  function stageManifest(entry: ManifestPending): void {
    setManifestPendings([...manifestPendings(), entry]);
  }

  load(resolveInputs());

  function pick(token: string): void {
    const sel = selection();
    if (!sel) return;
    if (scope() === "vocabulary") {
      const next = new Map(vocabPending());
      next.set(sel.placeholder, { placeholder: sel.placeholder, token });
      setVocabPending(next);
    } else {
      setPending(
        upsertPending(pending(), {
          group: groupName(),
          variant: scope() === "variant" ? sel.variantName : null,
          placeholder: sel.placeholder,
          token,
        }),
      );
    }
  }

  async function save(): Promise<void> {
    if (saving() || totalPending() === 0) return;
    setSaving(true);
    setSaveError(null);
    try {
      const next = inputs();
      const fresh = {
        icons: mtimeOf(next.iconsYaml),
        defaults: mtimeOf(defaultsPathFor(next.iconsYaml)),
      };
      if (
        fresh.icons !== loadedMtimes.icons ||
        fresh.defaults !== loadedMtimes.defaults
      ) {
        setStale(true);
        setSaveError(
          "icons.yaml or defaults.yaml changed on disk since load. Reload to continue.",
        );
        return;
      }
      // Stale template files block save (mtime guard, same as icons/defaults).
      for (const path of templateMtimes.keys()) {
        if (mtimeOf(path) !== templateMtimes.get(path)) {
          setStale(true);
          setSaveError(`A template file changed on disk since load: ${path}. Reload to continue.`);
          return;
        }
      }
      // 1. Template writes.
      for (const edit of templatePending().values()) {
        await templateSetPlaceholder(edit.templatePath, edit.shapeId, edit.newPlaceholder);
      }
      // 2. Vocabulary defaults for new placeholders.
      for (const [name, token] of newPlaceholders()) {
        await mappingSetDefault({
          defaultsYaml: defaultsPathFor(next.iconsYaml),
          manifestYaml: next.iconsYaml,
          colorScheme: next.colorScheme,
          placeholder: name,
          token,
        });
      }
      // 3. Manifest registration for brand-new files.
      for (const entry of manifestPendings()) {
        await manifestRegister({
          manifestYaml: entry.manifestPath,
          group: entry.group,
          variant: entry.variant,
          template: entry.template,
          output: entry.output,
        });
      }
      // 4. Mapping writes.
      for (const edit of pending().values()) {
        await mappingSet({
          iconsYaml: next.iconsYaml,
          colorScheme: next.colorScheme,
          group: edit.group,
          placeholder: edit.placeholder,
          token: edit.token,
          variant: edit.variant ?? undefined,
        });
      }
      for (const edit of vocabPending().values()) {
        await mappingSetDefault({
          defaultsYaml: defaultsPathFor(next.iconsYaml),
          manifestYaml: next.iconsYaml,
          colorScheme: next.colorScheme,
          placeholder: edit.placeholder,
          token: edit.token,
        });
      }
      setPending(new Map());
      setVocabPending(new Map());
      setTemplatePending(new Map());
      setNewPlaceholders(new Map());
      setManifestPendings([]);
      templateMtimes.clear();
      // Never triggers a render: sources only, generated icons refresh on the
      // next wallpaper/theme run.
      await refreshShow();
    } catch (error: unknown) {
      // Pending state is retained so nothing is lost.
      setSaveError(String(error));
    } finally {
      setSaving(false);
    }
  }

  function selectShapeId(shapeId: string): void {
    const loaded = show();
    const group = loaded?.groups.find((g) => g.group === groupName());
    const view = group?.variants.find((v) => v.variant === activeVariant());
    if (!view) return;
    const shape = extractShapes(view.svg_body).find((s) => String(s.id) === shapeId);
    if (!shape || shape.placeholder === null) return;
    setSelection({
      variantName: view.variant,
      shapeId,
      placeholder: shape.placeholder,
    });
  }

  // Current token follows on-disk mappings overlaid with pending edits.
  createEffect(() => {
    const loaded = show();
    const sel = selection();
    pending();
    vocabPending();
    const group = loaded?.groups.find((g) => g.group === groupName());
    const view = group?.variants.find((v) => v.variant === activeVariant());
    if (!loaded || !sel || !view || sel.variantName !== view.variant) {
      setCurrentToken(null);
      return;
    }
    const token = resolveToken(
      view.mappings.map((entry) => ({
        placeholder: entry.placeholder,
        token: entry.token,
        origin: entry.origin,
      })),
      groupName(),
      view.variant,
      sel.placeholder,
      pending(),
      vocabPending(),
    );
    if (token === null) {
      setCurrentToken(null);
      return;
    }
    setCurrentToken({
      token,
      hex: token.startsWith("#") ? token : (loaded.palette[token] ?? null),
    });
  });

  const status = new Gtk.Label({
    css_classes: ["icme-status"],
    wrap: true,
    max_width_chars: 40,
  });
  createEffect(() => {
    const error = loadError();
    if (error) {
      status.set_label(`Failed to load mappings: ${error}`);
      status.set_visible(true);
    } else if (!show()) {
      status.set_label("Loading mappings…");
      status.set_visible(true);
    } else {
      status.set_visible(false);
    }
  });

  const left = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["icme-left"],
  });
  left.append(
    InputsPanel({
      inputs,
      pendingCount: () => pending().size + vocabPending().size,
      onChange: (next) => load(next),
      // Native file choosers are regular windows and always render below a
      // layer-shell OVERLAY surface — hide the editor while one is open.
      onDialogOpenChange: (open) => {
        const win = app.get_window("icme-window");
        if (!win) return;
        if (open) win.show();
        else win.hide();
      },
    }),
  );
  left.append(status);
  const treeScroll = new Gtk.ScrolledWindow({
    hscrollbar_policy: Gtk.PolicyType.NEVER,
    vscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    hexpand: true,
    vexpand: true,
  });
  treeScroll.set_child(
    GroupTree({
      show,
      groupName,
      activeVariant,
      onSelectGroup: (group) => {
        setGroupName(group);
        const first = show()?.groups.find((g) => g.group === group)?.variants[0];
        if (first) setActiveVariant(first.variant);
        setSelection(null);
      },
      onSelectVariant: (variant) => {
        setActiveVariant(variant);
        setSelection(null);
      },
    }),
  );
  left.append(treeScroll);

  const right = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["icme-right"],
  });
  const rightScroll = new Gtk.ScrolledWindow({
    hscrollbar_policy: Gtk.PolicyType.NEVER,
    vscrollbar_policy: Gtk.PolicyType.AUTOMATIC,
    hexpand: true,
    vexpand: true,
  });
  const rightInner = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
  rightInner.append(
    SelectionPanel({
      show,
      groupName,
      activeVariant,
      selection,
      currentToken,
      onSelectShapeId: selectShapeId,
    }),
  );
  rightInner.append(
    ScopeSwitch({
      scope,
      show,
      groupName,
      activeVariant,
      selection,
      onScope: (next) => setScope(next),
    }),
  );
  rightInner.append(
    TokenPicker({
      palette: () => show()?.palette ?? {},
      missingTokens: () => show()?.missing_tokens ?? [],
      placeholder: () => selection()?.placeholder ?? null,
      currentToken: () => currentToken()?.token ?? null,
      onPick: pick,
    }),
  );
  rightScroll.set_child(rightInner);
  right.append(rightScroll);

  const saveErrorLabel = new Gtk.Label({
    css_classes: ["save-error"],
    xalign: 0,
    wrap: true,
  });
  const reloadButton = new Gtk.Button({ label: "Reload", css_classes: ["toggle"] });
  reloadButton.connect("clicked", () => load(inputs()));
  const saveButton = new Gtk.Button({
    label: "Save mappings",
    css_classes: ["btn", "primary"],
    hexpand: true,
  });
  saveButton.connect("clicked", () => void save());
  const revertButton = new Gtk.Button({ label: "Revert", css_classes: ["btn"] });
  revertButton.connect("clicked", () => {
    setPending(new Map());
    setVocabPending(new Map());
    setTemplatePending(new Map());
    setNewPlaceholders(new Map());
    setManifestPendings([]);
    templateMtimes.clear();
    setSaveError(null);
  });
  const footerButtons = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 8,
    css_classes: ["footer"],
  });
  footerButtons.append(revertButton);
  footerButtons.append(saveButton);
  const footer = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
  footer.append(saveErrorLabel);
  footer.append(reloadButton);
  footer.append(footerButtons);
  right.append(footer);

  createEffect(() => {
    const hasPending = totalPending() > 0;
    const busy = saving();
    saveButton.set_sensitive(hasPending && !busy);
    revertButton.set_sensitive(hasPending && !busy);
    saveButton.set_label(busy ? "Saving…" : "Save mappings");
    const error = saveError();
    saveErrorLabel.set_label(error ?? "");
    saveErrorLabel.set_visible(error !== null);
    reloadButton.set_visible(stale());
  });

  const center = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["icme-center"],
    hexpand: true,
    vexpand: true,
  });

  // --- tab bar + views ---
  function tabButton(label: string, sub: string): Gtk.Button {
    const box = new Gtk.Box({ orientation: Gtk.Orientation.VERTICAL });
    box.append(new Gtk.Label({ label, css_classes: ["tab-label"], xalign: 0 }));
    box.append(new Gtk.Label({ label: sub, css_classes: ["tab-sub"], xalign: 0 }));
    const button = new Gtk.Button({ css_classes: ["tab"] });
    button.set_child(box);
    return button;
  }

  const tabMapping = tabButton("Mappings", "recolor existing placeholders");
  const tabTemplates = tabButton("Templates", "assign / create placeholders");
  const tabBar = new Gtk.Box({ orientation: Gtk.Orientation.HORIZONTAL, spacing: 4, css_classes: ["tabs"] });
  tabBar.append(tabMapping);
  tabBar.append(tabTemplates);
  tabMapping.connect("clicked", () => setActiveTab("mappings"));
  tabTemplates.connect("clicked", () => setActiveTab("templates"));

  const mappingView = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    spacing: 0,
    css_classes: ["icme-root", "view"],
    hexpand: true,
    vexpand: true,
  });
  mappingView.append(left);
  mappingView.append(center);
  mappingView.append(right);

  const templatesView = new Gtk.Box({
    orientation: Gtk.Orientation.HORIZONTAL,
    css_classes: ["view"],
    hexpand: true,
    vexpand: true,
  });
  templatesView.append(
    TemplatesTab({
      show,
      inputs,
      templatePending,
      newPlaceholders,
      manifestPendings,
      onStageTemplate: stageTemplate,
      onStageNewPlaceholder: stageNewPlaceholder,
      onStageManifest: stageManifest,
      onSave: () => void save(),
      onRevert: () => {
        setPending(new Map());
        setVocabPending(new Map());
        setTemplatePending(new Map());
        setNewPlaceholders(new Map());
        setManifestPendings([]);
        templateMtimes.clear();
        setSaveError(null);
      },
      onDialogOpenChange: (open: boolean) => {
        const win = app.get_window("icme-window");
        if (!win) return;
        if (open) win.show();
        else win.hide();
      },
    }),
  );

  createEffect(() => {
    const tab = activeTab();
    mappingView.set_visible(tab === "mappings");
    templatesView.set_visible(tab === "templates");
    tabMapping.set_css_classes(tab === "mappings" ? ["tab", "active"] : ["tab"]);
    tabTemplates.set_css_classes(tab === "templates" ? ["tab", "active"] : ["tab"]);
  });

  return (
    <window
      visible
      name="icme-window"
      class="icme-window"
      title="Icon Color Mapping Editor"
      gdkmonitor={gdkmonitor}
      anchor={0}
      layer={Astal.Layer.OVERLAY}
      keymode={Astal.Keymode.ON_DEMAND}
      default_width={1280}
      default_height={800}
      $={(self) => {
        // ESC hides the window (the toggle-aware launcher brings it back).
        // Works while the window holds keyboard focus; keymode stays
        // ON_DEMAND so the editor never steals keys from other apps.
        const keys = new Gtk.EventControllerKey();
        keys.connect("key-pressed", (_c, keyval) => {
          if (keyval === Gdk.KEY_Escape) {
            self.hide();
            return true;
          }
          return false;
        });
        self.add_controller(keys);
        center.append(
          Preview({
            show,
            groupName,
            activeVariant,
            pending,
            vocabPending,
            selection,
            showGroup,
            barBackground,
            onSelectVariant: (variant: string) => {
              setActiveVariant(variant);
              setSelection(null);
            },
            onSelectShape: (next: ShapeSelection | null) => setSelection(next),
            onToggleGroup: () => setShowGroup(!showGroup()),
            onToggleBackdrop: () => setBarBackground(!barBackground()),
            onClose: () => self.close(),
            diffContent: DiffPane({ show, groupName, activeVariant, pending, vocabPending, inputs }),
          }),
        );
      }}
    >
      <box orientation={Gtk.Orientation.VERTICAL}>
        {tabBar}
        {mappingView}
        {templatesView}
      </box>
    </window>
  );
}

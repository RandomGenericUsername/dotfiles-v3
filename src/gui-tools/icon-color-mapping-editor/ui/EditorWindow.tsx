import { Astal, Gdk, Gtk } from "ags/gtk4";
import { createEffect, createState } from "ags";
import { mappingShow, type MappingShow } from "../lib/itr";
import { resolveInputs, type EditorInputs } from "../lib/inputs";
import type {
  PendingEdit,
  Scope,
  ShapeSelection,
  VocabularyPendingEdit,
} from "../lib/model";
import { resolveToken, upsertPending } from "../lib/model";
import { extractShapes } from "../lib/svg";
import { GroupTree } from "./GroupTree";
import { InputsPanel } from "./InputsPanel";
import { Preview } from "./Preview";
import { ScopeSwitch } from "./ScopeSwitch";
import { SelectionPanel, type CurrentToken } from "./SelectionPanel";
import { TokenPicker } from "./TokenPicker";

// Shell window hosting the editor. Owns session state; §6 adds the diff/save
// footer. One centered overlay window on the given monitor (same layer-shell
// pattern as the capture dialog).
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

  function load(next: EditorInputs): void {
    setInputs(next);
    setShow(null);
    setLoadError(null);
    setSelection(null);
    setPending(new Map());
    setVocabPending(new Map());
    mappingShow({
      iconsYaml: next.iconsYaml,
      templateDir: next.templateRoot,
      colorScheme: next.colorScheme,
    })
      .then((loaded) => {
        setShow(loaded);
        const first = loaded.groups[0];
        if (first) {
          setGroupName(first.group);
          const firstVariant = first.variants[0];
          if (firstVariant) setActiveVariant(firstVariant.variant);
        }
      })
      .catch((error: unknown) => setLoadError(String(error)));
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

  const center = new Gtk.Box({
    orientation: Gtk.Orientation.VERTICAL,
    css_classes: ["icme-center"],
    hexpand: true,
    vexpand: true,
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
          }),
        );
      }}
    >
      <box class="icme-root" orientation={Gtk.Orientation.HORIZONTAL} spacing={0}>
        {left}
        {center}
        {right}
      </box>
    </window>
  );
}

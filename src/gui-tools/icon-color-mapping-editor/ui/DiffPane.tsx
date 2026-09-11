import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import {
  describePending,
  renderPendingMarkup,
  type PendingRow,
} from "../lib/diff.ts";
import type { EditorInputs } from "../lib/inputs";
import type { PendingEdit, VocabularyPendingEdit } from "../lib/model";
import type { MappingShow } from "../lib/itr";
import {
  describeTemplatePending,
  type ManifestPending,
  type TemplatePendingEdit,
  type WorkingShape,
} from "../lib/templates";

export interface DiffPaneProps {
  show: Accessor<MappingShow | null>;
  groupName: Accessor<string>;
  activeVariant: Accessor<string>;
  pending: Accessor<ReadonlyMap<string, PendingEdit>>;
  vocabPending: Accessor<ReadonlyMap<string, VocabularyPendingEdit>>;
  templatePending?: Accessor<ReadonlyMap<string, TemplatePendingEdit>>;
  newPlaceholders?: Accessor<ReadonlyMap<string, string>>;
  manifestPendings?: Accessor<ReadonlyArray<ManifestPending>>;
  workingByPath?: Accessor<ReadonlyMap<string, ReadonlyArray<WorkingShape>>>;
  inputs: Accessor<EditorInputs>;
}

/** Live diff pane: semantic old→new rows for templates and mappings, never writes. */
export function DiffPane(props: DiffPaneProps) {
  const label = new Gtk.Label({
    css_classes: ["diff-text"],
    xalign: 0,
    wrap: true,
    selectable: true,
  });
  const box = new Gtk.Box({ css_classes: ["diff-pane"] });
  box.append(label);

  createEffect(() => {
    const show = props.show();
    const pending = props.pending();
    const vocabPending = props.vocabPending();
    const templatePending = props.templatePending?.() ?? new Map();
    const newPlaceholders = props.newPlaceholders?.() ?? new Map();
    const manifestPendings = props.manifestPendings?.() ?? [];
    const workingByPath = props.workingByPath?.() ?? new Map();
    props.inputs();

    const allRows: PendingRow[] = [];

    // Template edits & new placeholder defaults
    if (templatePending.size > 0 || newPlaceholders.size > 0 || manifestPendings.length > 0) {
      allRows.push(
        ...describeTemplatePending({
          templatePendings: templatePending,
          newPlaceholders,
          manifestPendings,
          workingByPath,
        }),
      );
    }

    // Mapping edits in icons.yaml & defaults.yaml
    if (show && (pending.size > 0 || vocabPending.size > 0)) {
      allRows.push(
        ...describePending(
          show,
          props.groupName(),
          props.activeVariant(),
          pending,
          vocabPending,
        ),
      );
    }

    if (allRows.length === 0) {
      label.set_text("— no changes —");
      return;
    }

    label.set_markup(renderPendingMarkup(allRows));
  });

  return box;
}

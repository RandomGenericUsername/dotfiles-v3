import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import {
  describePending,
  renderPendingMarkup,
} from "../lib/diff.ts";
import type { EditorInputs } from "../lib/inputs";
import type { PendingEdit, VocabularyPendingEdit } from "../lib/model";
import type { MappingShow } from "../lib/itr";

export interface DiffPaneProps {
  show: Accessor<MappingShow | null>;
  groupName: Accessor<string>;
  activeVariant: Accessor<string>;
  pending: Accessor<ReadonlyMap<string, PendingEdit>>;
  vocabPending: Accessor<ReadonlyMap<string, VocabularyPendingEdit>>;
  inputs: Accessor<EditorInputs>;
}

/** Live diff pane: semantic old→new rows per placeholder, never writes. */
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
    props.inputs();
    if (!show || (pending.size === 0 && vocabPending.size === 0)) {
      label.set_text("— no changes —");
      return;
    }
    const rows = describePending(
      show,
      props.groupName(),
      props.activeVariant(),
      pending,
      vocabPending,
    );
    label.set_markup(renderPendingMarkup(rows));
  });

  return box;
}

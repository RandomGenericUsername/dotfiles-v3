import { Gtk } from "ags/gtk4";
import { createEffect, type Accessor } from "ags";
import { mappingSet, mappingSetDefault } from "../lib/itr";
import { defaultsPathFor, type EditorInputs } from "../lib/inputs";
import type { PendingEdit, VocabularyPendingEdit } from "../lib/model";

export interface DiffPaneProps {
  pending: Accessor<ReadonlyMap<string, PendingEdit>>;
  vocabPending: Accessor<ReadonlyMap<string, VocabularyPendingEdit>>;
  inputs: Accessor<EditorInputs>;
}

/** YAML diff of all pending edits, sourced from dry-run CLI calls. */
export async function fetchPendingDiff(
  pending: ReadonlyMap<string, PendingEdit>,
  vocabPending: ReadonlyMap<string, VocabularyPendingEdit>,
  inputs: EditorInputs,
): Promise<string> {
  const parts: string[] = [];
  for (const edit of pending.values()) {
    const result = await mappingSet({
      iconsYaml: inputs.iconsYaml,
      colorScheme: inputs.colorScheme,
      group: edit.group,
      placeholder: edit.placeholder,
      token: edit.token,
      variant: edit.variant ?? undefined,
      dryRun: true,
      withDiff: true,
    });
    if (result.diff) parts.push(result.diff.trimEnd());
  }
  for (const edit of vocabPending.values()) {
    const result = await mappingSetDefault({
      defaultsYaml: defaultsPathFor(inputs.iconsYaml),
      manifestYaml: inputs.iconsYaml,
      colorScheme: inputs.colorScheme,
      placeholder: edit.placeholder,
      token: edit.token,
      dryRun: true,
      withDiff: true,
    });
    if (result.diff) parts.push(result.diff.trimEnd());
  }
  return parts.join("\n");
}

/** Live diff pane: recomputes on every pending change, never writes. */
export function DiffPane(props: DiffPaneProps) {
  const label = new Gtk.Label({
    css_classes: ["diff-text"],
    xalign: 0,
    wrap: true,
    selectable: true,
  });
  const box = new Gtk.Box({ css_classes: ["diff-pane"] });
  box.append(label);

  let seq = 0;
  createEffect(() => {
    const my = ++seq;
    const pending = props.pending();
    const vocabPending = props.vocabPending();
    const inputs = props.inputs();
    if (pending.size === 0 && vocabPending.size === 0) {
      label.set_label("— no changes —");
      return;
    }
    label.set_label("Computing diff…");
    fetchPendingDiff(pending, vocabPending, inputs).then(
      (text) => {
        if (seq === my) label.set_label(text || "— no changes —");
      },
      (error: unknown) => {
        if (seq === my) label.set_label(`Diff unavailable: ${String(error)}`);
      },
    );
  });

  return box;
}

// Pure template-assignment logic for the Templates tab.
//
// Placeholder assignment is a file-local operation: one shape's paint
// attribute is rewritten to {{NAME}} (existing or brand-new). Everything here
// is pure and dependency-free (erasable types only) so plain node can run it
// (see tests/templates.mjs); the reactive GTK surface lives in ui/TemplatesTab.tsx.

import type { PendingRow } from "./diff.ts";
import { escapeMarkup } from "./diff.ts";
import type { MappingShow } from "./itr.ts";
import { extractShapes } from "./svg.ts";

export type TemplateMode = "templated" | "bare";

export interface TemplateShapeInfo {
  id: number;
  tag: string;
  paintAttr: "fill" | "stroke";
  placeholder: string | null;
  literal: string | null;
}

export interface TemplateAnalysis {
  path: string;
  mode: TemplateMode;
  shapes: TemplateShapeInfo[];
}

/** A shape as the editor works on it (mutable working copy per loaded file). */
export interface WorkingShape {
  id: number;
  tag: string;
  attr: "fill" | "stroke";
  ph: string | null;
  literal: string | null;
}

/** A staged, unsaved template edit: one shape's paint attribute. */
export interface TemplatePendingEdit {
  templatePath: string;
  shapeId: number;
  attr: "fill" | "stroke";
  /** Original on-disk paint value: "{{NAME}}" or a literal hex. */
  oldValue: string;
  newPlaceholder: string;
}

export interface ManifestPending {
  manifestPath: string;
  group: string;
  variant: string;
  template: string;
  output: string;
}

/** Stable serialization for template pending-edit map keys (NUL-separated). */
export function templatePendingKey(templatePath: string, shapeId: number): string {
  return `${templatePath}\u0000${shapeId}`;
}

export function workingFrom(shape: TemplateShapeInfo): WorkingShape {
  return {
    id: shape.id,
    tag: shape.tag,
    attr: shape.paintAttr,
    ph: shape.placeholder,
    literal: shape.literal,
  };
}

/** Display form of a shape's paint value: "{{NAME}}" or a literal hex. */
export function paintValueOf(shape: WorkingShape): string {
  return shape.ph !== null ? `{{${shape.ph}}}` : (shape.literal ?? "");
}

/** Insert or replace a template pending edit; returns a new map. */
export function stageTemplateEdit(
  pending: ReadonlyMap<string, TemplatePendingEdit>,
  edit: TemplatePendingEdit,
): Map<string, TemplatePendingEdit> {
  const next = new Map(pending);
  next.set(templatePendingKey(edit.templatePath, edit.shapeId), edit);
  return next;
}

/** Apply a pending edit to a working copy, returning a new array. */
export function applyTemplateEdit(
  working: ReadonlyArray<WorkingShape>,
  edit: TemplatePendingEdit,
): WorkingShape[] {
  return working.map((shape) =>
    shape.id === edit.shapeId
      ? { ...shape, ph: edit.newPlaceholder, literal: null }
      : shape,
  );
}

/** Bare-mode progress: shapes carrying a placeholder over the total. */
export function bareProgress(
  shapes: ReadonlyArray<WorkingShape>,
): { assigned: number; total: number } {
  return { assigned: shapes.filter((s) => s.ph !== null).length, total: shapes.length };
}

export function modeOf(shapes: ReadonlyArray<WorkingShape>): TemplateMode {
  return shapes.some((s) => s.ph !== null) ? "templated" : "bare";
}

export function isValidPlaceholderName(name: string): boolean {
  return /^[A-Z][A-Z0-9_]*$/.test(name);
}

/**
 * Group a template path for the tree: the second path segment (after the
 * category like `status-bar/`) is the group; the label is the remaining
 * directory path (e.g. `battery-25/default`).
 */
export function groupAndLabel(
  templatePath: string,
  templateRoot: string,
): { group: string; label: string } {
  let rel = templatePath;
  if (templateRoot !== "" && templatePath.startsWith(templateRoot)) {
    rel = templatePath.slice(templateRoot.length).replace(/^\/+/, "");
  }
  const parts = rel.split("/").filter(Boolean);
  const file = parts.pop() ?? "";
  const group = parts[1] ?? parts[0] ?? file;
  const tail = parts.slice(2).join("/");
  return { group, label: tail !== "" ? tail : file };
}

export interface TemplateTreeEntry {
  path: string;
  group: string;
  label: string;
  mode: TemplateMode;
}

/** Build the tree entries from the loaded templates + analyze results. */
export function buildTreeEntries(
  templateRoot: string,
  modes: ReadonlyMap<string, TemplateMode>,
): TemplateTreeEntry[] {
  const entries: TemplateTreeEntry[] = [];
  for (const path of modes.keys()) {
    const { group, label } = groupAndLabel(path, templateRoot);
    entries.push({ path, group, label, mode: modes.get(path) ?? "bare" });
  }
  entries.sort((a, b) =>
    a.group === b.group ? a.label.localeCompare(b.label) : a.group.localeCompare(b.group),
  );
  return entries;
}

/** Unique template paths referenced by the manifest's variants. */
export function templatePathsFrom(show: MappingShow | null): string[] {
  const seen = new Set<string>();
  if (!show) return [];
  for (const group of show.groups) {
    for (const variant of group.variants) {
      seen.add(variant.template_path);
    }
  }
  return [...seen];
}

/** Resolved hex for a working shape, or null when it cannot be resolved. */
export function resolveColorHex(
  shape: WorkingShape,
  mappings: Record<string, string>,
  palette: Record<string, string>,
): string | null {
  if (shape.ph !== null) {
    const token = mappings[shape.ph];
    if (token === undefined) return null;
    return token.startsWith("#") ? token : (palette[token] ?? null);
  }
  return shape.literal ?? null;
}

/** Set one paint attribute on an element (adds it when missing, preserves quotes). */
function setPaintValue(element: string, attr: "fill" | "stroke", value: string): string {
  const re = new RegExp(`\\b${attr}\\s*=\\s*"([^"]*)"`);
  if (re.test(element)) {
    return element.replace(re, `${attr}="${value}"`);
  }
  return element.replace(/(\/>|>[\s\S]*<\/\w+>\s*)$/, ` ${attr}="${value}"$1`);
}

/**
 * Rewrite a body's shapes so each paints with its current (pending-applied)
 * paint value: `{{ph}}` when assigned, the literal hex otherwise. The caller
 * then runs `substitute` to resolve placeholders against the palette.
 */
export function renderPreviewBody(
  body: string,
  working: ReadonlyArray<WorkingShape>,
  paintValue: (shape: WorkingShape) => string | null,
): string {
  let out = body;
  const shapes = extractShapes(body);
  for (let i = 0; i < shapes.length; i += 1) {
    const info = shapes[i];
    const w = working[i];
    if (!w) continue;
    const value = paintValue(w);
    if (value === null) continue;
    const element = setPaintValue(info.element, w.attr, value);
    out = out.replace(info.element, () => element);
  }
  return out;
}

/** Merged placeholder→token table for the template's manifest variant. */
export function mappingsForTemplate(
  show: MappingShow | null,
  templatePath: string,
  newPlaceholders: ReadonlyMap<string, string>,
): Record<string, string> {
  const table: Record<string, string> = {};
  if (show) {
    for (const group of show.groups) {
      for (const variant of group.variants) {
        if (variant.template_path !== templatePath) continue;
        for (const entry of variant.mappings) {
          table[entry.placeholder] = entry.token;
        }
      }
    }
  }
  for (const [name, token] of newPlaceholders) {
    table[name] = token;
  }
  return table;
}

export interface TemplateDiffInput {
  templatePendings: ReadonlyMap<string, TemplatePendingEdit>;
  newPlaceholders: ReadonlyMap<string, string>;
  manifestPendings: ReadonlyArray<ManifestPending>;
  workingByPath: ReadonlyMap<string, ReadonlyArray<WorkingShape>>;
}

/** Semantic pending rows for template edits, defaults, and manifest registration. */
export function describeTemplatePending(input: TemplateDiffInput): PendingRow[] {
  const rows: PendingRow[] = [];
  let lastHeader: string | null = null;
  const emit = (header: string, html: string): void => {
    rows.push({ header: header === lastHeader ? null : header, html });
    lastHeader = header;
  };

  const sorted = [...input.templatePendings.values()].sort((a, b) =>
    a.templatePath === b.templatePath
      ? a.shapeId - b.shapeId
      : a.templatePath.localeCompare(b.templatePath),
  );
  for (const edit of sorted) {
    const working = input.workingByPath.get(edit.templatePath);
    const tag = working?.find((s) => s.id === edit.shapeId)?.tag ?? "path";
    const attr = edit.attr;
    const old = edit.oldValue;
    const neu = `{{${edit.newPlaceholder}}}`;
    const line = (sign: string, value: string): string =>
      `  ${sign}  ${escapeMarkup(`<${tag} … ${attr}="${value}"/>`)}`;
    emit(
      edit.templatePath,
      line("-", old) + String.fromCharCode(10) + line("+", neu),
    );
  }
  for (const [name, token] of input.newPlaceholders) {
    emit("defaults.yaml → defaults", `  +   ${escapeMarkup(name)}: ${escapeMarkup(token)}`);
  }
  for (const entry of input.manifestPendings) {
    emit(
      `${entry.manifestPath} → ${entry.group}`,
      `  +   - name: ${escapeMarkup(entry.variant)}` +
        String.fromCharCode(10) +
        `      template: ${escapeMarkup(entry.template)}` +
        String.fromCharCode(10) +
        `      output: ${escapeMarkup(entry.output)}`,
    );
  }
  return rows;
}

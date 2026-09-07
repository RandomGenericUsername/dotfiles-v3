// Session state for the editor: loaded groups, selection, scope, and the
// pending-edit set. Pure helpers stay testable; reactive containers are built
// with ags primitives by the UI layer.

export type Scope = "variant" | "group" | "vocabulary";

export interface ShapeSelection {
  variantName: string;
  shapeId: string;
  placeholder: string;
}

export interface PendingKey {
  group: string;
  /** Null means whole-group scope; set for variant overrides. */
  variant: string | null;
  placeholder: string;
}

export interface PendingEdit extends PendingKey {
  token: string;
}

/** Stable serialization for pending-edit map keys (NUL-separated). */
export function pendingKeyOf(key: PendingKey): string {
  return `${key.group}\u0000${key.variant ?? ""}\u0000${key.placeholder}`;
}

export function pendingTargetLabel(edit: PendingEdit): string {
  if (edit.variant !== null) {
    return `${edit.group}.variants[${edit.variant}].color_mappings.${edit.placeholder}`;
  }
  return `${edit.group}.color_mappings.${edit.placeholder}`;
}

/** Insert or replace a pending edit; returns a new map. */
export function upsertPending(
  pending: ReadonlyMap<string, PendingEdit>,
  edit: PendingEdit,
): Map<string, PendingEdit> {
  const next = new Map(pending);
  next.set(pendingKeyOf(edit), edit);
  return next;
}

/** Scope of a pending edit: variant edits carry a variant, group edits don't.
 * Vocabulary-scope edits are tracked separately (see below). */
export function scopeOf(edit: PendingEdit): Exclude<Scope, "vocabulary"> {
  return edit.variant === null ? "group" : "variant";
}

export interface VocabularyPendingEdit {
  placeholder: string;
  token: string;
}

export function vocabularyKeyOf(edit: VocabularyPendingEdit): string {
  return `defaults\u0000${edit.placeholder}`;
}
/**
 * Effective placeholder→token table for one variant: on-disk merged entries
 * with pending edits applied. Variant-scope edits win over group-scope edits;
 * vocabulary-scope edits retarget vocabulary-origin entries only (shadowed
 * group/variant entries keep their values).
 */
export function previewMappings(
  entries: MergedEntry[],
  group: string,
  variant: string,
  pending: ReadonlyMap<string, PendingEdit>,
  vocabPending: ReadonlyMap<string, VocabularyPendingEdit>,
): Record<string, string> {
  const table: Record<string, string> = {};
  for (const entry of entries) {
    const vocabEdit =
      entry.origin === "vocabulary" ? vocabPending.get(entry.placeholder) : undefined;
    table[entry.placeholder] = vocabEdit?.token ?? entry.token;
  }
  for (const edit of pending.values()) {
    if (edit.group !== group) continue;
    if (!(edit.placeholder in table)) continue;
    if (edit.variant === null || edit.variant === variant) {
      table[edit.placeholder] = edit.token;
    }
  }
  // Variant-scope edits outrank group-scope ones sharing a placeholder.
  for (const edit of pending.values()) {
    if (edit.group === group && edit.variant === variant && edit.placeholder in table) {
      table[edit.placeholder] = edit.token;
    }
  }
  return table;
}

/**
 * Current token for one placeholder: on-disk merged entry overlaid with
 * pending edits (variant-scope wins over group-scope; vocabulary-scope
 * retargets vocabulary origins only). Null when the placeholder is unmapped.
 */
export function resolveToken(
  entries: MergedEntry[],
  group: string,
  variant: string,
  placeholder: string,
  pending: ReadonlyMap<string, PendingEdit>,
  vocabPending: ReadonlyMap<string, VocabularyPendingEdit>,
): string | null {
  const base = entries.find((entry) => entry.placeholder === placeholder);
  if (!base) return null;
  const vocabEdit =
    base.origin === 'vocabulary' ? vocabPending.get(placeholder) : undefined;
  let token = vocabEdit?.token ?? base.token;
  for (const edit of pending.values()) {
    if (edit.group !== group || edit.placeholder !== placeholder) continue;
    if (edit.variant === null) token = edit.token;
  }
  for (const edit of pending.values()) {
    if (edit.group === group && edit.variant === variant && edit.placeholder === placeholder) {
      token = edit.token;
    }
  }
  return token;
}

/**
 * Pre-pick resolution of one placeholder: the effective token with the given
 * pending edit excluded, plus whether that value falls through to the
 * vocabulary default (the case that reads as an apparition in raw diffs).
 */
export function pendingOldValue(
  entries: MergedEntry[],
  group: string,
  variant: string,
  placeholder: string,
  pendingOthers: ReadonlyMap<string, PendingEdit>,
  vocabOthers: ReadonlyMap<string, VocabularyPendingEdit>,
): { token: string | null; fromVocabulary: boolean } {
  const table = previewMappings(entries, group, variant, pendingOthers, vocabOthers);
  const token = table[placeholder] ?? null;
  const base = entries.find((entry) => entry.placeholder === placeholder);
  return { token, fromVocabulary: base?.origin === 'vocabulary' };
}
